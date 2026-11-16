"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

C3 validation (docs/methodology.md section 6.3). Stages:

  p69      PGDA product 69 rerun on a stand-in for product 69's own terrain. The map product 69's label
           names (LDEM_85S_060M, 2016) is not public; the PDS LOLA map LDEM_75S_60M (V2.0, 2017) is used
           instead, stated as a stand-in (Kaitlin, 2026-11-15). It lies on the same 60 m pixel grid as
           product 69. Same 25 pixels, quantity and two start dates as the C1 pass, at 0 m and 2 m, because
           product 69's observer height is not stated. Never served.
  nearfield10m  What a 10 m near field (PGDA product 90, LDEM_83S_10MPP_ADJ, to 83 S) costs and loses against
           the 5 m site map, at the served Site01 point: the same scenario with the 10 m map in place of the
           5 m tile (same hand-over at 5 km), horizon and metrics compared, horizon time measured. For the
           decision to use 10 m beyond the 5 m maps (Kaitlin, 2026-11-15: measure data and compute cost).
  roisites At Site04, 07 and 11, every 5th pixel of every Barker RoI (1 m, 2024-2025): the RoI definition
           (pixels > 70%), per-RoI averages for the supplement's box plots (read from figures), and the
           largest RoI's centroid, also at 5 m (LCIP; Barker's text: ~150-175 d).
  mazarico At the 8 Mazarico et al. (2011) Table 3 points of the curated sites: average illumination and
           visibility at 0 m and 10 m, 1970 + 74.4 yr at 6 h, on the 240 m map; tolerance from 120 m shifts.
  summary  Collect the results into tests/engine/fixtures/validation_c3.json (committed; checked by
           tests/engine/test_validation_c3.py).

    uv run python scripts/validation_c3.py p69 summary

Tolerances were fixed before the run: Sun mean |difference| <= 9.6 pp at either height, derived from the C1
half-pixel diagnostic (validation_c1.P69_C3_TOL_PP); Earth <= 5 pp, as in C1. Results resume per item from
LSS_DATA_DIR/cache/validation/p69c3.json.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

from lss.registry.terrain import POLAR_80M, POLAR_240M, SITE01_TILE, LayerSpec
from lss.terrain.core import latlon_from_ps

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "engine" / "fixtures" / "validation_c3.json"


def _c1():
    spec = importlib.util.spec_from_file_location("validation_c1", ROOT / "scripts" / "validation_c1.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C1 = _c1()

STANDIN_CLIP = LayerSpec(
    "ldem_75s_60m_site01_clip",
    "pds_lola_gdr",
    60.0,
    "south",
    (-161_340.0, -162_300.0, 138_720.0, 137_760.0),
    "60 m PDS LOLA polar map (validation stand-in)",
    use_to_m=148_000.0,
)
STANDIN_LAYERS = (STANDIN_CLIP, POLAR_240M)  # 60 m to 148 km, then the 240 m map
HEIGHTS_M = C1.P69_C3_HEIGHTS_M  # (0, 2): product 69's observer height is not stated
SUN_TOL_PP = C1.P69_C3_TOL_PP  # 9.6, derived before this run (methodology 6.3)
EARTH_TOL_PP = C1.P69_TOL_PP  # 5.0, as in C1
BODIES = ("SUN", "EARTH")


def results_path() -> Path:
    return C1.vdir() / "p69c3.json"


def stage_p69(fresh: bool) -> None:
    path = results_path()
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() and not fresh else {}
    centres, _ = C1.p69_pixels()
    hz_dir = C1.vdir() / "p69c3_horizons"
    t_start = time.monotonic()
    for h in HEIGHTS_M:
        for i, (x, y) in enumerate(centres):
            lat, lon = (float(v) for v in latlon_from_ps(x, y, "south"))
            for start in C1.P69_STARTS:
                for body in BODIES:
                    key = f"{h:g}m_px{i:02d}_{start.year}_{body}"
                    if key in data:
                        continue
                    t0 = time.monotonic()
                    r = C1.p69_run(lat, lon, h, STANDIN_LAYERS, hz_dir, start, body)
                    data[key] = r | {"lat": lat, "lon": lon, "seconds": round(time.monotonic() - t0, 1)}
                    C1.write_json(path, data)
                    print(
                        f"  {key}: {r['time_steps_visible']:.4f} ({data[key]['seconds']} s; "
                        f"{time.monotonic() - t_start:.0f} s)",
                        flush=True,
                    )


def _stats(ours: np.ndarray, ref: np.ndarray, keep: np.ndarray) -> dict:
    d = 100.0 * (ours - ref)
    return {
        "mean_diff_pp": float(d[keep].mean()),
        "mean_abs_diff_pp": float(np.abs(d[keep]).mean()),
        "correlation": float(np.corrcoef(ours[keep], ref[keep])[0, 1]),
    }


def summary() -> dict:
    data = json.loads(results_path().read_text(encoding="utf-8"))
    c1 = json.loads((C1.vdir() / "p69.json").read_text(encoding="utf-8"))
    centres, vals = C1.p69_pixels()
    n = len(centres)
    ok = np.isfinite(vals["SUN"]) & np.isfinite(vals["EARTH"])
    nonzero = ok & (vals["SUN"] > 0) & (vals["EARTH"] > 0)
    out = {
        "terrain": "LDEM_75S_60M (PDS LOLA GDR V2.0, 60 m; stand-in for LDEM_85S_060M) to 148 km, "
        "LDEM_60S_240MPP_ADJ (240 m) to 400 km",
        "years": C1.P69_YEARS,
        "starts": [C1.iso(t) for t in C1.P69_STARTS],
        "heights_m": list(HEIGHTS_M),
        "tolerance_mean_abs_pp": {"SUN": SUN_TOL_PP, "EARTH": EARTH_TOL_PP},
        "surface_m": [data[f"0m_px{i:02d}_2024_SUN"]["surface_m"] for i in range(n)],
        "surface_m_c1_adj_map": [c1[f"px{i:02d}_2024_SUN"]["surface_m"] for i in range(n)],
    }
    out["surface_diff_m"] = {
        "mean": float(np.mean(np.subtract(out["surface_m"], out["surface_m_c1_adj_map"]))),
        "max_abs": float(np.abs(np.subtract(out["surface_m"], out["surface_m_c1_adj_map"])).max()),
    }
    for body in BODIES:
        ref = vals[body]
        c1_runs = [
            [c1[f"px{i:02d}_{s.year}_{body}"]["time_steps_visible"] for i in range(n)] for s in C1.P69_STARTS
        ]
        c1_ours = np.mean(c1_runs, axis=0)
        res = {"product69_pct": (100.0 * ref).round(2).tolist(), "c1_adj_map": _stats(c1_ours, ref, ok)}
        tol = out["tolerance_mean_abs_pp"][body]
        for h in HEIGHTS_M:
            by_start = np.array(
                [
                    [data[f"{h:g}m_px{i:02d}_{s.year}_{body}"]["time_steps_visible"] for i in range(n)]
                    for s in C1.P69_STARTS
                ]
            )
            ours = by_start.mean(axis=0)
            s = _stats(ours, ref, ok)
            res[f"{h:g}m"] = s | {
                "ours_pct": (100.0 * ours).round(2).tolist(),
                "start_date_spread_pp_max": float(100.0 * np.abs(by_start[0] - by_start[1]).max()),
                "centre_pixel_pct": float(100.0 * ours[n // 2]),
                "pass": bool(s["mean_abs_diff_pp"] <= tol),
                # Labelled diagnostic, as in C1 (not a re-test): product 69's zero-valued pixel left out.
                "diagnostic_zero_pixel_excluded": _stats(ours, ref, nonzero),
            }
        res["pass_at_either_height"] = any(res[f"{h:g}m"]["pass"] for h in HEIGHTS_M)
        out[body] = res
    return out


def nearfield_layers():
    """The served stack with the 10 m clip as near field instead of the 5 m Site01 tile."""
    import rasterio

    from lss.datafiles import get as datafile

    with rasterio.open(datafile("ldem_83s_10m_site01_clip").path) as d:
        b = d.bounds
    ten = LayerSpec(
        "ldem_83s_10m_site01_clip",
        "pgda_90_south_pole_dems",
        10.0,
        "south",
        (b.left, b.bottom, b.right, b.top),
        "10 m polar map",
        use_to_m=SITE01_TILE.use_to_m,
    )
    return (ten, POLAR_80M, POLAR_240M)


def stage_nearfield10m(fresh: bool) -> None:
    from lss.contract.examples import SCENARIO
    from lss.horizon import cached_horizon

    path = C1.vdir() / "nearfield10m.json"
    if path.is_file() and not fresh:
        return
    loc = SCENARIO.location
    layers = nearfield_layers()
    t0 = time.monotonic()
    _ = layers[0].dem().array  # load the DEM first, so the horizon time below is the ray casting only
    load_s = time.monotonic() - t0
    hz_dir = C1.vdir() / "nearfield10m_horizons"
    times = []
    for _ in range(3):
        for f in hz_dir.glob("*.npz") if hz_dir.is_dir() else []:
            f.unlink()
        t0 = time.monotonic()
        hz10 = cached_horizon(loc.lat, loc.lon, SCENARIO.unit_height_m, layers=layers, directory=hz_dir)
        times.append(time.monotonic() - t0)
    base = C1.compute_series(SCENARIO)
    hz5 = base.horizon
    d = hz10.elevation_deg - hz5.elevation_deg
    m5 = C1._metrics_with(base, hz5)
    m10 = C1._metrics_with(base, hz10)
    out = {
        "surface_m": {"5m": hz5.surface_height_m, "10m": hz10.surface_height_m},
        "horizon_diff_deg": {
            "median_abs": float(np.median(np.abs(d))),
            "p95_abs": float(np.percentile(np.abs(d), 95)),
            "max_abs": float(np.abs(d).max()),
            "mean": float(d.mean()),
        },
        "metrics_5m": m5,
        "metrics_10m": m10,
        "horizon_seconds": [round(t, 2) for t in times],
        "dem_load_seconds": round(load_s, 2),
    }
    C1.write_json(path, out)
    print(json.dumps({k: v for k, v in out.items() if not k.startswith("metrics")}, indent=1))
    for k in (
        "illumination_fraction",
        "mean_visible_disk_fraction",
        "shadow_count",
        "longest_shadow_h",
        "earth_visibility_fraction",
        "longest_earth_gap_h",
    ):
        print(f"  {k}: 5 m {m5[k]}  10 m {m10[k]}")


# ------------------------------------------------------------------ new sites: Barker RoIs, Mazarico Table 3

ROI_EVERY = 5  # every 5th pixel of the largest RoI, plus its centroid pixel
ROI_TOL_PP = 0.5  # as the Site01 contour test (methodology 6.2); fixed before the run
BARKER_TEXT_LCIP_5M_D = (
    150.0,
    175.0,
)  # "~150-175 days for the other sites" at 5 m (Barker et al. 2021, sec. 5)
# Barker et al. (2021) supplement, Figs S9 (Site04), S14 (Site07), S19 (Site11): open circles = nominal-DEM
# RoI averages at 1 m, 2024-2025. READ FROM FIGURES (digitised from 400 dpi renders: ring centre against the
# gridlines, about +-0.15 pp, +-0.6 d, +-0.08 d). Qualitative check, no tolerance. Per RoI 1, 2, ...
BARKER_SUPP_FIG_READS = {
    "pgda-site04": {
        "figure": "S9",
        "avg_ill_pct": (74.66, 72.06, 74.50, 76.60),
        "lcip_d": (82.8, 112.9, 104.8, 154.8),
        "lcsp_d": (7.31, 10.11, 11.68, 10.73),
    },
    "pgda-site07": {
        "figure": "S14",
        "avg_ill_pct": (72.90, 74.81),
        "lcip_d": (165.0, 147.9),
        "lcsp_d": (15.00, 13.95),
    },
    "pgda-site11": {
        "figure": "S19",
        "avg_ill_pct": (76.45, 71.37, 71.91, 72.25),
        "lcip_d": (144.9, 146.4, 146.4, 145.7),
        "lcsp_d": (12.90, 15.15, 9.56, 10.08),
    },
}

# Mazarico et al. (2011) Table 3, south pole: rank -> (east lon, south lat, surface: avg ill %, visibility %,
# 10 m: avg ill %, visibility %). Ranks = product 78 site numbers.
MAZARICO_TABLE3 = {
    1: (222.69, 89.45, 89.01, 92.66, 93.10, 95.83),
    4: (204.27, 89.78, 86.71, 90.46, 87.41, 90.99),
    6: (37.07, 85.30, 85.95, 89.43, 87.30, 89.52),
    7: (123.64, 88.81, 85.50, 88.20, 85.59, 88.29),
    11: (291.90, 88.67, 84.61, 87.64, 84.74, 87.74),
    20: (31.73, 85.43, 82.22, 85.76, 83.32, 86.66),
    23: (357.70, 85.97, 81.76, 84.43, 82.66, 85.23),
    42: (243.65, 85.83, 79.59, 82.24, 79.85, 82.30),
}
MAZ_START = C1.datetime(1970, 1, 1, tzinfo=C1.UTC)
MAZ_YEARS = 4 * 18.6  # "four precession cycles from 1970 to 2044"
MAZ_STEP_S = 6 * 3600.0
MAZ_HEIGHTS_M = (0.0, 10.0)
MAZ_LAYERS = (POLAR_240M,)  # 240 m map only, as Mazarico et al. (2011)
MAZ_SHIFT_M = 120.0  # half a 240 m pixel
# Mazarico et al. (2011, sec. 2.2.1) see the other grid elements' elevation angles, interpolated along
# 720 lines: the nearest terrain is one grid node (240 m) away. "emulated" starts our rays there (primary);
# "engine" is our default (rays from 1 m, 0.1 deg), where a sloping 240 m facet under a 0 m observer blocks
# the low Sun.
MAZ_VARIANTS = {"emulated": {"min_range_m": 240.0, "azimuth_step_deg": 0.5}, "engine": {}}


def stage_roisites(fresh: bool) -> None:
    from lss.datafiles import BY_ID
    from lss.registry.rois import largest, read_rois
    from lss.registry.sites import site_points

    path = C1.vdir() / "roisites.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() and not fresh else {}
    hz_dir = C1.vdir() / "roisites_horizons"
    for sid, p in site_points().items():
        if p.rule != "largest_roi_centroid" or sid == "pgda-site01":
            continue
        rois = read_rois(BY_ID[f"site{p.tile[4:].lower()}_rois"].path)
        big = largest(rois).number
        pts = [("centroid", big, *p.ps_m)]
        for r in rois:
            pts += [
                (f"roi{r.number}_px{i}", r.number, *xy) for i, xy in enumerate(r.pixels) if i % ROI_EVERY == 0
            ]
        for name, roi, x, y in pts:
            key = f"{sid}_{name}"
            if key in data:
                continue
            lat, lon = (float(v) for v in latlon_from_ps(x, y, "south"))
            t0 = time.monotonic()
            _, v = C1.sun_visibility(lat, lon, 1.0, *C1.BARKER, C1.BARKER_STEP_S, directory=hz_dir)
            s, _ = C1.pixel_stats(v, C1.BARKER[0], C1.BARKER_STEP_S)
            data[key] = {
                "site": sid,
                "roi": roi,
                "x": float(x),
                "y": float(y),
                **{k: s[k] for k in ("avg_ill_pct_hourly", "lcip_d_hourly", "lcsp_d_hourly")},
            }
            if name == "centroid":
                _, v5 = C1.sun_visibility(lat, lon, 5.0, *C1.BARKER, C1.BARKER_STEP_S, directory=hz_dir)
                data[key]["lcip_d_hourly_5m"] = C1.pixel_stats(v5, C1.BARKER[0], C1.BARKER_STEP_S)[0][
                    "lcip_d_hourly"
                ]
            data[key]["seconds"] = round(time.monotonic() - t0, 1)
            C1.write_json(path, data)
            print(f"  {key}: {s['avg_ill_pct_hourly']:.2f}% ({data[key]['seconds']} s)", flush=True)


def roisites_summary() -> dict | None:
    path = C1.vdir() / "roisites.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {
        "tolerance_pp": ROI_TOL_PP,
        "every": ROI_EVERY,
        "barker_text_lcip_5m_d": list(BARKER_TEXT_LCIP_5M_D),
    }
    for sid in sorted({v["site"] for v in data.values()}):
        px = [v for k, v in data.items() if v["site"] == sid and "_roi" in k]
        c = data[f"{sid}_centroid"]
        per_roi = {}
        for roi in sorted({v["roi"] for v in px}):
            vs = [v for v in px if v["roi"] == roi]
            per_roi[str(roi)] = {
                "sampled_pixels": len(vs),
                **{
                    q: float(np.mean([v[f"{q}_hourly"] for v in vs]))
                    for q in ("avg_ill_pct", "lcip_d", "lcsp_d")
                },
                "min_avg_ill_pct": min(v["avg_ill_pct_hourly"] for v in vs),
            }
        vals = [v["avg_ill_pct_hourly"] for v in px]
        out[sid] = {
            "sampled_pixels": len(vals),
            "min_pct": min(vals),
            "max_pct": max(vals),
            "roi_averages": per_roi,
            "centroid": {
                "roi": c["roi"],
                "avg_ill_pct": c["avg_ill_pct_hourly"],
                "lcip_d_1m": c["lcip_d_hourly"],
                "lcip_d_5m": c["lcip_d_hourly_5m"],
            },
            "pass": min(vals) >= 70.0 - ROI_TOL_PP,
        }
        fig = BARKER_SUPP_FIG_READS.get(sid)
        if fig:
            rows = []
            for k, roi in enumerate(sorted(per_roi, key=int)):
                row = {"roi": int(roi)}
                for q in ("avg_ill_pct", "lcip_d", "lcsp_d"):
                    ours, read = per_roi[roi][q], fig[q][k]
                    row[q] = {"ours_sampled": ours, "figure_read": read, "diff": ours - read}
                rows.append(row)
            out[sid]["barker_supplement_read_from_figure"] = {"figure": fig["figure"], "rois": rows}
    return out


def maz_point(rank: int, dx: float = 0.0, dy: float = 0.0) -> tuple[float, float]:
    from lss.terrain.core import ps_from_latlon

    lon_e, lat_s = MAZARICO_TABLE3[rank][:2]
    lon = lon_e - 360.0 if lon_e > 180.0 else lon_e
    x, y = (float(v) for v in ps_from_latlon(-lat_s, lon, "south"))
    lat, lon = (float(v) for v in latlon_from_ps(x + dx, y + dy, "south"))
    return lat, lon


def maz_run(lat: float, lon: float, h: float, hz_dir: Path, variant: str) -> dict:
    from datetime import timedelta

    from lss.ephem import MOON_RADIUS_M
    from lss.horizon import HorizonParams, cached_horizon
    from lss.series import SeriesParams, body_visibility, ephemeris_sampler

    params = HorizonParams(**MAZ_VARIANTS[variant])
    hz = cached_horizon(lat, lon, h, params, layers=MAZ_LAYERS, directory=hz_dir)
    obs = hz.observer_radius_m - MOON_RADIUS_M
    dur = timedelta(days=MAZ_YEARS * 365.25).total_seconds()
    sample = ephemeris_sampler("SUN", lat, lon, obs, MAZ_START)
    v = body_visibility(sample, hz.elevation_at, dur, False, SeriesParams(MAZ_STEP_S))  # geometric area
    f = v.grid.fraction[:-1]
    return {"avg_ill_pct": 100.0 * float(f.mean()), "visibility_pct": 100.0 * float((f > 0).mean())}


MAZ_DIRS = ((MAZ_SHIFT_M, 0.0), (-MAZ_SHIFT_M, 0.0), (0.0, MAZ_SHIFT_M), (0.0, -MAZ_SHIFT_M))


def stage_mazarico(fresh: bool) -> None:
    """Shifts first (they set each variant's tolerance and do not use Table 3's values), then the points."""
    path = C1.vdir() / "mazarico.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() and not fresh else {}
    hz_dir = C1.vdir() / "mazarico_horizons"
    for variant in MAZ_VARIANTS:
        for dx, dy in (*MAZ_DIRS, (0.0, 0.0)):
            for rank in MAZARICO_TABLE3:
                for h in MAZ_HEIGHTS_M:
                    key = f"{variant}_r{rank}_{h:g}m_{dx:+g}_{dy:+g}"
                    if key in data:
                        continue
                    t0 = time.monotonic()
                    data[key] = maz_run(*maz_point(rank, dx, dy), h, hz_dir, variant)
                    data[key]["seconds"] = round(time.monotonic() - t0, 1)
                    C1.write_json(path, data)
                    print(f"  {key}: {data[key]}", flush=True)


MAZ_COLS = {
    (0.0, "avg_ill_pct"): 2,
    (0.0, "visibility_pct"): 3,
    (10.0, "avg_ill_pct"): 4,
    (10.0, "visibility_pct"): 5,
}


def _maz_variant(data: dict, variant: str) -> dict:
    out = {}
    for (h, q), col in MAZ_COLS.items():
        changes, diffs, rows = [], [], []
        for rank, row in MAZARICO_TABLE3.items():
            centre = data[f"{variant}_r{rank}_{h:g}m_+0_+0"][q]
            for dx, dy in MAZ_DIRS:
                changes.append(data[f"{variant}_r{rank}_{h:g}m_{dx:+g}_{dy:+g}"][q] - centre)
            diffs.append(centre - row[col])
            rows.append({"rank": rank, "ours": centre, "mazarico": row[col]})
        tol = float(np.mean(np.abs(changes)))  # from the shifts only
        mad = float(np.mean(np.abs(diffs)))
        out[f"{h:g}m_{q}"] = {
            "tolerance_pp_from_shifts": tol,
            "mean_diff_pp": float(np.mean(diffs)),
            "mean_abs_diff_pp": mad,
            "rows": rows,
            "pass": mad <= tol,
        }
    return out


def mazarico_summary() -> dict | None:
    path = C1.vdir() / "mazarico.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {
        "period": [C1.iso(MAZ_START), MAZ_YEARS],
        "step_s": MAZ_STEP_S,
        "terrain": "LDEM_60S_240MPP_ADJ (240 m) only, as Mazarico et al. (2011)",
        "shift_m": MAZ_SHIFT_M,
        "variants": MAZ_VARIANTS,
        "primary": "emulated",
    }
    for variant in MAZ_VARIANTS:
        out[variant] = _maz_variant(data, variant)
    return out


def stage_summary(_fresh: bool) -> None:
    s = {"format": 1, "generated_by": "scripts/validation_c3.py", "product69_standin": summary()}
    nf = C1.vdir() / "nearfield10m.json"
    if nf.is_file():
        s["nearfield_10m_site01"] = json.loads(nf.read_text(encoding="utf-8"))
    s["barker_roi_sites"] = roisites_summary()
    s["mazarico_table3"] = mazarico_summary()
    C1.write_json(FIXTURE, s)
    p = s["product69_standin"]
    print(f"surface vs C1's ADJ map: {p['surface_diff_m']}")
    for body in BODIES:
        for h in HEIGHTS_M:
            r = p[body][f"{h:g}m"]
            print(
                f"{body} {h:g} m: mean diff {r['mean_diff_pp']:+.2f} pp, "
                f"mean |diff| {r['mean_abs_diff_pp']:.2f} pp, r {r['correlation']:.2f}, pass {r['pass']}"
            )
        print(f"{body} C1 (ADJ map, 0 m): {p[body]['c1_adj_map']}")
    print(f"written {FIXTURE}")


STAGES = {
    "p69": stage_p69,
    "nearfield10m": stage_nearfield10m,
    "roisites": stage_roisites,
    "mazarico": stage_mazarico,
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
