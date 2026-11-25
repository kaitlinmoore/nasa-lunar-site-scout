"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Validation of the first served result (docs/methodology.md section 6). Stages:

  barker   Barker et al. (2021) RoI 4 bound: every 5 m pixel in the RoI 4 outline, 1 m, Sun,
           2024-01-01 to 2026-01-01, averaged over the RoI as in Barker's Table 2 A rows (and C rows).
  barkerring  The same for every pixel outside RoI 4 that touches it: with the inside pixels, a two-sided
           check that the engine puts Barker's 70% contour (the RoI definition) in the same place.
  p69      PGDA product 69 internal pass: observer at 0 m on 60 m terrain, 18.6 years hourly, from two
           start dates, Sun and Earth, at the 5 x 5 product 69 pixels around RoI 4. Never served.
  ridge    Ridge-top check of the served window: the terrain horizon along the Sun's azimuths while it is
           visible, an independent ray scan of the DEMs at those azimuths, and how much of the visibility a
           horizon at the local horizontal would allow.
  accuracy How a horizon error carries into the served metrics: the served scenario rerun with the
           horizon shifted (whole horizon, or only where it is set by terrain under 1 km away).
  summary  Collect the results into tests/engine/fixtures/validation_c1.json (committed; checked against
           the stated tolerances by tests/engine/test_validation_c1.py).

    uv run python scripts/validation_c1.py barker p69 ridge summary

Per-item results go to LSS_DATA_DIR/cache/validation/ as they are made, so an interrupted run resumes where
it stopped (`--fresh` starts over). The barker stage computes 532 horizons and two years of Sun visibility
for each pixel, so it is the long one.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import tarfile
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from lss.config import get_settings
from lss.contract.examples import SCENARIO
from lss.datafiles import get as datafile
from lss.ephem import MOON_RADIUS_M, enu_basis
from lss.horizon import HORIZON_VERSION, cached_horizon
from lss.metrics import comms_metrics, power_metrics, time_mean
from lss.registry.terrain import C1_LAYERS, LAYERS, POLAR_240M, LayerSpec
from lss.series import SERIES_VERSION, SeriesParams, body_visibility, compute_series, ephemeris_sampler
from lss.terrain.core import latlon_from_ps

FORMAT = 1
H, DAY = 3600.0, 86400.0
BARKER = (datetime(2024, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC))
BARKER_STEP_S = 600.0  # internal grid of the area run; checked against 60 s on a subset (GRID_CHECK_EVERY)
GRID_CHECK_EVERY = 50
ROI = 4
# Barker et al. (2021) Table 2, Site 1 RoI 4, z = 1 m, A rows (1st/99th percentiles over 100 DEM clones of
# the RoI-averaged values).
BARKER_A = {"avg_ill_pct_p1": 69.61, "lcip_d_p1": 136.49, "lcsp_d_p99": 13.27}
BARKER_C = {"avg_ill_pct_p1": 86.81, "lcip_d_p1": 232.50, "lcsp_d_p99": 4.58}
# Tolerances, fixed before the run (docs/methodology.md section 6.2).
TOL = {"avg_ill_pct": 1.0, "lcip_d": 2.0, "lcsp_d": 1.0}
# Barker drew each RoI as the connected pixels with average illumination > 70% (1 m, 2024-2025): the two-sided
# contour check (inside >= 70% - t, outside edge neighbours <= 70% + t). t fixed before the full ring run.
CONTOUR_PCT = 70.0
CONTOUR_TOL_PP = 0.5

P69_YEARS = 18.6
P69_STARTS = (datetime(2000, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC))
P69_STEP_S = 3600.0  # product 69: "percentage of [hourly] timesteps"
P69_HALF = 2  # 5 x 5 pixels around the one containing the RoI 4 centroid
P69_TOL_PP = 5.0  # mean |difference| over the 5 x 5 pixels, percentage points (fixed before the run)
# For the rerun on product 69's own terrain (LDEM_85S_060M; scripts/validation_c3.py), at 0 m and 2 m: derived
# BEFORE that run from the half-pixel diagnostic (mean |change|, 9 central pixels x 4 directions = 9.55 pp;
# methodology 6.3).
P69_C3_TOL_PP = 9.6
P69_C3_HEIGHTS_M = (0.0, 2.0)
P69_CLIP = LayerSpec(
    "ldem_60m_site01_clip",
    "pgda_90_south_pole_dems",
    60.0,
    "south",
    (-161_340.0, -162_300.0, 138_720.0, 137_760.0),
    "60 m polar map (validation clip)",
    use_to_m=148_000.0,
)
P69_LAYERS = (P69_CLIP, POLAR_240M)  # 60 m to 148 km, then the 240 m map (beyond the clip)

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "engine" / "fixtures" / "validation_c1.json"

# Qualitative cross-checks read by eye from a 300 dpi render of Barker et al. (2021); not used for tolerances.
# Fig. 15, RoI 4 panel: horizon at 1 m = the higher of the near-field (coloured) and far-field (black) lines,
# every 22.5 deg of the figure's azimuth (about +-0.3 deg reading precision).
FIG15_ROI4 = {
    0.0: -1.9, 22.5: -1.6, 45.0: -0.85, 67.5: -1.5, 90.0: -2.0, 112.5: -2.2, 135.0: -0.9, 157.5: -1.6,
    180.0: -1.7, 202.5: -0.9, 225.0: 0.1, 247.5: 0.15, 270.0: -0.3, 292.5: -1.2, 315.0: -1.9, 337.5: -1.5,
}  # fmt: skip
# Fig. 15, RoI 4 panel, re-read around the two angles where the eye reading above differed from ours by 0.77
# deg (raised by the first correctness review): the far-field (black) line digitised column by column from a
# 1200 dpi render (pixel medians; axes from the panel's gridlines). Far field sets the horizon at all these
# angles.
FIG15_ROI4_DIGITISED = {
    85.0: -0.96, 87.5: -0.95, 90.0: -1.13, 92.5: -1.70, 95.0: -2.00,
    335.0: -2.46, 337.5: -2.32, 342.5: -1.53, 345.0: -1.42,
}  # fmt: skip
# Fig. 19, RoI 4, new (nominal) LDEM, open circles: average illumination, LCIP, LCSP, LCIP start/end months.
FIG19_ROI4 = {
    "avg_ill_pct": 77.5,
    "lcip_d": 192.0,
    "lcsp_d": 10.1,
    "lcip_start": "early Oct",
    "lcip_end": "early Apr",
}


def vdir() -> Path:
    return get_settings().cache_dir / "validation"


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    part.replace(path)


def iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


# ------------------------------------------------------------------ RoI outline (Barker's shapefile)


def roi_polygons() -> list[np.ndarray]:
    """Polygons of Site01_ROIs.shp (PS metres, south pole, true scale at the pole), RoI 1 first."""
    with tarfile.open(datafile("site01_rois").path) as tf:
        prj = tf.extractfile("Site01_ROIs.prj").read().decode()
        shp = tf.extractfile("Site01_ROIs.shp").read()
    if "Stereographic_South_Pole" not in prj or "1737400" not in prj:
        raise ValueError("unexpected RoI projection")
    polys, off = [], 100
    while off < len(shp):
        _, words = struct.unpack(">2i", shp[off : off + 8])
        rec = shp[off + 8 : off + 8 + 2 * words]
        if struct.unpack("<i", rec[:4])[0] != 5:
            raise ValueError("RoI record is not a polygon")
        nparts, npts = struct.unpack("<2i", rec[36:44])
        if nparts != 1:
            raise ValueError("multi-part RoI")
        start = 44 + 4 * nparts
        polys.append(np.array(struct.unpack(f"<{2 * npts}d", rec[start : start + 16 * npts])).reshape(-1, 2))
        off += 8 + 2 * words
    return polys


def _on_boundary(px, py, poly) -> np.ndarray:
    res = np.zeros(px.shape, bool)
    for (x1, y1), (x2, y2) in zip(poly[:-1], poly[1:], strict=True):
        cross = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
        inside_box = (px >= min(x1, x2)) & (px <= max(x1, x2)) & (py >= min(y1, y2)) & (py <= max(y1, y2))
        res |= (np.abs(cross) < 1e-6) & inside_box
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


def roi_pixels(roi: int = ROI) -> np.ndarray:
    """Centres (PS x, y) of the 5 m pixels of an RoI. The outline runs through pixel centres, so the pixels
    are those inside it or on it (RoI 4: 532 pixels = 13,300 m2, Barker's Table 2 area)."""
    poly = roi_polygons()[roi - 1]
    xs = np.arange(poly[:, 0].min(), poly[:, 0].max() + 1.0, 5.0)
    ys = np.arange(poly[:, 1].min(), poly[:, 1].max() + 1.0, 5.0)
    X, Y = np.meshgrid(xs, ys)
    keep = _inside(X, Y, poly) | _on_boundary(X, Y, poly)
    return np.column_stack([X[keep], Y[keep]])


# ------------------------------------------------------------------ helpers


def runs(mask: np.ndarray) -> int:
    """Length of the longest run of True."""
    if not mask.any():
        return 0
    m = np.concatenate([[0], mask.astype(np.int8), [0]])
    d = np.flatnonzero(np.diff(m))
    return int((d[1::2] - d[::2]).max())


def longest_period(periods):
    p = max(periods, key=lambda q: q.duration_s, default=None)
    return p


def sun_visibility(lat, lon, unit_height_m, start, end, step_s, layers=LAYERS, directory=None, horizon=None):
    hz = cached_horizon(lat, lon, unit_height_m, layers=layers, directory=directory)
    obs = hz.observer_radius_m - MOON_RADIUS_M
    horizon_at = horizon or hz.elevation_at
    sample = ephemeris_sampler("SUN", lat, lon, obs, start)
    v = body_visibility(
        sample, horizon_at, (end - start).total_seconds(), True, SeriesParams(grid_step_s=step_s)
    )
    return hz, v


def pixel_stats(v, start: datetime, step_s: float) -> tuple[dict, np.ndarray]:
    k = round(H / step_s)
    hourly = v.grid.fraction[::k][:-1]  # [start, end) at 1 h, as Barker samples
    lcip, lcsp = longest_period(v.visible), longest_period(v.hidden)
    T = float(v.grid.t_s[-1])
    s = {
        "avg_ill_pct_hourly": 100.0 * float(hourly.mean()),
        "avg_ill_pct": 100.0 * time_mean(v.grid.t_s, v.grid.fraction),
        "illumination_fraction": sum(p.duration_s for p in v.visible) / T,
        "lcip_d_hourly": runs(hourly > 0) / 24.0,
        "lcsp_d_hourly": runs(hourly <= 0) / 24.0,
        "lcip_d": lcip.duration_s / DAY if lcip else 0.0,
        "lcsp_d": lcsp.duration_s / DAY if lcsp else 0.0,
        "lcip_start": iso(start + timedelta(seconds=lcip.start_s)) if lcip else None,
        "lcip_end": iso(start + timedelta(seconds=lcip.end_s)) if lcip else None,
        "shadow_periods": len(v.hidden),
    }
    return s, hourly.astype(np.float32)


# ------------------------------------------------------------------ stage: barker


def stage_barker(fresh: bool) -> None:
    out = vdir() / f"roi{ROI}"
    hz_dir = vdir() / f"roi{ROI}_horizons"
    pix = roi_pixels()
    print(f"RoI {ROI}: {len(pix)} pixels, area {25.0 * len(pix):.0f} m2", flush=True)
    t_start = time.monotonic()
    for i, (x, y) in enumerate(pix):
        path = out / f"px_{i:03d}.npz"
        if path.is_file() and not fresh:
            continue
        lat, lon = (float(v) for v in latlon_from_ps(x, y, "south"))
        t0 = time.monotonic()
        hz, v = sun_visibility(lat, lon, 1.0, *BARKER, BARKER_STEP_S, directory=hz_dir)
        s, hourly = pixel_stats(v, BARKER[0], BARKER_STEP_S)
        s.update(i=i, x=float(x), y=float(y), lat=lat, lon=lon, surface_m=hz.surface_height_m)
        if i % GRID_CHECK_EVERY == 0:  # same pixel on the default 60 s grid
            _, v60 = sun_visibility(lat, lon, 1.0, *BARKER, 60.0, directory=hz_dir)
            s["grid60"] = pixel_stats(v60, BARKER[0], 60.0)[0]
        s["seconds"] = round(time.monotonic() - t0, 1)
        out.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part.npz")
        np.savez_compressed(part, hourly=hourly, stats=json.dumps(s))
        part.replace(path)
        done = i + 1
        print(
            f"  px {i:3d}/{len(pix)}  avg {s['avg_ill_pct']:6.2f}%  LCIP {s['lcip_d']:6.1f} d  "
            f"LCSP {s['lcsp_d']:5.1f} d  ({s['seconds']} s; {done} done, {time.monotonic() - t_start:.0f} s)",
            flush=True,
        )


def roi_ring(roi: int = ROI) -> tuple[np.ndarray, np.ndarray]:
    """Pixels outside the RoI that touch it: centres (PS x, y) and whether each shares an edge with it (True)
    or only a corner (False). Barker drew the RoI as the connected pixels above 70%, so an edge neighbour must
    be at most 70% under either connectivity; a corner-only neighbour must be too under 8-connectivity."""
    inside = {(float(x), float(y)) for x, y in roi_pixels(roi)}
    ring: dict[tuple[float, float], bool] = {}
    for x, y in inside:
        for dx in (-5.0, 0.0, 5.0):
            for dy in (-5.0, 0.0, 5.0):
                q = (x + dx, y + dy)
                if q not in inside:
                    ring[q] = ring.get(q, False) or (dx == 0.0 or dy == 0.0)
    keys = sorted(ring)
    return np.array(keys), np.array([ring[k] for k in keys])


def stage_barkerring(fresh: bool) -> None:
    out = vdir() / f"roi{ROI}_ring"
    hz_dir = vdir() / f"roi{ROI}_horizons"
    pix, edge = roi_ring()
    print(f"RoI {ROI}: {len(pix)} outside pixels touch it ({int(edge.sum())} share an edge)", flush=True)
    t_start = time.monotonic()
    for i, (x, y) in enumerate(pix):
        path = out / f"px_{i:03d}.npz"
        if path.is_file() and not fresh:
            continue
        lat, lon = (float(v) for v in latlon_from_ps(x, y, "south"))
        t0 = time.monotonic()
        hz, v = sun_visibility(lat, lon, 1.0, *BARKER, BARKER_STEP_S, directory=hz_dir)
        s, hourly = pixel_stats(v, BARKER[0], BARKER_STEP_S)
        s.update(i=i, x=float(x), y=float(y), edge=bool(edge[i]), lat=lat, lon=lon)
        s["seconds"] = round(time.monotonic() - t0, 1)
        out.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part.npz")
        np.savez_compressed(part, hourly=hourly, stats=json.dumps(s))
        part.replace(path)
        print(
            f"  ring {i:3d}/{len(pix)}  avg {s['avg_ill_pct_hourly']:6.2f}%  edge {bool(edge[i])}  "
            f"({s['seconds']} s; {time.monotonic() - t_start:.0f} s)",
            flush=True,
        )


def contour_summary(inside_pct: list[float]) -> dict:
    """Two-sided check of Barker's 70% contour (methodology section 6.2)."""
    out = vdir() / f"roi{ROI}_ring"
    pix, edge = roi_ring()
    stats = []
    for i in range(len(pix)):
        with np.load(out / f"px_{i:03d}.npz") as z:
            stats.append(json.loads(str(z["stats"])))
    e = [s["avg_ill_pct_hourly"] for s in stats if s["edge"]]
    c = [s["avg_ill_pct_hourly"] for s in stats if not s["edge"]]
    lo, hi = CONTOUR_PCT - CONTOUR_TOL_PP, CONTOUR_PCT + CONTOUR_TOL_PP
    return {
        "contour_pct": CONTOUR_PCT,
        "tolerance_pp": CONTOUR_TOL_PP,
        "inside": {"pixels": len(inside_pct), "min": min(inside_pct), "max": max(inside_pct)},
        "outside_edge": {
            "pixels": len(e),
            "min": min(e),
            "max": max(e),
            "median": float(np.median(e)),
            "above_contour": int(sum(v > CONTOUR_PCT for v in e)),
        },
        "outside_corner_only": {
            "pixels": len(c),
            "min": min(c),
            "max": max(c),
            "above_contour": int(sum(v > CONTOUR_PCT for v in c)),
        },
        "pass": {"inside": min(inside_pct) >= lo, "outside_edge": max(e) <= hi},
    }


def barker_summary() -> dict:
    out = vdir() / f"roi{ROI}"
    pix = roi_pixels()
    stats, hourly = [], []
    for i in range(len(pix)):
        with np.load(out / f"px_{i:03d}.npz") as z:
            stats.append(json.loads(str(z["stats"])))
            hourly.append(z["hourly"])
    Hm = np.vstack(hourly)
    best = Hm.max(axis=0)  # the most illuminated pixel at each hourly step (Barker's C rows)

    def mean(key):
        return float(np.mean([s[key] for s in stats]))

    a_rows = {
        "avg_ill_pct": mean("avg_ill_pct_hourly"),
        "lcip_d": mean("lcip_d_hourly"),
        "lcsp_d": mean("lcsp_d_hourly"),
    }
    engine = {k: mean(k) for k in ("avg_ill_pct", "lcip_d", "lcsp_d", "illumination_fraction")}
    c_rows = {
        "avg_ill_pct": 100.0 * float(best.mean()),
        "lcip_d": runs(best > 0) / 24.0,
        "lcsp_d": runs(best <= 0) / 24.0,
    }
    checks = {
        "avg_ill_pct": a_rows["avg_ill_pct"] >= BARKER_A["avg_ill_pct_p1"] - TOL["avg_ill_pct"],
        "lcip_d": a_rows["lcip_d"] >= BARKER_A["lcip_d_p1"] - TOL["lcip_d"],
        "lcsp_d": a_rows["lcsp_d"] <= BARKER_A["lcsp_d_p99"] + TOL["lcsp_d"],
    }
    grid = [
        {
            "i": s["i"],
            **{
                f"d_{k}": s["grid60"][k] - s[k]
                for k in ("avg_ill_pct", "lcip_d", "lcsp_d", "illumination_fraction", "shadow_periods")
            },
        }
        for s in stats
        if "grid60" in s
    ]
    starts = sorted(s["lcip_start"] for s in stats)
    ends = sorted(s["lcip_end"] for s in stats)
    per_pixel = {
        k: [float(s[k]) for s in stats] for k in ("avg_ill_pct_hourly", "lcip_d_hourly", "lcsp_d_hourly")
    }
    return {
        "period": [iso(t) for t in BARKER],
        "unit_height_m": 1.0,
        "pixels": len(stats),
        "area_m2": 25.0 * len(stats),
        "grid_step_s": BARKER_STEP_S,
        "barker_table2_A": BARKER_A,
        "barker_table2_C": BARKER_C,
        "tolerance": TOL,
        "roi_average_hourly": a_rows,
        "roi_average_engine": engine,
        "most_illuminated_pixel_hourly": c_rows,
        "pass": checks,
        "lcip_start_median": starts[len(starts) // 2],
        "lcip_end_median": ends[len(ends) // 2],
        "pixel_range": {k: [min(v), max(v)] for k, v in per_pixel.items()},
        "pixels_below_70pct": int(sum(v < 70.0 for v in per_pixel["avg_ill_pct_hourly"])),
        "contour_70pct": contour_summary(per_pixel["avg_ill_pct_hourly"]),
        "grid_check_60s_minus_600s": grid,
        "horizon_version": HORIZON_VERSION,
        "series_version": SERIES_VERSION,
    }


# ------------------------------------------------------------------ stage: p69


def p69_pixels():
    """Product 69 pixel centres (PS) and values (fraction) around the RoI 4 centroid: Sun and Earth."""
    import rasterio

    from lss.terrain.core import ps_from_latlon

    loc = SCENARIO.location
    x, y = (float(v) for v in ps_from_latlon(loc.lat, loc.lon, "south"))
    vals = {}
    for body, fid in (("SUN", "p69_sun_85s_60m"), ("EARTH", "p69_earth_85s_60m")):
        with rasterio.open(datafile(fid).path) as d:
            r, c = d.index(x, y)
            win = ((r - P69_HALF, r + P69_HALF + 1), (c - P69_HALF, c + P69_HALF + 1))
            a = d.read(1, window=win).astype(float)
            a = np.where(a == d.nodata, np.nan, a * d.scales[0] + d.offsets[0])
            centres = [
                d.xy(r + dr, c + dc)
                for dr in range(-P69_HALF, P69_HALF + 1)
                for dc in range(-P69_HALF, P69_HALF + 1)
            ]
        vals[body] = a.ravel()
    return np.array(centres, dtype=float), vals


def p69_run(lat, lon, unit_height_m, layers, directory, start, body):
    years = timedelta(days=P69_YEARS * 365.25)
    hz = cached_horizon(lat, lon, unit_height_m, layers=layers, directory=directory)
    obs = hz.observer_radius_m - MOON_RADIUS_M
    sample = ephemeris_sampler(body, lat, lon, obs, start)
    v = body_visibility(
        sample, hz.elevation_at, years.total_seconds(), body == "SUN", SeriesParams(P69_STEP_S)
    )
    steps = v.grid.fraction[:-1]
    return {
        "time_steps_visible": float((steps > 0).mean()),
        "visible_fraction_refined": sum(p.duration_s for p in v.visible) / float(v.grid.t_s[-1]),
        "surface_m": hz.surface_height_m,
    }


def stage_p69(fresh: bool) -> None:
    path = vdir() / "p69.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() and not fresh else {}
    centres, _ = p69_pixels()
    hz_dir = vdir() / "p69_horizons"
    jobs = []
    for i, (x, y) in enumerate(centres):
        lat, lon = (float(v) for v in latlon_from_ps(x, y, "south"))
        for start in P69_STARTS:
            for body in ("SUN", "EARTH"):
                jobs.append((f"px{i:02d}_{start.year}_{body}", lat, lon, 0.0, P69_LAYERS, start, body))
    # Sensitivities at the RoI 4 centroid: the served terrain stack (5 m near field) at 0 m and 1 m.
    loc = SCENARIO.location
    for h in (0.0, 1.0):
        for body in ("SUN", "EARTH"):
            jobs.append(
                (f"served_stack_{h:g}m_2024_{body}", loc.lat, loc.lon, h, LAYERS, P69_STARTS[1], body)
            )
    for key, lat, lon, h, layers, start, body in jobs:
        if key in data:
            continue
        t0 = time.monotonic()
        directory = hz_dir if layers is P69_LAYERS else None
        data[key] = p69_run(lat, lon, h, layers, directory, start, body) | {"lat": lat, "lon": lon}
        data[key]["seconds"] = round(time.monotonic() - t0, 1)
        write_json(path, data)
        print(f"  {key}: {data[key]['time_steps_visible']:.4f} ({data[key]['seconds']} s)", flush=True)


P69_SHIFT_M = 30.0  # half a 60 m pixel


def stage_p69shift(fresh: bool) -> None:
    """Diagnostic added after the product 69 Sun comparison missed its tolerance (stated as such in
    methodology section 6.3): how much our 0 m Sun value moves when the observer moves half a pixel
    (30 m) in each map direction, at the 3 x 3 central pixels, 2024 start. The 60 m terrain we use is a
    later, orbit-adjusted map than product 69's, so features can sit tens of metres apart."""
    path = vdir() / "p69shift.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() and not fresh else {}
    centres, _ = p69_pixels()
    n = 2 * P69_HALF + 1
    for i, (x, y) in enumerate(centres):
        r, c = divmod(i, n)
        if abs(r - P69_HALF) > 1 or abs(c - P69_HALF) > 1:
            continue
        for dx, dy in ((P69_SHIFT_M, 0.0), (-P69_SHIFT_M, 0.0), (0.0, P69_SHIFT_M), (0.0, -P69_SHIFT_M)):
            key = f"px{i:02d}_{dx:+g}_{dy:+g}"
            if key in data:
                continue
            lat, lon = (float(v) for v in latlon_from_ps(x + dx, y + dy, "south"))
            data[key] = p69_run(lat, lon, 0.0, P69_LAYERS, vdir() / "p69_horizons", P69_STARTS[1], "SUN")
            write_json(path, data)
            print(f"  {key}: {data[key]['time_steps_visible']:.4f}", flush=True)


def p69shift_summary() -> dict | None:
    path = vdir() / "p69shift.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    p69 = json.loads((vdir() / "p69.json").read_text(encoding="utf-8"))
    centres, vals = p69_pixels()
    rows = []
    for i in sorted({int(k[2:4]) for k in data}):
        shifted = [100.0 * v["time_steps_visible"] for k, v in data.items() if k.startswith(f"px{i:02d}_")]
        here = 100.0 * p69[f"px{i:02d}_2024_SUN"]["time_steps_visible"]
        ref = 100.0 * float(vals["SUN"][i])
        lo, hi = min(shifted + [here]), max(shifted + [here])
        rows.append(
            {
                "pixel": i,
                "product69_pct": ref,
                "ours_pct": here,
                "ours_shifted_pct": [round(v, 2) for v in shifted],
                "max_change_pp": max(abs(v - here) for v in shifted),
                "product69_within_shift_range": bool(lo <= ref <= hi),
            }
        )
    # Every (pixel, direction) change: the basis of the rerun's tolerance (methodology section 6.3).
    changes = np.array(
        [
            100.0 * v["time_steps_visible"] - r["ours_pct"]
            for r in rows
            for k, v in data.items()
            if k.startswith(f"px{r['pixel']:02d}_")
        ]
    )
    return {
        "shift_m": P69_SHIFT_M,
        "rows": rows,
        "median_max_change_pp": float(np.median([r["max_change_pp"] for r in rows])),
        "mean_abs_change_pp": float(np.abs(changes).mean()),
        "mean_change_pp": float(changes.mean()),
        "pixels_with_product69_within_shift_range": sum(r["product69_within_shift_range"] for r in rows),
    }


def p69_summary() -> dict:
    data = json.loads((vdir() / "p69.json").read_text(encoding="utf-8"))
    centres, vals = p69_pixels()
    out = {
        "years": P69_YEARS,
        "starts": [iso(t) for t in P69_STARTS],
        "step_s": P69_STEP_S,
        "observer_m": 0.0,
        "terrain": "LDEM_60S_60MPP_ADJ (60 m) to 148 km, LDEM_60S_240MPP_ADJ (240 m) to 400 km",
        "tolerance_mean_abs_pp": P69_TOL_PP,
        "pixel_centres_ps_m": centres.tolist(),
    }
    for body in ("SUN", "EARTH"):
        ours = {
            s.year: [data[f"px{i:02d}_{s.year}_{body}"]["time_steps_visible"] for i in range(len(centres))]
            for s in P69_STARTS
        }
        a, b = (np.array(ours[s.year]) for s in P69_STARTS)
        mean_ours = 0.5 * (a + b)
        ref = vals[body]
        ok = np.isfinite(ref)
        diff = 100.0 * (mean_ours - ref)
        nonzero = ok & (vals["SUN"] > 0) & (vals["EARTH"] > 0)
        centre = len(centres) // 2
        out[body] = {
            "product69_pct": (100.0 * ref).round(2).tolist(),
            "ours_pct_by_start": {
                str(s.year): (100.0 * np.array(ours[s.year])).round(2).tolist() for s in P69_STARTS
            },
            "start_date_spread_pp_max": float(100.0 * np.abs(a - b).max()),
            "diff_pp": diff.round(2).tolist(),
            "mean_diff_pp": float(diff[ok].mean()),
            "mean_abs_diff_pp": float(np.abs(diff[ok]).mean()),
            "correlation": float(np.corrcoef(mean_ours[ok], ref[ok])[0, 1]),
            # Diagnostic requested after the miss (the project author, 2026-11-15), not a re-test: the same
            # statistics without product 69's pixel(s) that read exactly 0 in both its Sun and Earth maps (an
            # artefact).
            "diagnostic_zero_pixel_excluded": {
                "pixels_excluded": int((ok & ~nonzero).sum()),
                "mean_diff_pp": float(diff[nonzero].mean()),
                "mean_abs_diff_pp": float(np.abs(diff[nonzero]).mean()),
                "correlation": float(np.corrcoef(mean_ours[nonzero], ref[nonzero])[0, 1]),
            },
            "centre_pixel": {
                "product69_pct": float(100.0 * ref[centre]),
                "ours_pct": float(100.0 * mean_ours[centre]),
            },
            "served_stack_roi4_centroid_pct": {
                f"{h:g}m": 100.0 * data[f"served_stack_{h:g}m_2024_{body}"]["time_steps_visible"]
                for h in (0.0, 1.0)
            },
            "pass": bool(np.abs(diff[ok]).mean() <= P69_TOL_PP),
        }
    return out


# ------------------------------------------------------------------ stage: ridge


def _destination(lat, lon, az_deg, dist_m):
    """Great-circle destination on the sphere (independent of lss.horizon's ray construction)."""
    p1, l1, th = np.radians(lat), np.radians(lon), np.radians(az_deg)
    d = np.asarray(dist_m) / MOON_RADIUS_M
    p2 = np.arcsin(np.sin(p1) * np.cos(d) + np.cos(p1) * np.sin(d) * np.cos(th))
    l2 = l1 + np.arctan2(np.sin(th) * np.sin(d) * np.cos(p1), np.cos(d) - np.sin(p1) * np.sin(p2))
    return np.degrees(p2), np.degrees(l2)


class _Dem:
    """A DEM read with rasterio and sampled bilinearly here (not through lss.terrain)."""

    def __init__(self, path):
        import rasterio

        with rasterio.open(path) as d:
            self.a = d.read(1)  # float32, NaN no-data
            t = d.transform
            self.x0, self.y0, self.res = t.c, t.f, t.a

    def height(self, lat, lon):
        rho = 2.0 * MOON_RADIUS_M * np.tan(np.pi / 4.0 + np.radians(lat) / 2.0)  # south polar stereographic
        x, y = rho * np.sin(np.radians(lon)), rho * np.cos(np.radians(lon))
        c = (x - self.x0) / self.res - 0.5
        r = (self.y0 - y) / self.res - 0.5
        c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int)
        fc, fr = c - c0, r - r0
        a = self.a
        return (
            a[r0, c0] * (1 - fc) * (1 - fr)
            + a[r0, c0 + 1] * fc * (1 - fr)
            + a[r0 + 1, c0] * (1 - fc) * fr
            + a[r0 + 1, c0 + 1] * fc * fr
        )


def independent_horizon(lat, lon, observer_radius_m, azimuths, dems):
    """Max elevation angle of the terrain along each azimuth, from 3-D vectors, with the same layer split as
    the served stack (5 m to 5 km, 80 m to 100 km, 240 m to 400 km)."""
    d = np.concatenate(
        [np.arange(1.0, 5_000.0, 1.0), np.arange(5_000.0, 100_000.0, 20.0), np.arange(1e5, 4e5, 60.0)]
    )
    which = np.where(d < 5_000.0, 0, np.where(d < 100_000.0, 1, 2))
    up = enu_basis(lat, lon)[2]
    obs = observer_radius_m * up
    out = []
    for az in azimuths:
        plat, plon = _destination(lat, lon, az, d)
        h = np.empty(d.size)
        for k, dem in enumerate(dems):
            m = which == k
            h[m] = dem.height(plat[m], plon[m])
        pr, pl = np.radians(plat), np.radians(plon)
        p = (MOON_RADIUS_M + h)[:, None] * np.column_stack(
            [np.cos(pr) * np.cos(pl), np.cos(pr) * np.sin(pl), np.sin(pr)]
        )
        v = p - obs
        el = np.degrees(np.arcsin((v @ up) / np.linalg.norm(v, axis=1)))
        j = int(np.nanargmax(el))
        out.append((float(el[j]), float(d[j])))
    return out


# ------------------------------------------------------------------ stage: accuracy


ACC_WHOLE_DEG = (-0.2, -0.1, -0.05, -0.01, 0.01, 0.05, 0.1, 0.2)  # whole-horizon shifts
ACC_NEAR_M, ACC_NEAR_DEG = 1000.0, (-0.2, 0.2)  # only azimuths whose horizon is set by terrain this close
# Barker et al. (2021) section 4: median RMS height error of the 5 m site map over 100 clones (MADb 0.15 m).
BARKER_RMS_Z_M = 0.37


def _metrics_with(base, hz):
    """The served scenario's metrics with another horizon (same ephemeris, grid and observer)."""
    dur = base.duration_s
    bodies = {}
    for name, limb in (("SUN", True), ("EARTH", False)):
        sample = ephemeris_sampler(name, base.lat, base.lon, base.observer_height_m, base.window_start)
        bodies[name] = body_visibility(sample, hz.elevation_at, dur, limb, base.params)
    res = replace(base, horizon=hz, sun=bodies["SUN"], earth=bodies["EARTH"])
    p, c = power_metrics(res), comms_metrics(res)
    return {
        "illumination_fraction": p.illumination_fraction,
        "mean_visible_disk_fraction": p.mean_visible_disk_fraction,
        "shadow_count": p.shadow_count,
        "longest_shadow_h": p.longest_shadow_h,
        "longest_sunlit_period_h": p.longest_sunlit_period_h,
        "time_to_sunset_h": p.time_to_sunset_h,
        "shadow_periods_h": sorted((q.duration_s / H for q in res.sun.hidden), reverse=True),
        "earth_visibility_fraction": c.earth_visibility_fraction,
        "earth_full_disc_fraction": c.earth_full_disc_fraction,
        "longest_earth_gap_h": c.longest_earth_gap_h,
        "sun_earth_overlap_fraction": c.sun_earth_overlap_fraction,
    }


def stage_accuracy(fresh: bool) -> None:
    """How a horizon error carries into the served metrics (methodology sections 3.2 and 6.6)."""
    path = vdir() / "accuracy.json"
    if path.is_file() and not fresh:
        return
    base = compute_series(SCENARIO)
    hz = base.horizon
    near = hz.distance_m < ACC_NEAR_M
    cases = [{"case": "served", "shift_deg": 0.0, "azimuths": "none"}]
    cases += [{"case": f"whole {d:+.2f}", "shift_deg": d, "azimuths": "all"} for d in ACC_WHOLE_DEG]
    cases += [
        {"case": f"near {d:+.2f}", "shift_deg": d, "azimuths": f"horizon set < {ACC_NEAR_M:.0f} m away"}
        for d in ACC_NEAR_DEG
    ]
    for c in cases:
        mask = near if c["azimuths"].startswith("horizon") else np.ones_like(near)
        hz2 = replace(hz, elevation_deg=hz.elevation_deg + c["shift_deg"] * mask)
        c.update(_metrics_with(base, hz2))
        print(
            f"  {c['case']:12s} illum {100 * c['illumination_fraction']:6.2f}%  "
            f"disc {100 * c['mean_visible_disk_fraction']:6.2f}%  shadows {c['shadow_count']}  "
            f"longest {c['longest_shadow_h']:7.2f} h  earth {100 * c['earth_visibility_fraction']:6.2f}%  "
            f"gap {c['longest_earth_gap_h']:7.2f} h",
            flush=True,
        )
    # What sets the horizon, and how much of the time the result depends on it.
    d = hz.distance_m
    res_m = hz.params.azimuth_step_deg
    out = {"cases": cases, "near_m": ACC_NEAR_M, "barker_rms_z_m": BARKER_RMS_Z_M}
    out["horizon_distance_share"] = {
        "lt_100m": float((d < 100.0).mean()),
        "lt_1km": float((d < 1000.0).mean()),
        "gt_5km": float((d > 5000.0).mean()),
    }
    for name, body in (("SUN", base.sun), ("EARTH", base.earth)):
        g = body.grid
        part = (g.fraction > 0) & (g.fraction < 1)
        idx = np.round(g.azimuth_deg / res_m).astype(int) % d.size
        out[name] = {
            "time_partly_visible": float(part.mean()),
            "partly_visible_horizon_lt_100m": float((d[idx][part] < 100.0).mean()) if part.any() else 0.0,
            "partly_visible_horizon_lt_1km": float((d[idx][part] < 1000.0).mean()) if part.any() else 0.0,
        }
    # Horizon change from a height error of Barker's median RMS at the terrain's distance.
    out["horizon_change_deg_for_rms_z"] = {
        f"{r:.0f}m": float(np.degrees(np.arctan(BARKER_RMS_Z_M / r))) for r in (50.0, 100.0, 1000.0, 50_000.0)
    }
    write_json(path, out)


def stage_ridge(fresh: bool) -> None:
    path = vdir() / "ridge.json"
    if path.is_file() and not fresh:
        return
    res = compute_series(SCENARIO)
    g, hz = res.sun.grid, res.horizon
    vis = g.fraction > 0
    upper = g.elevation_deg + g.radius_deg
    sectors = []
    for a0 in range(0, 360, 30):
        m = vis & (g.azimuth_deg >= a0) & (g.azimuth_deg < a0 + 30)
        if not m.any():
            sectors.append({"az": [a0, a0 + 30], "visible_h": 0.0})
            continue
        idx = np.round(g.azimuth_deg[m] / hz.params.azimuth_step_deg).astype(int) % hz.azimuth_deg.size
        dist = hz.distance_m[idx] / 1000.0
        sectors.append(
            {
                "az": [a0, a0 + 30],
                "visible_h": float(m.sum() * res.params.grid_step_s / H),
                "sun_centre_el": [float(g.elevation_deg[m].min()), float(g.elevation_deg[m].max())],
                "horizon_el": [float(g.horizon_deg[m].min()), float(g.horizon_deg[m].max())],
                "horizon_distance_km": [float(dist.min()), float(dist.max())],
            }
        )
    # Independent ray scan at the Sun's azimuths while visible, every 5 deg of azimuth visited.
    az_vis = np.unique(np.round(g.azimuth_deg[vis] / 5.0) * 5.0 % 360.0)
    dems = [_Dem(spec.dem().path) for spec in C1_LAYERS]
    ind = independent_horizon(res.lat, res.lon, hz.observer_radius_m, az_vis, dems)
    scan = [
        {
            "az": float(a),
            "engine_el": float(hz.elevation_at(a)),
            "independent_el": e,
            "independent_distance_km": dk / 1000.0,
        }
        for a, (e, dk) in zip(az_vis, ind, strict=True)
    ]
    # Visibility a horizon at the local horizontal would allow (no terrain, no curvature dip).
    flat_window = float((upper > 0).mean())
    lat, lon = res.lat, res.lon
    _, vb = sun_visibility(
        lat, lon, 1.0, *BARKER, BARKER_STEP_S, horizon=lambda az: np.zeros_like(np.asarray(az, float))
    )
    flat_barker = pixel_stats(vb, BARKER[0], BARKER_STEP_S)[0]
    long_start = P69_STARTS[1]
    long_end = long_start + timedelta(days=P69_YEARS * 365.25)
    _, vl = sun_visibility(
        lat, lon, 1.0, long_start, long_end, H, horizon=lambda az: np.zeros_like(np.asarray(az, float))
    )
    _, vr = sun_visibility(lat, lon, 1.0, long_start, long_end, H)
    pm = power_metrics(res)
    h_obs = hz.observer_radius_m - MOON_RADIUS_M
    data = {
        "scenario_key": SCENARIO.key(),
        "observer_height_m": h_obs,
        "sphere_dip_deg": -float(np.degrees(np.arccos(MOON_RADIUS_M / hz.observer_radius_m))),
        "horizon_range_deg": [float(hz.elevation_deg.min()), float(hz.elevation_deg.max())],
        "illumination_fraction": pm.illumination_fraction,
        "sun_centre_el_all": [float(g.elevation_deg.min()), float(g.elevation_deg.max())],
        "while_visible": {
            "hours": float(vis.sum() * res.params.grid_step_s / H),
            "sun_centre_el": [float(g.elevation_deg[vis].min()), float(g.elevation_deg[vis].max())],
            "sun_upper_limb_el": [float(upper[vis].min()), float(upper[vis].max())],
            "horizon_el": [float(g.horizon_deg[vis].min()), float(g.horizon_deg[vis].max())],
            "upper_limb_clearance_deg": [
                float((upper - g.horizon_deg)[vis].min()),
                float((upper - g.horizon_deg)[vis].max()),
            ],
            "share_with_upper_limb_below_horizontal": float((upper[vis] < 0).mean()),
        },
        "sectors": sectors,
        "independent_scan": scan,
        "independent_scan_max_abs_diff_deg": float(
            max(abs(s["engine_el"] - s["independent_el"]) for s in scan)
        ),
        "horizon_every_22_5_deg": {f"{a:g}": float(hz.elevation_at(a)) for a in np.arange(0.0, 360.0, 22.5)},
        "flat_horizontal_horizon": {
            "served_window_time_any_part": flat_window,
            "barker_period_avg_ill_pct": flat_barker["avg_ill_pct"],
            "barker_period_time_any_part": flat_barker["illumination_fraction"],
            "years_18_6_from_2024_time_any_part": sum(p.duration_s for p in vl.visible)
            / float(vl.grid.t_s[-1]),
        },
        "real_horizon_18_6_years_from_2024_time_any_part": sum(p.duration_s for p in vr.visible)
        / float(vr.grid.t_s[-1]),
    }
    write_json(path, data)
    print(json.dumps({k: v for k, v in data.items() if k not in ("sectors", "independent_scan")}, indent=1))


# ------------------------------------------------------------------ summary


def fig15_table() -> dict:
    """Our served horizon at the azimuths of Barker's Fig. 15 RoI 4 panel.

    Barker's figure angle a is measured counter-clockwise from the polar stereographic map's +x axis; in our
    convention (clockwise from local north) that direction is az = (90 - lon) - a. This mapping was found by
    matching the profile's shape and then derived from the projection; under it the profiles agree.
    """
    loc = SCENARIO.location
    hz = cached_horizon(loc.lat, loc.lon, SCENARIO.unit_height_m)

    def table(values):
        rows = []
        for a, read in values.items():
            az = (90.0 - loc.lon - a) % 360.0
            i = round(az / hz.params.azimuth_step_deg) % hz.azimuth_deg.size
            rows.append(
                {
                    "figure_angle_deg": a,
                    "our_azimuth_deg": az,
                    "figure_read_el_deg": read,
                    "ours_el_deg": float(hz.elevation_at(az)),
                    "ours_distance_km": float(hz.distance_m[i] / 1000.0),
                }
            )
        d = np.array([r["ours_el_deg"] - r["figure_read_el_deg"] for r in rows])
        return {
            "rows": rows,
            "median_abs_diff_deg": float(np.median(np.abs(d))),
            "max_abs_diff_deg": float(np.abs(d).max()),
        }

    return table(FIG15_ROI4) | {"digitised_near_outliers": table(FIG15_ROI4_DIGITISED)}


def stage_summary(_fresh: bool) -> None:
    ridge = json.loads((vdir() / "ridge.json").read_text(encoding="utf-8"))
    ridge["barker_fig15_roi4"] = fig15_table()
    s = {
        "format": FORMAT,
        "generated_by": "scripts/validation_c1.py",
        "scenario_key": SCENARIO.key(),
        "barker_roi4": barker_summary() | {"fig19_read_nominal": FIG19_ROI4},
        "product69": p69_summary() | {"diagnostic_half_pixel_shift": p69shift_summary()},
        "ridge_top": ridge,
        "served_accuracy": json.loads((vdir() / "accuracy.json").read_text(encoding="utf-8")),
    }
    write_json(FIXTURE, s)
    write_json(vdir() / "validation_c1.json", s)
    b, p = s["barker_roi4"], s["product69"]
    print("Barker RoI 4 A (hourly):", b["roi_average_hourly"], "pass", b["pass"])
    print("Barker RoI 4 C:", b["most_illuminated_pixel_hourly"])
    for body in ("SUN", "EARTH"):
        print(
            f"p69 {body}: mean diff {p[body]['mean_diff_pp']:.2f} pp, "
            f"mean |diff| {p[body]['mean_abs_diff_pp']:.2f} pp, "
            f"r {p[body]['correlation']:.2f}, centre {p[body]['centre_pixel']}, pass {p[body]['pass']}"
        )
    print(f"written {FIXTURE}")


STAGES = {
    "barker": stage_barker,
    "barkerring": stage_barkerring,
    "p69": stage_p69,
    "p69shift": stage_p69shift,
    "ridge": stage_ridge,
    "accuracy": stage_accuracy,
    "summary": stage_summary,
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("stages", nargs="+", choices=list(STAGES))
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args(argv)
    for name in a.stages:
        print(f"== {name}", flush=True)
        STAGES[name](a.fresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
