"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Per-site regression fixtures: for every curated site with a PGDA tile, other than Site01 (which has
tests/engine/fixtures/site01_roi4_c1.json), the 1 m scenario over the first served window (2028-05-15,
30 days, PT1H), taken from its served file so the fixture is exactly what the API serves.

    tests/engine/fixtures/c3/<site id>.json: scenario key, metrics, the series every 24th sample and the
    horizon every 10th azimuth (no contract_version or created_utc, so a contract bump that leaves these
    models alone does not touch them).

Checked against a fresh computation by tests/engine/test_regression_c3.py. Run after scripts/precompute_c3.py:

    uv run python scripts/regression_c3.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "engine" / "fixtures" / "c3"
SERIES_EVERY = 24
HORIZON_EVERY = 10
UNVERSIONED = ("contract_version", "created_utc")


def _c3():
    spec = importlib.util.spec_from_file_location("precompute_c3", ROOT / "scripts" / "precompute_c3.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def thin(body: dict, every: int, keys: tuple[str, ...]) -> dict:
    return {k: (v[::every] if k in keys else v) for k, v in body.items() if k not in UNVERSIONED}


def main() -> int:
    from lss.contract import Scenario
    from lss.registry.sites import load_sites, site_points

    c3 = _c3()
    start, length, step = c3.WINDOWS[0]
    OUT.mkdir(parents=True, exist_ok=True)
    pgda = site_points()  # sites with a PGDA product 78 tile (served by precompute_c3.py)
    for site in load_sites():
        if site.id == "pgda-site01" or site.id not in pgda:
            continue
        sc = Scenario(
            location=site.location,
            unit_height_m=1.0,
            window_start=start,
            window_end=start + length,
            step=step,
        )
        path = c3.served_dir() / c3.file_name(site.id, sc)
        if not path.is_file():
            print(f"  skip {site.id}: {path.name} not computed (scripts/precompute_c3.py)")
            continue
        served = json.loads(path.read_text(encoding="utf-8"))
        assert served["scenario_key"] == sc.key()
        s = served["series"]
        series = {k: v for k, v in s.items() if k not in UNVERSIONED}
        series["time"] = s["time"][::SERIES_EVERY]
        series["downsampled"] = True
        for body in ("sun", "earth"):
            series[body] = {k: v[::SERIES_EVERY] for k, v in s[body].items()}
        fixture = {
            "format": 1,
            "site_id": site.id,
            "scenario_key": sc.key(),
            "series_every": SERIES_EVERY,
            "horizon_every": HORIZON_EVERY,
            "metrics": {k: v for k, v in served["metrics"].items() if k not in UNVERSIONED},
            "series": series,
            "horizon": thin(served["horizon"], HORIZON_EVERY, ("azimuth_deg", "elevation_deg")),
        }
        out = OUT / f"{site.id}.json"
        out.write_text(json.dumps(fixture, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"  {out.relative_to(ROOT)} ({out.stat().st_size:,} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
