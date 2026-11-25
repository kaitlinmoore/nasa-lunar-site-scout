"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Compute the first served scenario (lss.contract.examples.SCENARIO) once and write:

1. the served result, LSS_DATA_DIR/cache/served/c1_<scenario key>.json (format 2): the metrics, series and
   horizon responses with their provenance, which the API loads (it needs no DEMs or kernels; file format in
   lss/api/served.py);
2. the regression fixture, tests/engine/fixtures/site01_roi4_c1.json: the same metrics response, the series
   every 6 h and the horizon every 1 deg, checked against a fresh computation by
   tests/engine/test_regression_c1.py.

    uv run python scripts/precompute_c1.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from lss.config import get_settings
from lss.contract import CONTRACT_VERSION
from lss.contract.examples import SCENARIO
from lss.ephem import ABCORR, FRAME
from lss.ephem.core import KERNEL_IDS
from lss.horizon import HORIZON_VERSION
from lss.horizon.cache import cache_key, key_spec
from lss.metrics import elevation_histogram, metrics_response
from lss.registry.terrain import resolve
from lss.series import SERIES_VERSION, compute_series, horizon_response, series_response

FORMAT = 3  # lss/api/served.py: format 2 adds the horizon; 3 adds the Sun-elevation histogram
REGRESSION = Path(__file__).resolve().parents[1] / "tests" / "engine" / "fixtures" / "site01_roi4_c1.json"
SERIES_EVERY = 6  # regression fixture keeps every 6th hourly sample
HORIZON_EVERY = 10  # and every 10th horizon azimuth (1 deg)


def served_path(key: str | None = None) -> Path:
    return get_settings().cache_dir / "served" / f"c1_{key or SCENARIO.key()}.json"


def provenance(res) -> dict:
    manifest_path = get_settings().data_dir / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    hz = res.horizon
    stack = resolve(res.lat, res.lon, hz.params.max_range_m, res.layers)
    spec = key_spec(res.lat, res.lon, res.unit_height_m, hz.params, stack)
    return {
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "contract_version": CONTRACT_VERSION,
        "horizon_version": HORIZON_VERSION,
        "series_version": SERIES_VERSION,
        "horizon_cache_key": cache_key(spec),
        "horizon_params": asdict(hz.params),
        "series_params": asdict(res.params),
        "observer_height_m": res.observer_height_m,
        "frame": FRAME,
        "aberration_correction": ABCORR,
        "files": {
            fid: {k: manifest.get(fid, {}).get(k) for k in ("url", "sha256", "size")}
            for fid in (*KERNEL_IDS, *(sl.spec.file_id for sl in stack.layers))
            if fid in manifest
        },
    }


def sun_histogram(res) -> dict:
    """Time histogram of the Sun's disc-centre elevation over the window (lss.metrics.elevation_band)."""
    g = res.sun.grid
    return elevation_histogram(g.t_s, g.elevation_deg).to_json()


def main() -> int:
    res = compute_series(SCENARIO)
    if res.horizon.missing_samples:  # methodology section 3.1: never serve a horizon with uncovered samples
        raise SystemExit(f"horizon has {res.horizon.missing_samples} ray samples no terrain layer covers")
    m = metrics_response(res).model_dump(mode="json", by_alias=True)
    s = series_response(res).model_dump(mode="json", by_alias=True)
    h = horizon_response(res).model_dump(mode="json", by_alias=True)
    key = SCENARIO.key()
    served = {
        "format": FORMAT,
        "scenario_key": key,
        "metrics": m,
        "series": s,
        "horizon": h,
        "sun_elevation_histogram": sun_histogram(res),
        "provenance": provenance(res),
    }
    out = served_path(key)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(served, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"written {out} ({out.stat().st_size} bytes)")

    thin = dict(s)
    thin["time"] = s["time"][::SERIES_EVERY]
    thin["downsampled"] = True
    for body in ("sun", "earth"):
        thin[body] = {k: v[::SERIES_EVERY] if isinstance(v, list) else v for k, v in s[body].items()}
    # Without contract_version, so a contract bump that leaves these models alone does not touch the fixture.
    unversioned = ("contract_version", "created_utc")
    regression = {
        "format": FORMAT,
        "scenario_key": key,
        "series_every": SERIES_EVERY,
        "metrics": {k: v for k, v in m.items() if k not in unversioned},
        "series": {k: v for k, v in thin.items() if k not in unversioned},
        "horizon_every": HORIZON_EVERY,
        "horizon": {
            k: v[::HORIZON_EVERY] if k in ("azimuth_deg", "elevation_deg") else v
            for k, v in h.items()
            if k not in unversioned
        },
        "provenance": {k: v for k, v in served["provenance"].items() if k not in unversioned},
    }
    REGRESSION.write_text(json.dumps(regression, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"written {REGRESSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
