"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Barker et al. (2021) regions of interest (RoIs), from the PGDA product 78 shapefile archives
(`SiteXX_ROIs.tgz`).

Barker drew each RoI as the connected 5 m pixels ("corners or sides touching") with average illumination above
70% at 1 m over 2024-2025, total area above 2500 m2. The outlines run through pixel centres, so an RoI is the
pixels inside its outline or on it. Its centroid is the centre of the 5 m pixel that contains the mean of
those pixel centres: Barker's tabulated centroids are pixel centres, and this rule reproduces all seven at
Site01 (Table 2) exactly. Areas: 6 of the 7 Site01 RoIs match Table 2 exactly; RoI 2 has two pixels more
(7,600 vs 7,550 m2).
"""

from __future__ import annotations

import struct
import tarfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PIXEL_M = 5.0


@dataclass(frozen=True)
class Roi:
    number: int  # 1-based, in file order (Barker's numbering at Site01)
    outline: np.ndarray  # (n, 2) PS metres, south pole
    pixels: np.ndarray  # (m, 2) centres of the 5 m pixels inside or on the outline

    @property
    def area_m2(self) -> float:
        return PIXEL_M * PIXEL_M * len(self.pixels)

    @property
    def mean_ps(self) -> tuple[float, float]:
        x, y = self.pixels.mean(axis=0)
        return float(x), float(y)

    @property
    def centroid_ps(self) -> tuple[float, float]:
        """Centre of the pixel containing the mean (Barker's convention; pixel centres at 2.5 m + 5 m n)."""
        x, y = self.mean_ps
        return snap(x), snap(y)


def snap(v: float) -> float:
    return float(np.floor(v / PIXEL_M) * PIXEL_M + PIXEL_M / 2.0)


def read_outlines(archive: Path) -> list[np.ndarray]:
    """Polygons of the archive's shapefile (PS metres; south polar stereographic on the 1737.4 km sphere)."""
    stem = archive.name.removesuffix(".tgz")
    with tarfile.open(archive) as tf:
        prj = tf.extractfile(f"{stem}.prj").read().decode()
        shp = tf.extractfile(f"{stem}.shp").read()
    if "Stereographic_South_Pole" not in prj or "1737400" not in prj:
        raise ValueError(f"{archive.name}: unexpected RoI projection")
    polys, off = [], 100
    while off < len(shp):
        _, words = struct.unpack(">2i", shp[off : off + 8])
        rec = shp[off + 8 : off + 8 + 2 * words]
        if struct.unpack("<i", rec[:4])[0] != 5:
            raise ValueError(f"{archive.name}: RoI record is not a polygon")
        nparts, npts = struct.unpack("<2i", rec[36:44])
        if nparts != 1:
            raise ValueError(f"{archive.name}: multi-part RoI")
        start = 44 + 4 * nparts
        polys.append(np.array(struct.unpack(f"<{2 * npts}d", rec[start : start + 16 * npts])).reshape(-1, 2))
        off += 8 + 2 * words
    return polys


def _on_boundary(px, py, poly) -> np.ndarray:
    res = np.zeros(px.shape, bool)
    for (x1, y1), (x2, y2) in zip(poly[:-1], poly[1:], strict=True):
        cross = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
        box = (px >= min(x1, x2)) & (px <= max(x1, x2)) & (py >= min(y1, y2)) & (py <= max(y1, y2))
        res |= (np.abs(cross) < 1e-6) & box
    return res


def _inside(px, py, poly) -> np.ndarray:
    x, y = poly[:, 0], poly[:, 1]
    res = np.zeros(px.shape, bool)
    j = len(x) - 1
    for i in range(len(x)):
        with np.errstate(divide="ignore", invalid="ignore"):
            xc = (x[j] - x[i]) * (py - y[i]) / (y[j] - y[i]) + x[i]
        res ^= ((y[i] > py) != (y[j] > py)) & (px < xc)
        j = i
    return res


def outline_pixels(poly: np.ndarray) -> np.ndarray:
    xs = np.arange(poly[:, 0].min(), poly[:, 0].max() + 1.0, PIXEL_M)
    ys = np.arange(poly[:, 1].min(), poly[:, 1].max() + 1.0, PIXEL_M)
    X, Y = np.meshgrid(xs, ys)
    keep = _inside(X, Y, poly) | _on_boundary(X, Y, poly)
    return np.column_stack([X[keep], Y[keep]])


def read_rois(archive: Path) -> list[Roi]:
    return [Roi(k, p, outline_pixels(p)) for k, p in enumerate(read_outlines(archive), start=1)]


def largest(rois: list[Roi]) -> Roi:
    """The RoI with the most area (ties: the lower number)."""
    return max(rois, key=lambda r: (r.area_m2, -r.number))
