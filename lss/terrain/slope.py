"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Surface slope on a polar stereographic DEM (docs/methodology.md, "Slope").

- **Slope at a pixel**: central differences, the angle between the local surface and the plane normal to the
  sphere radius: tan(slope) = hypot(dz/dx, dz/dy), dz/dx = (z[col + 1] - z[col - 1]) / (2 dx), dz/dy likewise
  along rows. This is the definition of Barker et al. (2021)'s published 5 m slope maps (PGDA product 78
  `*_slp.tif`): it reproduces Site01's map to a median 0.0001 deg (Kaitlin, 2026-11-15; tested).
- **Ground distances**: the map is conformal and true at the pole; its scale factor is
  k = 1 + (rho / 2R)^2 at map distance rho from the pole (1.0002 at 88 S, 1.0037 at 83 S), so a map step
  dx is a ground step dx / k.
- **Statistics within a radius**: over the pixels whose centres lie within that ground distance of the point
  (map distance / k at the point; < 1e-5 relative error within 10 km). Edge pixels of the window, which have
  no neighbour on every side, are not used.
- **Slope at the point**: the slope of the pixel containing it.
- **Latitude/longitude grids** (the global coarse layer, C7; stream E, one-off exception: insertions only, the
  polar path above unchanged): the same central differences on a simple-cylindrical grid, with the ground step
  of each direction on the 1737.4 km sphere: R dphi north-south, R cos(lat) dlambda east-west at each row's
  latitude; statistics over pixel centres within that great-circle distance (`slope_stats_lonlat`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from lss.ephem import MOON_RADIUS_M

if TYPE_CHECKING:
    from lss.terrain.core import LonLatGrid

SLOPE_VERSION = 1  # bump when the definition or the statistics change


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
# Latitude/longitude grids (C7, stream E; docs/methodology.md section 5.6.1). Same definition as `slope_deg`;
# only the ground steps differ: they are not equal in the two directions on a simple-cylindrical grid.


def slope_deg_lonlat(
    z: np.ndarray, res_deg: float, row_lats_deg: np.ndarray, radius_m: float = MOON_RADIUS_M
) -> np.ndarray:
    """Slope (deg) of the interior pixels of z on a latitude/longitude grid by central differences; shape
    (rows - 2, cols - 2). `row_lats_deg`: the latitude of each row's pixel centres. Ground steps on the
    sphere: R * res north-south, R * cos(latitude) * res east-west at each row's own latitude."""
    step = np.radians(res_deg) * radius_m
    dx = step * np.cos(np.radians(np.asarray(row_lats_deg, dtype=float)[1:-1]))[:, None]
    dzdx = (z[1:-1, 2:] - z[1:-1, :-2]) / (2.0 * dx)
    dzdy = (z[2:, 1:-1] - z[:-2, 1:-1]) / (2.0 * step)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


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
    circle leaves the window, has no data, or the window contains a pole (east-west steps vanish there)."""
    if grid.wrap:
        raise ValueError(
            "windows that contain a pole are not supported (east-west ground steps vanish there)"
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
    vals = s[within_all[1:-1, 1:-1]]
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
