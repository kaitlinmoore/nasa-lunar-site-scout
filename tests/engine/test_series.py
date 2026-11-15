# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""lss.series: limb-darkening law, disc fractions against horizons, periods and events.

Disc fractions are checked against closed-form circular segments and against a brute-force 2-D integration
over the disc that shares no code with the column integrals in lss.series.disc. Events are checked on
synthetic tracks whose rise and set times are known in closed form.
"""

import numpy as np
import pytest

from lss.series import (
    LIMB_U2,
    LIMB_V2,
    SeriesParams,
    body_visibility,
    limb_darkened_disc_mean,
    limb_darkening,
    margins,
    visible_fraction,
)
from lss.series.core import _grid_times


def brute(horizon_at, az_c, el_c, r, limb, n=1201):
    """Visible fraction by direct 2-D integration on an n x n grid over the disc's bounding square."""
    g = (np.arange(n) + 0.5) / n * 2.0 - 1.0
    X, Y = np.meshgrid(g, g)
    inside = X * X + Y * Y <= 1.0
    x, y = X[inside] * r, Y[inside] * r
    w = (
        limb_darkening(np.sqrt(np.clip(1.0 - (x * x + y * y) / (r * r), 0.0, 1.0)))
        if limb
        else np.ones_like(x)
    )
    vis = el_c + y > horizon_at(np.mod(az_c + x / np.cos(np.radians(el_c)), 360.0))
    return float(np.sum(w * vis) / np.sum(w))


def flat(level):
    return lambda az: np.full(np.shape(az), level, dtype=float)


def segment_fraction(d, r):
    """Area fraction of a disc above a horizontal line at height d relative to the centre (closed form)."""
    d = np.clip(d, -r, r)
    return (r * r * np.arccos(d / r) - d * np.sqrt(r * r - d * d)) / (np.pi * r * r)


# ------------------------------------------------------------------ limb-darkening law


def test_limb_darkening_law_is_one_at_disc_centre():
    assert limb_darkening(1.0) == pytest.approx(1.0, abs=1e-15)


def test_limb_darkening_constants_and_limb():
    assert (LIMB_U2, LIMB_V2) == (0.93, -0.23)  # Allen (1973) section 81, row 0.55 um
    assert limb_darkening(0.0) == pytest.approx(0.30)  # limb / centre
    mu = np.linspace(0.0, 1.0, 101)
    assert np.all(np.diff(limb_darkening(mu)) > 0)  # brighter towards the centre


def test_limb_darkened_disc_mean_matches_integration():
    # mean over the disc area of I(mu), mu = sqrt(1 - rho^2): 2 * int_0^1 I(sqrt(1 - rho^2)) rho drho
    rho = np.linspace(0.0, 1.0, 200_001)
    v = limb_darkening(np.sqrt(1.0 - rho * rho)) * rho
    numeric = 2.0 * np.sum(0.5 * (v[1:] + v[:-1]) * np.diff(rho))
    assert limb_darkened_disc_mean() == pytest.approx(numeric, abs=1e-8)
    assert limb_darkened_disc_mean() == pytest.approx(0.805, abs=1e-12)  # Allen's table: 0.803 (rounded)


# ------------------------------------------------------------------ disc fractions


@pytest.mark.parametrize("limb", [False, True])
def test_fraction_limits_and_half(limb):
    r, el = 0.27, 1.0
    assert visible_fraction(flat(el - 1.0), 50.0, el, r, limb)[0] == 1.0
    assert visible_fraction(flat(el + 1.0), 50.0, el, r, limb)[0] == 0.0
    assert visible_fraction(flat(el), 50.0, el, r, limb)[0] == pytest.approx(0.5, abs=1e-12)  # symmetry


@pytest.mark.parametrize("d", [-0.25, -0.12, -0.03, 0.05, 0.2, 0.26])
def test_geometric_fraction_matches_circular_segment(d):
    r, el = 0.27, 0.6
    got = visible_fraction(flat(el + d), 200.0, el, r, limb_darkened=False)[0]
    assert got == pytest.approx(segment_fraction(d, r), abs=1e-5)


@pytest.mark.parametrize("d", [-0.2, -0.05, 0.1, 0.24])
def test_limb_darkened_fraction_matches_brute_force(d):
    r, el = 0.27, 0.6
    got = visible_fraction(flat(el + d), 10.0, el, r, limb_darkened=True)[0]
    assert got == pytest.approx(brute(flat(el + d), 10.0, el, r, True), abs=5e-4)
    # light-weighted differs from area-weighted for an off-centre cut (the limb is darker)
    geo = segment_fraction(d, r)
    # a cap near the limb holds less light than area: visible cap (d > 0): got < geo; hidden: got > geo
    assert (got - geo) * d < 0


@pytest.mark.parametrize("limb", [False, True])
def test_fraction_against_a_sloped_jagged_horizon(limb):
    """Horizon varying across the disc (the real-profile cut, not a flat line), incl. az = x / cos(el)."""
    rng = np.random.default_rng(3)
    nodes = rng.normal(0.0, 0.15, 3600)

    def horizon(az):  # 0.1 deg piecewise-linear profile, like lss.horizon
        u = np.asarray(az) / 0.1
        i = np.floor(u).astype(int) % 3600
        f = u - np.floor(u)
        return 2.0 + nodes[i] * (1 - f) + nodes[(i + 1) % 3600] * f + 0.3 * np.sin(np.radians(az) * 40.0)

    for az_c in (12.34, 181.0, 359.9):  # incl. a disc straddling north
        el = float(horizon(az_c)) + 0.05
        got = visible_fraction(horizon, az_c, el, 0.27, limb)[0]
        assert got == pytest.approx(brute(horizon, az_c, el, 0.27, limb), abs=1e-3)


def test_margins_signs_match_brute_force():
    rng = np.random.default_rng(7)
    for _ in range(200):
        level, slope = rng.normal(0.0, 0.3), rng.normal(0.0, 0.5)
        el, r, az_c = rng.normal(0.0, 0.3), 0.27, rng.uniform(0, 360)

        def horizon(az, level=level, slope=slope, az_c=az_c):
            dx = (np.asarray(az) - az_c + 180.0) % 360.0 - 180.0
            return level + slope * dx

        any_m, full_m = margins(horizon, az_c, el, r)
        f = brute(horizon, az_c, el, r, False, n=401)
        if abs(any_m[0]) > 2e-3:
            assert (any_m[0] > 0) == (f > 0)
        if abs(full_m[0]) > 2e-3:
            assert (full_m[0] >= 0) == (f == 1.0)


# ------------------------------------------------------------------ periods and events


def transit(rate_deg_h=10.0, el=0.5, r=0.25, az0=0.0):
    """Body at constant elevation moving in azimuth at a constant rate (synthetic track)."""

    def sample(t_s):
        t = np.asarray(t_s, dtype=float)
        return (az0 + rate_deg_h * t / 3600.0) % 360.0, np.full(t.shape, el), np.full(t.shape, r)

    return sample


def block(lo=90.0, hi=180.0, inside=1.0, outside=-1.0):
    """Horizon of `inside` deg for azimuths in [lo, hi), `outside` elsewhere: the body hides in the block."""

    def h(az):
        a = np.asarray(az)
        return np.where((a >= lo) & (a < hi), inside, outside)

    return h


def test_rise_and_set_times_are_refined_exactly():
    el, r, rate = 0.5, 0.25, 10.0
    half = r / np.cos(np.radians(el))  # half-width of the disc in azimuth
    T = 30 * 3600.0
    v = body_visibility(transit(rate, el, r), block(), T, limb_darkened=False)
    # hidden only while the whole disc is inside the block: centre az in [90 + half, 180 - half]
    assert len(v.sets) == len(v.rises) == 1
    assert v.sets[0] == pytest.approx((90.0 + half) / rate * 3600.0, abs=1.0)
    assert v.rises[0] == pytest.approx((180.0 - half) / rate * 3600.0, abs=1.0)
    (shadow,) = v.hidden
    assert not shadow.clipped
    assert shadow.start_s == v.sets[0] and shadow.end_s == v.rises[0]
    # whole disc visible only while the disc is entirely outside the block
    assert v.full[0].end_s == pytest.approx((90.0 - half) / rate * 3600.0, abs=1.0)
    assert v.full[1].start_s == pytest.approx((180.0 + half) / rate * 3600.0, abs=1.0)


def test_periods_tile_the_window_and_edge_periods_are_clipped():
    T = 30 * 3600.0
    v = body_visibility(transit(az0=120.0), block(), T, limb_darkened=True)  # starts hidden
    periods = sorted(v.visible + v.hidden, key=lambda p: p.start_s)
    assert periods[0].start_s == 0.0 and periods[-1].end_s == T
    assert all(a.end_s == b.start_s for a, b in zip(periods, periods[1:], strict=False))
    assert v.hidden[0].start_s == 0.0 and v.hidden[0].clipped  # began before the window
    assert periods[-1].clipped
    assert not any(p.clipped for p in periods[1:-1])
    assert v.rises[0] < min(v.sets, default=np.inf)  # the first event is a rise


def test_grid_step_does_not_change_refined_events():
    T = 20 * 3600.0
    a = body_visibility(transit(), block(), T, False, SeriesParams(grid_step_s=60.0))
    b = body_visibility(transit(), block(), T, False, SeriesParams(grid_step_s=7.0))
    assert a.sets[0] == pytest.approx(b.sets[0], abs=1.0)
    assert a.rises[0] == pytest.approx(b.rises[0], abs=1.0)


def test_short_flicker_is_counted_as_a_shadow():
    """A notch of high horizon just wider than the disc hides all of it for 0.1 deg of travel (36 s)."""
    el, r, rate = 0.5, 0.25, 10.0
    half = r / np.cos(np.radians(el))
    notch = (200.0, 200.0 + 2 * half + 0.1)  # the whole disc fits for 0.1 deg of travel = 36 s
    v = body_visibility(
        transit(rate, el, r), block(*notch), 30 * 3600.0, False, SeriesParams(grid_step_s=10.0)
    )
    assert len(v.hidden) == 1
    assert v.hidden[0].duration_s == pytest.approx(0.1 / rate * 3600.0, abs=1.5)


def test_grid_times_cover_the_window():
    t = _grid_times(100.0, 30.0)
    assert t[0] == 0.0 and t[-1] == 100.0 and np.all(np.diff(t) <= 30.0 + 1e-12)


def test_series_params_validated():
    with pytest.raises(ValueError):
        SeriesParams(grid_step_s=0.0)
