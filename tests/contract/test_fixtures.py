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


@pytest.mark.parametrize("name", sorted(set(EXAMPLES) - {"health.json", "datasets.json"}))
def test_examples_are_marked_placeholder(name):
    data = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    assert data["_placeholder"] is True
    assert "PLACEHOLDER" in data["_note"]


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
