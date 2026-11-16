# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Cached showcase NL answers (C8): writer, strict loader, endpoint and static copy. Fakes only."""

import json

import pytest
from fastapi.testclient import TestClient

import lss.api.app as app_module
from lss.api import nl, nl_cache, static_export
from lss.config import get_settings
from lss.contract import NLAnswer, NLRequest, StaticIndex
from lss.nl.evalset import label_output, load_eval_set
from lss.nl.provider import FakeProvider
from tests.api.test_terrain_api import terrain_body, write_terrain
from tests.api.test_thin_slice import write_served

EVAL = load_eval_set()
K2 = next(i for i in EVAL.items if i.id == "k2")  # "How steep is the terrain?", Site01 selected


def results_file(tmp_path, output):
    """A minimal saved eval run with one item's output (what `nl.eval` writes)."""
    run = {
        "reference_date": EVAL.reference_date.isoformat(),
        "model": "fake",
        "prompt_version": "p-test",
        "schema_version": "nl-output-6",
        "items": [{"id": "k2", "output": output}],
    }
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run), encoding="utf-8")
    return path


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path / "data"))
    caches = (get_settings, app_module._served, app_module._terrain, app_module.get_nl_service)
    for f in caches:
        f.cache_clear()
    write_served(tmp_path / "data" / "cache" / "served")
    write_terrain(tmp_path / "data" / "cache" / "terrain", [terrain_body(1000.0), terrain_body(10_000.0)])
    yield tmp_path / "data"
    for f in caches:
        f.cache_clear()


def test_add_from_run_replays_the_saved_output(tmp_path, data_dir):
    path = nl_cache.add_from_run(results_file(tmp_path, label_output(K2)), "k2")
    assert path.parent == data_dir / "cache" / "nl"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert (
        data["provenance"]["est_cost_usd"] == 0.0 and data["provenance"]["recorded_for_date"] == "2026-11-15"
    )
    entry = next(iter(nl.load_cache_entries(path.parent).values()))
    assert isinstance(entry.response, NLAnswer) and entry.response.result["radius_m"] == 1000.0
    assert nl_cache.list_entries() == [
        f"{path.stem}: How steep is the terrain? [site pgda-site01] -> NLAnswer"
    ]


def test_not_understood_outputs_are_never_cached(tmp_path, data_dir):
    bad = {"outcome": "answer", "interpretation": "x", "query": {"operation": "metrics", "params": {}}}
    with pytest.raises(nl_cache.CacheWriteError, match="didn't validate"):
        nl_cache.add_from_run(results_file(tmp_path, bad), "k2")
    assert not (data_dir / "cache" / "nl").exists() or not list((data_dir / "cache" / "nl").glob("*.json"))


def test_one_entry_per_request_unless_replaced(tmp_path, data_dir):
    run = results_file(tmp_path, label_output(K2))
    nl_cache.add_from_run(run, "k2")
    with pytest.raises(nl_cache.CacheWriteError, match="already answers"):
        nl_cache.add_from_run(run, "k2")
    nl_cache.add_from_run(run, "k2", replace=True)
    assert len(list((data_dir / "cache" / "nl").glob("*.json"))) == 1


def test_add_live_uses_the_demo_pipeline(data_dir):
    path = nl_cache.add_live(
        K2.text, site_id="pgda-site01", provider_factory=lambda: FakeProvider({K2.text: label_output(K2)})
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["provenance"]["source"] == "live" and data["response"]["result"]["radius_m"] == 1000.0


def test_cli_add_needs_live():
    with pytest.raises(SystemExit):
        nl_cache.main(["add", "How steep is the terrain?"])


def test_loader_refuses_another_contract_version(tmp_path, data_dir):
    path = nl_cache.add_from_run(results_file(tmp_path, label_output(K2)), "k2")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["response"]["contract_version"] = "0.0.1"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(nl.CacheFileError, match="record it again"):
        nl.load_cache_entries(path.parent)


def test_endpoint_serves_the_cached_answer_without_a_model(tmp_path, data_dir):
    nl_cache.add_from_run(results_file(tmp_path, label_output(K2)), "k2")

    def no_model():
        raise AssertionError("a cached answer must not call the model")

    service = app_module.get_nl_service()
    service.provider_factory = no_model
    r = TestClient(app_module.create_app()).post(
        "/api/nl", json={"text": "how steep is the terrain", "selected_site_id": "pgda-site01"}
    )
    assert r.status_code == 200 and r.json()["result"]["radius_m"] == 1000.0


def test_static_copy_publishes_cached_answers_and_checks_them(tmp_path, data_dir, monkeypatch):
    nl_cache.add_from_run(results_file(tmp_path, label_output(K2)), "k2")
    client = TestClient(app_module.create_app())

    def fake_get_json(url, body=None):
        path = url.removeprefix("https://api.example")
        r = client.post(path, json=body) if body is not None else client.get(path)
        r.raise_for_status()
        return r.json()

    monkeypatch.setattr(static_export, "_get_json", fake_get_json)
    out = tmp_path / "static"
    assert static_export.main([str(out), "--check-api", "https://api.example"]) == 0
    index = StaticIndex.model_validate(json.loads((out / "index.json").read_text(encoding="utf-8")))
    (entry,) = index.nl_answers
    assert entry.request == NLRequest(text=K2.text, selected_site_id="pgda-site01")
    static = json.loads((out / entry.path).read_text(encoding="utf-8"))
    assert (
        static == client.post("/api/nl", json=entry.request.model_dump(mode="json", exclude_none=True)).json()
    )
