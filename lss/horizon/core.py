"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Terrain horizon by ray casting (plan sections 3.2 and 4.2; docs/methodology.md section 3).

Geometry (exact on the 1737.4 km reference sphere, no small-angle approximation):
- The observer is on the sphere normal at the site, at radius r_o = R + surface height + unit height.
  The surface height comes from the finest terrain layer (the near field).
- The ray at azimuth A (clockwise from north) is the great circle leaving the site in direction A:
  the unit vector at angular distance theta is p = cos(theta) up + sin(theta) (cos A north + sin A east).
  Its arc length on the reference sphere, d = R theta, is the "ray distance" that sets which terrain layer
  is used.
- A terrain sample at height h (radius r = R + h) is seen at elevation
      tan(el) = (r cos(theta) - r_o) / (r sin(theta)),
  measured from the observer's local horizontal plane. For small theta this is the plan's
  atan((dh - d^2 / 2R) / d) with dh = r - r_o. The exact form is used because the approximation is
  off by ~0.005 deg at short range (it uses R where the geometry has R + h) and ~0.03 deg for terrain
  400 km away (tested).
- The horizon at azimuth A is the maximum elevation over the ray samples, from `min_range_m` to the
  maximum range. Heights are bilinear between pixel centres (lss.terrain). The spacing at distance d is
      min(sample_factor x pixel size of the layer in use, relative_step x d):
  uniform far out, geometric close to the observer. Close in, elevation changes with distance like 1/d,
  so pixel-based spacing alone misses near-field peaks (0.19 deg at Site01 with 2.5 m spacing at
  ~18 m; docs/methodology.md section 3).
- Each ray distance has a designated layer (lss.registry.terrain.resolve). Where that layer has no data,
  the next coarser layer of the stack is used; samples no layer covers are counted as missing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numba import njit, prange
from numba.typed import List

from lss.ephem.core import enu_basis
from lss.registry.terrain import LAYERS, MAX_RANGE_M, LayerSpec, TerrainStack, resolve
from lss.terrain.core import MOON_RADIUS_M, Grid, ps_from_latlon

# Bump when the algorithm changes in a way that changes results (part of the cache key).
HORIZON_VERSION = 1


class HorizonUnavailable(ValueError):
    """No horizon can be computed here (no terrain covers the location, or rays have no data)."""


@dataclass(frozen=True)
class HorizonParams:
    """Numerical settings. Defaults are set by the convergence study (docs/methodology.md section 3)."""

    azimuth_step_deg: float = 0.1
    sample_factor: float = 0.5  # max ray sample spacing, as a fraction of the pixel size of the layer in use
    max_range_m: float = MAX_RANGE_M
    relative_step: float = 0.002  # max ray sample spacing, as a fraction of the distance from the site
    min_range_m: float = 1.0  # first ray sample

    def __post_init__(self) -> None:
        n = 360.0 / self.azimuth_step_deg
        if not (self.azimuth_step_deg > 0 and abs(n - round(n)) < 1e-9):
            raise ValueError("azimuth_step_deg must divide 360")
        if not self.sample_factor > 0:
            raise ValueError("sample_factor must be > 0")
        if not self.max_range_m > 0:
            raise ValueError("max_range_m must be > 0")
        if not self.relative_step > 0:
            raise ValueError("relative_step must be > 0")
        if not 0 < self.min_range_m < self.max_range_m:
            raise ValueError("min_range_m must be > 0 and below max_range_m")

    @property
    def n_azimuths(self) -> int:
        return round(360.0 / self.azimuth_step_deg)


@dataclass(frozen=True)
class Segment:
    """One terrain grid and the ray-distance interval (arc metres) it is designated for."""

    grid: Grid
    min_range_m: float
    max_range_m: float
    label: str = ""


@dataclass(frozen=True, eq=False)
class Horizon:
    lat: float
    lon: float
    unit_height_m: float
    surface_height_m: float  # terrain at the site (near-field layer), m above the reference sphere
    azimuth_deg: np.ndarray  # 0, step, 2 step, ... < 360; clockwise from north
    elevation_deg: np.ndarray  # terrain horizon elevation above the local horizontal plane
    distance_m: np.ndarray  # ray distance of the sample that sets the horizon (diagnostic)
    missing_samples: int  # samples no layer covered (0 for a fully supported location)
    total_samples: int
    params: HorizonParams
    layers: tuple[dict, ...] = field(default=())  # provenance: label, resolution, ray-distance range

    @property
    def observer_radius_m(self) -> float:
        return MOON_RADIUS_M + self.surface_height_m + self.unit_height_m

    def elevation_at(self, azimuth_deg) -> np.ndarray:
        """Horizon elevation at arbitrary azimuths: linear between the computed azimuths, periodic."""
        step = self.params.azimuth_step_deg
        n = self.elevation_deg.size
        u = np.mod(np.asarray(azimuth_deg, dtype=float), 360.0) / step
        i0 = np.floor(u).astype(np.int64) % n
        f = u - np.floor(u)
        return self.elevation_deg[i0] * (1.0 - f) + self.elevation_deg[(i0 + 1) % n] * f


def elevation_deg(terrain_radius_m, observer_radius_m, theta_rad):
    """Exact elevation (deg) of a point at radius r and angular distance theta, seen from radius r_o."""
    r, ro, t = np.asarray(terrain_radius_m), observer_radius_m, np.asarray(theta_rad)
    return np.degrees(np.arctan2(r * np.cos(t) - ro, r * np.sin(t)))


# ----------------------------------------------------------------------------- numba kernel


@njit(cache=True, inline="always")
def _height(a, x0, y0, res, south, px, py, pz, radius):
    """Bilinear height of grid `a` at unit vector p (polar stereographic directly from p)."""
    if south:
        den = 1.0 - pz
        x = 2.0 * radius * py / den
        y = 2.0 * radius * px / den
    else:
        den = 1.0 + pz
        x = 2.0 * radius * py / den
        y = -2.0 * radius * px / den
    col = (x - x0) / res - 0.5
    row = (y0 - y) / res - 0.5
    h, w = a.shape
    if not (col >= 0.0 and row >= 0.0 and col <= w - 1 and row <= h - 1):
        return np.nan
    c0 = min(int(math.floor(col)), w - 2)
    r0 = min(int(math.floor(row)), h - 2)
    fc = col - c0
    fr = row - r0
    top = a[r0, c0] * (1.0 - fc) + a[r0, c0 + 1] * fc
    bottom = a[r0 + 1, c0] * (1.0 - fc) + a[r0 + 1, c0 + 1] * fc
    return top * (1.0 - fr) + bottom * fr


@njit(parallel=True, cache=True)
def _cast(
    arrays,
    meta,
    s_layer,
    s_cos,
    s_sin,
    s_theta,
    east,
    north,
    up,
    az_rad,
    r_obs,
    radius,
    out_tan,
    out_theta,
    out_missing,
):
    n_layers = meta.shape[0]
    n_s = s_cos.shape[0]
    for i in prange(az_rad.shape[0]):
        ca = math.cos(az_rad[i])
        sa = math.sin(az_rad[i])
        d0 = ca * north[0] + sa * east[0]
        d1 = ca * north[1] + sa * east[1]
        d2 = ca * north[2] + sa * east[2]
        best = -np.inf
        best_theta = np.nan
        missing = 0
        for k in range(n_s):
            ct = s_cos[k]
            st = s_sin[k]
            px = ct * up[0] + st * d0
            py = ct * up[1] + st * d1
            pz = ct * up[2] + st * d2
            h = np.nan
            for layer in range(s_layer[k], n_layers):
                m = meta[layer]
                h = _height(arrays[layer], m[0], m[1], m[2], m[3] > 0.0, px, py, pz, radius)
                if not np.isnan(h):
                    break
            if np.isnan(h):
                missing += 1
                continue
            r = radius + h
            t = (r * ct - r_obs) / (r * st)
            if t > best:
                best = t
                best_theta = s_theta[k]
        out_tan[i] = best
        out_theta[i] = best_theta
        out_missing[i] = missing


# ----------------------------------------------------------------------------- entry points


def _spacing_samples(start: float, end: float, cap: float, rel: float) -> np.ndarray:
    """Distances in (start, end], spaced at most min(cap, rel * d): geometric, then uniform."""
    parts = []
    switch = cap / rel  # beyond this distance the pixel-based cap is the tighter one
    d = start
    if d < min(switch, end):
        g_end = min(switch, end)
        n = max(1, math.ceil(math.log(g_end / d) / math.log1p(rel) - 1e-9))
        parts.append(d * (g_end / d) ** (np.arange(1, n + 1) / n))
        d = g_end
    if d < end:
        n = max(1, math.ceil((end - d) / cap - 1e-9))
        parts.append(d + np.arange(1, n + 1) * ((end - d) / n))
    return np.concatenate(parts) if parts else np.empty(0)


def ray_samples(segments: list[Segment], params: HorizonParams) -> tuple[np.ndarray, np.ndarray]:
    """Ray distances (arc m) and the designated segment index of each sample."""
    dist, layer = [], []
    for i, seg in enumerate(segments):
        start = max(seg.min_range_m, params.min_range_m)
        end = min(seg.max_range_m, params.max_range_m)
        if end <= start:
            continue
        d = _spacing_samples(start, end, params.sample_factor * seg.grid.res, params.relative_step)
        if not dist:
            d = np.concatenate([[start], d])  # the first sample sits at min_range_m
        dist.append(d)
        layer.append(np.full(d.size, i, dtype=np.int64))
    if not dist:
        raise HorizonUnavailable("no ray samples: empty terrain stack or zero range")
    return np.concatenate(dist), np.concatenate(layer)


def compute_horizon(
    lat: float,
    lon: float,
    unit_height_m: float,
    segments: list[Segment],
    params: HorizonParams | None = None,
) -> Horizon:
    """Horizon at (lat, lon) for an observer `unit_height_m` above the near-field terrain.

    `segments` are ordered finest (near field) first. `unit_height_m` may be 0 (used internally for the
    product 69 comparison; the API itself requires > 0).
    """
    params = params or HorizonParams()
    if not (math.isfinite(unit_height_m) and unit_height_m >= 0.0):
        raise ValueError("unit_height_m must be finite and >= 0")
    if not segments:
        raise HorizonUnavailable("no terrain covers this location")
    near = segments[0].grid
    surface = float(near.height_at_ps(*ps_from_latlon(lat, lon, near.pole))[0])
    if not math.isfinite(surface):
        raise HorizonUnavailable("the near-field terrain has no height at the site")
    r_obs = MOON_RADIUS_M + surface + unit_height_m

    dist, layer = ray_samples(segments, params)
    theta = dist / MOON_RADIUS_M
    east, north, up = enu_basis(lat, lon)
    az = np.arange(params.n_azimuths) * params.azimuth_step_deg

    arrays = List()
    for seg in segments:
        arrays.append(np.ascontiguousarray(seg.grid.array, dtype=np.float32))
    meta = np.array(
        [[s.grid.x0, s.grid.y0, s.grid.res, 1.0 if s.grid.pole == "south" else -1.0] for s in segments]
    )
    out_tan = np.empty(az.size)
    out_theta = np.empty(az.size)
    out_missing = np.empty(az.size, dtype=np.int64)
    _cast(
        arrays,
        meta,
        layer,
        np.cos(theta),
        np.sin(theta),
        theta,
        east,
        north,
        up,
        np.radians(az),
        r_obs,
        MOON_RADIUS_M,
        out_tan,
        out_theta,
        out_missing,
    )

    if not np.isfinite(out_tan).all():
        raise HorizonUnavailable("some azimuths have no terrain data at all")
    return Horizon(
        lat=lat,
        lon=lon,
        unit_height_m=unit_height_m,
        surface_height_m=surface,
        azimuth_deg=az,
        elevation_deg=np.degrees(np.arctan(out_tan)),
        distance_m=out_theta * MOON_RADIUS_M,
        missing_samples=int(out_missing.sum()),
        total_samples=int(dist.size * az.size),
        params=params,
        layers=tuple(
            {
                "label": s.label,
                "resolution_m": s.grid.res,
                "min_range_m": s.min_range_m,
                "max_range_m": min(s.max_range_m, params.max_range_m),
            }
            for s in segments
        ),
    )


def segments_for(stack: TerrainStack) -> list[Segment]:
    """Load the stack's DEMs (once per process) as ray-cast segments."""
    return [Segment(sl.spec.dem().grid, sl.min_range_m, sl.max_range_m, sl.spec.label) for sl in stack.layers]


def horizon_at(
    lat: float,
    lon: float,
    unit_height_m: float,
    params: HorizonParams | None = None,
    layers: tuple[LayerSpec, ...] = LAYERS,
) -> Horizon:
    """Horizon from the registry's terrain stack for this location (no cache; see lss.horizon.cache)."""
    params = params or HorizonParams()
    stack = resolve(lat, lon, params.max_range_m, layers)
    if not stack.supported:
        raise HorizonUnavailable(f"no terrain layer covers ({lat}, {lon})")
    return compute_horizon(lat, lon, unit_height_m, segments_for(stack), params)
