# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""NL output schema + validation (step 4.3), checked against the committed fixtures."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

import pytest

from lss.config import FIXTURES_DIR
from lss.contract import NLAnswer, NLClarification, NLUnsupported, Operation, SitesQuery
from lss.nl.schema import fill_json_schema, llm_json_schema
from lss.nl.validate import NLValidationError, default_context, to_response, validate_output
from lss.nl.vocabulary import (
    ALLOWED_OPERATIONS,
    AROUND_RADIUS_TEXT,
    NEARBY_RADIUS_TEXT,
    OPERATION_PARAMS,
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
        "interpretation": "Power and Earth-visibility metrics for Connecting Ridge (Site01).",
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
    reason = resp.unsupported.reason
    assert "any boulder information at the poles" in reason  # registry fragment, inside one sentence
    assert reason.endswith(".") and not re.search(r"\.\s+[A-Z]", reason)  # one sentence (stream B)
    assert "can't answer:" not in reason  # no stitched "<dataset> can't answer: ..." parts


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
    assert PROXY_ASSUMPTION_TEXT[HeightSource(source)] in resp.assumptions


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
        "interpretation": "Power and Earth-visibility metrics for Connecting Ridge.",
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
    assert resp.assumptions[:2] == [
        "Window: 30 days from 2026-11-15 00:00 UTC (default; no dates were given).",
        PROXY_ASSUMPTION_TEXT[HeightSource.default],
    ]
    assert "Assumed:" not in resp.interpretation  # C8: disclosures have their own field now


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
        "interpretation": "Craters near Connecting Ridge.",
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
    assert NEARBY_RADIUS_TEXT in resp.assumptions


def test_safe_default_echo_names_the_terrain_data(ctx):
    validated = validate_output(search_output(), ctx)
    with pytest.raises(NLValidationError, match="slope_terrain"):
        to_response(validated, ctx)  # no terrain named: the echo can't be built
    resp = to_response(validated, ctx, slope_terrain="the PGDA 5 m south pole mosaic")
    assert resp.assumptions[0] == safe_slope_text("the PGDA 5 m south pole mosaic")
    assert "under 5°" in resp.assumptions[0]


def test_user_values_are_not_disclosed_as_defaults(ctx):
    resp = to_response(validate_output(search_output(slope=10.0, slope_source="user"), ctx), ctx)
    assert not any(a.startswith("Safe:") for a in resp.assumptions)
    resp = to_response(validate_output(proximity_output(2_000.0, "user"), ctx), ctx)
    assert NEARBY_RADIUS_TEXT not in resp.assumptions


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


# ------------------------------------------- contract 0.7.0: clarify, terrain, site_summary, areas


def test_clarification_becomes_the_contract_response(ctx):
    out = {
        "outcome": "clarify",
        "interpretation": "A summary of a site; none selected.",
        "question": "Which site?",
    }
    resp = to_response(validate_output(out, ctx), ctx)
    assert isinstance(resp, NLClarification)
    assert resp.question == "Which site?" and resp.interpretation.startswith("A summary")


@pytest.mark.parametrize(
    "out",
    [
        {"outcome": "clarify", "interpretation": "i"},  # no question
        {"outcome": "clarify", "interpretation": "i", "question": "Which?", "query": {"operation": "sites"}},
        {"outcome": "answer", "interpretation": "i", "question": "Which?", "query": {"operation": "sites"}},
    ],
)
def test_clarify_is_consistent(ctx, out):
    with pytest.raises(NLValidationError, match="schema"):
        validate_output(out, ctx)


def test_refusal_keeps_its_echo(ctx):
    resp = to_response(validate_output(fixture_unsupported_output(), ctx), ctx)
    assert isinstance(resp, NLUnsupported) and resp.interpretation


def fixture_unsupported_output() -> dict[str, Any]:
    return {
        "outcome": "unsupported",
        "interpretation": "Sites with no boulders >0.5 m in a 50 m ellipse.",
        "limitations": [
            {
                "topic": "Boulders",
                "citations": [
                    {
                        "dataset_id": "aussel_2025_boulders",
                        "cannot_answer": "Any boulder information at the poles",
                    }
                ],
            }
        ],
    }


def terrain_output(radius=1000.0, radius_source="around_default") -> dict[str, Any]:
    return {
        "outcome": "answer",
        "interpretation": "Slope at and around Connecting Ridge.",
        "query": {
            "operation": "terrain",
            "params": {"location": {"site_id": "pgda-site01"}, "radius_m": radius},
        },
        "radius_source": radius_source,
    }


def test_around_default_is_checked_and_disclosed(ctx):
    resp = to_response(validate_output(terrain_output(), ctx), ctx)
    assert resp.assumptions == [AROUND_RADIUS_TEXT]
    with pytest.raises(NLValidationError, match="around_default' requires radius = 1000"):
        validate_output(terrain_output(radius=10_000.0), ctx)


def test_site_summary_scenario_must_be_at_the_site(ctx):
    out = {
        "outcome": "answer",
        "interpretation": "Summary of Connecting Ridge.",
        "query": {
            "operation": "site_summary",
            "params": {
                "location": {"site_id": "pgda-site01"},
                "radius_m": 10_000.0,
                "scenario": {
                    "location": {"lat": -85.0, "lon": 30.0},
                    "unit_height_m": 2.0,
                    "window_start": "2028-05-15T00:00:00Z",
                    "window_end": "2028-06-14T00:00:00Z",
                },
            },
        },
        "radius_source": "nearby_default",
        "height_source": "user",
        "window_source": "user",
    }
    with pytest.raises(NLValidationError, match="scenario.location"):
        validate_output(out, ctx)
    out["query"]["params"]["scenario"]["location"] = {"site_id": "pgda-site01"}
    validate_output(out, ctx)


@pytest.mark.parametrize(
    "area",
    [
        {"kind": "circle", "center": {"site_id": "pgda-site01"}, "radius_m": 2000.0},
        {"kind": "cap", "pole": "south", "max_colatitude_deg": 6},
        {"kind": "all"},
    ],
)
def test_new_area_kinds_validate(ctx, area):
    out = search_output(slope=10.0, slope_source="user")
    out["query"]["params"]["area"] = area
    if area["kind"] == "circle":
        out["radius_source"] = "user"
    validate_output(out, ctx)


@pytest.mark.parametrize("op", sorted(ALLOWED_OPERATIONS, key=lambda o: o.value), ids=lambda o: o.value)
def test_every_fill_schema_builds_and_its_refs_resolve(op):
    schema = fill_json_schema(op)
    for ref in _refs(schema):
        assert ref.removeprefix("#/$defs/") in schema["$defs"], (op, ref)
    assert json.dumps(schema)


def test_sites_uses_the_contract_query_model():
    assert OPERATION_PARAMS[Operation.sites] is SitesQuery
    assert {Operation.terrain, Operation.site_summary} <= ALLOWED_OPERATIONS


# ------------------------------------- nl-output-6: disclosures come only from code (stream B, 2026-11-16)


def test_model_cannot_write_assumptions():
    from lss.nl.schema import NLFill, NLOutput

    assert "assumptions" not in NLFill.model_fields and "assumptions" not in NLOutput.model_fields
    assert "assumptions" not in json.dumps(fill_json_schema(Operation.terrain)["properties"])
    with pytest.raises(NLValidationError, match="schema"):
        validate_output({**terrain_output(), "assumptions": ["a working note"]}, default_context())


def test_selected_site_is_checked_and_disclosed_by_code():
    out = {**terrain_output(), "site_source": "selected_site"}
    with pytest.raises(NLValidationError, match="no site is selected"):
        validate_output(out, default_context())
    ctx = default_context(selected_site_id="pgda-site04")
    with pytest.raises(NLValidationError, match="selected site's id"):
        validate_output(out, ctx)  # params use pgda-site01, the selection is pgda-site04
    ctx = default_context(selected_site_id="pgda-site01")
    resp = to_response(validate_output(out, ctx), ctx)
    # The registry's short name (lss/registry/sites.yaml, approved by Kaitlin 2026-11-16).
    assert resp.assumptions[0] == "Using the selected site, Connecting Ridge."


# ------------------------------------------------ short display names (Kaitlin, 2026-11-16)


def _ctx_with_short_name(short="Connecting Ridge"):
    from dataclasses import replace

    base = default_context(selected_site_id="pgda-site01")
    sites = [
        s.model_copy(update={"short_name": short, "subtitle": "PGDA Site01 · Barker 2021 RoI 4"})
        if s.id == "pgda-site01"
        else s
        for s in base.sites
    ]
    return replace(base, sites=sites)


def test_model_sees_short_names_and_subtitles():
    from lss.nl.prompt import _context

    ctx = _ctx_with_short_name()
    entry = next(
        s for s in _context(ctx, date(2026, 11, 16), registry=False)["sites"] if s["site_id"] == "pgda-site01"
    )
    assert entry["name"] == "Connecting Ridge" and entry["subtitle"] == "PGDA Site01 · Barker 2021 RoI 4"
    from lss.contract import display_name

    plain = next(s for s in _context(default_context(), date(2026, 11, 16), registry=False)["sites"])
    assert plain["name"] == display_name(default_context().sites[0]) == "Connecting Ridge"  # the registry's


def test_selected_site_disclosure_uses_the_short_name():
    ctx = _ctx_with_short_name()
    out = {**terrain_output(), "site_source": "selected_site"}
    resp = to_response(validate_output(out, ctx), ctx)
    assert resp.assumptions[0] == "Using the selected site, Connecting Ridge."
    loc = resp.structured_query.params["location"]
    assert loc["name"] == "Site01 Connecting ridge (Barker 2021 RoI 4)"  # results keep the full name


def test_site_model_fields_are_optional():
    from lss.contract import Site, display_name

    s = default_context().sites[0].model_copy(update={"short_name": None, "subtitle": None})
    assert s.short_name is None and display_name(s) == s.name  # null short name: the full name
    assert (
        display_name(Site.model_validate({**s.model_dump(), "short_name": "Connecting Ridge"}))
        == "Connecting Ridge"
    )


# ------------------------------------------- C3: filters, rank, across (contract 0.10.0)


def ranking_output(**over) -> dict[str, Any]:
    params = {
        "across": {
            "unit_height_m": 5.0,
            "window_start": "2028-01-01T00:00:00Z",
            "window_end": "2029-01-01T00:00:00Z",
            "step": "PT6H",
        },
        "rank": {"metric": "power.illumination_fraction", "order": "desc", "limit": 3},
    }
    params.update(over.pop("params", {}))
    return {
        "outcome": "answer",
        "interpretation": "Top three sites by illumination.",
        "query": {"operation": "compare", "params": params},
        "height_source": "default",
        "window_source": "ranking_default",
        **over,
    }


def test_ranking_default_window_is_checked_and_disclosed():
    from lss.nl.vocabulary import RANKING_WINDOW_TEXT

    ctx = default_context()
    resp = to_response(validate_output(ranking_output(), ctx), ctx)
    assert RANKING_WINDOW_TEXT in resp.assumptions
    with pytest.raises(NLValidationError, match="only for rankings"):
        validate_output(ranking_output(params={"rank": None}), ctx)
    wrong = ranking_output()
    wrong["query"]["params"]["across"]["window_end"] = "2028-12-01T00:00:00Z"
    with pytest.raises(NLValidationError, match="ranking_default' requires"):
        validate_output(wrong, ctx)


def test_safe_slope_in_a_compare_filter_is_checked():
    ctx = default_context()

    def k6_like(limit):
        return {
            "outcome": "answer",
            "interpretation": "Safe sites without shadow.",
            "query": {
                "operation": "compare",
                "params": {
                    "across": {
                        "unit_height_m": 5.0,
                        "window_start": "2028-11-15T00:00:00Z",
                        "window_days": 10,
                    },
                    "filters": [{"metric": "terrain.slope_at_point_deg", "op": "lt", "value": limit}],
                },
            },
            "height_source": "default",
            "window_source": "user",
            "slope_source": "safe_default",
        }

    validate_output(k6_like(5.0), ctx)  # the window comes from window_days
    with pytest.raises(NLValidationError, match="safe_default' requires slope = 5"):
        validate_output(k6_like(6.0), ctx)


# ---------------------------- a selected scenario's values are filled in by code (B's G2 recheck, 2026-11-16)


def _year_10m():
    from lss.contract import Scenario

    site = default_context().sites[0]
    return Scenario(
        location=site.location,
        unit_height_m=10.0,
        window_start="2028-01-01T00:00:00Z",
        window_end="2029-01-01T00:00:00Z",
        step="PT6H",
    )


def test_selected_scenario_values_replace_the_models():
    sel = _year_10m()
    ctx = default_context(selected_site_id="pgda-site01", selected_scenario=sel)
    out = {
        "outcome": "answer",
        "interpretation": "Longest shadow here.",
        "query": {
            "operation": "metrics",
            "params": {
                "scenario": {  # step dropped, window end and height changed: what B saw once
                    "location": {"site_id": "pgda-site01"},
                    "unit_height_m": 5.0,
                    "window_start": "2028-01-01T00:00:00Z",
                    "window_end": "2028-12-31T00:00:00Z",
                }
            },
        },
        "height_source": "selected_scenario",
        "window_source": "selected_scenario",
        "site_source": "selected_site",
    }
    v = validate_output(out, ctx)
    sc = v.structured_query.params["scenario"]
    assert (sc["unit_height_m"], sc["window_start"], sc["window_end"], sc["step"]) == (
        10.0,
        "2028-01-01T00:00:00Z",
        "2029-01-01T00:00:00Z",
        "PT6H",
    )
    from lss.contract import Scenario

    assert Scenario.model_validate(sc).key() == sel.key()
    resp = to_response(v, ctx)
    assert "Height 10 m: from the selected scenario." in resp.assumptions
    assert (
        "Window: 1 Jan 2028 – 1 Jan 2029 UTC, every 6 hours, from the selected scenario." in resp.assumptions
    )


def test_only_the_selected_parts_are_filled():
    ctx = default_context(selected_site_id="pgda-site01", selected_scenario=_year_10m())
    out = {
        "outcome": "answer",
        "interpretation": "Metrics at 2 m over the selected window.",
        "query": {
            "operation": "metrics",
            "params": {
                "scenario": {
                    "location": {"site_id": "pgda-site01"},
                    "unit_height_m": 2.0,
                    "window_start": "2028-01-01T00:00:00Z",
                    "window_end": "2029-01-01T00:00:00Z",
                }
            },
        },
        "height_source": "user",  # the user asked for 2 m
        "window_source": "selected_scenario",
        "site_source": "selected_site",
    }
    sc = validate_output(out, ctx).structured_query.params["scenario"]
    assert sc["unit_height_m"] == 2.0 and sc["step"] == "PT6H"


def test_selected_scenario_source_without_a_selection_is_still_refused():
    out = {**metrics_output(), "height_source": "selected_scenario"}
    with pytest.raises(NLValidationError, match="no scenario is selected"):
        validate_output(out, default_context())


def test_step_text():
    from datetime import timedelta

    from lss.nl.vocabulary import step_text

    assert step_text(timedelta(hours=1)) == "every hour" and step_text(timedelta(hours=6)) == "every 6 hours"
    assert step_text(timedelta(minutes=30)) == "every 30 minutes"


def test_sun_band_answers_disclose_the_horizontal_not_the_terrain():
    """Fable G2 review m5: band elevations are above the local horizontal, terrain or not."""
    from lss.nl.vocabulary import SUN_BAND_TEXT

    band = {"min_deg": 10, "max_deg": 25}
    ctx = default_context()
    out = ranking_output(
        params={"filters": [{"metric": band, "op": "gt", "value": 0}], "rank": {"metric": band}}
    )
    resp = to_response(validate_output(out, ctx), ctx)
    assert SUN_BAND_TEXT in resp.assumptions and "whether or not terrain hides the Sun" in SUN_BAND_TEXT
    plain = to_response(validate_output(ranking_output(), ctx), ctx)  # ranks by illumination: no band
    assert SUN_BAND_TEXT not in plain.assumptions
