# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""NL output schema + validation (step 4.3), checked against the committed fixtures."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest

from lss.config import FIXTURES_DIR
from lss.contract import NLAnswer, NLUnsupported, Operation
from lss.nl.schema import llm_json_schema
from lss.nl.validate import NLValidationError, default_context, to_response, validate_output
from lss.nl.vocabulary import (
    ALLOWED_OPERATIONS,
    NEARBY_RADIUS_TEXT,
    PROXY_ASSUMPTION_TEXT,
    HeightSource,
    safe_slope_text,
)


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
        "window_source": "user",
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
        (_mutate(["query", "params", "scenario", "window_end"], "2020-01-01T00:00:00Z"), "window_end"),
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


# ------------------------------------------------- defaults (D-height, D-window)


def default_output(start="2026-11-15T00:00:00Z", end="2026-12-15T00:00:00Z", height=5.0):
    return {
        "outcome": "answer",
        "interpretation": "Power and Earth-visibility metrics for Connecting ridge.",
        "query": {
            "operation": "metrics",
            "params": {
                "scenario": {
                    "location": {"site_id": "pgda-site01"},
                    "unit_height_m": height,
                    "window_start": start,
                    "window_end": end,
                }
            },
        },
        "height_source": "default",
        "window_source": "default",
    }


def test_defaults_are_checked_and_disclosed():
    ctx = default_context(today=date(2026, 11, 15))
    resp = to_response(validate_output(default_output(), ctx), ctx)
    assert "Window: 30 days from 2026-11-15 00:00 UTC (default; no dates were given)." in resp.interpretation
    assert PROXY_ASSUMPTION_TEXT[HeightSource.default] in resp.interpretation


@pytest.mark.parametrize(
    ("kwargs", "problem"),
    [
        ({"end": "2026-11-29T00:00:00Z"}, "30-day window"),
        ({"start": "2026-11-16T00:00:00Z", "end": "2026-12-16T00:00:00Z"}, "request's date"),
        ({"height": 2.0}, "requires unit_height_m = 5.0"),
    ],
)
def test_defaults_must_be_exact(kwargs, problem):
    with pytest.raises(NLValidationError, match=problem):
        validate_output(default_output(**kwargs), default_context(today=date(2026, 11, 15)))


def test_window_source_needed_when_params_have_a_window(ctx):
    out = metrics_output()
    del out["window_source"]
    with pytest.raises(NLValidationError, match="window_source is 'not_applicable'"):
        validate_output(out, ctx)


# ------------------------------------------------- defaults (D-safe, D-radius)


def proximity_output(radius=10_000.0, radius_source="nearby_default") -> dict[str, Any]:
    return {
        "outcome": "answer",
        "interpretation": "Craters near Connecting ridge.",
        "query": {
            "operation": "proximity",
            "params": {"location": {"site_id": "pgda-site01"}, "types": ["crater"], "radius_m": radius},
        },
        "radius_source": radius_source,
    }


def search_output(slope=5.0, slope_source="safe_default") -> dict[str, Any]:
    return {
        "outcome": "answer",
        "interpretation": "Safe terrain at 85 S, 30 E.",
        "query": {
            "operation": "search",
            "params": {
                "area": {"kind": "points", "points": [{"lat": -85.0, "lon": 30.0}]},
                "criteria": {"max_slope_deg": slope},
            },
        },
        "slope_source": slope_source,
    }


def test_nearby_default_is_checked_and_disclosed(ctx):
    resp = to_response(validate_output(proximity_output(), ctx), ctx)
    assert NEARBY_RADIUS_TEXT in resp.interpretation


def test_safe_default_echo_names_the_terrain_data(ctx):
    validated = validate_output(search_output(), ctx)
    with pytest.raises(NLValidationError, match="slope_terrain"):
        to_response(validated, ctx)  # no terrain named: the echo can't be built
    resp = to_response(validated, ctx, slope_terrain="the PGDA 5 m south pole mosaic")
    assert safe_slope_text("the PGDA 5 m south pole mosaic") in resp.interpretation
    assert "under 5°" in resp.interpretation


def test_user_values_are_not_disclosed_as_defaults(ctx):
    resp = to_response(validate_output(search_output(slope=10.0, slope_source="user"), ctx), ctx)
    assert "Safe:" not in resp.interpretation
    resp = to_response(validate_output(proximity_output(2_000.0, "user"), ctx), ctx)
    assert NEARBY_RADIUS_TEXT not in resp.interpretation


@pytest.mark.parametrize(
    ("raw", "problem"),
    [
        (search_output(slope=10.0), "requires slope = 5"),
        (search_output(slope_source="not_applicable"), "slope_source is 'not_applicable'"),
        (proximity_output(radius=5_000.0), "requires radius = 10000"),
        (proximity_output(radius_source="not_applicable"), "radius_source is 'not_applicable'"),
        ({**BOULDERS, "slope_source": "safe_default"}, "slope_source is set but there is no query"),
    ],
)
def test_slope_and_radius_sources_must_match_params(ctx, raw, problem):
    with pytest.raises(NLValidationError, match=problem):
        validate_output(raw, ctx)
