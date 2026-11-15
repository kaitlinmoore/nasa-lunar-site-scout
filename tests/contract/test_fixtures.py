# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Contract round-trip: every fixture validates against its model and re-serializes identically."""

import json

import pytest

from lss.config import FIXTURES_DIR
from lss.contract import CONTRACT_VERSION, Location, Scenario
from lss.contract.examples import EXAMPLES
from lss.contract.export import main as export_main


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_fixture_round_trip(name):
    _, model = EXAMPLES[name]
    data = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    parsed = model.model_validate(data)
    assert parsed.model_dump(mode="json", by_alias=True) == data
    assert data["contract_version"] == CONTRACT_VERSION


# Real (non-placeholder) fixtures: health, the registry, and the curated site list.
REAL_FIXTURES = {"health.json", "datasets.json", "sites.json"}


@pytest.mark.parametrize("name", sorted(set(EXAMPLES) - REAL_FIXTURES))
def test_examples_are_marked_placeholder(name):
    data = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    assert data["_placeholder"] is True
    assert "PLACEHOLDER" in data["_note"]


@pytest.mark.parametrize("name", sorted(REAL_FIXTURES))
def test_real_fixtures_not_placeholder(name):
    assert name in EXAMPLES, f"REAL_FIXTURES lists {name}, which is not an example"
    data = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    assert data["_placeholder"] is False
    assert "PLACEHOLDER" not in (data.get("_note") or "")


def test_fixtures_up_to_date():
    assert export_main(["--check"]) == 0, "run: uv run python -m lss.contract.export"


def test_scenario_key_is_stable_across_offsets_and_names():
    a = Scenario(
        location=Location(lat=-89.45, lon=-137.31, name="A"),
        unit_height_m=2,
        window_start="2028-11-15T00:00:00Z",
        window_end="2028-11-29T00:00:00Z",
    )
    b = Scenario(
        location=Location(lat=-89.45, lon=-137.31, name="B"),
        unit_height_m=2.0,
        window_start="2028-11-14T19:00:00-05:00",
        window_end="2028-11-29T00:00:00+00:00",
        step="PT1H",
    )
    assert a.key() == b.key()


def test_scenario_rejects_bad_window():
    with pytest.raises(ValueError):
        Scenario(
            location=Location(lat=0, lon=0),
            unit_height_m=2,
            window_start="2028-11-15T00:00:00Z",
            window_end="2028-11-14T00:00:00Z",
        )


# The C1 served scenario (precomputed; the endpoint matches requests on its key). Stream B sends exactly
# this scenario, so changing it is a cross-stream change: update the precomputed result and tell B.
C1_SCENARIO_KEY = "00010cfa5fef681c"


def test_c1_example_scenario_is_the_served_one():
    from lss.contract.examples import SCENARIO

    assert SCENARIO.key() == C1_SCENARIO_KEY
    for name in ("series.json", "metrics.json"):
        data = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
        assert Scenario.model_validate(data["scenario"]).key() == C1_SCENARIO_KEY
        assert data["scenario_key"] == C1_SCENARIO_KEY


def test_c1_key_matches_a_browser_request_and_depends_on_every_field():
    from lss.contract.examples import SCENARIO

    # As JSON.stringify writes it: 1.0 becomes 1; the site name may differ (it is not part of the key).
    sent = {
        "location": {"lat": -89.452675, "lon": -137.148653, "name": "anything"},
        "unit_height_m": 1,
        "window_start": "2028-05-15T00:00:00Z",
        "window_end": "2028-06-14T00:00:00Z",
        "step": "PT1H",
    }
    assert Scenario.model_validate(sent).key() == C1_SCENARIO_KEY
    changes = [
        {"location": {"lat": -89.45, "lon": -137.148653}},
        {"unit_height_m": 2},
        {"window_start": "2028-05-16T00:00:00Z"},
        {"window_end": "2028-06-13T00:00:00Z"},
        {"step": "PT6H"},
    ]
    for change in changes:
        assert Scenario.model_validate({**sent, **change}).key() != SCENARIO.key()


def test_every_metric_field_has_a_description():
    # Stream B shows these as on-screen definitions (read at build time from fixtures/openapi.json).
    from lss.contract import CommsMetrics, PowerMetrics
    from lss.contract.models import BodyTrack

    for model in (PowerMetrics, CommsMetrics, BodyTrack):
        for name, field in model.model_fields.items():
            assert field.description, f"{model.__name__}.{name} has no description"


def test_horizon_and_tracks_state_the_same_frame():
    # Stream B overlays the Sun/Earth tracks on the horizon profile: the alignment is stated, not assumed.
    from lss.contract.models import AZIMUTH_CONVENTION, ELEVATION_CONVENTION, BodyTrack, HorizonProfile

    for model in (BodyTrack, HorizonProfile):
        assert AZIMUTH_CONVENTION in model.model_fields["azimuth_deg"].description
        assert ELEVATION_CONVENTION in model.model_fields["elevation_deg"].description
