# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Eval harness (step 4.5), with fake providers only: no network calls."""

from __future__ import annotations

import json
from datetime import date

import pytest

from lss.contract import Operation
from lss.nl import eval as nl_eval
from lss.nl.evalset import EvalSet, load_eval_set
from lss.nl.prompt import PROMPT_VERSION, build_fill_prompt, build_route_prompt
from lss.nl.provider import FakeProvider
from lss.nl.validate import default_context

SCENARIO = {
    "location": {"site_id": "pgda-site01"},
    "unit_height_m": 5.0,
    "window_start": "2029-01-01T00:00:00Z",
    "window_end": "2029-02-01T00:00:00Z",
}
LANDER = "What fraction of the time can a lander at Connecting ridge see Earth during January 2029?"
BOULDERS = (
    "Which candidate sites have zero boulders larger than 0.5 meters within a 50-meter landing ellipse?"
)
CITE_81 = {
    "dataset_id": "pgda_81_mosaic_5m",
    "cannot_answer": "Hazards smaller than a few pixels (e.g. sub-meter boulders)",
}
CITE_AUSSEL = {"dataset_id": "aussel_2025_boulders", "cannot_answer": "Any boulder information at the poles"}
CITE_ROUGH = {
    "dataset_id": "pgda_98_polar_roughness",
    "cannot_answer": "Individual boulders or meter-scale hazards",
}
CITE_CRATERS = {"dataset_id": "robbins_craters", "cannot_answer": "Craters smaller than ~1 km"}


def eval_set() -> EvalSet:
    """A small synthetic set: one query item (exact), one subset item, one refusal."""
    return EvalSet.model_validate(
        {
            "version": 0,
            "reference_date": "2026-11-15",
            "items": [
                {
                    "id": "q",
                    "source": "si_supplied",
                    "text": LANDER,
                    "target": "t",
                    "status": "ready",
                    "expected": {
                        "outcome": "answer",
                        "height_source": "lander_proxy",
                        "query": {"operation": "metrics", "params": {"scenario": SCENARIO}},
                    },
                },
                {
                    "id": "sub",
                    "source": "si_supplied",
                    "text": "Craters within 10 km of Connecting ridge?",
                    "target": "t",
                    "status": "ready",
                    "expected": {
                        "outcome": "answer",
                        "params_match": "subset",
                        "query": {
                            "operation": "proximity",
                            "params": {"location": {"site_id": "pgda-site01"}, "types": ["crater"]},
                        },
                    },
                },
                {
                    "id": "r",
                    "source": "kaitlin",
                    "text": BOULDERS,
                    "target": "t",
                    "status": "ready",
                    "expected": {
                        "outcome": "unsupported",
                        "citations": [CITE_81, CITE_AUSSEL],
                        "citations_optional": [CITE_ROUGH],
                    },
                },
                {
                    "id": "b",
                    "source": "kaitlin",
                    "text": "How steep is the terrain?",
                    "target": "t",
                    "status": "blocked",
                    "blocked_on": ["C2"],
                },
            ],
        }
    )


def answer(scenario=SCENARIO, height_source="lander_proxy", operation="metrics"):
    return {
        "outcome": "answer",
        "interpretation": "i",
        "height_source": height_source,
        "window_source": "user",
        "query": {"operation": operation, "params": {"scenario": scenario}},
    }


def refusal(*cites):
    return {
        "outcome": "unsupported",
        "interpretation": "i",
        "limitations": [{"topic": "boulders", "citations": list(cites)}],
    }


PROXIMITY_OK = {
    "outcome": "answer",
    "interpretation": "i",
    "query": {
        "operation": "proximity",
        "params": {"location": {"site_id": "pgda-site01"}, "types": ["crater"], "radius_m": 10000},
    },
    "radius_source": "user",
}


def run(responses):
    es = eval_set()
    report = nl_eval.run_eval(FakeProvider(responses), es)
    return report, {r["id"]: r for r in report["items"]}


def test_perfect_outputs_score_one():
    report, _ = run(
        {
            LANDER: answer(),
            "Craters within 10 km of Connecting ridge?": PROXIMITY_OK,
            BOULDERS: refusal(CITE_81, CITE_AUSSEL),
        }
    )
    assert report["scores"]["a_structured_query"] == {"correct": 2, "total": 2, "score": 1.0}
    assert report["scores"]["b_refusal_reason"] == {"correct": 1, "total": 1, "score": 1.0}
    assert report["counts"] == {"items_in_set": 4, "run": 3, "scored": 3, "blocked": 1}
    assert report["prompt_version"] == PROMPT_VERSION


@pytest.mark.parametrize(
    ("output", "problem"),
    [
        (answer(operation="series"), "operation series != expected metrics"),
        (answer(scenario={**SCENARIO, "window_end": "2029-01-31T00:00:00Z"}), "params differ"),
        (
            {**answer(), "outcome": "partial", "limitations": [{"topic": "x", "citations": [CITE_CRATERS]}]},
            "outcome partial != expected answer",
        ),
        (answer(scenario={**SCENARIO, "unit_height_m": 1.0}, height_source="rover_proxy"), "height_source"),
        ("not json", "not JSON"),
    ],
)
def test_wrong_queries_score_zero(output, problem):
    report, items = run(
        {
            LANDER: output,
            "Craters within 10 km of Connecting ridge?": PROXIMITY_OK,
            BOULDERS: refusal(CITE_81, CITE_AUSSEL),
        }
    )
    assert items["q"]["query_correct"] is False
    assert any(problem in p for p in items["q"]["problems"]), items["q"]["problems"]
    assert report["scores"]["a_structured_query"]["correct"] == 1


def test_subset_label_checks_only_its_keys():
    wrong = json.loads(json.dumps(PROXIMITY_OK))
    wrong["query"]["params"]["types"] = ["psr"]
    _, items = run(
        {LANDER: answer(), "Craters within 10 km of Connecting ridge?": wrong, BOULDERS: refusal(CITE_81)}
    )
    assert items["sub"]["query_correct"] is False


@pytest.mark.parametrize(
    ("cites", "ok"),
    [
        ((CITE_81, CITE_AUSSEL), True),
        ((CITE_81, CITE_AUSSEL, CITE_ROUGH), True),  # optional citation: no penalty
        ((CITE_AUSSEL,), False),  # missing a required citation
        ((CITE_81, CITE_AUSSEL, CITE_CRATERS), False),  # citation outside required + optional
    ],
)
def test_reason_scoring(cites, ok):
    _, items = run(
        {
            LANDER: answer(),
            "Craters within 10 km of Connecting ridge?": PROXIMITY_OK,
            BOULDERS: refusal(*cites),
        }
    )
    assert items["r"]["reason_correct"] is ok


def test_provider_errors_are_recorded_not_raised():
    report, items = run({})  # FakeProvider raises KeyError for every item
    assert all(r["error"] for r in items.values())
    assert report["scores"]["a_structured_query"]["correct"] == 0


def test_blocked_items_run_only_on_request_and_are_never_scored():
    report = nl_eval.run_eval(FakeProvider(respond=lambda p: "{}"), eval_set(), include_blocked=True)
    blocked = next(r for r in report["items"] if r["id"] == "b")
    assert blocked["scored"] is False and blocked["blocked_reasons"] == ["blocked on contract"]
    assert report["counts"]["scored"] == 3


def test_oracle_scores_one_on_the_real_eval_set():
    es = load_eval_set()
    report = nl_eval.run_eval(nl_eval.oracle_provider(es), es)
    for score in report["scores"].values():
        assert score["score"] in (None, 1.0), report["scores"]


def test_results_file_names_model_and_prompt(tmp_path):
    report, _ = run({})
    path = nl_eval.write_results(report, tmp_path)
    assert "fake" in path.name and "fake-1" in path.name and PROMPT_VERSION in path.name
    assert json.loads(path.read_text(encoding="utf-8"))["model"] == "fake-1"


def test_cli_oracle_and_live_guard(capsys):
    assert nl_eval.main(["--no-write"]) == 0
    with pytest.raises(SystemExit):
        nl_eval.main(["--provider", "claude", "--no-write"])  # no --live: refused before any call
    assert "--live" in capsys.readouterr().err


def test_stage_prompts():
    route = build_route_prompt(BOULDERS, default_context(), date(2026, 11, 15))
    fill = build_fill_prompt(LANDER, default_context(), date(2026, 11, 15), Operation.metrics)
    assert "aussel_2025_boulders" in route.user and "registry" not in fill.user  # fill needs no registry
    assert "2026-11-15" in route.user and "2026-11-15" in fill.user
    assert route.meta["stage"] == "route" and fill.meta["operation"] == "metrics"
    assert fill.json_schema["$defs"]["ScenarioRequest"]  # typed params for the chosen operation only
    assert "SearchRequest" not in fill.json_schema["$defs"]
    other = build_route_prompt("How steep is the terrain?", default_context("pgda-site01"), date(2027, 1, 1))
    assert other.system == route.system  # stable system text: cacheable across requests and days
    assert "sk-ant" not in route.system + route.user + fill.system + fill.user


def test_unsupported_route_makes_one_call_and_answers_make_two():
    provider = FakeProvider({LANDER: answer(), BOULDERS: refusal(CITE_81, CITE_AUSSEL)})
    nl_eval.run_eval(provider, eval_set())
    stages = [(c.meta["text"], c.meta["stage"]) for c in provider.calls]
    assert stages.count((BOULDERS, "route")) == 1 and (BOULDERS, "fill") not in stages
    assert (LANDER, "route") in stages and (LANDER, "fill") in stages


def test_inconsistent_route_is_a_problem_not_a_crash():
    bad = {"outcome": "answer", "operation": None, "interpretation": "i", "limitations": []}
    _, items = run(
        {
            LANDER: bad,
            "Craters within 10 km of Connecting ridge?": PROXIMITY_OK,
            BOULDERS: refusal(CITE_81, CITE_AUSSEL),
        }
    )
    assert any("needs an operation" in p for p in items["q"]["problems"])


def _with_split(es: EvalSet, item_id: str, split: str) -> EvalSet:
    data = es.model_dump(mode="json")
    for item in data["items"]:
        if item["id"] == item_id:
            item["split"] = split
    return EvalSet.model_validate(data)


def test_scores_are_reported_per_split():
    es = _with_split(eval_set(), "r", "holdout")
    responses = {
        LANDER: answer(),
        "Craters within 10 km of Connecting ridge?": PROXIMITY_OK,
        BOULDERS: refusal(CITE_81, CITE_AUSSEL),
    }
    report = nl_eval.run_eval(FakeProvider(responses), es)
    by = report["scores_by_split"]
    assert by["holdout"]["b_refusal_reason"] == {"correct": 1, "total": 1, "score": 1.0}
    assert by["holdout"]["a_structured_query"]["total"] == 0
    assert by["dev"]["a_structured_query"] == {"correct": 2, "total": 2, "score": 1.0}
    assert by["dev"]["b_refusal_reason"]["total"] == 0


def test_rescore_applies_current_labels_without_calls(tmp_path):
    responses = {
        LANDER: answer(),
        "Craters within 10 km of Connecting ridge?": PROXIMITY_OK,
        BOULDERS: refusal(CITE_81, CITE_AUSSEL, CITE_CRATERS),  # extra citation: wrong under the label
    }
    es = eval_set()
    report = nl_eval.run_eval(FakeProvider(responses), es)
    path = nl_eval.write_results(report, tmp_path)
    assert {r["id"]: r for r in report["items"]}["r"]["reason_correct"] is False

    data = es.model_dump(mode="json")
    next(i for i in data["items"] if i["id"] == "r")["expected"]["citations_optional"].append(CITE_CRATERS)
    relabeled = _with_split(EvalSet.model_validate(data), "r", "holdout")
    re = nl_eval.rescore(path, relabeled)
    items = {r["id"]: r for r in re["items"]}
    assert items["r"]["reason_correct"] is True and items["r"]["split"] == "holdout"
    assert re["rescored_from"] == path.name and re["usage"] == report["usage"]
    out = nl_eval.write_results(re, tmp_path)
    assert "_rescored-" in out.name and out != path


def test_rescore_refuses_runs_from_another_schema(tmp_path):
    responses = {LANDER: answer(), BOULDERS: refusal(CITE_81, CITE_AUSSEL)}
    report = nl_eval.run_eval(FakeProvider(responses), eval_set())
    path = nl_eval.write_results({**report, "schema_version": "nl-output-3"}, tmp_path)
    with pytest.raises(ValueError, match="nl-output-3"):
        nl_eval.rescore(path, eval_set())
