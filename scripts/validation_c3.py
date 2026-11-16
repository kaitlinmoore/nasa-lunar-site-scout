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
    "pgda_69_polar_illumination",
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


def stage_summary(_fresh: bool) -> None:
    s = {"format": 1, "generated_by": "scripts/validation_c3.py", "product69_standin": summary()}
    nf = C1.vdir() / "nearfield10m.json"
    if nf.is_file():
        s["nearfield_10m_site01"] = json.loads(nf.read_text(encoding="utf-8"))
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


STAGES = {"p69": stage_p69, "nearfield10m": stage_nearfield10m, "summary": stage_summary}


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
