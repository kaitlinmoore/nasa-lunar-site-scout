"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

C3 served results: every curated site (lss/registry/sites.yaml) whose 5 m tile is downloaded, at the standard
heights 1, 2, 5 and 10 m, over three windows (Kaitlin, 2026-11-15 and 2026-11-16):

  - 2028-05-15 to 2028-06-14 at PT1H (the C1 window, comparable with Site01's served result);
  - 2028-01-01 to 2029-01-01 at PT6H (metrics from the 60 s internal grid, as always; PT6H sets the series).
  - 2028-11-15 to 2028-11-25 at PT1H (C api's request RA8, eval item k6).

Each file also carries the Sun-elevation histogram (format 3; RA7).

One file per scenario in LSS_DATA_DIR/cache/served/ (format 2: metrics, series, horizon; lss/api/served.py),
named c3_<site>_<height>m_<start>_<days>d.json. A scenario already served by another file (Site01, 1 m, C1
window: scripts/precompute_c1.py) is skipped, because the API refuses duplicate keys. The list of served
scenarios and the measured cost per scenario go to LSS_DATA_DIR/cache/served_c3_index.json (outside served/,
which the API reads whole).

    uv run python scripts/precompute_c3.py [--sites pgda-site04 ...] [--force]

Without --sites: every curated site with a downloaded PGDA 5 m tile. Sites without one (e.g. the Apollo sites,
which the resolver gives the global layer, fidelity low) are computed only when named with --sites.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from lss.config import get_settings
from lss.contract import CONTRACT_VERSION, Scenario
from lss.datafiles import BY_ID
from lss.metrics import metrics_response
from lss.registry.sites import load_sites, site_points
from lss.series import compute_series, horizon_response, series_response

ROOT = Path(__file__).resolve().parents[1]
HEIGHTS_M = (1.0, 2.0, 5.0, 10.0)
WINDOWS = (
    (datetime(2028, 5, 15, tzinfo=UTC), timedelta(days=30), timedelta(hours=1)),
    (datetime(2028, 1, 1, tzinfo=UTC), timedelta(days=366), timedelta(hours=6)),  # 2028 is a leap year
    (datetime(2028, 11, 15, tzinfo=UTC), timedelta(days=10), timedelta(hours=1)),  # k6 (C api RA8)
)


def _c1():
    spec = importlib.util.spec_from_file_location("precompute_c1", ROOT / "scripts" / "precompute_c1.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C1 = _c1()


def served_dir() -> Path:
    return get_settings().cache_dir / "served"


def index_path() -> Path:
    return get_settings().cache_dir / "served_c3_index.json"


def file_name(site_id: str, sc: Scenario) -> str:
    days = round((sc.window_end - sc.window_start).total_seconds() / 86400)
    return f"c3_{site_id}_{sc.unit_height_m:g}m_{sc.window_start:%Y%m%d}_{days}d.json"


def other_keys() -> set[str]:
    """Scenario keys already served by files this script does not write."""
    keys = set()
    for p in served_dir().glob("*.json") if served_dir().is_dir() else []:
        if not p.name.startswith("c3_"):
            keys.add(json.loads(p.read_text(encoding="utf-8"))["scenario_key"])
    return keys


def write(site_id: str, sc: Scenario) -> dict:
    t0 = time.monotonic()
    res = compute_series(sc)
    if res.horizon.missing_samples:  # methodology section 3.1
        raise SystemExit(f"{site_id}: horizon has {res.horizon.missing_samples} uncovered ray samples")
    t_compute = time.monotonic() - t0
    body = {
        "format": C1.FORMAT,
        "scenario_key": sc.key(),
        "metrics": metrics_response(res).model_dump(mode="json", by_alias=True),
        "series": series_response(res).model_dump(mode="json", by_alias=True),
        "horizon": horizon_response(res).model_dump(mode="json", by_alias=True),
        "sun_elevation_histogram": C1.sun_histogram(res),
        "provenance": C1.provenance(res) | {"site_id": site_id, "compute_seconds": round(t_compute, 2)},
    }
    path = served_dir() / file_name(site_id, sc)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8", newline="\n")
    part.replace(path)
    return {
        "file": path.name,
        "site_id": site_id,
        "scenario_key": sc.key(),
        "scenario": sc.model_dump(mode="json"),
        "bytes": path.stat().st_size,
        "compute_seconds": round(t_compute, 2),
        "total_seconds": round(time.monotonic() - t0, 2),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--sites", nargs="*", help="site ids (default: every site whose 5 m tile is downloaded)")
    ap.add_argument("--force", action="store_true", help="recompute files that already exist")
    a = ap.parse_args(argv)
    sites = {s.id: s for s in load_sites()}
    points = site_points()
    chosen = a.sites or [
        sid for sid, p in points.items() if BY_ID[f"site{p.tile[4:].lower()}_dem"].path.is_file()
    ]
    skip = other_keys()
    index = json.loads(index_path().read_text(encoding="utf-8")) if index_path().is_file() else {}
    entries = {e["file"]: e for e in index.get("served", [])}
    for sid in chosen:
        loc = sites[sid].location
        for h in HEIGHTS_M:
            for start, length, step in WINDOWS:
                sc = Scenario(
                    location=loc, unit_height_m=h, window_start=start, window_end=start + length, step=step
                )
                name = file_name(sid, sc)
                if sc.key() in skip:
                    print(f"  skip {name}: already served by another file")
                    continue
                if name in entries and (served_dir() / name).is_file() and not a.force:
                    continue
                e = write(sid, sc)
                entries[name] = e
                print(f"  {name}: {e['bytes']:,} B, {e['compute_seconds']} s", flush=True)
                index_path().write_text(
                    json.dumps(
                        {
                            "contract_version": CONTRACT_VERSION,
                            "served": sorted(entries.values(), key=lambda x: x["file"]),
                        },
                        indent=1,
                    )
                    + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
