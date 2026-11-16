# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Every contract version in COMPATIBLE_VERSIONS has the current result format (lss.api.served_format).

Each listed version needs a snapshot in tests/api/served_formats/<version>.json, made from that version's
committed fixtures/openapi.json (commands in lss/api/served_format.py). When a version is dropped from
COMPATIBLE_VERSIONS (e.g. once stream A has regenerated its served files), delete its snapshot too.
"""

import json
from pathlib import Path

import pytest

from lss.api.served import COMPATIBLE_VERSIONS
from lss.api.served_format import SERVED_MODELS, result_format
from lss.config import FIXTURES_DIR

SNAPSHOTS = Path(__file__).with_name("served_formats")
CURRENT = result_format(json.loads((FIXTURES_DIR / "openapi.json").read_text(encoding="utf-8")))


def test_one_snapshot_per_compatible_version():
    assert {p.stem for p in SNAPSHOTS.glob("*.json")} == set(COMPATIBLE_VERSIONS)


@pytest.mark.parametrize("version", sorted(COMPATIBLE_VERSIONS))
def test_compatible_version_has_the_current_result_format(version):
    old = json.loads((SNAPSHOTS / f"{version}.json").read_text(encoding="utf-8"))
    assert old["contract_version"] == version
    assert old["schemas"].keys() == CURRENT["schemas"].keys(), "different models referenced"
    for name, schema in CURRENT["schemas"].items():
        assert old["schemas"][name] == schema, f"{name} changed since {version}: drop {version}"


def test_format_covers_the_served_bodies_and_what_they_reference():
    assert set(SERVED_MODELS) <= CURRENT["schemas"].keys()
    assert {"Scenario", "BodyTrack", "PowerMetrics", "CommsMetrics", "TerrainLayer"} <= CURRENT[
        "schemas"
    ].keys()


def test_format_ignores_wording_but_not_structure():
    doc = json.loads((FIXTURES_DIR / "openapi.json").read_text(encoding="utf-8"))
    reworded = json.loads(json.dumps(doc))
    reworded["components"]["schemas"]["PowerMetrics"]["properties"]["shadow_count"]["description"] = "x"
    assert result_format(reworded) == CURRENT
    restructured = json.loads(json.dumps(doc))
    restructured["components"]["schemas"]["PowerMetrics"]["properties"]["new_metric"] = {"type": "number"}
    assert result_format(restructured) != CURRENT
    new_default = json.loads(json.dumps(doc))
    assert new_default["components"]["schemas"]["Scenario"]["properties"]["step"]["default"] == "PT1H"
    new_default["components"]["schemas"]["Scenario"]["properties"]["step"]["default"] = "PT6H"
    assert result_format(new_default) != CURRENT
