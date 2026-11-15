"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Horizon convergence study (docs/methodology.md section 3): how much each numerical setting changes
the horizon, against a much finer reference, at one site and unit height.

    uv run python scripts/horizon_convergence.py                       # served Site01 point, 1 m
    uv run python scripts/horizon_convergence.py --lat -89.45 --lon -137.31 --height 10

Settings studied: azimuth step, ray sample spacing (fraction of the pixel size and of the distance),
the first sample distance, where the 5 m site map
hands over to the 80 m map, where the 80 m map hands over to the 240 m map, and the maximum ray range.
Each variant is compared with the reference on the reference's azimuth grid (coarser horizons are
interpolated linearly, as the engine does). Results are printed and written as JSON to
LSS_DATA_DIR/cache/horizon_convergence_<lat>_<lon>_<h>m.json, after every variant: an interrupted run
(sleep, restart) resumes where it stopped when rerun with the same arguments (`--fresh` starts over).
The reference horizon is cached in LSS_DATA_DIR/cache/horizon_convergence/. Timings are wall-clock
seconds of the computation itself, recorded when it ran.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from lss.config import get_settings
from lss.contract.examples import SITE01
from lss.horizon import HORIZON_VERSION, HorizonParams, cached_horizon, horizon_at
from lss.horizon.cache import cache_path, key_spec
from lss.registry.terrain import LAYERS, resolve

# Horizon elevations where the Sun's disc can touch the horizon at Site01: centre within +-2.11 deg
# (2024-2043, lss.ephem), plus the 0.27 deg disc radius.
SUN_BAND_DEG = 2.4

# Index of each layer in LAYERS: 0 = 5 m site map, 1 = 80 m, 2 = 240 m.
DEFAULT = {
    "az": 0.1,
    "factor": 0.5,
    "near_to": 5_000.0,
    "mid_to": 100_000.0,
    "max_range": 400_000.0,
    "rel": 0.002,
    "min_range": 1.0,
}
REFERENCE = {
    "az": 0.05,
    "factor": 0.25,
    "near_to": 7_500.0,
    "mid_to": 290_000.0,
    "max_range": 800_000.0,
    "rel": 0.0005,
    "min_range": 0.5,
}
COARSER = {
    "az": 0.25,
    "factor": 1.0,
    "near_to": 2_500.0,
    "mid_to": 50_000.0,
    "max_range": 200_000.0,
    "rel": 0.01,
    "min_range": 2.5,
}
LABELS = {
    "az": "azimuth step (deg)",
    "factor": "sample spacing (x pixel)",
    "near_to": "5 m map used to (m)",
    "mid_to": "80 m map used to (m)",
    "max_range": "max ray range (m)",
    "rel": "spacing / distance",
    "min_range": "first sample (m)",
}


def settings_to_engine(s: dict):
    layers = (
        replace(LAYERS[0], use_to_m=s["near_to"]),
        replace(LAYERS[1], use_to_m=s["mid_to"]),
        LAYERS[2],
    )
    return layers, HorizonParams(s["az"], s["factor"], s["max_range"], s["rel"], s["min_range"])


def run(lat: float, lon: float, height: float, s: dict):
    layers, p = settings_to_engine(s)
    t0 = time.monotonic()
    h = horizon_at(lat, lon, height, p, layers)
    return h, time.monotonic() - t0


def compare(h, ref) -> dict:
    d = h.elevation_at(ref.azimuth_deg) - ref.elevation_deg
    band = np.abs(ref.elevation_deg) <= SUN_BAND_DEG
    a = np.abs(d)
    return {
        "max_abs_deg": float(a.max()),
        "p99_abs_deg": float(np.percentile(a, 99)),
        "rms_deg": float(np.sqrt(np.mean(d**2))),
        "max_abs_in_sun_band_deg": float(a[band].max()) if band.any() else None,
        "missing_samples": h.missing_samples,
    }


def out_path(lat: float, lon: float, height: float) -> Path:
    return get_settings().cache_dir / f"horizon_convergence_{lat:+.4f}_{lon:+.4f}_{height:g}m.json"


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    part.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--lat", type=float, default=SITE01.lat, help="default: the served Site01 point")
    ap.add_argument("--lon", type=float, default=SITE01.lon)
    ap.add_argument("--height", type=float, default=1.0)
    ap.add_argument("--fresh", action="store_true", help="ignore saved results and recompute everything")
    a = ap.parse_args(argv)

    # Resumable: results are saved after every variant (atomically), and the reference horizon is cached,
    # so a rerun after an interruption (sleep, restart) skips what is already done. Saved results are only
    # reused if they were made with the same reference settings and horizon algorithm version.
    out = out_path(a.lat, a.lon, a.height)
    head = {
        "format": 3,
        "horizon_version": HORIZON_VERSION,
        "site": [a.lat, a.lon],
        "unit_height_m": a.height,
        "reference": REFERENCE,
    }
    saved = json.loads(out.read_text(encoding="utf-8")) if out.is_file() and not a.fresh else {}
    same = all(saved.get(k) == v for k, v in head.items())
    data = (
        {**head, "reference_seconds": saved.get("reference_seconds"), "rows": saved.get("rows", [])}
        if same
        else {**head, "reference_seconds": None, "rows": []}
    )
    if same and data["rows"]:
        print(f"resuming {out}: {len(data['rows'])} variants already done")

    print(f"site ({a.lat}, {a.lon}), unit height {a.height} m")
    ref_layers, ref_params = settings_to_engine(REFERENCE)
    ref_dir = get_settings().cache_dir / "horizon_convergence"
    stack = resolve(a.lat, a.lon, ref_params.max_range_m, ref_layers)
    ref_cached = (
        not a.fresh and cache_path(key_spec(a.lat, a.lon, a.height, ref_params, stack), ref_dir).is_file()
    )
    t0 = time.monotonic()
    ref = cached_horizon(a.lat, a.lon, a.height, ref_params, ref_layers, recompute=a.fresh, directory=ref_dir)
    if not ref_cached:  # timing recorded only when the reference was actually computed
        data["reference_seconds"] = round(time.monotonic() - t0, 2)
        write_atomic(out, data)
    print(f"reference {REFERENCE}: {data['reference_seconds']} s, missing samples {ref.missing_samples}")
    done = {row["variant"]: row for row in data["rows"]}

    def record(name: str, s: dict):
        if name in done and done[name]["settings"] == s:
            row = done[name]
        else:
            h, t = run(a.lat, a.lon, a.height, s)
            row = {"variant": name, "settings": s, "seconds": round(t, 2), **compare(h, ref)}
            data["rows"] = [r for r in data["rows"] if r["variant"] != name] + [row]
            write_atomic(out, data)
        band = row["max_abs_in_sun_band_deg"]
        print(
            f"  {name:42s} max {row['max_abs_deg']:.4f}  p99 {row['p99_abs_deg']:.4f}  "
            f"rms {row['rms_deg']:.5f}  sun band max {band if band is None else round(band, 4)}  "
            f"({row['seconds']:.1f} s)"
        )

    record("default (all settings)", DEFAULT)
    for k in DEFAULT:  # one setting at its default, all others at the reference: attributes the error
        record(f"reference, {LABELS[k]} = {DEFAULT[k]:g}", {**REFERENCE, k: DEFAULT[k]})
    for k in COARSER:  # one setting coarser than the default: is there headroom?
        record(f"default, {LABELS[k]} = {COARSER[k]:g}", {**DEFAULT, k: COARSER[k]})
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
