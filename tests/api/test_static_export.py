# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Static JSON fallback: the same bodies as the API, at the current contract version."""

import json

import pytest
from fastapi.testclient import TestClient

import lss.api.app as app_module
from lss.api import static_export
from lss.config import get_settings
from lss.contract import (
    CONTRACT_VERSION,
    DatasetsResponse,
    HorizonProfile,
    MetricsResponse,
    SeriesResponse,
    SitesResponse,
    StaticIndex,
)
from tests.api.test_api_v0 import SITE, add_horizon
from tests.api.test_thin_slice import WEB_SCENARIO, write_served


@pytest.fixture()
def served(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    app_module._served.cache_clear()
    path = write_served(tmp_path / "data" / "cache" / "served")
    yield path
    get_settings.cache_clear()
    app_module._served.cache_clear()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_export_writes_the_api_bodies(served, tmp_path):
    add_horizon(served)
    out = tmp_path / "static-api"
    assert static_export.main([str(out)]) == 0
    index = StaticIndex.model_validate(read(out / "index.json"))
    assert index.contract_version == CONTRACT_VERSION and index.placeholder is False
    (entry,) = index.scenarios
    assert entry.scenario.model_dump(mode="json") == WEB_SCENARIO and entry.horizon

    client = TestClient(app_module.create_app())
    live = client.post("/api/metrics", json={"scenario": WEB_SCENARIO}).json()
    assert read(out / entry.metrics) == live
    MetricsResponse.model_validate(live)
    assert read(out / entry.series) == client.post("/api/series", json={"scenario": WEB_SCENARIO}).json()
    SeriesResponse.model_validate(read(out / entry.series))
    h = client.post("/api/horizon", json={"location": SITE, "unit_height_m": 1.0}).json()
    assert read(out / entry.horizon) == h
    HorizonProfile.model_validate(h)
    assert read(out / index.sites) == client.get("/api/sites").json()
    SitesResponse.model_validate(read(out / index.sites))
    assert read(out / index.datasets) == client.get("/api/datasets").json()
    DatasetsResponse.model_validate(read(out / index.datasets))


def test_export_without_horizons_has_null_paths(served, tmp_path):
    out = tmp_path / "static-api"
    assert static_export.main([str(out)]) == 0
    assert StaticIndex.model_validate(read(out / "index.json")).scenarios[0].horizon is None
    assert not (out / "horizon").exists()


def test_export_from_a_compatible_version_is_stamped_current(tmp_path, monkeypatch):
    from lss.api.served import COMPATIBLE_VERSIONS

    if not COMPATIBLE_VERSIONS:
        pytest.skip("no compatible older version")
    d = tmp_path / "served"
    write_served(d, version=sorted(COMPATIBLE_VERSIONS)[0])
    out = tmp_path / "static-api"
    assert static_export.main([str(out), "--served-dir", str(d)]) == 0
    index = StaticIndex.model_validate(read(out / "index.json"))
    assert read(out / index.scenarios[0].metrics)["contract_version"] == CONTRACT_VERSION


def test_export_refuses_nothing_served(tmp_path):
    assert static_export.main([str(tmp_path / "out"), "--served-dir", str(tmp_path / "none")]) == 1


def test_check_api_passes_against_the_same_api(served, tmp_path, monkeypatch):
    client = TestClient(app_module.create_app())

    def fake_get_json(url, body=None):
        path = url.removeprefix("https://api.example")
        r = client.post(path, json=body) if body is not None else client.get(path)
        r.raise_for_status()
        return r.json()

    monkeypatch.setattr(static_export, "_get_json", fake_get_json)
    assert static_export.main([str(tmp_path / "out"), "--check-api", "https://api.example"]) == 0


def test_check_api_fails_on_another_contract_version(served, tmp_path, monkeypatch):
    monkeypatch.setattr(static_export, "_get_json", lambda url, body=None: {"contract_version": "0.0.1"})
    assert static_export.main([str(tmp_path / "out"), "--check-api", "https://api.example"]) == 1


def test_check_api_fails_when_the_metrics_differ(served, tmp_path, monkeypatch):
    def fake_get_json(url, body=None):
        if body is None:
            return {"contract_version": CONTRACT_VERSION}
        return {"different": True}

    monkeypatch.setattr(static_export, "_get_json", fake_get_json)
    assert static_export.main([str(tmp_path / "out"), "--check-api", "https://api.example"]) == 1
