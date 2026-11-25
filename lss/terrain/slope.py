"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Surface slope on a polar stereographic DEM (docs/methodology.md, "Slope").

- **Slope at a pixel**: central differences, the angle between the local surface and the plane normal to the
  sphere radius: tan(slope) = hypot(dz/dx, dz/dy), dz/dx = (z[col + 1] - z[col - 1]) / (2 dx), dz/dy likewise
  along rows. This is the definition of Barker et al. (2021)'s published 5 m slope maps (PGDA product 78
  `*_slp.tif`): it reproduces Site01's map to a median 0.0001 deg (the project author, 2026-11-15; tested).
- **Ground distances**: the map is conformal and true at the pole; its scale factor is
  k = 1 + (rho / 2R)^2 at map distance rho from the pole (1.0002 at 88 S, 1.0037 at 83 S), so a map step
  dx is a ground step dx / k.
- **Statistics within a radius**: over the pixels whose centres lie within that ground distance of the point
  (map distance / k at the point; < 1e-5 relative error within 10 km). Edge pixels of the window, which have
  no neighbour on every side, are not used.
- **Slope at the point**: the slope of the pixel containing it.
- **Latitude/longitude grids** (the global coarse layer): the same central differences on a simple-cylindrical
  grid, with the ground step of each direction on the 1737.4 km sphere: R dphi north-south, R cos(lat) dlambda
  east-west at each row's latitude; statistics over pixel centres within that great-circle distance
  (`slope_stats_lonlat`). East-west, the difference spans n = round(1 / cos(lat)) columns on each side
  (`ew_offset_px`; n = 1 below 48.19 deg), so its baseline does not shrink towards the poles below the 0.5 m
  height quantisation. No slope at the poles themselves, where east and north are undefined.
- **Aspect and gradient**: the downhill azimuth (deg clockwise from north) and the east and north height
  gradients, from exactly the same differences as the slope (`slope_aspect`, `slope_aspect_lonlat`,
  `gradient_ps`, `gradient_lonlat`). On a polar stereographic map the map-axis gradient is turned to east
  and north at each pixel's own position; at a pole, where they are undefined, the aspect is NaN.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from lss.ephem import MOON_RADIUS_M

if TYPE_CHECKING:
    from lss.terrain.core import LonLatGrid

SLOPE_VERSION = 2  # bump when the definition or the statistics change


def scale_factor(x_m, y_m) -> np.ndarray:
    rho = np.hypot(x_m, y_m)
    return 1.0 + (rho / (2.0 * MOON_RADIUS_M)) ** 2


def slope_deg(z: np.ndarray, step_m: float, k: float | np.ndarray = 1.0) -> np.ndarray:
    """Slope (deg) of the interior pixels of z by central differences; shape (rows - 2, cols - 2).
    `step_m` is the map pixel size; `k` the map scale factor (ground step = step / k)."""
    ground = step_m / k
    dzdx = (z[1:-1, 2:] - z[1:-1, :-2]) / (2.0 * ground)
    dzdy = (z[2:, 1:-1] - z[:-2, 1:-1]) / (2.0 * ground)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


@dataclass(frozen=True)
class SlopeStats:
    at_point_deg: float
    min_deg: float
    max_deg: float
    mean_deg: float
    pixels: int
    resolution_m: float


def slope_stats(path: Path, x_m: float, y_m: float, radius_m: float) -> SlopeStats:
    """Slope at (x, y) and over the pixels within radius_m of it, on the GeoTIFF at `path` (north-up PS grid,
    pixel-registered). Reads only the window it needs. Raises if the circle leaves the map or has no data."""
    import rasterio
    from rasterio.windows import Window

    with rasterio.open(path) as d:
        t = d.transform
        if t.b != 0 or t.d != 0 or t.e >= 0:
            raise ValueError("only north-up, unrotated grids are supported")
        step = t.a
        k0 = float(scale_factor(x_m, y_m))
        reach = radius_m * k0 + 2.0 * step  # map distance, plus the neighbours
        col0 = int(np.floor((x_m - reach - t.c) / step))
        col1 = int(np.ceil((x_m + reach - t.c) / step))
        row0 = int(np.floor((t.f - (y_m + reach)) / step))
        row1 = int(np.ceil((t.f - (y_m - reach)) / step))
        if col0 < 0 or row0 < 0 or col1 > d.width or row1 > d.height:
            raise ValueError(f"{path.name}: a {radius_m:g} m circle around the point leaves the map")
        z = d.read(1, window=Window(col0, row0, col1 - col0, row1 - row0)).astype(np.float64)
        if d.nodata is not None and not np.isnan(d.nodata):
            z[z == d.nodata] = np.nan
    cols = np.arange(col0 + 1, col1 - 1)
    rows = np.arange(row0 + 1, row1 - 1)
    xc = t.c + (cols + 0.5) * step
    yc = t.f - (rows + 0.5) * step
    X, Y = np.meshgrid(xc, yc)
    s = slope_deg(z, step, scale_factor(X, Y))
    within = np.hypot(X - x_m, Y - y_m) / k0 <= radius_m
    vals = s[within]
    if vals.size == 0 or np.isnan(vals).any():
        raise ValueError(f"{path.name}: no data (or gaps) within {radius_m:g} m of the point")
    r = int(np.floor((t.f - y_m) / step)) - (row0 + 1)
    c = int(np.floor((x_m - t.c) / step)) - (col0 + 1)
    return SlopeStats(
        float(s[r, c]), float(vals.min()), float(vals.max()), float(vals.mean()), int(vals.size), step
    )


# ----------------------------------------------------------------------------------------------------
# Latitude/longitude grids (the global coarse layer; docs/methodology.md section 5.6.1). Same definition as
# `slope_deg`; only the ground steps differ: they are not equal in the two directions on a simple-cylindrical
# grid.


def ew_offset_px(lat_deg) -> np.ndarray:
    """Columns on each side used for the east-west difference at latitude `lat_deg`: n = round(1 / cos(lat)),
    at least 1. The east-west baseline 2 n R cos(lat) dlambda is then 2/3 to 4/3 of the north-south baseline
    2 R dphi, instead of shrinking towards the poles. n = 1 (the plain central difference) wherever
    1 / cos(lat) < 1.5, i.e. |lat| < 48.19 deg. Capped at 2**31 near the pole, where cos(lat) vanishes."""
    c = np.abs(np.cos(np.radians(np.asarray(lat_deg, dtype=float))))
    inv = np.divide(1.0, c, out=np.full_like(c, np.inf), where=c > 0.0)
    return np.maximum(np.rint(np.minimum(inv, 2.0**31)), 1.0).astype(np.int64)


def gradient_lonlat(
    z: np.ndarray, res_deg: float, row_lats_deg: np.ndarray, radius_m: float = MOON_RADIUS_M
) -> tuple[np.ndarray, np.ndarray]:
    """East and north height gradients (m per ground metre) of the interior pixels of z on a latitude /
    longitude grid; each of shape (rows - 2, cols - 2). North-south: z[row - 1] - z[row + 1] over 2 R dphi.
    East-west: z[col + n] - z[col - n] over 2 n R cos(lat) dlambda, at each row's own latitude, with
    n = ew_offset_px(lat). Pixels whose n-th neighbour on either side is outside the grid get NaN."""
    z = np.asarray(z)
    n_rows, n_cols = z.shape
    lats = np.asarray(row_lats_deg, dtype=float)[1:-1]
    step = np.radians(res_deg) * radius_m
    dx = step * np.cos(np.radians(lats))[:, None]
    n_px = ew_offset_px(lats)
    east = np.full((n_rows - 2, n_cols - 2), np.nan)
    zi = z[1:-1]
    for n in np.unique(n_px):
        if 2 * n >= n_cols:
            continue  # no pixel of these rows has both neighbours in the grid
        sel = n_px == n
        # interior column j is grid column j + 1; it needs grid columns j + 1 - n and j + 1 + n
        east[sel, n - 1 : n_cols - 1 - n] = (zi[sel, 2 * n :] - zi[sel, : n_cols - 2 * n]) / (
            2.0 * (n * dx[sel])
        )
    north = (z[:-2, 1:-1] - z[2:, 1:-1]) / (2.0 * step)
    return east, north


def slope_deg_lonlat(
    z: np.ndarray, res_deg: float, row_lats_deg: np.ndarray, radius_m: float = MOON_RADIUS_M
) -> np.ndarray:
    """Slope (deg) of the interior pixels of z on a latitude/longitude grid by central differences; shape
    (rows - 2, cols - 2). `row_lats_deg`: the latitude of each row's pixel centres (north at row 0). Ground
    steps on the sphere: 2 R dphi north-south, and 2 n R cos(lat) dlambda east-west at each row's own
    latitude, n = ew_offset_px(lat) (a matched baseline: 1 at |lat| < 48.19 deg). Pixels whose east-west
    neighbours fall outside the grid get NaN."""
    east, north = gradient_lonlat(z, res_deg, row_lats_deg, radius_m)
    return np.degrees(np.arctan(np.hypot(east, north)))


def arc_m(lat1_deg, lon1_deg, lat2_deg, lon2_deg, radius_m: float = MOON_RADIUS_M) -> np.ndarray:
    """Great-circle distance (m) on the sphere (haversine)."""
    p1, p2 = np.radians(lat1_deg), np.radians(lat2_deg)
    a = (
        np.sin((p2 - p1) / 2.0) ** 2
        + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2_deg - lon1_deg) / 2.0) ** 2
    )
    return 2.0 * radius_m * np.arcsin(np.sqrt(np.minimum(a, 1.0)))


def slope_stats_lonlat(grid: LonLatGrid, lat: float, lon: float, radius_m: float) -> SlopeStats:
    """Slope at (lat, lon) and over the pixels whose centres lie within radius_m (great-circle) of it, on a
    LonLatGrid window (lss.terrain.global_layer.window). Edge pixels of the window are not used. Raises if the
    circle leaves the window (or a pixel in it has an east-west neighbour outside the window), has no data,
    or the window spans every longitude (it contains a pole, where east and north are undefined)."""
    if grid.wrap:
        raise ValueError(
            "windows that span every longitude (around a pole) are not supported: east and north are "
            "undefined at the pole"
        )
    z = np.asarray(grid.array, dtype=np.float64)
    n_rows, n_cols = z.shape
    lats = grid.lat0 - (np.arange(n_rows) + 0.5) * grid.res_deg
    lons = grid.lon0 + (np.arange(n_cols) + 0.5) * grid.res_deg
    s = slope_deg_lonlat(z, grid.res_deg, lats)
    lon_c, lat_c = np.meshgrid(lons, lats)
    within_all = arc_m(lat, lon, lat_c, lon_c) <= radius_m
    if within_all[[0, -1], :].any() or within_all[:, [0, -1]].any():
        raise ValueError(f"a {radius_m:g} m circle around the point leaves the grid")
    within = within_all[1:-1, 1:-1]
    ew_px = ew_offset_px(lats[1:-1])[:, None]
    cols = np.arange(1, n_cols - 1)[None, :]
    if (within & ((cols - ew_px < 0) | (cols + ew_px > n_cols - 1))).any():
        raise ValueError(f"the east-west neighbours of a pixel within {radius_m:g} m leave the grid")
    vals = s[within]
    if vals.size == 0 or np.isnan(vals).any():
        raise ValueError(f"no data (or gaps) within {radius_m:g} m of the point")
    r = int(np.floor((grid.lat0 - lat) / grid.res_deg)) - 1
    c = int(np.floor(np.mod(lon - grid.lon0, 360.0) / grid.res_deg)) - 1
    if not (0 <= r < s.shape[0] and 0 <= c < s.shape[1]):
        raise ValueError("the point is not inside the grid's interior")
    return SlopeStats(
        float(s[r, c]),
        float(vals.min()),
        float(vals.max()),
        float(vals.mean()),
        int(vals.size),
        float(grid.res),
    )


# ----------------------------------------------------------------------------------------------------
# Aspect and gradient (docs/methodology.md section 5.6.2). The same differences as `slope_deg` and
# `slope_deg_lonlat`, so the slope returned here equals theirs exactly.


def aspect_deg(east: np.ndarray, north: np.ndarray) -> np.ndarray:
    """Downhill azimuth (deg, clockwise from north, in [0, 360)) of a surface whose height rises by `east`
    and `north` metres per ground metre in those directions. NaN where the surface is flat or a gradient is
    NaN."""
    east, north = np.asarray(east, dtype=float), np.asarray(north, dtype=float)
    az = np.mod(np.degrees(np.arctan2(-east, -north)), 360.0)
    return np.where((east == 0.0) & (north == 0.0), np.nan, az)


def gradient_ps(z: np.ndarray, step_m: float, k: float | np.ndarray = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Height gradients (m per ground metre) of the interior pixels of z on a north-up polar stereographic
    map, along the map's +x (columns) and +y (up the map, against rows) axes; shape (rows - 2, cols - 2).
    The differences of `slope_deg`: tan(slope) = hypot of the two."""
    ground = step_m / k
    dzdx = (z[1:-1, 2:] - z[1:-1, :-2]) / (2.0 * ground)
    dzdy = (z[2:, 1:-1] - z[:-2, 1:-1]) / (2.0 * ground)
    return dzdx, -dzdy


def slope_aspect(
    z: np.ndarray, step_m: float, x_m: np.ndarray, y_m: np.ndarray, pole: str = "south"
) -> tuple[np.ndarray, np.ndarray]:
    """Slope (deg) and aspect (downhill azimuth, deg clockwise from north) of the interior pixels of z on a
    north-up polar stereographic map; `x_m`, `y_m`: the map coordinates of those pixels' centres (shape
    (rows - 2, cols - 2), or broadcastable to it). The slope is `slope_deg(z, step_m, scale_factor(x_m, y_m))`
    exactly.

    Map axes to east and north at each pixel: at distance rho from the pole, north points away from the south
    pole, (x, y) / rho, and towards the north pole, -(x, y) / rho; east is north turned 90 deg clockwise. The
    aspect is NaN at the pole itself (rho = 0), where east and north are undefined."""
    if pole not in ("south", "north"):
        raise ValueError("pole must be 'south' or 'north'")
    x, y = np.asarray(x_m, dtype=float), np.asarray(y_m, dtype=float)
    gx, gy = gradient_ps(z, step_m, scale_factor(x, y))
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    rho = np.hypot(x, y)
    with np.errstate(invalid="ignore", divide="ignore"):
        sign = 1.0 if pole == "south" else -1.0
        nx, ny = sign * x / rho, sign * y / rho  # unit north in map axes
    east = gx * ny - gy * nx  # unit east = (ny, -nx)
    north = gx * nx + gy * ny
    return slope, np.where(rho > 0.0, aspect_deg(east, north), np.nan)


def slope_aspect_lonlat(
    z: np.ndarray, res_deg: float, row_lats_deg: np.ndarray, radius_m: float = MOON_RADIUS_M
) -> tuple[np.ndarray, np.ndarray]:
    """Slope (deg) and aspect (downhill azimuth, deg clockwise from north) of the interior pixels of z on a
    latitude/longitude grid, from `gradient_lonlat` (the matched east-west baseline). The slope is
    `slope_deg_lonlat` exactly; both are NaN where the east-west neighbours fall outside the grid."""
    east, north = gradient_lonlat(z, res_deg, row_lats_deg, radius_m)
    return np.degrees(np.arctan(np.hypot(east, north))), aspect_deg(east, north)
