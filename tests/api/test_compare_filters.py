# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Filter, rank and the site template on POST /api/compare (contract 0.10.0, NL gap C3)."""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import lss.api.app as app_module
from lss.api import compare
from lss.config import get_settings
from lss.contract import (
    CompareAcross,
    CompareRank,
    CompareRequest,
    CompareResponse,
    InvalidRequestError,
    MetricFilter,
    MetricName,
    MetricsResponse,
    Scenario,
    SunElevationBand,
)
from lss.contract.examples import metrics as example_metrics
from lss.registry.sites import load_sites
from tests.api.test_thin_slice import REGRESSION, WEB_SCENARIO

NO_SLOPE = lambda lat, lon: None  # noqa: E731


def m_with(height: float, **power) -> MetricsResponse:
    """The example MetricsResponse at another unit height, with some power metrics replaced."""
    base = example_metrics()
    sc = base.scenario.model_copy(update={"unit_height_m": height})
    return base.model_copy(
        update={"scenario": sc, "scenario_key": sc.key(), "power": base.power.model_copy(update=power)}
    )


# ---------------------------------------------------------------------------------- pure rules


def test_value_of_reads_dotted_paths_slope_and_band():
    m = m_with(1.0, shadow_count=3)
    assert compare.value_of(MetricName.shadow_count, m, NO_SLOPE) == 3.0
    assert compare.value_of(MetricName.sun_elevation_max_deg, m, NO_SLOPE) == m.power.sun_elevation_deg.max
    assert (
        compare.value_of(MetricName.slope_at_point_deg, m, lambda lat, lon: (1.5, "5 m PGDA site map")) == 1.5
    )
    assert compare.value_of(SunElevationBand(min_deg=10, max_deg=25), m, NO_SLOPE) is None  # RA7 pending
    assert compare.value_of(MetricName.time_to_sunset_h, m_with(1.0, time_to_sunset_h=None), NO_SLOPE) is None


def test_filters_never_pass_a_null():
    served = [
        (0, m_with(1.0, shadow_count=0)),
        (1, m_with(2.0, shadow_count=2)),
        (2, m_with(5.0, shadow_count=None)),
    ]
    out = compare.apply(
        served, [MetricFilter(metric=MetricName.shadow_count, op="eq", value=0)], None, NO_SLOPE
    )
    assert [m.scenario.unit_height_m for m in out.items] == [1.0]
    by_index = {f.index: f for f in out.filtered_out}
    assert by_index[1].failed == ["power.shadow_count"] and by_index[1].not_computed == []
    assert by_index[2].not_computed == ["power.shadow_count"] and by_index[2].failed == []
    assert {e.value for e in out.evaluated} == {0.0, 2.0, None}


def test_rank_orders_marks_ties_and_cuts_at_the_limit():
    served = [
        (0, m_with(1.0, illumination_fraction=0.5)),
        (1, m_with(2.0, illumination_fraction=0.9)),
        (2, m_with(5.0, illumination_fraction=0.5)),
        (3, m_with(10.0, illumination_fraction=None)),
    ]
    rank = CompareRank(metric=MetricName.illumination_fraction, order="desc", limit=2)
    out = compare.apply(served, [], rank, NO_SLOPE)
    assert [m.scenario.unit_height_m for m in out.items] == [2.0, 1.0]  # tie 1 m / 5 m keeps compared order
    assert out.beyond_limit == 1
    assert out.rank_ties == [[served[0][1].scenario_key, served[2][1].scenario_key]]
    assert [f.index for f in out.filtered_out] == [3] and out.filtered_out[0].not_computed  # null excluded
    asc = compare.apply(
        served, [], CompareRank(metric=MetricName.illumination_fraction, order="asc"), NO_SLOPE
    )
    assert [m.scenario.unit_height_m for m in asc.items] == [1.0, 5.0, 2.0]


def test_all_failing_is_an_empty_answer_not_an_error():
    served = [(0, m_with(1.0, shadow_count=4))]
    out = compare.apply(
        served, [MetricFilter(metric=MetricName.shadow_count, op="eq", value=0)], None, NO_SLOPE
    )
    assert out.items == [] and len(out.filtered_out) == 1


def test_expand_by_ids_region_or_all():
    sites = [
        s.model_copy(update={"regions": ["shackleton"]}) if s.id == "pgda-site01" else s for s in load_sites()
    ]
    base = {"unit_height_m": 5.0, "window_start": datetime(2028, 11, 15, tzinfo=UTC), "window_days": 10}
    one = compare.expand(CompareAcross(site_ids=["pgda-site01"], **base), sites)
    assert len(one) == 1 and one[0].window_end == datetime(2028, 11, 25, tzinfo=UTC)
    assert [s.location for s in compare.expand(CompareAcross(region="shackleton", **base), sites)] == [
        sites[0].location
    ]
    assert len(compare.expand(CompareAcross(**base), sites)) == len(sites)
    with pytest.raises(compare.UnknownSitesError, match="nope"):
        compare.expand(CompareAcross(site_ids=["nope"], **base), sites)
    with pytest.raises(compare.UnknownSitesError, match="region"):
        compare.expand(CompareAcross(region="mars", **base), sites)


@pytest.mark.parametrize(
    "across",
    [
        {
            "site_ids": ["a"],
            "region": "r",
            "unit_height_m": 5,
            "window_start": "2028-01-01T00:00:00Z",
            "window_days": 1,
        },
        {"unit_height_m": 5, "window_start": "2028-01-01T00:00:00Z"},  # no end, no days
        {
            "unit_height_m": 5,
            "window_start": "2028-01-01T00:00:00Z",
            "window_end": "2028-01-02T00:00:00Z",
            "window_days": 1,
        },
    ],
)
def test_across_rejects_ambiguous_templates(across):
    with pytest.raises(ValidationError):
        CompareRequest.model_validate({"across": across})


def test_compare_needs_scenarios_or_across():
    with pytest.raises(ValidationError):
        CompareRequest.model_validate({})


def test_band_must_be_ordered():
    with pytest.raises(ValidationError):
        SunElevationBand(min_deg=25, max_deg=10)


# ---------------------------------------------------------------------------------- endpoint


def write_served_at(directory, height):
    """A served file from the regression fixture, moved to another unit height (keys recomputed)."""
    ref = json.loads(REGRESSION.read_text(encoding="utf-8"))
    sc = Scenario.model_validate(ref["metrics"]["scenario"]).model_copy(update={"unit_height_m": height})
    key = sc.key()
    scj = sc.model_dump(mode="json")
    from lss.contract import CONTRACT_VERSION

    data = {
        "format": 1,
        "scenario_key": key,
        "metrics": ref["metrics"]
        | {"contract_version": CONTRACT_VERSION, "scenario": scj, "scenario_key": key},
        "series": ref["series"]
        | {"contract_version": CONTRACT_VERSION, "scenario": scj, "scenario_key": key},
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"t_{key}.json").write_text(json.dumps(data), encoding="utf-8")
    return key


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path))
    for f in (get_settings, app_module._served, app_module._terrain):
        f.cache_clear()
    for h in (1.0, 2.0):
        write_served_at(tmp_path / "cache" / "served", h)
    yield TestClient(app_module.create_app())
    for f in (get_settings, app_module._served, app_module._terrain):
        f.cache_clear()


def across_site01(**kw):
    sc = WEB_SCENARIO
    return {
        "site_ids": ["pgda-site01"],
        "unit_height_m": kw.get("height", 1.0),
        "window_start": sc["window_start"],
        "window_end": sc["window_end"],
        "step": sc["step"],
    }


def test_across_expands_and_lists_what_was_compared(client):
    r = client.post("/api/compare", json={"across": across_site01()})
    assert r.status_code == 200
    body = CompareResponse.model_validate(r.json())
    assert len(body.items) == 1 and len(body.compared) == 1 and body.not_served == []


def test_filters_on_the_endpoint_and_an_empty_answer(client):
    sc2 = dict(WEB_SCENARIO, unit_height_m=2.0)
    req = {
        "scenarios": [WEB_SCENARIO, sc2],
        "filters": [{"metric": "power.shadow_count", "op": "lt", "value": 0}],  # nothing passes
    }
    r = client.post("/api/compare", json=req)
    assert r.status_code == 200
    body = CompareResponse.model_validate(r.json())
    assert (
        body.items == [] and len(body.filtered_out) == 2 and body.compared == []
    )  # no `across`: not repeated


def test_unknown_site_or_region_is_a_request_error(client):
    bad = dict(across_site01(), site_ids=["pgda-site99"])
    r = client.post("/api/compare", json={"across": bad})
    assert r.status_code == 422
    assert "pgda-site99" in InvalidRequestError.model_validate(r.json()).detail[0].msg
