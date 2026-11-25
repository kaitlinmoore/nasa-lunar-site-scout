"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Global coarse terrain layer (docs/methodology.md section 3.5): the LOLA gridded DEM LDEM_128.

The product (PDS data set LRO-L-LOLA-4-GDR-V1.0, product version 3.0, 2017-09-15) is one raw image with a
detached PDS3 label. Facts used here, all from the label and checked against it by `check_label`:
- SIMPLE CYLINDRICAL, 128 pixels per degree (MAP_SCALE 236.901 m/pix), 23040 lines x 46080 samples,
  LSB 16-bit integers, pixel registered;
- COORDINATE_SYSTEM_NAME "MEAN EARTH/POLAR AXIS OF DE421": the engine's MOON_ME / DE421 frame;
- height = DN x 0.5 m above a 1737.4 km sphere (OFFSET 1737400 m): the PGDA maps' reference sphere;
- pixel centres: 0-based line r is at latitude (LINE_PROJECTION_OFFSET - r) / 128 and 0-based sample s at
  east longitude CENTER_LONGITUDE + (s - SAMPLE_PROJECTION_OFFSET) / 128, so line 0 is centred 1/256 deg
  below 90 N and sample 0 1/256 deg east of 0 E.

The 2.1 GB image is memory-mapped, never loaded whole: a horizon reads a window that covers its maximum ray
range around the point (`window`). Windows that would reach a pole, or span all longitudes, take whole
rows (`LonLatGrid.wrap`); others may straddle the 0/360 meridian (columns taken modulo 46080).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from lss.terrain.core import MOON_RADIUS_M, LonLatGrid


@dataclass(frozen=True)
class CylindricalMap:
    """Geometry and encoding of a PDS3 simple-cylindrical elevation image (values from its label)."""

    lines: int
    samples: int
    ppd: float  # MAP_RESOLUTION, pixels per degree
    line_offset: float  # LINE_PROJECTION_OFFSET (pixels)
    sample_offset: float  # SAMPLE_PROJECTION_OFFSET (pixels)
    center_lon: float  # CENTER_LONGITUDE (deg E)
    scale: float  # SCALING_FACTOR: metres per count
    map_scale_m: float  # MAP_SCALE, m per pixel along a meridian

    @property
    def nbytes(self) -> int:
        return self.lines * self.samples * 2

    def row_of(self, lat_deg):
        """Fractional 0-based line of pixel centres at latitude `lat_deg`."""
        return self.line_offset - self.ppd * np.asarray(lat_deg, dtype=float)

    def col_of(self, lon_deg):
        """Fractional 0-based sample of pixel centres at east longitude `lon_deg` (any range; 0..360 map)."""
        return self.sample_offset + self.ppd * (
            np.mod(np.asarray(lon_deg, dtype=float), 360.0) - self.center_lon
        )


LDEM_128 = CylindricalMap(
    lines=23040,
    samples=46080,
    ppd=128.0,
    line_offset=11519.5,
    sample_offset=23039.5,
    center_lon=180.0,
    scale=0.5,
    map_scale_m=236.901,
)

# Label fields that must hold exactly (values as written in the label, units stripped) for LDEM_128.
LDEM_128_LABEL = {
    "PRODUCT_ID": "LDEM_128",
    "DATA_SET_ID": "LRO-L-LOLA-4-GDR-V1.0",
    "LINES": "23040",
    "LINE_SAMPLES": "46080",
    "SAMPLE_BITS": "16",
    "SAMPLE_TYPE": "LSB_INTEGER",
    "SCALING_FACTOR": "0.5",
    "OFFSET": "1737400.",
    "MAP_PROJECTION_TYPE": "SIMPLE CYLINDRICAL",
    "MAP_RESOLUTION": "128",
    "MAP_SCALE": "236.901",
    "A_AXIS_RADIUS": "1737.4",
    "CENTER_LATITUDE": "0",
    "CENTER_LONGITUDE": "180",
    "POSITIVE_LONGITUDE_DIRECTION": "EAST",
    "LINE_PROJECTION_OFFSET": "11519.5",
    "SAMPLE_PROJECTION_OFFSET": "23039.5",
    "COORDINATE_SYSTEM_NAME": "MEAN EARTH/POLAR AXIS OF DE421",
}


def read_label(path: Path) -> dict[str, str]:
    """`KEY = value` pairs of a PDS3 label (first occurrence of each key; quotes and <units> removed)."""
    out: dict[str, str] = {}
    for line in Path(path).read_text(encoding="latin-1").splitlines():
        m = re.match(r"^\s*([A-Z_^][A-Z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if not m or m.group(1) in out:
            continue
        value = re.sub(r"\s*<[^>]*>\s*$", "", m.group(2)).strip().strip('"').strip()
        out[m.group(1)] = value
    return out


def check_label(path: Path, expected: dict[str, str] = LDEM_128_LABEL) -> None:
    """Raise ValueError if any expected label field differs (so a changed product is never misread)."""
    got = read_label(path)
    bad = {k: (v, got.get(k)) for k, v in expected.items() if got.get(k) != v}
    if bad:
        raise ValueError(f"{path}: label differs from what the reader assumes: {bad}")


def open_image(img: Path, label: Path, m: CylindricalMap = LDEM_128, expected=LDEM_128_LABEL) -> np.memmap:
    """The image as a read-only (lines, samples) int16 memmap, after checking its label and exact size."""
    check_label(label, expected)
    size = Path(img).stat().st_size
    if size != m.nbytes:
        raise ValueError(f"{img}: {size} bytes, expected {m.nbytes} ({m.lines} x {m.samples} x 2)")
    return np.memmap(img, dtype="<i2", mode="r", shape=(m.lines, m.samples))


def window(
    image: np.ndarray,
    lat: float,
    lon: float,
    radius_m: float,
    m: CylindricalMap = LDEM_128,
    margin_px: int = 2,
    extra_cols: int = 0,
) -> LonLatGrid:
    """Heights (float32, m above 1737.4 km) of every pixel within `radius_m` (arc length) of (lat, lon), as a
    LonLatGrid, with `margin_px` extra pixels on each side for bilinear interpolation at the edges, and
    `extra_cols` more columns on the east and west sides (for wider east-west differences).

    The window is a latitude band [lat - d, lat + d], d = radius / R, clipped at the poles, and the longitude
    span that band needs at its highest |latitude|. If that reaches a pole or spans 360 deg, whole rows are
    taken (wrap = True).
    """
    d_deg = math.degrees(radius_m / MOON_RADIUS_M)
    lat_n, lat_s = min(lat + d_deg, 90.0), max(lat - d_deg, -90.0)
    r0 = max(int(math.floor(float(m.row_of(lat_n)))) - margin_px, 0)
    r1 = min(int(math.ceil(float(m.row_of(lat_s)))) + margin_px, m.lines - 1)
    lat0 = (m.line_offset - r0) / m.ppd + 0.5 / m.ppd  # outer north edge of line r0
    res_deg = 1.0 / m.ppd

    # A cap of angular radius delta around latitude phi spans asin(sin delta / cos phi) of longitude each way,
    # unless it contains a pole (sin delta >= cos phi), when it spans every longitude.
    s_delta, c_phi = math.sin(radius_m / MOON_RADIUS_M), math.cos(math.radians(lat))
    half_lon = 180.0 if s_delta >= c_phi else math.degrees(math.asin(s_delta / c_phi))
    n_cols = 2 * int(math.ceil(half_lon * m.ppd)) + 2 * (margin_px + extra_cols) + 2
    wrap = half_lon >= 180.0 or n_cols >= m.samples
    if wrap:
        data = np.asarray(image[r0 : r1 + 1, :])
        lon0 = m.center_lon - (m.sample_offset + 0.5) / m.ppd  # outer west edge of sample 0
    else:
        c_start = int(math.floor(float(m.col_of(lon)) - half_lon * m.ppd)) - margin_px - extra_cols
        c_end = c_start + n_cols  # exclusive
        cols = np.arange(c_start, c_end) % m.samples
        if cols[0] < cols[-1]:  # one contiguous slice
            data = np.asarray(image[r0 : r1 + 1, cols[0] : cols[-1] + 1])
        else:  # straddles the 0/360 meridian
            data = np.concatenate(
                [np.asarray(image[r0 : r1 + 1, cols[0] :]), np.asarray(image[r0 : r1 + 1, : cols[-1] + 1])],
                axis=1,
            )
        lon0 = m.center_lon + (c_start - m.sample_offset - 0.5) / m.ppd
    heights = data.astype(np.float32) * np.float32(m.scale)
    return LonLatGrid(np.ascontiguousarray(heights), float(lon0), float(lat0), res_deg, m.map_scale_m, wrap)


@dataclass(frozen=True)
class GlobalWindow:
    """What lss.registry.terrain's layer specs return from `dem()`: an object with a `.grid`."""

    grid: LonLatGrid


@lru_cache(maxsize=4)
def cached_window(img: Path, label: Path, lat: float, lon: float, radius_m: float) -> GlobalWindow:
    """`window` of the LDEM_128 image at `img` (label at `label`), kept for a few points per process."""
    return GlobalWindow(window(open_image(img, label), lat, lon, radius_m))


def global_slope_stats(
    lat: float, lon: float, radius_m: float, img: Path | None = None, label: Path | None = None
):
    """Slope at (lat, lon) and min / max / mean within radius_m on LDEM_128 (docs/methodology.md section
    5.6.1): lss.terrain.slope.slope_stats_lonlat on a window covering the circle, widened east and west for
    the matched east-west baseline at the circle's most poleward latitude. For points off the polar maps; at
    ~237 m pixels these are regional slopes (low fidelity). Memory-maps the 2.1 GB image. Raises near a pole
    (when the window would span every longitude)."""
    from lss.datafiles import BY_ID

    img = img or BY_ID["ldem_128_img"].path
    label = label or BY_ID["ldem_128_lbl"].path
    return image_slope_stats(open_image(img, label), lat, lon, radius_m)


def image_slope_stats(
    image: np.ndarray, lat: float, lon: float, radius_m: float, m: CylindricalMap = LDEM_128
):
    """`global_slope_stats` on an image already open (anything `window` can read)."""
    from lss.terrain.slope import ew_offset_px, slope_stats_lonlat

    poleward = min(abs(lat) + math.degrees(radius_m / MOON_RADIUS_M), 90.0)
    extra = int(min(ew_offset_px(poleward), m.samples)) - 1  # the default margin already holds n = 1
    grid = window(image, lat, lon, radius_m, m, extra_cols=extra)
    return slope_stats_lonlat(grid, lat, lon, radius_m)
