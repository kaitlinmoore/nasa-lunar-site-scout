# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""NL output schema + validation (step 4.3), checked against the committed fixtures."""

from __future__ import annotations

import json
from typing import Any

import pytest

from lss.config import FIXTURES_DIR
from lss.contract import NLAnswer, NLUnsupported, Operation
from lss.nl.schema import llm_json_schema
from lss.nl.validate import NLValidationError, default_context, to_response, validate_output
from lss.nl.vocabulary import ALLOWED_OPERATIONS, PROXY_ASSUMPTION_TEXT, HeightSource


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def ctx():
    return default_context()


def metrics_output(**overrides: Any) -> dict[str, Any]:
    """LLM output equivalent to fixtures/nl_answer.json, with Site01 referenced by id."""
    scenario = fixture("nl_answer.json")["structured_query"]["params"]["scenario"]
    out = {
        "outcome": "answer",
        "interpretation": "Power and Earth-visibility metrics for Connecting ridge (Site01).",
        "query": {
            "operation": "metrics",
            "params": {"scenario": {**scenario, "location": {"site_id": "pgda-site01"}}},
        },
        "height_source": "user",
    }
    out.update(overrides)
    return out


BOULDERS = {
    "outcome": "unsupported",
    "interpretation": "Candidate sites with no boulders >0.5 m in a 50 m landing ellipse.",
    "limitations": [
        {
            "topic": "Boulders larger than 0.5 m within a 50 m landing ellipse",
            "citations": [
                {
                    "dataset_id": "pgda_81_mosaic_5m",
                    "cannot_answer": "Hazards smaller than a few pixels (e.g. sub-meter boulders)",
                },
                {
                    "dataset_id": "aussel_2025_boulders",
                    "cannot_answer": "Any boulder information at the poles",
                },
            ],
        }
    ],
}


# ------------------------------------------------------------------ schema


def _refs(node: Any) -> list[str]:
    if isinstance(node, dict):
        out = [node["$ref"]] if "$ref" in node else []
        return out + [r for v in node.values() for r in _refs(v)]
    if isinstance(node, list):
        return [r for v in node for r in _refs(v)]
    return []


def test_llm_schema_has_one_variant_per_allowed_operation():
    schema = llm_json_schema()
    variants = schema["properties"]["query"]["anyOf"]
    ops = {v["properties"]["operation"]["const"] for v in variants if v.get("type") == "object"}
    assert ops == {op.value for op in ALLOWED_OPERATIONS}
    assert {"type": "null"} in variants


def test_llm_schema_refs_resolve_and_locations_accept_site_ids():
    schema = llm_json_schema()
    defs = schema["$defs"]
    for ref in _refs(schema):
        assert ref.startswith("#/$defs/") and ref.removeprefix("#/$defs/") in defs, ref
    assert {"$ref": "#/$defs/SiteRef"} in defs["Location"]["anyOf"]
    json.dumps(schema)  # serializable


def test_vocabulary_excludes_operations_not_in_core():
    assert Operation.features not in ALLOWED_OPERATIONS


# ------------------------------------------------------- fixtures round trip


def test_metrics_answer_matches_fixture(ctx):
    validated = validate_output(metrics_output(), ctx)
    resp = to_response(validated, ctx)
    assert isinstance(resp, NLAnswer)
    assert resp.structured_query.model_dump(mode="json") == fixture("nl_answer.json")["structured_query"]
    assert resp.result is None  # the engine fills it, never the LLM
    NLAnswer.model_validate(resp.model_dump(mode="json", by_alias=True))


def test_site_id_is_replaced_by_catalog_location(ctx):
    out = metrics_output()
    out["query"]["params"]["scenario"]["location"] = {"site_id": "pgda-site01"}
    sq = validate_output(out, ctx).structured_query
    site = next(s for s in ctx.sites if s.id == "pgda-site01")
    assert sq.params["scenario"]["location"] == site.location.model_dump(mode="json")


def test_boulder_refusal_matches_fixture_datasets(ctx):
    resp = to_response(validate_output(BOULDERS, ctx), ctx)
    assert isinstance(resp, NLUnsupported)
    expected = fixture("nl_unsupported.json")["unsupported"]["datasets_considered"]
    assert resp.unsupported.datasets_considered == expected
    assert "Any boulder information at the poles" in resp.unsupported.reason


def test_partial_answer_carries_limitations(ctx):
    out = metrics_output(outcome="partial", limitations=BOULDERS["limitations"])
    resp = to_response(validate_output(out, ctx), ctx)
    assert isinstance(resp, NLAnswer)
    assert [lim.datasets_considered for lim in resp.limitations] == [
        ["pgda_81_mosaic_5m", "aussel_2025_boulders"]
    ]


# ------------------------------------------------------------ unit heights


@pytest.mark.parametrize(("source", "height"), [("rover_proxy", 1.0), ("lander_proxy", 5.0)])
def test_proxy_heights_are_disclosed(ctx, source, height):
    out = metrics_output(height_source=source)
    out["query"]["params"]["scenario"]["unit_height_m"] = height
    resp = to_response(validate_output(out, ctx), ctx)
    assert PROXY_ASSUMPTION_TEXT[HeightSource(source)] in resp.interpretation


def test_proxy_height_must_match_proxy_value(ctx):
    out = metrics_output(height_source="lander_proxy")  # fixture height is 1 m
    with pytest.raises(NLValidationError, match="lander_proxy"):
        validate_output(out, ctx)


def test_selected_scenario_height_needs_a_selection(ctx):
    with pytest.raises(NLValidationError, match="no scenario is selected"):
        validate_output(metrics_output(height_source="selected_scenario"), ctx)


def test_height_source_not_applicable_rejects_a_height(ctx):
    with pytest.raises(NLValidationError, match="not_applicable"):
        validate_output(metrics_output(height_source="not_applicable"), ctx)


# --------------------------------------------------------------- rejections


def _mutate(path: list[Any], value: Any) -> dict[str, Any]:
    out = metrics_output()
    node = out
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return out


@pytest.mark.parametrize(
    ("raw", "problem"),
    [
        ("not json", "not JSON"),
        ({**metrics_output(), "extra": 1}, "schema"),
        ({**metrics_output(), "outcome": "unsupported"}, "schema"),
        ({**metrics_output(), "outcome": "partial"}, "schema"),
        ({**BOULDERS, "outcome": "answer"}, "schema"),
        (_mutate(["query", "operation"], "features"), "not in the Core NL vocabulary"),
        (_mutate(["query", "operation"], "thermal"), "schema"),
        (_mutate(["query", "params", "scenario", "window_end"], "2028-11-01T00:00:00Z"), "window_end"),
        (_mutate(["query", "params", "scenario", "window_start"], "2028-11-15T00:00:00"), "params"),
        (_mutate(["query", "params", "scenario", "colour"], "red"), "params"),
        (_mutate(["query", "params", "scenario", "location"], {"site_id": "nope"}), "unknown site_id"),
        (_mutate(["query", "params", "scenario", "location"], {"lat": -95, "lon": 0}), "params"),
    ],
)
def test_rejects_what_the_contract_would_not_accept(ctx, raw, problem):
    with pytest.raises(NLValidationError, match=problem):
        validate_output(raw, ctx)


def test_rejects_citations_not_in_registry(ctx):
    bad = json.loads(json.dumps(BOULDERS))
    bad["limitations"][0]["citations"][1]["cannot_answer"] = "Boulders anywhere"
    with pytest.raises(NLValidationError, match="not a cannot_answer entry"):
        validate_output(bad, ctx)
    bad["limitations"][0]["citations"][1]["dataset_id"] = "made_up"
    with pytest.raises(NLValidationError, match="unknown dataset_id"):
        validate_output(bad, ctx)


def test_custom_coordinates_pass_through(ctx):
    out = {
        "outcome": "answer",
        "interpretation": "Terrain data and fidelity at 85 S, 30 E.",
        "query": {"operation": "locate", "params": {"lat": -85.0, "lon": 30.0}},
    }
    sq = validate_output(out, ctx).structured_query
    assert sq.params == {"lat": -85.0, "lon": 30.0}


def test_sites_query_validates_category(ctx):
    ok = {
        "outcome": "answer",
        "interpretation": "Apollo sites.",
        "query": {"operation": "sites", "params": {"category": "apollo"}},
    }
    assert validate_output(ok, ctx).structured_query.params == {"category": "apollo"}
    ok["query"]["params"]["category"] = "mars"
    with pytest.raises(NLValidationError, match="params"):
        validate_output(ok, ctx)
