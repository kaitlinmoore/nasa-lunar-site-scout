"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Measurements behind docs/methodology.md section 5, made with the lss.series / lss.metrics code:

1. Limb-darkened vs geometric time-mean solar fraction (served point, 1 m, Barker's 2024-01-01 to 2026-01-01).
2. Shadow periods over that period: count, and how many are short (horizon flickers).
3. Real horizon profile vs Barker's flat cut at the disc centre's azimuth: mean fraction and short periods.
4. Internal grid step: the served C1 scenario at 60 s (default) vs 15 s.

    uv run python scripts/series_checks.py            # writes LSS_DATA_DIR/cache/series_checks.json

Each check is saved as soon as it is done, so a rerun after an interruption skips finished checks
(`--fresh` starts over). Results are reused only if made with the same series version and settings.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

import lss.series.disc as disc
from lss.config import get_settings
from lss.contract.examples import SCENARIO
from lss.ephem import MOON_RADIUS_M
from lss.horizon import HORIZON_VERSION, cached_horizon
from lss.metrics import power_metrics, time_mean
from lss.series import SERIES_VERSION, SeriesParams, body_visibility, compute_series, ephemeris_sampler
from lss.series.disc import DISC_NODES, MARGIN_NODES

BARKER = (datetime(2024, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC))
SHORT_H = (1.0, 10 / 60)


def out_path() -> Path:
    return get_settings().cache_dir / "series_checks.json"


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    part.replace(path)


@contextmanager
def flat_cut():
    """Barker's approximation: every disc column sees the horizon at the disc centre's azimuth."""
    original = disc._horizon_at_columns

    def centre_only(horizon_at, az_c, el_c, x):
        return np.broadcast_to(np.asarray(horizon_at(np.mod(az_c, 360.0)), dtype=float)[:, None], x.shape)

    disc._horizon_at_columns = centre_only
    try:
        yield
    finally:
        disc._horizon_at_columns = original


def sun_over(start, end, limb: bool, params: SeriesParams):
    loc = SCENARIO.location
    hz = cached_horizon(loc.lat, loc.lon, SCENARIO.unit_height_m)
    obs = hz.observer_radius_m - MOON_RADIUS_M
    sample = ephemeris_sampler("SUN", loc.lat, loc.lon, obs, start)
    return body_visibility(sample, hz.elevation_at, (end - start).total_seconds(), limb, params)


def summarise(v) -> dict:
    d = np.array([p.duration_s / 3600 for p in v.hidden])
    return {
        "mean_fraction": time_mean(v.grid.t_s, v.grid.fraction),
        "illumination_fraction": sum(p.duration_s for p in v.visible) / float(v.grid.t_s[-1]),
        "shadow_periods": len(v.hidden),
        "shorter_than_h": {f"{s:g}": int((d < s).sum()) for s in SHORT_H},
        "shortest_h": float(d.min()) if d.size else None,
        "longest_h": float(d.max()) if d.size else None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args(argv)
    params = SeriesParams()
    head = {
        "format": 1,
        "series_version": SERIES_VERSION,
        "horizon_version": HORIZON_VERSION,
        "series_params": asdict(params),
        "disc_nodes": DISC_NODES,
        "margin_nodes": MARGIN_NODES,
        "site": [SCENARIO.location.lat, SCENARIO.location.lon],
        "unit_height_m": SCENARIO.unit_height_m,
    }
    out = out_path()
    saved = json.loads(out.read_text(encoding="utf-8")) if out.is_file() and not a.fresh else {}
    data = saved if all(saved.get(k) == v for k, v in head.items()) else dict(head)
    data.setdefault("checks", {})

    def check(name, fn):
        if name not in data["checks"]:
            t0 = time.monotonic()
            data["checks"][name] = {**fn(), "seconds": round(time.monotonic() - t0, 1)}
            write_atomic(out, data)
        print(f"{name}: {json.dumps(data['checks'][name])}")

    check("barker_period_limb_darkened_profile", lambda: summarise(sun_over(*BARKER, True, params)))
    check("barker_period_geometric_profile", lambda: summarise(sun_over(*BARKER, False, params)))

    def flat():
        with flat_cut():
            return summarise(sun_over(*BARKER, True, params))

    check("barker_period_limb_darkened_flat_cut", flat)

    def grid():
        out = {}
        for step in (60.0, 15.0):
            pm = power_metrics(compute_series(SCENARIO, SeriesParams(grid_step_s=step)))
            out[f"{step:g}s"] = pm.model_dump(mode="json")
        return out

    check("served_scenario_grid_step", grid)
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
