# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""API v0: datasets, locate, horizon, compare, and the OpenAPI error bodies."""

import json

import pytest
from fastapi.testclient import TestClient

import lss.api.app as app_module
from lss.api.served import ServedFileError, load_all
from lss.config import FIXTURES_DIR, get_settings
from lss.contract import (
    CONTRACT_VERSION,
    CompareNotServedError,
    CompareResponse,
    DatasetsResponse,
    HorizonProfile,
    HorizonRequest,
    InvalidRequestError,
    LocateResponse,
    NotServedError,
    UnavailableError,
)
from lss.contract.examples import SCENARIO
from lss.contract.export import build_openapi
from tests.api.test_thin_slice import WEB_SCENARIO, write_served

SITE = WEB_SCENARIO["location"]


def horizon_body(lat=SITE["lat"], lon=SITE["lon"], height=1.0, version=CONTRACT_VERSION) -> dict:
    """A non-placeholder HorizonProfile body (synthetic values: only the plumbing is under test)."""
    az = [i * 0.5 for i in range(720)]
    return HorizonProfile(
        contract_version=version,
        location={"lat": lat, "lon": lon},
        unit_height_m=height,
        azimuth_deg=az,
        elevation_deg=[-1.0] * len(az),
        max_range_km=400.0,
    ).model_dump(mode="json", by_alias=True)


def add_horizon(path, **kw):
    data = json.loads(path.read_text(encoding="utf-8"))
    data["format"] = 2
    data["horizon"] = horizon_body(**kw)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    app_module._served.cache_clear()
    yield tmp_path
    get_settings.cache_clear()
    app_module._served.cache_clear()


@pytest.fixture()
def served_path(data_dir):
    return write_served(data_dir / "cache" / "served")


def client():
    return TestClient(app_module.create_app())


def other_scenario(**changes):
    sc = json.loads(json.dumps(WEB_SCENARIO))
    sc.update(changes)
    return sc


# ------------------------------------------------------------------ datasets, locate


def test_datasets_is_the_registry():
    r = client().get("/api/datasets")
    assert r.status_code == 200
    body = DatasetsResponse.model_validate(r.json())
    fixture = json.loads((FIXTURES_DIR / "datasets.json").read_text(encoding="utf-8"))
    assert [d.id for d in body.datasets] == [d["id"] for d in fixture["datasets"]]
    assert body.placeholder is False


def test_locate_gives_the_stack_the_served_result_used():
    r = client().post("/api/locate", json={"lat": SITE["lat"], "lon": SITE["lon"]})
    assert r.status_code == 200
    body = LocateResponse.model_validate(r.json())
    served_fidelity = json.loads((FIXTURES_DIR / "metrics.json").read_text(encoding="utf-8"))
    assert body.placeholder is False
    assert [layer.role for layer in body.terrain_stack][0] == "near_field"
    assert body.fidelity.tier == "high"
    # Same resolver the engine used for the served Site01 result (its fidelity label is the resolver's).
    assert body.fidelity.near_field_resolution_m == 5.0
    assert served_fidelity["scenario"]["location"]["lat"] == body.location.lat


def test_locate_off_the_polar_maps_is_the_low_fidelity_global_layer():
    # Every valid location is covered, off the polar maps by the global
    # coarse layer (LOLA LDEM_128), so this is a 200 with a low fidelity label, no longer a 422.
    r = client().post("/api/locate", json={"lat": 0.0, "lon": 0.0})
    assert r.status_code == 200
    body = LocateResponse.model_validate(r.json())
    assert [layer.dataset_id for layer in body.terrain_stack] == ["lola_ldem_128"]
    assert body.fidelity.tier == "low"


def test_locate_malformed_is_validation_422():
    r = client().post("/api/locate", json={"lat": 91.0, "lon": 0.0})
    assert r.status_code == 422
    InvalidRequestError.model_validate(r.json())


# ------------------------------------------------------------------------- horizon


def test_horizon_is_served_from_a_format_2_file(served_path):
    add_horizon(served_path)
    r = client().post("/api/horizon", json={"location": SITE, "unit_height_m": 1.0})
    assert r.status_code == 200
    body = HorizonProfile.model_validate(r.json())
    assert body.contract_version == CONTRACT_VERSION and body.placeholder is False
    assert len(body.azimuth_deg) == 720


def test_horizon_ignores_the_location_name(served_path):
    add_horizon(served_path)
    loc = dict(SITE, name="anything")
    assert client().post("/api/horizon", json={"location": loc, "unit_height_m": 1.0}).status_code == 200


@pytest.mark.parametrize(
    "change, differs",
    [({"unit_height_m": 2.0}, ["unit_height_m"]), ({"lat": -89.45}, ["location"])],
)
def test_other_horizon_is_422_listing_what_is_served(served_path, change, differs):
    add_horizon(served_path)
    loc = dict(SITE, **{k: v for k, v in change.items() if k in ("lat", "lon")})
    req = {"location": loc, "unit_height_m": change.get("unit_height_m", 1.0)}
    r = client().post("/api/horizon", json=req)
    assert r.status_code == 422
    d = NotServedError.model_validate(r.json()).detail
    assert d.reason == app_module.HORIZON_NOT_SERVED_REASON
    assert d.scenario_key == HorizonRequest.model_validate(req).key()
    (served,) = d.served
    assert served.differs_in == differs  # never the window or step


def test_no_horizon_in_any_file_is_422_with_nothing_served(served_path):
    r = client().post("/api/horizon", json={"location": SITE, "unit_height_m": 1.0})
    assert r.status_code == 422
    assert NotServedError.model_validate(r.json()).detail.served == []


def test_horizon_503_when_nothing_is_installed(data_dir):
    r = client().post("/api/horizon", json={"location": SITE, "unit_height_m": 1.0})
    assert r.status_code == 503
    UnavailableError.model_validate(r.json())


def test_horizon_for_another_point_than_the_scenario_is_refused(served_path):
    add_horizon(served_path, height=2.0)
    with pytest.raises(ServedFileError, match="another location or unit height"):
        load_all(served_path.parent)


def test_horizon_from_another_contract_version_than_the_metrics_is_refused(served_path):
    add_horizon(served_path, version="0.0.1")
    with pytest.raises(ServedFileError, match="different contract versions"):
        load_all(served_path.parent)


def test_two_files_for_one_scenario_are_refused(served_path):
    (served_path.parent / "copy.json").write_text(served_path.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ServedFileError, match="serve the same scenario"):
        load_all(served_path.parent)


# ------------------------------------------------------------------------- compare


def test_compare_all_served(served_path):
    r = client().post("/api/compare", json={"scenarios": [WEB_SCENARIO, WEB_SCENARIO]})
    assert r.status_code == 200
    body = CompareResponse.model_validate(r.json())
    assert [i.scenario_key for i in body.items] == [SCENARIO.key()] * 2
    assert body.not_served == [] and body.placeholder is False


def test_compare_partial_lists_the_unserved_in_order(served_path):
    other = other_scenario(unit_height_m=2.0)
    r = client().post("/api/compare", json={"scenarios": [other, WEB_SCENARIO, other]})
    assert r.status_code == 200
    body = CompareResponse.model_validate(r.json())
    assert [i.scenario_key for i in body.items] == [SCENARIO.key()]
    assert [n.index for n in body.not_served] == [0, 2]
    assert all(n.reason == app_module.COMPARE_NOT_SERVED_REASON for n in body.not_served)
    assert "listed" not in app_module.COMPARE_NOT_SERVED_REASON  # a compare answer lists no scenarios
    assert body.not_served[0].scenario_key != SCENARIO.key()


def test_compare_none_served_is_422(served_path):
    r = client().post("/api/compare", json={"scenarios": [other_scenario(step="PT6H")]})
    assert r.status_code == 422
    d = CompareNotServedError.model_validate(r.json()).detail
    assert [n.index for n in d.not_served] == [0]
    assert d.reason == app_module.COMPARE_NOT_SERVED_REASON


def test_compare_empty_is_validation_422(served_path):
    r = client().post("/api/compare", json={"scenarios": []})
    assert r.status_code == 422
    InvalidRequestError.model_validate(r.json())


def test_compare_503_when_nothing_is_installed(data_dir):
    r = client().post("/api/compare", json={"scenarios": [WEB_SCENARIO]})
    assert r.status_code == 503


# ------------------------------------------------------------------------- OpenAPI


@pytest.mark.parametrize(
    "path, method, codes",
    [
        ("/api/datasets", "get", {"200"}),
        ("/api/locate", "post", {"200", "422"}),
        ("/api/horizon", "post", {"200", "422", "503"}),
        ("/api/metrics", "post", {"200", "422", "503"}),
        ("/api/series", "post", {"200", "422", "503"}),
        ("/api/compare", "post", {"200", "422", "503"}),
    ],
)
def test_openapi_documents_every_error_body(path, method, codes):
    responses = build_openapi()["paths"][path][method]["responses"]
    assert codes <= set(responses)
    for code in codes:
        assert "$ref" in responses[code]["content"]["application/json"]["schema"], (path, code)
