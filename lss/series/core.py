"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Visibility time series and events for one scenario (docs/methodology.md section 5).

Each body (Sun, Earth) is sampled on a fine internal grid over the window (`SeriesParams.grid_step_s`,
independent of the scenario's `step`). Two continuous margins per sample (lss.series.disc.margins) decide
visibility: any part above the horizon, and the whole disc above it. Their sign changes between grid points
are refined by bisection to `root_tol_s`. The refined times split the window into periods that
tile it: visible / hidden (any part), and whole-disc-visible / not.

Time axis: seconds since `window_start` (UTC). Ephemeris time is et(window_start) + seconds. This assumes no
leap second inside the window (none is scheduled; section 2), and ignores the periodic TDB - UTC terms
(< 2 ms).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

import numpy as np

from lss.contract import BodyTrack, Event, EventKind, HorizonProfile, Scenario, SeriesResponse
from lss.ephem import MOON_RADIUS_M, topocentric, utc_to_et
from lss.horizon import Horizon, HorizonParams, cached_horizon
from lss.registry.terrain import LAYERS, LayerSpec, resolve
from lss.series.disc import margins, visible_fraction

SERIES_VERSION = 1
CHUNK = 20_000  # samples per vectorised block (memory)

# sample(t_s) -> (azimuth_deg, elevation_deg, angular_radius_deg), arrays like t_s
Sampler = Callable[[np.ndarray], tuple[np.ndarray, np.ndarray, np.ndarray]]


@dataclass(frozen=True)
class SeriesParams:
    grid_step_s: float = 60.0  # internal sampling for periods, events and time means (convergence: section 5)
    root_tol_s: float = 0.5  # event refinement tolerance

    def __post_init__(self):
        if not (self.grid_step_s > 0 and self.root_tol_s > 0):
            raise ValueError("grid_step_s and root_tol_s must be positive")


@dataclass(frozen=True)
class Period:
    start_s: float
    end_s: float
    clipped: bool  # touches a window edge, so it may continue outside the window

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


@dataclass(frozen=True)
class Grid:
    """Per-sample values of one body on the internal grid."""

    t_s: np.ndarray
    azimuth_deg: np.ndarray
    elevation_deg: np.ndarray
    radius_deg: np.ndarray
    horizon_deg: np.ndarray  # terrain horizon at the disc centre's azimuth
    fraction: np.ndarray  # visible fraction (Sun: light-weighted; Earth: area)

    @property
    def clearance_deg(self) -> np.ndarray:
        return self.elevation_deg - self.horizon_deg


@dataclass(frozen=True)
class BodyVisibility:
    grid: Grid
    visible: list[Period]  # any part visible (sunlit / Earth visible)
    hidden: list[Period]  # no part visible (shadow / Earth gap)
    full: list[Period]  # whole disc visible
    rises: list[float]  # refined times (s) of hidden -> visible
    sets: list[float]  # refined times (s) of visible -> hidden


@dataclass(frozen=True)
class SeriesResult:
    lat: float
    lon: float
    unit_height_m: float
    window_start: datetime
    window_end: datetime
    horizon: Horizon
    observer_height_m: float  # above the 1737.4 km sphere: DEM surface + unit height
    sun: BodyVisibility
    earth: BodyVisibility
    params: SeriesParams = field(default_factory=SeriesParams)
    scenario: Scenario | None = None  # None for internal runs the contract cannot express (0 m observer)
    layers: tuple[LayerSpec, ...] = LAYERS  # terrain layers the horizon was computed with

    @property
    def duration_s(self) -> float:
        return (self.window_end - self.window_start).total_seconds()


def _grid_times(duration_s: float, step_s: float) -> np.ndarray:
    n = int(np.ceil(duration_s / step_s - 1e-9)) + 1
    return np.linspace(0.0, duration_s, max(n, 2))


def _blocks(n: int):
    for i in range(0, n, CHUNK):
        yield slice(i, min(n, i + CHUNK))


def _periods(t: np.ndarray, state: np.ndarray, crossings: list[float], duration_s: float):
    """Split [0, duration] at the crossings; returns (periods in state True, periods in state False)."""
    bounds = [0.0, *crossings, duration_s]
    on, off = [], []
    s = bool(state[0])
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        if b > a:
            (on if s else off).append(Period(a, b, clipped=(a == 0.0 or b == duration_s)))
        s = not s
    return on, off


def _bisect(fn: Callable[[float], float], positive: Callable, a: float, b: float, tol: float) -> float:
    """Time in [a, b] where positive(fn) changes, to within tol; positive(fn(a)) != positive(fn(b))."""
    pa = bool(positive(np.array([fn(a)]))[0])
    while b - a > tol:
        mid = 0.5 * (a + b)
        if bool(positive(np.array([fn(mid)]))[0]) == pa:
            a = mid
        else:
            b = mid
    return 0.5 * (a + b)


def _refine(fn: Callable[[float], float], t: np.ndarray, m: np.ndarray, positive: Callable, tol: float):
    """Refined times where `positive(m)` changes between consecutive grid points."""
    state = positive(m)
    out = [
        _bisect(fn, positive, float(t[i]), float(t[i + 1]), tol)
        for i in np.flatnonzero(state[1:] != state[:-1])
    ]
    return out, state


def _fraction(horizon_at, az, el, r, limb_darkened, any_m=None, full_m=None):
    """Visible fraction: 1 / 0 where the margins say whole disc / no part visible, integrated in between."""
    if any_m is None:
        any_m, full_m = margins(horizon_at, az, el, r)
    frac = np.where(full_m >= 0, 1.0, 0.0)
    part = np.flatnonzero((any_m > 0) & (full_m < 0))
    for k in range(0, part.size, CHUNK):
        i = part[k : k + CHUNK]
        frac[i] = visible_fraction(horizon_at, az[i], el[i], r[i], limb_darkened)
    return frac


def body_visibility(
    sample: Sampler,
    horizon_at: Callable,
    duration_s: float,
    limb_darkened: bool,
    params: SeriesParams = SeriesParams(),
) -> BodyVisibility:
    """Visibility of one body over [0, duration_s] (seconds since window_start)."""
    t = _grid_times(duration_s, params.grid_step_s)
    az, el, r = (np.empty_like(t) for _ in range(3))
    any_m, full_m = np.empty_like(t), np.empty_like(t)
    for sl in _blocks(t.size):
        az[sl], el[sl], r[sl] = sample(t[sl])
        any_m[sl], full_m[sl] = margins(horizon_at, az[sl], el[sl], r[sl])
    # Integrated only for partly hidden discs: consistent with the periods, and most samples are 0 or 1.
    frac = _fraction(horizon_at, az, el, r, limb_darkened, any_m, full_m)
    hz = np.asarray(horizon_at(az), dtype=float)

    def margin(which: int) -> Callable[[float], float]:
        def f(s: float) -> float:
            a, e, rr = sample(np.array([s]))
            return float(margins(horizon_at, a, e, rr)[which][0])

        return f

    cross_any, vis = _refine(margin(0), t, any_m, lambda m: m > 0, params.root_tol_s)
    cross_full, full = _refine(margin(1), t, full_m, lambda m: m >= 0, params.root_tol_s)
    visible, hidden = _periods(t, vis, cross_any, duration_s)
    full_on, _ = _periods(t, full, cross_full, duration_s)
    rises = [c for c, i in zip(cross_any, np.flatnonzero(vis[1:] != vis[:-1]), strict=True) if vis[i + 1]]
    sets = [c for c, i in zip(cross_any, np.flatnonzero(vis[1:] != vis[:-1]), strict=True) if not vis[i + 1]]
    grid = Grid(t, az, el, r, hz, frac)
    return BodyVisibility(grid, visible, hidden, full_on, rises, sets)


def ephemeris_sampler(body: str, lat: float, lon: float, observer_height_m: float, window_start: datetime):
    et0 = float(utc_to_et(window_start)[0])

    def sample(t_s: np.ndarray):
        tp = topocentric(body, lat, lon, observer_height_m, et0 + np.asarray(t_s, dtype=float))
        return tp.azimuth_deg, tp.elevation_deg, tp.angular_radius_deg

    return sample


def compute_visibility(
    lat: float,
    lon: float,
    unit_height_m: float,
    window_start: datetime,
    window_end: datetime,
    params: SeriesParams = SeriesParams(),
    horizon_params: HorizonParams | None = None,
    layers: tuple[LayerSpec, ...] = LAYERS,
) -> SeriesResult:
    """Sun and Earth visibility at a site (horizon from the cache, or computed and cached).

    Accepts a 0 m observer, for the internal product 69 reproduction (methodology section 4.2); served
    results go through compute_series, whose Scenario requires a positive unit height.
    """
    hz = cached_horizon(lat, lon, unit_height_m, horizon_params, layers)
    observer_height_m = hz.observer_radius_m - MOON_RADIUS_M
    duration_s = (window_end - window_start).total_seconds()
    if duration_s <= 0:
        raise ValueError("window_end must be after window_start")
    bodies = {}
    for name, limb in (("SUN", True), ("EARTH", False)):
        sample = ephemeris_sampler(name, lat, lon, observer_height_m, window_start)
        bodies[name] = body_visibility(sample, hz.elevation_at, duration_s, limb, params)
    return SeriesResult(
        lat,
        lon,
        unit_height_m,
        window_start,
        window_end,
        hz,
        observer_height_m,
        bodies["SUN"],
        bodies["EARTH"],
        params,
        layers=layers,
    )


def compute_series(
    scenario: Scenario,
    params: SeriesParams = SeriesParams(),
    horizon_params: HorizonParams | None = None,
    layers: tuple[LayerSpec, ...] = LAYERS,
) -> SeriesResult:
    """compute_visibility for a contract Scenario."""
    loc = scenario.location
    res = compute_visibility(
        loc.lat,
        loc.lon,
        scenario.unit_height_m,
        scenario.window_start,
        scenario.window_end,
        params,
        horizon_params,
        layers,
    )
    return replace(res, scenario=scenario)


def events(result: SeriesResult) -> list[Event]:
    """Sunrise/sunset and Earthrise/Earthset inside the window, in time order (refined)."""
    start = result.window_start
    out = []
    for vis, rise, set_ in (
        (result.sun, EventKind.sunrise, EventKind.sunset),
        (result.earth, EventKind.earthrise, EventKind.earthset),
    ):
        out += [(s, rise) for s in vis.rises] + [(s, set_) for s in vis.sets]
    out.sort(key=lambda e: e[0])
    return [Event(kind=k, time=start + timedelta(seconds=s), refined=True) for s, k in out]


def series_response(result: SeriesResult) -> SeriesResponse:
    """Samples at the scenario's step (computed at those exact times, not interpolated)."""
    sc = result.scenario
    if sc is None:
        raise ValueError("series_response needs a contract Scenario (use compute_series)")
    step = sc.step.total_seconds()
    n = int(np.floor(result.duration_s / step + 1e-9)) + 1
    t_s = np.arange(n) * step
    hz = result.horizon
    loc = sc.location
    tracks = {}
    for name, limb in (("SUN", True), ("EARTH", False)):
        sample = ephemeris_sampler(name, loc.lat, loc.lon, result.observer_height_m, sc.window_start)
        az, el, r = sample(t_s)
        frac = _fraction(hz.elevation_at, az, el, r, limb)
        tracks[name] = BodyTrack(
            azimuth_deg=az.tolist(),
            elevation_deg=el.tolist(),
            visible_fraction=frac.tolist(),
            clearance_deg=(el - hz.elevation_at(az)).tolist(),
        )
    return SeriesResponse(
        scenario=sc,
        scenario_key=sc.key(),
        time=[sc.window_start + timedelta(seconds=float(s)) for s in t_s],
        sun=tracks["SUN"],
        earth=tracks["EARTH"],
        events=events(result),
    )


def horizon_response(result: SeriesResult) -> HorizonProfile:
    """The horizon the result was computed with, at full resolution (every computed azimuth), for the
    scenario's own location and unit height; terrain stack and fidelity from the resolver."""
    sc = result.scenario
    if sc is None:
        raise ValueError("horizon_response needs a contract Scenario (use compute_series)")
    hz = result.horizon
    stack = resolve(result.lat, result.lon, hz.params.max_range_m, result.layers)
    return HorizonProfile(
        location=sc.location,
        unit_height_m=sc.unit_height_m,
        azimuth_deg=hz.azimuth_deg.tolist(),
        elevation_deg=hz.elevation_deg.tolist(),
        max_range_km=hz.params.max_range_m / 1000.0,
        terrain_stack=stack.contract_layers(),
        fidelity=stack.fidelity(),
    )
