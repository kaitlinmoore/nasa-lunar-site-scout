# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Bodies high in the sky, up to the zenith (docs/methodology.md section 5.5, "High elevations, up to the
zenith").

lss.series.disc places a disc point at tangent-plane offsets (x horizontal, y vertical) at azimuth
az + x / cos(el) and elevation el + y. Here that is compared with the exact geometry on the celestial sphere,
computed without lss.series.disc: the disc is the cap of angular radius r around the centre direction, and
each point's azimuth and elevation are read from its unit vector in east-north-up.

Measured (2026-11-23): for a disc cut by the terrain horizon, the fraction error of the tangent-plane model is
about 0.1 x r x tan(el), r in radians, from 5 deg to 89 deg, for both the Sun (0.27 deg) and the Earth
(0.95 deg). A disc wholly above the terrain is exactly whole at any elevation, the zenith included. The
azimuth arc is right for tracks passing the zenith closer than one 60 s step.
"""

import numpy as np
import pytest

from lss.metrics.core import azimuth_arc
from lss.series import SeriesParams, body_visibility, limb_darkening, margins, visible_fraction
from lss.series.core import _fraction

SUN_R, EARTH_R = 0.27, 0.95  # deg, about the apparent radii seen from the Moon
BODIES = [("sun", SUN_R, True), ("earth", EARTH_R, False)]
SYNODIC_S = 29.530589 * 86400.0
SUN_RATE = 2.0 * np.pi / SYNODIC_S  # rad/s: the Sun's mean motion across the lunar sky


def law_tol(r_deg, el_deg, extra):
    """The measured error law of the tangent-plane model, with 20% headroom, plus quadrature or sampling
    error."""
    return 0.12 * np.radians(r_deg) * np.tan(np.radians(el_deg)) + extra


# ------------------------------------------------------------------ exact geometry on the sphere


def _frame(az_c, el_c):
    """Centre direction C and the sky tangent basis at it: e1 horizontal towards increasing azimuth, e2
    towards the zenith (ENU components)."""
    a, e = np.radians(az_c), np.radians(el_c)
    c = np.array([np.cos(e) * np.sin(a), np.cos(e) * np.cos(a), np.sin(e)])
    e1 = np.array([np.cos(a), -np.sin(a), 0.0])
    e2 = np.array([-np.sin(e) * np.sin(a), -np.sin(e) * np.cos(a), np.cos(e)])
    return c, e1, e2


def exact_points(az_c, el_c, r, limb, n=1601):
    """Points of the disc on the sphere (n x n tangent grid, mapped exactly) with their true azimuth (deg,
    0..360) and elevation (deg), and weights: sphere area x limb darkening (Sun) or area (Earth)."""
    g = (np.arange(n) + 0.5) / n * 2.0 - 1.0
    X, Y = np.meshgrid(g, g)
    m = X * X + Y * Y <= 1.0
    rr = np.radians(r)
    rho = np.hypot(X[m], Y[m]) * rr  # angular distance from the centre
    psi = np.arctan2(Y[m], X[m])
    c, e1, e2 = _frame(az_c, el_c)
    off = np.cos(psi)[:, None] * e1 + np.sin(psi)[:, None] * e2
    p = np.cos(rho)[:, None] * c + np.sin(rho)[:, None] * off
    el = np.degrees(np.arcsin(np.clip(p[:, 2], -1.0, 1.0)))
    az = np.degrees(np.arctan2(p[:, 0], p[:, 1])) % 360.0
    w = np.sinc(rho / np.pi)  # sin(rho) / rho: sphere area per unit of tangent grid
    if limb:
        w = w * limb_darkening(np.sqrt(np.clip(1.0 - (np.sin(rho) / np.sin(rr)) ** 2, 0.0, 1.0)))
    return az, el, w


def exact_rim(az_c, el_c, r, n=7200):
    """True azimuth and elevation (deg) of n points on the disc's rim."""
    psi = np.arange(n) * (2.0 * np.pi / n)
    c, e1, e2 = _frame(az_c, el_c)
    rr = np.radians(r)
    p = np.cos(rr) * c + np.sin(rr) * (np.cos(psi)[:, None] * e1 + np.sin(psi)[:, None] * e2)
    az = np.degrees(np.arctan2(p[:, 0], p[:, 1])) % 360.0
    return az, np.degrees(np.arcsin(np.clip(p[:, 2], -1.0, 1.0)))


def exact_fraction(horizon, az_c, el_c, r, limb, n=1601):
    az, el, w = exact_points(az_c, el_c, r, limb, n)
    return float(np.sum(w * (el > horizon(az))) / np.sum(w))


def exact_flat_fraction(level, el_c, r, limb, n=200_000):
    """Exact fraction above a flat horizon `level`, by rings: on the ring at angular distance rho from the
    centre, sin(el) = cos(rho) sin(el_c) + sin(rho) sin(psi) cos(el_c), so the share of the ring above the
    level is 1/2 - asin(s) / pi with s = (sin(level) - cos(rho) sin(el_c)) / (sin(rho) cos(el_c))."""
    rr, e = np.radians(r), np.radians(el_c)
    rho = (np.arange(n) + 0.5) / n * rr
    s = (np.sin(np.radians(level)) - np.cos(rho) * np.sin(e)) / (np.sin(rho) * np.cos(e))
    share = 0.5 - np.arcsin(np.clip(s, -1.0, 1.0)) / np.pi
    w = np.sin(rho)
    if limb:
        w = w * limb_darkening(np.sqrt(np.clip(1.0 - (np.sin(rho) / np.sin(rr)) ** 2, 0.0, 1.0)))
    return float(np.sum(w * share) / np.sum(w))


def flat(level):
    return lambda az: np.full(np.shape(az), level, dtype=float)


def rough(top, seed=5):
    """0.1 deg steps of uniform random height in [0, top] deg: a rough horizon, every azimuth different."""
    nodes = np.random.default_rng(seed).uniform(0.0, top, 3600)
    return lambda az: nodes[np.floor(np.asarray(az) / 0.1).astype(int) % 3600]


def jagged(base, amp=0.05, seed=1):
    """0.1 deg piecewise-linear profile around `base`, with a slow swing (like lss.horizon output)."""
    nodes = np.random.default_rng(seed).normal(0.0, amp, 3600)

    def h(az):
        u = np.asarray(az) / 0.1
        i = np.floor(u).astype(int) % 3600
        f = u - np.floor(u)
        return base + nodes[i] * (1 - f) + nodes[(i + 1) % 3600] * f + 0.2 * np.sin(np.radians(az) * 7.0)

    return h


def test_exact_flat_fraction_at_low_elevation_is_the_circular_segment():
    """The ring formula against the closed-form segment, where the tangent plane is exact enough (0.1 deg)."""
    for d in (-0.2, 0.0, 0.15):
        r = EARTH_R
        seg = (r * r * np.arccos(d / r) - d * np.sqrt(r * r - d * d)) / (np.pi * r * r)
        assert exact_flat_fraction(0.1 + d, 0.1, r, False) == pytest.approx(seg, abs=1e-5)


# ------------------------------------------------------------------ partly hidden discs


@pytest.mark.parametrize("el", [5.0, 10.0, 15.0, 20.0, 30.0, 45.0, 60.0, 75.0, 85.0, 89.0])
@pytest.mark.parametrize("body, r, limb", BODIES, ids=[b[0] for b in BODIES])
def test_flat_cut_against_the_exact_sphere(body, r, limb, el):
    for d in (-0.8, -0.4, 0.0, 0.4, 0.8):
        level = el + d * r
        got = visible_fraction(flat(level), 123.0, el, r, limb)[0]
        assert got == pytest.approx(exact_flat_fraction(level, el, r, limb), abs=law_tol(r, el, 2e-5)), d


@pytest.mark.parametrize("el", [5.0, 15.0, 30.0, 60.0, 85.0])
@pytest.mark.parametrize("body, r, limb", BODIES, ids=[b[0] for b in BODIES])
def test_jagged_cut_against_the_exact_sphere(body, r, limb, el):
    h = jagged(el)
    got = visible_fraction(h, 123.0, el, r, limb)[0]
    assert 0.05 < got < 0.95  # the horizon really cuts the disc
    assert got == pytest.approx(exact_fraction(h, 123.0, el, r, limb), abs=law_tol(r, el, 1e-4))


def test_served_range_bounds():
    """Partly hidden discs occur only where the body is within its radius of the terrain horizon. At the polar
    sites the Sun stays within about 6 deg of the horizontal and the Earth within about 11 deg; the highest
    Apollo horizon is 14.2 deg (Apollo 17). Up to 15 deg the error is at most 1.5e-4 (Sun), 5e-4 (Earth)."""
    for body, r, limb in BODIES:
        errors = [
            visible_fraction(flat(el + d * r), 0.0, el, r, limb)[0]
            - exact_flat_fraction(el + d * r, el, r, limb)
            for el in (6.0, 11.0, 15.0)
            for d in (-0.8, -0.4, 0.0, 0.4, 0.8)
        ]
        assert max(np.abs(errors)) < (1.5e-4 if body == "sun" else 5e-4), body


@pytest.mark.parametrize("el", [30.0, 60.0, 85.0, 89.0])
def test_margin_signs_against_the_exact_sphere(el):
    """Any part / whole disc decisions on sloped horizons through the disc; the margins' geometric error is at
    most about r^2 tan(el) / 2 (the almucantar's curvature across the disc)."""
    rng = np.random.default_rng(int(el))
    for _, r, _ in BODIES:
        curv = np.degrees(np.radians(r) ** 2 * np.tan(np.radians(el)) / 2.0)
        for _ in range(40):
            level, slope = el + rng.normal(0.0, r), rng.normal(0.0, 0.5) * np.cos(np.radians(el))

            def h(az, level=level, slope=slope):
                return level + slope * ((np.asarray(az) - 200.0 + 180.0) % 360.0 - 180.0)

            any_m, full_m = (v[0] for v in margins(h, 200.0, el, r))
            az, e = exact_rim(200.0, el, r)  # a near-planar cut: the extremes of el - h are on the rim
            rel = e - h(az)
            if abs(any_m) > curv + 2e-3:
                assert (any_m > 0) == (rel.max() > 0)
            if abs(full_m) > curv + 2e-3:
                assert (full_m >= 0) == (rel.min() >= 0)
        # a flat horizon: the margins are exact (the disc's top and bottom points are on its vertical)
        any_m, full_m = (v[0] for v in margins(flat(el), 200.0, el, r))
        assert any_m == pytest.approx(r, abs=1e-9) and full_m == pytest.approx(-r, abs=1e-9)


# ------------------------------------------------------------------ near the zenith


@pytest.mark.parametrize("el", [80.0, 89.0, 89.9, 89.99, 89.999, 90.0])
@pytest.mark.parametrize("body, r, limb", BODIES, ids=[b[0] for b in BODIES])
def test_near_the_zenith_a_disc_above_the_terrain_is_whole(body, r, limb, el):
    """Up to and at the zenith, a disc above the terrain is exactly whole, though az + x / cos(el) is far from
    the true azimuth there (above 89.73 deg the Sun's disc contains the zenith). Horizons up to 30 deg, about
    twice the highest served one (15.7 deg)."""
    h = rough(30.0)
    for az_c in (0.0, 137.0, 359.95):
        any_m, full_m = (v[0] for v in margins(h, az_c, el, r))
        assert any_m > 0 and full_m >= 0
        assert _fraction(h, np.array([az_c]), np.array([el]), np.array([r]), limb)[0] == 1.0
        assert visible_fraction(h, az_c, el, r, limb)[0] == pytest.approx(1.0, abs=1e-12)
        assert exact_fraction(h, az_c, el, r, limb, n=401) == pytest.approx(1.0, abs=1e-12)


def _pass(beta_deg, north: bool, t0=0.0):
    """A body crossing the sky east to west on a great circle at the Sun's mean rate, closest to the zenith
    (beta_deg away, to the north or the south) at t = t0. Returns sample(t_s) and arc(t1, t2), the closed-form
    azimuth arc of the track from t1 to t2: its azimuth is atan2(-sin s, +-cos s sin beta), s = rate (t - t0),
    and it turns through north (or south) only, so the arc runs between the azimuths at t1 and t2."""
    b = np.radians(beta_deg)
    sgn = 1.0 if north else -1.0
    a = np.array([0.0, sgn * np.sin(b), np.cos(b)])  # closest point (E, N, U)
    move = np.array([-1.0, 0.0, 0.0])  # towards the west

    def sample(t_s, r=SUN_R):
        s = (np.asarray(t_s, dtype=float) - t0) * SUN_RATE
        p = np.cos(s)[:, None] * a + np.sin(s)[:, None] * move
        az = np.degrees(np.arctan2(p[:, 0], p[:, 1])) % 360.0
        return az, np.degrees(np.arcsin(np.clip(p[:, 2], -1.0, 1.0))), np.full(s.shape, r)

    def arc(t1, t2):
        s1, s2 = (t1 - t0) * SUN_RATE, (t2 - t0) * SUN_RATE
        az1, az2 = (np.degrees(np.arctan2(-np.sin(x), sgn * np.cos(x) * np.sin(b))) % 360.0 for x in (s1, s2))
        return (az2, az1) if north else (az1, az2)  # north: azimuth falls through 0; south: rises through 180

    return sample, arc


@pytest.mark.parametrize("beta", [2.0, 0.1, 0.005, 1e-4])
@pytest.mark.parametrize("north", [True, False], ids=["north", "south"])
def test_azimuth_arc_through_a_near_zenith_pass(beta, north):
    """The azimuth arc unwraps the 60 s track (methodology section 5.3). Passing the zenith at 1e-4 deg, 85
    times closer than one 60 s step, the azimuth swings by almost 180 deg between two samples; it still turns
    the short way, so the arc is right."""
    half = 5 * 86400.0
    sample, arc_between = _pass(beta, north, t0=30.0)  # closest approach midway between two samples
    t = np.linspace(-half, half, int(2 * half / 60.0) + 1)
    az, el, _ = sample(t)
    assert el.max() > 90.0 - beta - 0.01
    swing = float(np.max(np.abs((np.diff(az) + 180.0) % 360.0 - 180.0)))
    if beta < 0.005:
        assert swing > 170.0  # the swing really happens within one step
    arc = azimuth_arc(az)
    assert (arc.min, arc.max) == pytest.approx(arc_between(-half, half), abs=1e-6)


def test_series_through_the_zenith_has_no_spurious_events():
    """End to end: ten days with the Sun passing 0.005 deg from the zenith, terrain horizon up to 20 deg. The
    Sun is always wholly visible (no events, one period, every fraction exactly 1); the arc is the closed
    form."""
    half = 5 * 86400.0
    sample, arc_between = _pass(0.005, north=True, t0=half + 30.0)
    v = body_visibility(sample, rough(20.0), 2 * half, limb_darkened=True, params=SeriesParams())
    assert v.rises == [] and v.sets == [] and v.hidden == [] and len(v.visible) == len(v.full) == 1
    assert np.all(v.grid.fraction == 1.0) and v.grid.elevation_deg.max() > 89.99
    arc = azimuth_arc(v.grid.azimuth_deg)
    assert (arc.min, arc.max) == pytest.approx(arc_between(0.0, 2 * half), abs=1e-6)
