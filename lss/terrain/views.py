"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Terrain images for the 2D site view (plan F6): hillshade and slope classes, as georeferenced PNGs on the
DEM's own polar stereographic grid.

- **Hillshade:** cartographic shading for reading the relief, not the real Sun. Light from map azimuth 315°
  (upper left of the north-up polar stereographic grid) at 45° elevation; the gradient by central differences,
  as the slope. 8-bit grey, 0 = facing away, 255 = facing the light.
- **Slope classes:** the slope of docs/methodology.md section 5.6 (central differences, map scale factor), in
  five classes; the PNG stores the class number, so the client chooses the colours (a validated suggestion is
  in SLOPE_PALETTE). 255 = no data.
"""

from __future__ import annotations

import numpy as np

from lss.terrain.slope import scale_factor, slope_deg

HILLSHADE_AZIMUTH_DEG = 315.0
HILLSHADE_ALTITUDE_DEG = 45.0
# Class upper edges (deg): class k covers [edges[k-1], edges[k]); the last class is 20 deg and steeper.
SLOPE_CLASS_EDGES_DEG = (5.0, 10.0, 15.0, 20.0)
SLOPE_CLASS_LABELS = ("under 5°", "5–10°", "10–15°", "15–20°", "20° or more")
NODATA_CLASS = 255
# One-hue ordinal ramps (blue), flattest first; checked with the dataviz skill's validator (--ordinal) on the
# light (#fcfcfb) and dark (#1a1a19) surfaces: monotone lightness, visible step gaps, end step >= 2:1.
SLOPE_PALETTE = {
    "light": ("#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"),
    "dark": ("#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4"),
}


def _gradient(z: np.ndarray, step_m: float, k: np.ndarray | float):
    """dz/dx (east, along columns) and dz/dy (map up, against rows) of the interior pixels, ground units."""
    ground = step_m / k
    dzdx = (z[1:-1, 2:] - z[1:-1, :-2]) / (2.0 * ground)
    dzdy = -(z[2:, 1:-1] - z[:-2, 1:-1]) / (2.0 * ground)  # rows run down the map
    return dzdx, dzdy


def hillshade(z: np.ndarray, step_m: float, k: np.ndarray | float = 1.0) -> np.ndarray:
    """8-bit hillshade of the interior pixels (shape rows - 2, cols - 2); 0 where z has no data."""
    dzdx, dzdy = _gradient(z, step_m, k)
    az, alt = np.radians(HILLSHADE_AZIMUTH_DEG), np.radians(HILLSHADE_ALTITUDE_DEG)
    light = np.array([np.sin(az) * np.cos(alt), np.cos(az) * np.cos(alt), np.sin(alt)])
    norm = np.sqrt(dzdx**2 + dzdy**2 + 1.0)
    shade = (-dzdx * light[0] - dzdy * light[1] + light[2]) / norm
    out = np.clip(np.round(255.0 * np.clip(shade, 0.0, 1.0)), 0, 255)
    ok = np.isfinite(out) & np.isfinite(z[1:-1, 1:-1])  # the pixel itself and its neighbours have data
    return np.where(ok, out, 0).astype(np.uint8)


def slope_classes(z: np.ndarray, step_m: float, k: np.ndarray | float = 1.0) -> np.ndarray:
    """Slope class number (0-4) of the interior pixels; NODATA_CLASS where z has no data."""
    s = slope_deg(z, step_m, k)
    cls = np.digitize(s, SLOPE_CLASS_EDGES_DEG).astype(np.uint8)
    ok = np.isfinite(s) & np.isfinite(z[1:-1, 1:-1])  # the pixel itself and its neighbours have data
    return np.where(ok, cls, NODATA_CLASS).astype(np.uint8)


def interior_scale_factor(x0: float, y0: float, step_m: float, rows: int, cols: int) -> np.ndarray:
    """Map scale factor at the interior pixel centres of a window whose top-left corner is (x0, y0)."""
    xc = x0 + (np.arange(1, cols - 1) + 0.5) * step_m
    yc = y0 - (np.arange(1, rows - 1) + 0.5) * step_m
    X, Y = np.meshgrid(xc, yc)
    return scale_factor(X, Y)
