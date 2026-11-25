# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""End to end on a synthetic DEM: terrain -> horizon -> visibility -> metrics.

A ring ridge around a real polar site (88 S) gives a horizon that is the same at every azimuth and known
analytically (h0, about 0.16 deg). The engine's whole path, the ray caster, the disc margins and their
refinement, the visible fractions and the metrics, runs on it with the real ephemeris over 120 days
(about four lunar days). The expected answer uses only the ephemeris and h0:

- any part of a disc is visible iff el + r > h0, and all of it iff el - r >= h0 (constant horizon);
- the Earth's visible fraction is the circular segment above a horizontal line;
- the Sun's is the limb-darkened segment, integrated by brute force on a fine 2-D grid.

Crossing times are compared within |horizon error| / elevation rate + 2 s: near the pole the Sun can graze
the horizon, where a small horizon error moves a crossing by many seconds.
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from test_horizon import R, make_grid

from lss.horizon import HorizonParams, Segment, compute_horizon, elevation_deg
from lss.metrics import comms_metrics, power_metrics
from lss.series import SeriesParams, SeriesResult, body_visibility, ephemeris_sampler
from lss.series.disc import limb_darkening

try:
    from lss.ephem import load_kernels, topocentric, utc_to_et

    load_kernels()
    HAVE_KERNELS = True
except Exception:  # noqa: BLE001 - any missing-kernel error means: skip
    HAVE_KERNELS = False

pytestmark = pytest.mark.skipif(not HAVE_KERNELS, reason="SPICE kernels missing (scripts/fetch_data.py)")

LAT, LON, POLE = -88.0, 60.0, "south"
H, D, W = 13.0, 3_000.0, 300.0  # ring ridge: height, distance, Gaussian width (m)
UNIT_H = 2.0
START = datetime(2028, 1, 1, tzinfo=UTC)
DAYS = 120
STEP = 60.0  # brute-force sampling (s)


def ridge(d):
    return H * np.exp(-(((d - D) / W) ** 2))


@pytest.fixture(scope="module")
def run():
    g = make_grid(LAT, LON, POLE, 5.0, 4_000.0, lambda d, az: ridge(d))
    hz = compute_horizon(LAT, LON, UNIT_H, [Segment(g, 0, 3_900)], HorizonParams(0.1, 0.5, 3_900))
    d = np.arange(1.0, 3_900.0, 0.25)
    h0 = float(elevation_deg(R + ridge(d), R + UNIT_H, d / R).max())
    T = DAYS * 86400.0
    params = SeriesParams()
    vis = {
        name: body_visibility(
            ephemeris_sampler(name, LAT, LON, UNIT_H, START), hz.elevation_at, T, limb, params
        )
        for name, limb in (("SUN", True), ("EARTH", False))
    }
    res = SeriesResult(
        LAT, LON, UNIT_H, START, START + timedelta(days=DAYS), hz, UNIT_H, vis["SUN"], vis["EARTH"], params
    )
    et0 = float(utc_to_et(START)[0])
    t = np.arange(0.0, T + 1.0, STEP)
    brute = {name: topocentric(name, LAT, LON, UNIT_H, et0 + t) for name in ("SUN", "EARTH")}
    return hz, h0, res, t, brute


def crossings(t, m):
    s = m > 0
    i = np.flatnonzero(s[1:] != s[:-1])
    return t[i] + (t[1] - t[0]) * m[i] / (m[i] - m[i + 1]), i


def test_horizon_is_the_analytic_ring_horizon(run):
    hz, h0, *_ = run
    assert 0.1 < h0 < 0.2
    assert np.abs(hz.elevation_deg - h0).max() < 1e-4


@pytest.mark.parametrize("body", ["SUN", "EARTH"])
def test_rises_and_sets_match_the_ephemeris(run, body):
    hz, h0, res, t, brute = run
    v = res.sun if body == "SUN" else res.earth
    tp = brute[body]
    want, i = crossings(t, tp.elevation_deg + tp.angular_radius_deg - h0)
    got = np.array(sorted(v.rises + v.sets))
    assert len(want) >= 6 and len(got) == len(want)  # several lunar days, each with a rise and a set
    rate = np.abs(np.gradient(tp.elevation_deg, STEP))[i]
    allowed = np.abs(hz.elevation_deg - h0).max() / rate + 2.0
    assert (np.abs(got - want) <= allowed).all()


@pytest.mark.parametrize("body", ["SUN", "EARTH"])
def test_any_part_and_whole_disc_fractions(run, body):
    _, h0, res, t, brute = run
    v, tp, T = (res.sun if body == "SUN" else res.earth), brute[body], res.duration_s
    any_part = (tp.elevation_deg + tp.angular_radius_deg > h0)[:-1].mean()
    whole = (tp.elevation_deg - tp.angular_radius_deg >= h0)[:-1].mean()
    tol = 4 * STEP / T * 8  # a few samples per crossing
    assert sum(p.duration_s for p in v.visible) / T == pytest.approx(any_part, abs=tol)
    assert sum(p.duration_s for p in v.full) / T == pytest.approx(whole, abs=tol)


def segment_fraction(u):
    """Area fraction of a unit disc above the horizontal line y = u."""
    u = np.clip(u, -1.0, 1.0)
    return (np.arccos(u) - u * np.sqrt(1.0 - u * u)) / np.pi


def test_earth_visible_fraction_is_the_circular_segment(run):
    _, h0, res, *_ = run
    g = res.earth.grid
    want = segment_fraction((h0 - g.elevation_deg) / g.radius_deg)
    partial = (want > 1e-6) & (want < 1 - 1e-6)
    assert partial.sum() > 100
    assert np.abs(g.fraction - want).max() < 1e-4


def test_sun_visible_fraction_is_the_limb_darkened_segment(run):
    _, h0, res, *_ = run
    g = res.sun.grid
    u = (h0 - g.elevation_deg) / g.radius_deg
    idx = np.flatnonzero(np.abs(u) < 0.95)[::40]  # a spread of partly hidden discs
    assert idx.size >= 10
    n = 1601
    x, y = np.meshgrid(np.linspace(-1, 1, n), np.linspace(-1, 1, n))
    inside = x * x + y * y < 1.0
    w = np.where(inside, limb_darkening(np.sqrt(np.clip(1.0 - x * x - y * y, 0.0, 1.0))), 0.0)
    for k in idx:
        want = w[y > u[k]].sum() / w.sum()
        assert g.fraction[k] == pytest.approx(want, abs=2e-3)  # grid integration error ~1/n


def test_metrics_follow_from_the_periods(run):
    _, h0, res, t, brute = run
    p, c = power_metrics(res), comms_metrics(res)
    sun, earth = brute["SUN"], brute["EARTH"]
    s = sun.elevation_deg + sun.angular_radius_deg > h0
    want_cross, _ = crossings(t, sun.elevation_deg + sun.angular_radius_deg - h0)
    bounds = np.concatenate([[0.0], want_cross, [t[-1]]])
    lengths = np.diff(bounds) / 3600.0
    hidden = lengths[0 if not s[0] else 1 :: 2]
    assert p.shadow_count == len(hidden)
    assert p.longest_shadow_h == pytest.approx(hidden.max(), abs=0.02)
    e = earth.elevation_deg + earth.angular_radius_deg > h0
    both = (s & e)[:-1].mean()
    assert c.sun_earth_overlap_fraction == pytest.approx(both, abs=3e-4)
    assert p.sun_elevation_deg.min == pytest.approx(sun.elevation_deg.min(), abs=1e-6)
