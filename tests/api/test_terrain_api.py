# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""POST /api/terrain and /api/site_summary (contract 0.9.0): precomputed slope statistics, cache/terrain/."""

import json

import pytest
from fastapi.testclient import TestClient

import lss.api.app as app_module
from lss.api import nl
from lss.api.served import ServedFileError, load_terrain
from lss.config import get_settings
from lss.contract import (
    CONTRACT_VERSION,
    NLAnswer,
    NLRequest,
    SiteSummaryResponse,
    TerrainNotServedError,
    TerrainRequest,
    TerrainResponse,
    UnavailableError,
)
from lss.contract.export import build_openapi
from lss.nl.provider import FakeProvider
from tests.api.test_thin_slice import WEB_SCENARIO, write_served

SITE = {"lat": WEB_SCENARIO["location"]["lat"], "lon": WEB_SCENARIO["location"]["lon"]}


def terrain_body(radius, version=CONTRACT_VERSION, **loc):
    return TerrainResponse(
        contract_version=version,
        location=loc or SITE,
        radius_m=radius,
        slope_at_point_deg=1.2,
        slope_deg={"min": 0.0, "max": 30.0, "mean": 9.0},
        slope_layer={"dataset_id": "pgda_78_site_dems", "role": "near_field", "resolution_m": 5.0},
        limitations=["synthetic"],
    ).model_dump(mode="json", by_alias=True)


def write_terrain(directory, bodies, name="pgda-site01.json"):
    directory.mkdir(parents=True, exist_ok=True)
    data = {"format": 1, "site_id": "pgda-site01", "terrain": bodies, "provenance": {}}
    (directory / name).write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path))
    for f in (get_settings, app_module._served, app_module._terrain):
        f.cache_clear()
    yield tmp_path
    for f in (get_settings, app_module._served, app_module._terrain):
        f.cache_clear()


@pytest.fixture()
def client(data_dir):
    write_served(data_dir / "cache" / "served")
    write_terrain(data_dir / "cache" / "terrain", [terrain_body(1000.0), terrain_body(10_000.0)])
    return TestClient(app_module.create_app())


def test_terrain_is_served_for_an_exact_location_and_radius(client):
    r = client.post("/api/terrain", json={"location": dict(SITE, name="any"), "radius_m": 1000})
    assert r.status_code == 200
    body = TerrainResponse.model_validate(r.json())
    assert body.radius_m == 1000 and body.contract_version == CONTRACT_VERSION and not body.placeholder


def test_other_radius_is_422_listing_what_is_served(client):
    r = client.post("/api/terrain", json={"location": SITE, "radius_m": 500})
    assert r.status_code == 422
    d = TerrainNotServedError.model_validate(r.json()).detail
    assert d.reason == app_module.TERRAIN_NOT_SERVED_REASON
    assert d.terrain_key == TerrainRequest(location=SITE, radius_m=500).key()
    assert sorted(o.radius_m for o in d.served) == [1000, 10_000]


def test_no_terrain_installed_is_503(data_dir):
    r = TestClient(app_module.create_app()).post("/api/terrain", json={"location": SITE, "radius_m": 1000})
    assert r.status_code == 503
    assert "slope statistics" in UnavailableError.model_validate(r.json()).detail.technical


def test_terrain_files_follow_the_served_file_rules(tmp_path):
    write_terrain(tmp_path / "a", [terrain_body(1000.0, version="0.0.1")])
    with pytest.raises(ServedFileError, match="precompute_terrain"):
        load_terrain(tmp_path / "a")
    write_terrain(tmp_path / "b", [terrain_body(1000.0)])
    write_terrain(tmp_path / "b", [terrain_body(1000.0)], name="copy.json")
    with pytest.raises(ServedFileError, match="same location and radius"):
        load_terrain(tmp_path / "b")


def test_site_summary_assembles_terrain_and_metrics(client):
    r = client.post(
        "/api/site_summary", json={"location": SITE, "radius_m": 10_000, "scenario": WEB_SCENARIO}
    )
    assert r.status_code == 200
    body = SiteSummaryResponse.model_validate(r.json())
    assert body.terrain.radius_m == 10_000 and body.metrics.scenario_key == "00010cfa5fef681c"
    assert body.features is None
    assert body.limitations == [nl.NOT_AVAILABLE_YET[nl.Operation.proximity]]


def test_site_summary_says_what_is_missing(client):
    sc = dict(WEB_SCENARIO, unit_height_m=2.0)
    body = SiteSummaryResponse.model_validate(
        client.post("/api/site_summary", json={"location": SITE, "radius_m": 500, "scenario": sc}).json()
    )
    assert body.terrain is None and body.metrics is None
    assert app_module.SUMMARY_NO_TERRAIN_REASON in body.limitations
    assert app_module.COMPARE_NOT_SERVED_REASON in body.limitations  # the reason that names no list
    assert not any("listed" in lim for lim in body.limitations)


def test_nl_terrain_question_gets_the_statistics(client):
    out = {
        "outcome": "answer",
        "interpretation": "Slope at and around Connecting ridge.",
        "query": {
            "operation": "terrain",
            "params": {"location": {"site_id": "pgda-site01"}, "radius_m": 1000.0},
        },
        "radius_source": "around_default",
    }
    service = nl.NLService(
        executors=app_module.NL_EXECUTORS, provider_factory=lambda: FakeProvider({"q": out})
    )
    body = service.answer(NLRequest(text="q"), "1.2.3.4")
    assert isinstance(body, NLAnswer) and body.result["radius_m"] == 1000.0 and body.limitations == []


def test_openapi_documents_the_new_routes():
    paths = build_openapi()["paths"]
    assert {"200", "422", "503"} <= set(paths["/api/terrain"]["post"]["responses"])
    assert "/api/site_summary" in paths


def test_static_copy_includes_terrain_and_checks_it(client, data_dir, monkeypatch):
    from lss.api import static_export
    from lss.contract import StaticIndex

    out = data_dir / "static"
    tc = TestClient(app_module.create_app())

    def fake_get_json(url, body=None):
        path = url.removeprefix("https://api.example")
        r = tc.post(path, json=body) if body is not None else tc.get(path)
        r.raise_for_status()
        return r.json()

    monkeypatch.setattr(static_export, "_get_json", fake_get_json)
    assert static_export.main([str(out), "--check-api", "https://api.example"]) == 0
    index = StaticIndex.model_validate(json.loads((out / "index.json").read_text(encoding="utf-8")))
    assert sorted(t.radius_m for t in index.terrain) == [1000, 10_000]
    first = index.terrain[0]
    assert json.loads((out / first.path).read_text(encoding="utf-8"))["radius_m"] == first.radius_m
