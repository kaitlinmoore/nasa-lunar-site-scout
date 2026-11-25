"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Terrain access: polar stereographic projection, DEM layers, height at a point.

Conventions (docs/methodology.md section 1.2):
- Heights are metres above the 1737.4 km reference sphere (MOON_ME / DE421), as in the PGDA maps.
- Projection: spherical polar stereographic, true scale at the pole, on the 1737.4 km sphere.
  South pole: rho = 2 R tan((90 + lat) / 2), x = rho sin(lon), y = rho cos(lon).
  North pole: rho = 2 R tan((90 - lat) / 2), x = rho sin(lon), y = -rho cos(lon).
  (Matches the PROJ definitions in the GeoTIFFs: +proj=stere +lat_0=-90 +lat_ts=-90 +R=1737400, and the
  northern counterpart; tested against PROJ.)
- Rasters are pixel-registered: a value belongs to its pixel's centre. Heights between centres are
  bilinear; points within half a pixel of the raster edge, or next to a no-data pixel, have no value.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import NamedTuple

import numpy as np

MOON_RADIUS_M = 1_737_400.0


def ps_from_latlon(lat_deg, lon_deg, pole: str = "south"):
    """Planetocentric lat/lon (deg) -> polar stereographic x, y (m). Arrays or scalars."""
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    if pole == "south":
        rho = 2.0 * MOON_RADIUS_M * np.tan((np.pi / 2 + lat) / 2.0)
        return rho * np.sin(lon), rho * np.cos(lon)
    if pole == "north":
        rho = 2.0 * MOON_RADIUS_M * np.tan((np.pi / 2 - lat) / 2.0)
        return rho * np.sin(lon), -rho * np.cos(lon)
    raise ValueError("pole must be 'south' or 'north'")


def latlon_from_ps(x_m, y_m, pole: str = "south"):
    """Polar stereographic x, y (m) -> planetocentric lat, east lon in -180..180 (deg)."""
    x, y = np.asarray(x_m, dtype=float), np.asarray(y_m, dtype=float)
    rho = np.hypot(x, y)
    colat = 2.0 * np.arctan(rho / (2.0 * MOON_RADIUS_M))
    if pole == "south":
        lat = np.degrees(colat) - 90.0
        lon = np.degrees(np.arctan2(x, y))
    elif pole == "north":
        lat = 90.0 - np.degrees(colat)
        lon = np.degrees(np.arctan2(x, -y))
    else:
        raise ValueError("pole must be 'south' or 'north'")
    return lat, lon


class Grid(NamedTuple):
    """An elevation raster in memory: heights (float32, NaN = no data) and its pixel-registered geometry.

    `x0`, `y0` are the outer top-left corner (PS metres), `res` the square pixel size. Used by the horizon
    ray caster; synthetic DEMs in tests are built directly as Grids.
    """

    array: np.ndarray
    x0: float
    y0: float
    res: float
    pole: str = "south"

    def height_at_ps(self, x_m, y_m) -> np.ndarray:
        col = (np.asarray(x_m) - self.x0) / self.res - 0.5
        row = (self.y0 - np.asarray(y_m)) / self.res - 0.5
        return bilinear(self.array, col, row)


class LonLatGrid(NamedTuple):
    """An elevation raster on a planetocentric latitude / east-longitude grid (simple cylindrical), in memory.

    Added for the global coarse layer (lss.terrain.global_layer, docs/methodology.md section
    3.5). Pixel-registered like `Grid`: a value belongs to its pixel's centre; heights between centres are
    bilinear in (longitude, latitude).

    `lon0`, `lat0` are the outer west and north edges (deg). Longitudes are measured eastward from `lon0`
    modulo 360, so a window may straddle the 0/360 meridian. `res_deg` is the pixel size in degrees (the
    same in latitude and longitude). `res` is the spacing in metres used to step rays over this grid
    (lss.horizon.core.ray_samples), set by the reader. `wrap`: the columns span the full 360 deg, so the last
    column is next to the first. `pole` is always "lonlat": it tells the ray caster this is not a polar
    stereographic grid.
    """

    array: np.ndarray
    lon0: float
    lat0: float
    res_deg: float
    res: float
    wrap: bool = False
    pole: str = "lonlat"

    def to_pixel(self, lat_deg, lon_deg):
        """(lat, lon) deg -> fractional (col, row) of pixel centres (centre of pixel (0, 0) is (0, 0))."""
        col = np.mod(np.asarray(lon_deg, dtype=float) - self.lon0, 360.0) / self.res_deg - 0.5
        row = (self.lat0 - np.asarray(lat_deg, dtype=float)) / self.res_deg - 0.5
        return col, row

    def height_at_latlon(self, lat_deg, lon_deg) -> np.ndarray:
        """Bilinear height (m above the sphere); NaN outside the grid or next to no-data."""
        col, row = self.to_pixel(lat_deg, lon_deg)
        if not self.wrap:
            return bilinear(self.array, col, row)
        # Full circle: append the first column after the last, and move columns west of the first centre
        # (col in [-0.5, 0)) to the far side, so every longitude has two neighbouring columns.
        a = np.concatenate([self.array, self.array[:, :1]], axis=1)
        col = np.where(np.asarray(col) < 0.0, np.asarray(col) + self.array.shape[1], col)
        return bilinear(a, col, row)


@dataclass
class DemLayer:
    """One elevation raster (north-up, square pixels, polar stereographic metres)."""

    dataset_id: str
    path: Path
    pole: str = "south"
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @cached_property
    def meta(self) -> dict:
        import rasterio

        with rasterio.open(self.path) as d:
            t = d.transform
            if t.b != 0 or t.d != 0 or t.a <= 0 or t.e >= 0 or abs(t.a + t.e) > 1e-9:
                raise ValueError(f"{self.path}: expected a north-up grid with square pixels")
            return {
                "x0": t.c,
                "y0": t.f,
                "res": t.a,
                "width": d.width,
                "height": d.height,
                "nodata": d.nodata,
                "scale": (d.scales[0] or 1.0),
                "offset": (d.offsets[0] or 0.0),
            }

    @property
    def resolution_m(self) -> float:
        return self.meta["res"]

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        m = self.meta
        return m["x0"], m["y0"] - m["height"] * m["res"], m["x0"] + m["width"] * m["res"], m["y0"]

    @cached_property
    def array(self) -> np.ndarray:
        """The whole raster as float32 heights (no-data -> NaN). Loaded once, on first use."""
        import rasterio

        with self._lock, rasterio.open(self.path) as d:
            a = d.read(1).astype(np.float32, copy=False)
        m = self.meta
        if m["nodata"] is not None and not np.isnan(m["nodata"]):
            a = np.where(a == m["nodata"], np.float32(np.nan), a)
        if m["scale"] != 1.0 or m["offset"] != 0.0:
            a = a * np.float32(m["scale"]) + np.float32(m["offset"])
        return a

    @cached_property
    def grid(self) -> Grid:
        m = self.meta
        return Grid(self.array, m["x0"], m["y0"], m["res"], self.pole)

    def to_pixel(self, x_m, y_m):
        """PS metres -> fractional (col, row) of pixel centres (centre of pixel (0, 0) is (0, 0))."""
        m = self.meta
        return (np.asarray(x_m) - m["x0"]) / m["res"] - 0.5, (m["y0"] - np.asarray(y_m)) / m["res"] - 0.5

    def contains(self, x_m, y_m, margin_m: float = 0.0) -> np.ndarray:
        """True where (x, y) is inside the raster by at least `margin_m` (ignores no-data)."""
        left, bottom, right, top = self.bounds
        x, y = np.asarray(x_m), np.asarray(y_m)
        in_x = (x >= left + margin_m) & (x <= right - margin_m)
        return in_x & (y >= bottom + margin_m) & (y <= top - margin_m)

    def height_at_ps(self, x_m, y_m) -> np.ndarray:
        """Bilinear height (m above the sphere) at PS points; NaN outside or next to no-data."""
        return bilinear(self.array, *self.to_pixel(x_m, y_m))

    def height_at(self, lat_deg, lon_deg) -> np.ndarray:
        return self.height_at_ps(*ps_from_latlon(lat_deg, lon_deg, self.pole))


def bilinear(a: np.ndarray, col, row) -> np.ndarray:
    """Bilinear interpolation of `a` at fractional pixel-centre coordinates; NaN outside the grid."""
    col, row = np.atleast_1d(np.asarray(col, dtype=float)), np.atleast_1d(np.asarray(row, dtype=float))
    h, w = a.shape
    out = np.full(col.shape, np.nan)
    ok = (col >= 0) & (row >= 0) & (col <= w - 1) & (row <= h - 1)
    c, r = col[ok], row[ok]
    c0 = np.minimum(np.floor(c).astype(np.int64), w - 2)
    r0 = np.minimum(np.floor(r).astype(np.int64), h - 2)
    fc, fr = c - c0, r - r0
    v00, v01 = a[r0, c0], a[r0, c0 + 1]
    v10, v11 = a[r0 + 1, c0], a[r0 + 1, c0 + 1]
    out[ok] = (v00 * (1 - fc) + v01 * fc) * (1 - fr) + (v10 * (1 - fc) + v11 * fc) * fr
    return out
