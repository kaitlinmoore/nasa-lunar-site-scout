# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Every number in the four Mazarico sites' descriptions (lss/registry/sites.yaml; G2 review M3 and M2,
wording approved by Kaitlin 2026-11-16) against the data it comes from:

- 2028 results at 1, 2, 5 and 10 m: stream A's served files
  (LSS_DATA_DIR/cache/served/c3_<site>_<h>m_20280101_366d.json): `mean_visible_disk_fraction` ("of the Sun's
  disc in view on average", Table 3's quantity),
  `illumination_fraction` ("some of the Sun is in view"), `earth_visibility_fraction`, Sun elevation, horizon;
- the slope at the point: the site's 5 m map (lss.terrain.slope, methodology section 5.6);
- Mazarico's method on the 240 m map: stream A's validation fixture (tests/engine/fixtures/validation_c3.json,
  matched setting) and, for Site20's nearest grid points, scripts/mazarico_node.py's output.

Percentages are rounded half up to whole numbers, as written, from the exact values (not from one-decimal
displays). Tests skip where the data are not on this machine.
"""

import json
import math
from pathlib import Path

import pytest

from lss.config import get_settings
from lss.datafiles import BY_ID
from lss.registry.sites import load_sites, site_points

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "validation_c3.json").read_text(encoding="utf-8"))[
    "mazarico_table3"
]["emulated"]
RANK = {"pgda-site06": 6, "pgda-site20": 20, "pgda-site23": 23, "pgda-site42": 42}


def whole(percent: float) -> int:
    """A percentage rounded half up to a whole number, as the descriptions write it."""
    return math.floor(percent + 0.5)


def pct(fraction: float) -> int:
    return whole(100.0 * fraction)


def served(site_id: str, height_m: int) -> dict:
    p = get_settings().cache_dir / "served" / f"c3_{site_id}_{height_m}m_20280101_366d.json"
    if not p.is_file():
        pytest.skip(f"served file not on this machine: {p.name}")
    return json.loads(p.read_text(encoding="utf-8"))


def disc(site_id, h):
    return pct(served(site_id, h)["metrics"]["power"]["mean_visible_disk_fraction"])


def lit(site_id, h):
    return pct(served(site_id, h)["metrics"]["power"]["illumination_fraction"])


def earth(site_id, h):
    return pct(served(site_id, h)["metrics"]["comms"]["earth_visibility_fraction"])


def matched(rank: int, height: str) -> tuple[int, int]:
    """(ours, Table 3) for average illumination with the Mazarico-matched setting, from A's fixture."""
    row = next(r for r in FIXTURE[f"{height}_avg_ill_pct"]["rows"] if r["rank"] == rank)
    return whole(row["ours"]), whole(row["mazarico"])


def description(site_id: str) -> str:
    return next(s for s in load_sites() if s.id == site_id).description


# Expected sentence for each slope site, built from the data (the approved wording around the numbers).
SLOPE_SITES = {
    "pgda-site06": ("5 m and 10 m", lambda s: f"{disc(s, 5)}% at 5 m and {disc(s, 10)}% at 10 m", "close to"),
    "pgda-site23": (
        "2, 5 and 10 m",
        lambda s: f"{disc(s, 2)}% at 2 m and {disc(s, 5)}% at 5 m and 10 m",
        "close to",
    ),
    "pgda-site42": ("5 m and 10 m", lambda s: f"{disc(s, 5)}% at 5 m and {disc(s, 10)}% at 10 m", "against"),
}


@pytest.mark.parametrize("site_id", list(SLOPE_SITES))
def test_slope_sentence_numbers(site_id):
    _, rest, word = SLOPE_SITES[site_id]
    if site_id == "pgda-site23":
        assert disc(site_id, 5) == disc(site_id, 10)  # "82% at 5 m and 10 m"
    ours, theirs = matched(RANK[site_id], "10m")
    expected = (
        f"in 2028, at 1 m above the ground, {disc(site_id, 1)}% of the Sun's disc is in view on average "
        f"(some of the Sun is in view {lit(site_id, 1)}% of the time), rising to {rest(site_id)}. "
        "Mazarico's 240 m map is too coarse to show this slope; repeating their method on a 240 m map gives "
        f"{ours}% at 10 m, {word} their {theirs}%."
    )
    assert expected in description(site_id)


@pytest.mark.parametrize("site_id", list(SLOPE_SITES))
def test_sun_low_and_near_horizon_high_at_1m(site_id):
    """'The Sun never rises more than about 6°'; 'the slope beside the point hides it' (at 1 m, not 10 m)."""
    m1, m10 = served(site_id, 1), served(site_id, 10)
    assert round(m1["metrics"]["power"]["sun_elevation_deg"]["max"]) == 6
    assert "never rises more than about 6° above the horizon" in description(site_id)
    h1, h10 = max(m1["horizon"]["elevation_deg"]), max(m10["horizon"]["elevation_deg"])
    assert h1 > 5.0 and h10 < h1 - 2.0


@pytest.mark.parametrize("site_id, deg", [("pgda-site06", 8), ("pgda-site23", 7), ("pgda-site42", 7)])
def test_slope_at_the_point(site_id, deg):
    from lss.terrain.slope import slope_stats

    p = site_points()[site_id]
    tile = BY_ID[f"{p.tile.lower()}_dem"].path
    if not tile.is_file():
        pytest.skip(f"5 m map not on this machine: {tile.name}")
    s = slope_stats(tile, *p.ps_m, 100.0)
    assert math.floor(s.at_point_deg + 0.5) == deg
    article = "an" if deg == 8 else "a"
    assert f"On the 5 m map used here, the point is on {article} {deg}° slope." in description(site_id)


def test_site23_earth_sentence():
    pgda = [s.id for s in load_sites() if s.category == "pgda"]
    e10 = {sid: served(sid, 10)["metrics"]["comms"]["earth_visibility_fraction"] for sid in pgda}
    assert max(e10, key=e10.get) == "pgda-site23"
    expected = (
        f"The Earth is in view {earth('pgda-site23', 1)}% of 2028 at 1 m and {earth('pgda-site23', 10)}% at "
        "10 m, the most of the eight PGDA sites at that height."
    )
    assert len(pgda) == 8 and expected in description("pgda-site23")


def test_site20_sentences():
    sid = "pgda-site20"
    d = description(sid)
    ours0, theirs0 = matched(20, "0m")
    ours10, theirs10 = matched(20, "10m")
    assert (
        f"gives about {ours0}% of the Sun's disc in view at surface level ({ours10}% at 10 m), against their "
        f"{theirs0}% ({theirs10}%)." in d
    )
    expected = (
        f"On the 5 m map in 2028, {disc(sid, 1)}% of the Sun's disc is in view on average at 1 m above the "
        f"ground (some of the Sun is in view {lit(sid, 1)}% of the time) and {disc(sid, 10)}% at 10 m."
    )
    assert expected in d
    node = get_settings().cache_dir / "sites" / "mazarico_node_rank20.json"
    if not node.is_file():
        pytest.skip("scripts/mazarico_node.py output not on this machine")
    cands = [
        c
        for c in json.loads(node.read_text(encoding="utf-8"))["candidates"]
        if c["registration"] != "published"
    ]
    dists = sorted(round(c["distance_to_published_m"]) for c in cands)
    best = max(c["10m"]["avg_ill_pct"] for c in cands)  # percent
    assert (
        f"The two nearest points of a 240 m grid, {dists[0]} and {dists[1]} m away, do no better than " in d
    )
    assert f"{whole(best)}% at 10 m, so the published coordinate is kept." in d and len(dists) == 2


def test_rounding_is_half_up():
    assert [whole(51.5), whole(87.5), whole(82.49), pct(0.1374), pct(0.4659)] == [52, 88, 82, 14, 47]
