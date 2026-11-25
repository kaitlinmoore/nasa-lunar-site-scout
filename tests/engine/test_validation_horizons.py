# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Validation: lss.ephem topocentric Sun and Earth az/el at the served site vs JPL Horizons.

Reference values: tests/engine/fixtures/horizons_site01_roi4.json, fetched by scripts/horizons_check.py
(Horizons DE441, MEAN_ME frame, apparent az/el). Tolerance and reasons: docs/methodology.md section 6.1.
Needs the SPICE kernels (skipped otherwise).
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from lss.contract.examples import SCENARIO
from lss.datafiles import get as datafile
from lss.ephem import core as ephem

FIXTURE = Path(__file__).parent / "fixtures" / "horizons_site01_roi4.json"
# A second site far from the pole at an eastern longitude (methodology 6.1, second correctness review):
# Site06, 85.3S 37E.
FIXTURE_SITE06 = Path(__file__).parent / "fixtures" / "horizons_pgda-site06.json"
TOL_ARCSEC = 1.0  # on the angular separation; measured agreement is ~0.05 arcsec

needs_kernels = pytest.mark.skipif(
    not all(datafile(k).path.is_file() for k in ephem.KERNEL_IDS),
    reason="SPICE kernels missing: uv run python scripts/fetch_data.py kernels",
)
REF = json.loads(FIXTURE.read_text(encoding="utf-8"))
REF06 = json.loads(FIXTURE_SITE06.read_text(encoding="utf-8"))


def test_fixture_is_the_served_site():
    s, loc = REF["site"], SCENARIO.location
    assert s["lat_deg"] == pytest.approx(loc.lat, abs=1e-6)
    assert s["east_lon_deg"] == pytest.approx(loc.lon % 360.0, abs=1e-6)
    assert s["altitude_m"] == pytest.approx(1957.39, abs=0.01)  # 5 m DEM surface + 1 m
    for body in ("SUN", "EARTH"):
        h = REF["bodies"][body]["header"]
        assert "MEAN_ME" in h["Center pole/equ"] and "1737.4, 1737.4, 1737.4" in h["Center radii"]
        assert len(REF["bodies"][body]["rows"]) == 25


def separation_deg(az1, el1, az2, el2):
    a1, e1, a2, e2 = map(np.radians, (az1, el1, az2, el2))
    c = np.sin(e1) * np.sin(e2) + np.cos(e1) * np.cos(e2) * np.cos(a1 - a2)
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def test_site06_fixture_is_the_served_point():
    from lss.registry.sites import get_site

    loc, s = get_site("pgda-site06").location, REF06["site"]
    assert REF06["site_id"] == "pgda-site06"
    assert s["lat_deg"] == pytest.approx(loc.lat, abs=1e-9) and s["east_lon_deg"] == pytest.approx(
        loc.lon % 360.0
    )
    for body in ("SUN", "EARTH"):
        assert "MEAN_ME" in REF06["bodies"][body]["header"]["Center pole/equ"]
        assert len(REF06["bodies"][body]["rows"]) == 25


@needs_kernels
@pytest.mark.parametrize("ref", [REF, REF06], ids=["site01", "site06"])
@pytest.mark.parametrize("body", ["SUN", "EARTH"])
def test_topocentric_az_el_matches_horizons(body, ref):
    s, rows = ref["site"], ref["bodies"][body]["rows"]
    t = [datetime.fromisoformat(r["utc"].replace("Z", "+00:00")) for r in rows]
    tp = ephem.topocentric(body, s["lat_deg"], s["east_lon_deg"] - 360.0, s["altitude_m"], ephem.utc_to_et(t))
    az = np.array([r["azimuth_deg"] for r in rows])
    el = np.array([r["elevation_deg"] for r in rows])
    sep = separation_deg(tp.azimuth_deg, tp.elevation_deg, az, el) * 3600.0
    assert sep.max() < TOL_ARCSEC
    assert np.abs(tp.elevation_deg - el).max() * 3600.0 < TOL_ARCSEC
    daz = (tp.azimuth_deg - az + 180.0) % 360.0 - 180.0  # near the pole azimuth error is not a separation
    assert np.abs(daz).max() * 3600.0 < TOL_ARCSEC
    km = np.array([r["distance_au"] for r in rows]) * 149_597_870.7
    assert np.abs(tp.distance_km - km).max() < 1.0  # sets the light time and the angular radius
