# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""GET /api/scenarios (contract 0.11.0), its static copy, and list-free NL limitation reasons."""

import json

import pytest
from fastapi.testclient import TestClient

import lss.api.app as app_module
from lss.api import nl, static_export
from lss.config import get_settings
from lss.contract import NLAnswer, NLRequest, ScenariosResponse, StaticIndex
from lss.nl.provider import FakeProvider
from tests.api.test_compare_filters import write_served_at
from tests.api.test_thin_slice import WEB_SCENARIO


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path))
    for f in (get_settings, app_module._served, app_module._terrain):
        f.cache_clear()
    for h in (2.0, 1.0):
        write_served_at(tmp_path / "cache" / "served", h)
    yield tmp_path
    for f in (get_settings, app_module._served, app_module._terrain):
        f.cache_clear()


def test_scenarios_lists_every_served_scenario_with_its_site(data_dir):
    r = TestClient(app_module.create_app()).get("/api/scenarios")
    assert r.status_code == 200
    body = ScenariosResponse.model_validate(r.json())
    assert [e.scenario.unit_height_m for e in body.scenarios] == [1.0, 2.0]  # ordered by height
    assert {e.site_id for e in body.scenarios} == {"pgda-site01"}  # matched on the exact location
    assert all(e.scenario_key == e.scenario.key() and not e.has_horizon for e in body.scenarios)


def test_scenarios_for_one_site(data_dir):
    c = TestClient(app_module.create_app())
    assert len(c.get("/api/scenarios", params={"site_id": "pgda-site01"}).json()["scenarios"]) == 2
    assert c.get("/api/scenarios", params={"site_id": "pgda-site04"}).json()["scenarios"] == []


def test_scenarios_503_when_nothing_is_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    app_module._served.cache_clear()
    try:
        assert TestClient(app_module.create_app()).get("/api/scenarios").status_code == 503
    finally:
        get_settings.cache_clear()
        app_module._served.cache_clear()


def test_static_copy_has_the_same_list_and_checks_it(data_dir, monkeypatch):
    client = TestClient(app_module.create_app())

    def fake_get_json(url, body=None):
        path = url.removeprefix("https://api.example")
        r = client.post(path, json=body) if body is not None else client.get(path)
        r.raise_for_status()
        return r.json()

    monkeypatch.setattr(static_export, "_get_json", fake_get_json)
    out = data_dir / "static"
    assert static_export.main([str(out), "--check-api", "https://api.example"]) == 0
    index = StaticIndex.model_validate(json.loads((out / "index.json").read_text(encoding="utf-8")))
    assert index.scenario_list == "scenarios.json"
    assert (
        json.loads((out / "scenarios.json").read_text(encoding="utf-8"))
        == client.get("/api/scenarios").json()
    )
    assert {e.site_id for e in index.scenarios} == {"pgda-site01"}


def test_static_check_fails_when_the_lists_differ(data_dir, monkeypatch):
    client = TestClient(app_module.create_app())

    def fake_get_json(url, body=None):
        path = url.removeprefix("https://api.example")
        if path == "/api/scenarios":
            return {"different": True}
        r = client.post(path, json=body) if body is not None else client.get(path)
        return r.json()

    monkeypatch.setattr(static_export, "_get_json", fake_get_json)
    assert static_export.main([str(data_dir / "static"), "--check-api", "https://api.example"]) == 1


def test_nl_not_served_limitation_refers_to_no_list(data_dir):
    sc = dict(WEB_SCENARIO, unit_height_m=5.0)  # not served
    out = {
        "outcome": "answer",
        "interpretation": "Metrics at Connecting Ridge, 5 m.",
        "query": {"operation": "metrics", "params": {"scenario": sc}},
        "height_source": "user",
        "window_source": "user",
    }
    service = nl.NLService(
        executors=app_module.NL_EXECUTORS,
        provider_factory=lambda: FakeProvider({"q": out}),
        list_free_reasons=app_module.LIST_FREE_REASONS,
    )
    body = service.answer(NLRequest(text="q"), "1.2.3.4")
    assert isinstance(body, NLAnswer) and body.result is None
    assert body.limitations[-1].reason == app_module.COMPARE_NOT_SERVED_REASON
    assert "listed" not in body.limitations[-1].reason


def test_every_listing_reason_has_a_list_free_version():
    for listing in (
        app_module.NOT_SERVED_REASON,
        app_module.HORIZON_NOT_SERVED_REASON,
        app_module.TERRAIN_NOT_SERVED_REASON,
    ):
        free = app_module.LIST_FREE_REASONS[listing]
        assert "listed" not in free and "here" not in free.split()
