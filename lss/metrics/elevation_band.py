"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Time histogram of the Sun's elevation, for "fraction of the window with the Sun's elevation in [a, b]"
(C api's request RA7; docs/methodology.md section 5.3).

- **Quantity:** the apparent elevation of the Sun's disc centre above the local horizontal plane
  (section 2), the same quantity as `PowerMetrics.sun_elevation_deg`. No atmospheric refraction (the Moon has
  none). It does not depend on the terrain: a band can include times when the Sun is hidden.
- **Histogram:** the seconds the elevation spends in each bin
  [first_edge + k * bin, first_edge + (k + 1) * bin) over the window, from the 60 s internal grid with the
  elevation taken as linear between grid points (each interval's time is split across the bins it passes
  through). The seconds sum to the window length.
- **Band fraction:** the summed seconds of the bins inside [a, b] divided by the window length. It is exact
  for the piecewise-linear track when a and b are bin edges; otherwise the end bins are prorated linearly,
  as if their time were spread evenly across the bin.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BIN_DEG = 0.1
_CHUNK = 200_000


@dataclass(frozen=True)
class ElevationHistogram:
    bin_deg: float
    first_edge_deg: float
    seconds: np.ndarray  # one value per bin
    total_seconds: float

    def to_json(self) -> dict:
        return {
            "quantity": "Sun disc-centre apparent elevation above the local horizontal, deg (no refraction)",
            "bin_deg": self.bin_deg,
            "first_edge_deg": self.first_edge_deg,
            "seconds": [round(float(s), 3) for s in self.seconds],
            "total_seconds": self.total_seconds,
        }


def _time_below(t_s: np.ndarray, el: np.ndarray, levels: np.ndarray) -> np.ndarray:
    """Seconds with elevation < each level, for the piecewise-linear track through (t_s, el)."""
    out = np.zeros(levels.size)
    for i in range(0, t_s.size - 1, _CHUNK):
        sl = slice(i, min(i + _CHUNK, t_s.size - 1))
        e0, e1 = el[sl], el[sl.start + 1 : sl.stop + 1]
        dt = np.diff(t_s[sl.start : sl.stop + 1])
        de = e1 - e0
        flat = de == 0.0
        safe = np.where(flat, 1.0, de)
        u = (levels[:, None] - e0[None, :]) / safe[None, :]
        frac = np.where(de[None, :] > 0, np.clip(u, 0.0, 1.0), 1.0 - np.clip(u, 0.0, 1.0))
        frac = np.where(flat[None, :], (e0[None, :] < levels[:, None]).astype(float), frac)
        out += (frac * dt[None, :]).sum(axis=1)
    return out


def elevation_histogram(t_s: np.ndarray, el_deg: np.ndarray, bin_deg: float = BIN_DEG) -> ElevationHistogram:
    t_s, el = np.asarray(t_s, float), np.asarray(el_deg, float)
    lo = np.floor(el.min() / bin_deg) * bin_deg
    n = int(np.ceil((el.max() - lo) / bin_deg - 1e-9)) + 1
    edges = lo + bin_deg * np.arange(n + 1)
    below = _time_below(t_s, el, edges)
    total = float(t_s[-1] - t_s[0])
    return ElevationHistogram(bin_deg, round(float(lo), 6), np.diff(below), total)


def band_seconds(h: ElevationHistogram | dict, a_deg: float, b_deg: float) -> float:
    """Seconds with elevation in [a, b] (end bins prorated linearly)."""
    if isinstance(h, dict):
        h = ElevationHistogram(
            h["bin_deg"], h["first_edge_deg"], np.asarray(h["seconds"], float), h["total_seconds"]
        )
    if b_deg < a_deg:
        raise ValueError("b_deg must be >= a_deg")
    lo = h.first_edge_deg + h.bin_deg * np.arange(h.seconds.size)
    hi = lo + h.bin_deg
    overlap = np.clip(np.minimum(hi, b_deg) - np.maximum(lo, a_deg), 0.0, None) / h.bin_deg
    return float((overlap * h.seconds).sum())


def band_fraction(h: ElevationHistogram | dict, a_deg: float, b_deg: float) -> float:
    total = h.total_seconds if isinstance(h, ElevationHistogram) else h["total_seconds"]
    return band_seconds(h, a_deg, b_deg) / total
