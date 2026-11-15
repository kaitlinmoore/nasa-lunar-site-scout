"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Power (F3) and DTE comms (F4) metrics from a series (definitions: docs/methodology.md section 5).

Durations and fractions come from the refined periods (lss.series), so they are not limited by the grid step.
Time means (visible fraction, elevations, clearance) integrate the internal grid with the trapezoid rule.
"""

from __future__ import annotations

import numpy as np

from lss.contract import CommsMetrics, MetricsResponse, PowerMetrics, Stat
from lss.registry.terrain import resolve
from lss.series import Period, SeriesResult, events

H = 3600.0


def time_mean(t_s: np.ndarray, v: np.ndarray) -> float:
    """Time average over the grid's span (trapezoid rule)."""
    span = float(t_s[-1] - t_s[0])
    return float(np.sum(0.5 * (v[1:] + v[:-1]) * np.diff(t_s)) / span)


def stat(t_s: np.ndarray, v: np.ndarray) -> Stat:
    """min, max and time mean over the whole window."""
    return Stat(min=float(np.min(v)), max=float(np.max(v)), mean=time_mean(t_s, v))


def azimuth_arc(azimuth_deg: np.ndarray) -> Stat:
    """Smallest arc containing the (continuous) azimuth track; mean always None (methodology section 5.3).

    From the unwrapped track: a full circle if it spans 360 deg or more (min 0, max 360), otherwise its ends,
    modulo 360, read clockwise from min to max (min > max when the arc crosses north).
    """
    u = np.degrees(np.unwrap(np.radians(np.asarray(azimuth_deg, dtype=float))))
    lo, hi = float(u.min()), float(u.max())
    if hi - lo >= 360.0:
        return Stat(min=0.0, max=360.0, mean=None)
    return Stat(min=lo % 360.0, max=hi % 360.0, mean=None)


def total_h(periods: list[Period]) -> float:
    return sum(p.duration_s for p in periods) / H


def longest(periods: list[Period]) -> tuple[float, bool]:
    """(length h, clipped) of the longest period; (0, False) if there is none. Exact ties prefer clipped."""
    if not periods:
        return 0.0, False
    p = max(periods, key=lambda q: (q.duration_s, q.clipped))
    return p.duration_s / H, p.clipped


def overlap_s(a: list[Period], b: list[Period]) -> float:
    """Total time covered by both period lists (each list is disjoint and sorted)."""
    total, i, j = 0.0, 0, 0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i].start_s, b[j].start_s), min(a[i].end_s, b[j].end_s)
        total += max(0.0, hi - lo)
        if a[i].end_s < b[j].end_s:
            i += 1
        else:
            j += 1
    return total


def _first(times: list[float]) -> float | None:
    return times[0] / H if times else None


def power_metrics(res: SeriesResult) -> PowerMetrics:
    sun, T = res.sun, res.duration_s
    g = sun.grid
    shadow_h, shadow_clipped = longest(sun.hidden)
    return PowerMetrics(
        illumination_fraction=min(1.0, total_h(sun.visible) * H / T),
        mean_visible_disk_fraction=min(1.0, max(0.0, time_mean(g.t_s, g.fraction))),
        sunlit_duration_h=total_h(sun.visible),
        longest_sunlit_period_h=longest(sun.visible)[0],
        longest_shadow_h=shadow_h,
        longest_shadow_clipped=shadow_clipped,
        shadow_count=len(sun.hidden),
        sun_elevation_deg=stat(g.t_s, g.elevation_deg),
        sun_azimuth_deg=azimuth_arc(g.azimuth_deg),
        time_to_sunset_h=_first(sun.sets),
    )


def comms_metrics(res: SeriesResult) -> CommsMetrics:
    earth, T = res.earth, res.duration_s
    g = earth.grid
    gap_h, gap_clipped = longest(earth.hidden)
    return CommsMetrics(
        earth_visibility_fraction=min(1.0, total_h(earth.visible) * H / T),
        earth_full_disc_fraction=min(1.0, total_h(earth.full) * H / T),
        longest_earth_gap_h=gap_h,
        longest_earth_gap_clipped=gap_clipped,
        earth_elevation_deg=stat(g.t_s, g.elevation_deg),
        earth_clearance_deg=stat(g.t_s, g.clearance_deg),
        sun_earth_overlap_fraction=min(1.0, overlap_s(res.sun.visible, earth.visible) / T),
        time_to_earthset_h=_first(earth.sets),
    )


def metrics_response(res: SeriesResult) -> MetricsResponse:
    sc = res.scenario
    if sc is None:
        raise ValueError("metrics_response needs a contract Scenario (use lss.series.compute_series)")
    stack = resolve(res.lat, res.lon, res.horizon.params.max_range_m, res.layers)
    return MetricsResponse(
        scenario=sc,
        scenario_key=sc.key(),
        power=power_metrics(res),
        comms=comms_metrics(res),
        events=events(res),
        fidelity=stack.fidelity(),
    )
