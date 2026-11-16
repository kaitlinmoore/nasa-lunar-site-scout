# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""POST /api/metrics and /api/series (C1 thin slice): precomputed results only, matched on Scenario.key()."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import lss.api.app as app_module
from lss.api.served import COMPATIBLE_VERSIONS, load_file
from lss.config import FIXTURES_DIR, REPO_ROOT, get_settings
from lss.contract import (
    CONTRACT_VERSION,
    InvalidRequestError,
    MetricsResponse,
    NotServedError,
    UnavailableError,
    UnprocessableError,
)
from lss.contract.examples import SCENARIO

REGRESSION = REPO_ROOT / "tests" / "engine" / "fixtures" / "site01_roi4_c1.json"
# Stream B sends exactly this (web/src/api/source.ts builds the live request from fixtures/metrics.json).
WEB_SCENARIO = json.loads((FIXTURES_DIR / "metrics.json").read_text(encoding="utf-8"))["scenario"]


def write_served(directory: Path, version: str = CONTRACT_VERSION) -> Path:
    """A served file made from the regression fixture (the validated result; series every 6 h)."""
    ref = json.loads(REGRESSION.read_text(encoding="utf-8"))
    data = {
        "format": 1,
        "scenario_key": ref["scenario_key"],
        "metrics": ref["metrics"] | {"contract_version": version},
        "series": ref["series"] | {"contract_version": version},
    }
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"c1_{ref['scenario_key']}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    app_module._served.cache_clear()
    yield tmp_path
    get_settings.cache_clear()
    app_module._served.cache_clear()


@pytest.fixture()
def client(data_dir):
    write_served(data_dir / "cache" / "served")
    return TestClient(app_module.create_app())


def test_web_request_gets_the_served_metrics(client):
    assert WEB_SCENARIO == SCENARIO.model_dump(mode="json")  # the fixture's scenario is the served one
    r = client.post("/api/metrics", json={"scenario": WEB_SCENARIO})
    assert r.status_code == 200
    body = r.json()
    assert body["_placeholder"] is False and body["contract_version"] == CONTRACT_VERSION
    assert body["scenario_key"] == "00010cfa5fef681c"
    ref = json.loads(REGRESSION.read_text(encoding="utf-8"))["metrics"]
    assert body["power"] == ref["power"] and body["comms"] == ref["comms"] and body["events"] == ref["events"]
    MetricsResponse.model_validate(body)


def test_series_is_served_too(client):
    r = client.post("/api/series", json={"scenario": WEB_SCENARIO})
    assert r.status_code == 200
    body = r.json()
    assert body["_placeholder"] is False and body["scenario_key"] == SCENARIO.key()
    assert len(body["time"]) == len(body["sun"]["azimuth_deg"])


def test_location_name_is_not_part_of_the_match(client):
    sc = json.loads(json.dumps(WEB_SCENARIO))
    sc["location"]["name"] = "anything"
    assert client.post("/api/metrics", json={"scenario": sc}).status_code == 200


@pytest.mark.parametrize(
    "field, value",
    [
        ("lat", -89.45),
        ("lon", -137.31),
        ("unit_height_m", 2.0),
        ("window_start", "2028-05-15T01:00:00Z"),
        ("window_end", "2028-06-13T00:00:00Z"),
        ("step", "PT6H"),
    ],
)
@pytest.mark.parametrize("path", ["/api/metrics", "/api/series"])
def test_any_other_scenario_gets_422_with_the_reason(client, path, field, value):
    sc = json.loads(json.dumps(WEB_SCENARIO))
    if field in ("lat", "lon"):
        sc["location"][field] = value
    else:
        sc[field] = value
    r = client.post(path, json={"scenario": sc})
    assert r.status_code == 422
    NotServedError.model_validate(r.json())  # the contract's 422 body
    assert isinstance(UnprocessableError.model_validate(r.json()).root, NotServedError)
    d = r.json()["detail"]
    assert "precomputed" in d["reason"] and "`" not in d["reason"] and d["scenario_key"] != SCENARIO.key()
    (served,) = d["served"]
    assert served["scenario_key"] == SCENARIO.key() and served["scenario"] == WEB_SCENARIO
    assert served["differs_in"] == ["location" if field in ("lat", "lon") else field]


def test_invalid_request_is_rejected_by_validation(client):
    sc = dict(WEB_SCENARIO, unit_height_m=0.0)
    r = client.post("/api/metrics", json={"scenario": sc})
    assert r.status_code == 422 and isinstance(r.json()["detail"], list)  # FastAPI's validation errors
    InvalidRequestError.model_validate(r.json())
    assert isinstance(UnprocessableError.model_validate(r.json()).root, InvalidRequestError)


def test_no_served_results_is_503(data_dir):
    r = TestClient(app_module.create_app()).post("/api/metrics", json={"scenario": WEB_SCENARIO})
    assert r.status_code == 503
    d = UnavailableError.model_validate(r.json()).detail
    assert "temporarily unavailable" in d.reason and "no precomputed results are installed" in d.technical
    assert "/" not in d.reason and "\\" not in d.reason  # no server paths in the visitor-facing text


def test_result_from_another_contract_version_is_refused(data_dir):
    write_served(data_dir / "cache" / "served", version="0.0.1")
    r = TestClient(app_module.create_app()).post("/api/metrics", json={"scenario": WEB_SCENARIO})
    assert r.status_code == 503
    d = UnavailableError.model_validate(r.json()).detail
    assert "precompute_c1" in d.technical and "precompute_c1" not in d.reason


@pytest.mark.parametrize("version", sorted(COMPATIBLE_VERSIONS))
@pytest.mark.parametrize("path", ["/api/metrics", "/api/series"])
def test_result_from_a_compatible_version_is_served_with_the_current_version(data_dir, version, path):
    write_served(data_dir / "cache" / "served", version=version)
    r = TestClient(app_module.create_app()).post(path, json={"scenario": WEB_SCENARIO})
    assert r.status_code == 200 and r.json()["contract_version"] == CONTRACT_VERSION


def test_compatible_versions_are_older_than_the_contract():
    def parse(v):
        return tuple(int(x) for x in v.split("."))

    assert CONTRACT_VERSION not in COMPATIBLE_VERSIONS
    assert all(parse(v) < parse(CONTRACT_VERSION) for v in COMPATIBLE_VERSIONS)


def test_serving_loads_no_terrain_or_ephemeris_code(data_dir):
    write_served(data_dir / "cache" / "served")
    code = (
        "import json, sys\n"
        "from fastapi.testclient import TestClient\n"
        "from lss.api.app import app\n"
        f"sc = json.loads({json.dumps(json.dumps(WEB_SCENARIO))})\n"
        "c = TestClient(app)\n"
        "assert c.post('/api/metrics', json={'scenario': sc}).status_code == 200\n"
        "assert c.post('/api/series', json={'scenario': sc}).status_code == 200\n"
        "assert c.post('/api/compare', json={'scenarios': [sc]}).status_code == 200\n"
        "loc = sc['location']\n"
        "assert c.post('/api/horizon', json={'location': loc, 'unit_height_m': 1.0}).status_code == 422\n"
        "assert c.post('/api/locate', json={'lat': loc['lat'], 'lon': loc['lon']}).status_code == 200\n"
        "assert c.get('/api/datasets').status_code == 200\n"
        "print(sorted(m for m in ('spiceypy', 'rasterio', 'numba') if m in sys.modules))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "LSS_DATA_DIR": str(data_dir)},
        check=True,
    )
    assert out.stdout.strip() == "[]"


def test_installed_served_file_is_the_validated_result():
    """The real served file, if this machine has it (scripts/precompute_c1.py)."""
    path = Path(get_settings().data_dir) / "cache" / "served" / f"c1_{SCENARIO.key()}.json"
    if not path.is_file():
        pytest.skip("served result not generated on this machine")
    sv = load_file(path)
    ref = json.loads(REGRESSION.read_text(encoding="utf-8"))
    got = sv.metrics.model_dump(mode="json", by_alias=True)
    assert got["power"] == ref["metrics"]["power"] and got["comms"] == ref["metrics"]["comms"]
    assert len(sv.series.time) == 721


def test_compatible_mechanism_works_while_the_list_is_empty(data_dir, monkeypatch):
    """COMPATIBLE_VERSIONS is empty when every file is current; the re-stamping path must still work."""
    import lss.api.served as served_module

    monkeypatch.setattr(served_module, "COMPATIBLE_VERSIONS", frozenset({"0.0.9"}))
    write_served(data_dir / "cache" / "served", version="0.0.9")
    r = TestClient(app_module.create_app()).post("/api/metrics", json={"scenario": WEB_SCENARIO})
    assert r.status_code == 200 and r.json()["contract_version"] == CONTRACT_VERSION
