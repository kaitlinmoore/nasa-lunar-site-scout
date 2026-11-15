# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""lss.metrics: definitions of methodology section 5 on synthetic series with known answers, plus the served
C1 scenario on real data (kernels + DEMs)."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from test_series import block, brute, transit  # synthetic helpers (pytest puts tests/engine on sys.path)

from lss.contract.examples import SCENARIO
from lss.metrics import (
    azimuth_arc,
    comms_metrics,
    longest,
    metrics_response,
    overlap_s,
    power_metrics,
    time_mean,
)
from lss.registry.terrain import LAYERS
from lss.series import Period, SeriesParams, SeriesResult, body_visibility, compute_series, series_response

START = datetime(2028, 5, 15, tzinfo=UTC)


def synthetic_result(T_h=30.0, sun=None, earth=None):
    T = T_h * 3600.0
    s = sun or body_visibility(transit(10.0, 0.5, 0.25), block(), T, True)
    e = earth or body_visibility(transit(5.0, 2.0, 1.0, az0=60.0), block(100.0, 170.0, 4.0), T, False)
    return SeriesResult(-89.0, 0.0, 1.0, START, START + timedelta(seconds=T), None, 0.0, s, e, SeriesParams())


# ------------------------------------------------------------------ helpers


def test_azimuth_arc_cases():
    assert azimuth_arc(np.linspace(10, 50, 100)).model_dump() == {"min": 10.0, "max": 50.0, "mean": None}
    cross = azimuth_arc(np.r_[np.linspace(350, 359.9, 50), np.linspace(0, 20, 50)])
    assert (cross.min, cross.max, cross.mean) == (
        pytest.approx(350.0),
        pytest.approx(20.0),
        None,
    )  # min > max
    assert azimuth_arc(np.linspace(0, 720, 2000) % 360).model_dump() == {
        "min": 0.0,
        "max": 360.0,
        "mean": None,
    }
    wobble = azimuth_arc((30 + 15 * np.sin(np.linspace(0, 20, 500))) % 360)  # back and forth, no wrap
    assert (wobble.min, wobble.max) == (pytest.approx(15.0, abs=1e-3), pytest.approx(45.0, abs=1e-3))
    near_full = azimuth_arc(np.linspace(5, 355, 500))
    assert (near_full.min, near_full.max) == (5.0, 355.0)  # not a full circle


def test_longest_overlap_time_mean():
    assert longest([]) == (0.0, False)
    p = [Period(0, 3600, True), Period(7200, 18000, False), Period(20000, 30800, True)]
    assert longest(p) == (3.0, True)  # exact tie: the clipped one
    a = [Period(0, 100, True), Period(200, 300, False)]
    b = [Period(50, 250, False)]
    assert overlap_s(a, b) == 100.0
    t = np.linspace(0, 10, 11)
    assert time_mean(t, t) == pytest.approx(5.0)


# ------------------------------------------------------------------ metrics on synthetic series


def test_power_metrics_tile_the_window_and_follow_the_definitions():
    res = synthetic_result()
    pm = power_metrics(res)
    T_h = res.duration_s / 3600
    hidden = res.sun.hidden
    assert pm.shadow_count == len(hidden) == 1  # one passage behind the block
    assert pm.sunlit_duration_h + sum(p.duration_s for p in hidden) / 3600 == pytest.approx(T_h)
    assert pm.illumination_fraction == pytest.approx(pm.sunlit_duration_h / T_h)
    assert pm.longest_shadow_h == pytest.approx(hidden[0].duration_s / 3600)
    assert pm.longest_shadow_clipped is False
    assert pm.time_to_sunset_h == pytest.approx(res.sun.sets[0] / 3600)
    # light-weighted mean < illumination fraction (partial discs during rise/set count less than 1)
    assert 0 < pm.mean_visible_disk_fraction < pm.illumination_fraction
    assert pm.sun_elevation_deg.model_dump() == pytest.approx({"min": 0.5, "max": 0.5, "mean": 0.5})
    assert pm.sun_azimuth_deg.model_dump() == {"min": 0.0, "max": 300.0, "mean": None}  # 10 deg/h for 30 h


def test_clipped_flags_when_the_window_starts_in_shadow():
    T = 12 * 3600.0
    sun = body_visibility(transit(10.0, 0.5, 0.25, az0=120.0), block(), T, True)  # starts behind the block
    earth = body_visibility(transit(10.0, 0.5, 0.25, az0=120.0), block(), T, False)
    res = synthetic_result(12.0, sun, earth)
    pm, cm = power_metrics(res), comms_metrics(res)
    assert pm.longest_shadow_clipped is True and cm.longest_earth_gap_clipped is True
    assert pm.time_to_sunset_h is None  # the Sun rises in the window but never sets
    assert pm.shadow_count == 1


def test_comms_metrics():
    res = synthetic_result()
    cm = comms_metrics(res)
    T = res.duration_s
    e = res.earth
    assert cm.earth_visibility_fraction == pytest.approx(sum(p.duration_s for p in e.visible) / T)
    assert cm.earth_full_disc_fraction < cm.earth_visibility_fraction
    assert cm.longest_earth_gap_h == pytest.approx(max(p.duration_s for p in e.hidden) / 3600)
    assert cm.earth_clearance_deg.max == pytest.approx(2.0 + 1.0)  # el 2 over a -1 deg horizon
    assert cm.earth_clearance_deg.min == pytest.approx(2.0 - 4.0)
    assert cm.sun_earth_overlap_fraction == pytest.approx(overlap_s(res.sun.visible, e.visible) / T)


# ------------------------------------------------------------------ the served scenario (real data)

try:
    from lss.ephem import load_kernels

    load_kernels()
    HAVE_KERNELS = True
except Exception:  # noqa: BLE001 - any missing-kernel error means: skip
    HAVE_KERNELS = False
HAVE_DATA = HAVE_KERNELS and all(spec.dem().path.is_file() for spec in LAYERS)
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="kernels/DEMs not downloaded (scripts/fetch_data.py)")


@pytest.fixture(scope="module")
def served():
    return compute_series(SCENARIO)


@needs_data
def test_served_scenario_responses(served):
    m, s = metrics_response(served), series_response(served)
    assert m.scenario_key == s.scenario_key == SCENARIO.key()
    assert m.placeholder is False and s.placeholder is False
    assert len(s.time) == 721 and s.time[0] == SCENARIO.window_start and s.time[-1] == SCENARIO.window_end
    assert m.fidelity is not None and m.fidelity.near_field_resolution_m == 5
    kinds = [e.kind.value for e in m.events]
    assert kinds.count("sunset") == m.power.shadow_count  # no shadow is clipped in this window
    assert all(e.refined for e in m.events)
    p = m.power
    assert p.sunlit_duration_h + sum(q.duration_s for q in served.sun.hidden) / 3600 == pytest.approx(720.0)


@needs_data
def test_served_fraction_agrees_with_brute_force_on_the_real_horizon(served):
    g, hz = served.sun.grid, served.horizon
    partial = np.flatnonzero((g.fraction > 0.02) & (g.fraction < 0.98))
    assert partial.size > 20
    for i in partial[:: max(1, partial.size // 12)]:
        ref = brute(hz.elevation_at, g.azimuth_deg[i], g.elevation_deg[i], g.radius_deg[i], True, n=801)
        assert g.fraction[i] == pytest.approx(ref, abs=2e-3)


@needs_data
def test_served_metrics_do_not_depend_on_the_grid_step(served):
    fine = compute_series(SCENARIO, SeriesParams(grid_step_s=15.0))
    a, b = power_metrics(served), power_metrics(fine)
    assert a.shadow_count == b.shadow_count
    assert a.longest_shadow_h == pytest.approx(b.longest_shadow_h, abs=1e-3)
    assert a.illumination_fraction == pytest.approx(b.illumination_fraction, abs=1e-6)
    assert a.mean_visible_disk_fraction == pytest.approx(b.mean_visible_disk_fraction, abs=1e-4)
    c, d = comms_metrics(served), comms_metrics(fine)
    assert c.earth_visibility_fraction == pytest.approx(d.earth_visibility_fraction, abs=1e-6)
    assert c.longest_earth_gap_h == pytest.approx(d.longest_earth_gap_h, abs=1e-3)
