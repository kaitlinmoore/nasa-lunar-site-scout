"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Static JSON fallback (plan section 4.7; Kaitlin, 2026-11-15): the API's precomputed results as static files
on the web host, so the demo still works when the API is down.

    uv run python -m lss.api.static_export OUT_DIR [--served-dir DIR] [--terrain-dir DIR] [--check-api URL]

Writes, under OUT_DIR (deploy/deploy-web.sh uses web/dist/static-api):
- `index.json`: a StaticIndex, listing every served scenario and the paths of its files;
- `sites.json`, `datasets.json`, `scenarios.json`: what GET /api/sites, /api/datasets and /api/scenarios
  return;
- `metrics/<scenario_key>.json`, `series/<scenario_key>.json`: what POST /api/metrics and /api/series return;
- `horizon/<horizon_key>.json`: what POST /api/horizon returns, where a served file has a horizon;
- `terrain/<terrain_key>.json`: what POST /api/terrain returns (precomputed slope statistics);
- `nl/<name>.json`: the cached showcase answers (C8), what POST /api/nl returns for their requests.

The files are built with the API's own loader (lss.api.served) and response code, so they are the API's
bodies, and every one must carry the current CONTRACT_VERSION. `--check-api` also requires the deployed
API to report the same contract version and to return the same metrics for every exported scenario and
the same slope statistics for every exported location and radius, and the same answer for every cached
showcase question (cached answers cost nothing and aren't rate limited).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
from pathlib import Path

from pydantic import BaseModel

from lss.api import app as api
from lss.api.nl import cache_dir as nl_cache_dir
from lss.api.nl import load_cache_entries
from lss.api.served import horizons, load_all, load_terrain, served_dir, terrain_dir
from lss.contract import (
    CONTRACT_VERSION,
    ScenariosResponse,
    StaticEntry,
    StaticIndex,
    StaticNLEntry,
    StaticTerrainEntry,
)

INDEX_NOTE = "Static copy of the API's precomputed results, for when the API is unavailable (plan 4.7)."


class StaticExportError(RuntimeError):
    pass


def _write(path: Path, body: BaseModel) -> dict:
    data = body.model_dump(mode="json", by_alias=True)
    if data.get("contract_version") != CONTRACT_VERSION:
        raise StaticExportError(
            f"{path.name}: contract {data.get('contract_version')}, not {CONTRACT_VERSION}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data


def export(
    out_dir: Path,
    served_from: Path | None = None,
    terrain_from: Path | None = None,
    nl_from: Path | None = None,
) -> StaticIndex:
    """Write the static fallback to out_dir (replacing it); returns the index."""
    served = load_all(served_from or served_dir())
    if not served:
        raise StaticExportError(f"no precomputed results in {served_from or served_dir()}")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    horizon_paths = {}
    for hkey, sv in horizons(served).items():
        rel = f"horizon/{hkey}.json"
        _write(out_dir / rel, sv.horizon)
        horizon_paths[hkey] = rel

    sites = api._sites().sites
    entries = []
    for key, sv in served.items():
        entry = StaticEntry(
            scenario=sv.scenario,
            scenario_key=key,
            site_id=api.site_of(sv, sites),
            metrics=f"metrics/{key}.json",
            series=f"series/{key}.json",
            horizon=horizon_paths.get(sv.horizon_key),
        )
        _write(out_dir / entry.metrics, sv.metrics)
        _write(out_dir / entry.series, sv.series)
        entries.append(entry)

    terrain = []
    for tkey, st in load_terrain(terrain_from or terrain_dir()).items():
        entry = StaticTerrainEntry(
            location=st.body.location,
            radius_m=st.body.radius_m,
            terrain_key=tkey,
            path=f"terrain/{tkey}.json",
        )
        _write(out_dir / entry.path, st.body)
        terrain.append(entry)

    nl_answers = []
    for entry in load_cache_entries(nl_from or nl_cache_dir()).values():
        rel = f"nl/{entry.path.stem}.json"
        _write(out_dir / rel, entry.response)
        nl_answers.append(StaticNLEntry(request=entry.request, path=rel))

    _write(out_dir / "sites.json", api._sites())
    _write(out_dir / "datasets.json", api._datasets())
    _write(out_dir / "scenarios.json", ScenariosResponse(scenarios=api.build_scenarios(served, sites)))
    index = StaticIndex(
        scenarios=entries,
        terrain=terrain,
        sites="sites.json",
        datasets="datasets.json",
        scenario_list="scenarios.json",
        nl_answers=nl_answers,
        _note=INDEX_NOTE,
    )
    _write(out_dir / "index.json", index)
    return index


def _get_json(url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(
        url, data=data, headers=headers, method="POST" if body is not None else "GET"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (the deploy script's own API URL)
        return json.loads(resp.read().decode("utf-8"))


def check_api(index: StaticIndex, out_dir: Path, api_url: str) -> None:
    """The deployed API must be on the same contract version and serve the same metrics."""
    base = api_url.rstrip("/")
    health = _get_json(f"{base}/api/health")
    if health.get("contract_version") != CONTRACT_VERSION:
        raise StaticExportError(
            f"the API at {base} is contract {health.get('contract_version')}, "
            f"these files are {CONTRACT_VERSION} (deploy the API first)"
        )
    for entry in index.scenarios:
        live = _get_json(f"{base}/api/metrics", {"scenario": entry.scenario.model_dump(mode="json")})
        static = json.loads((out_dir / entry.metrics).read_text(encoding="utf-8"))
        if live != static:
            raise StaticExportError(f"the API's metrics for {entry.scenario_key} differ from the static copy")
    if _get_json(f"{base}/api/scenarios") != json.loads(
        (out_dir / "scenarios.json").read_text(encoding="utf-8")
    ):
        raise StaticExportError("the API's scenario list differs from the static copy")
    for a in index.nl_answers:
        live = _get_json(f"{base}/api/nl", a.request.model_dump(mode="json", exclude_none=True))
        if live != json.loads((out_dir / a.path).read_text(encoding="utf-8")):
            raise StaticExportError(f"the API's cached answer for {a.path} differs from the static copy")
    for t in index.terrain:
        live = _get_json(
            f"{base}/api/terrain", {"location": t.location.model_dump(mode="json"), "radius_m": t.radius_m}
        )
        if live != json.loads((out_dir / t.path).read_text(encoding="utf-8")):
            raise StaticExportError(
                f"the API's slope statistics for {t.terrain_key} differ from the static copy"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the static JSON fallback (plan 4.7).")
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--served-dir", type=Path, default=None, help="default: LSS_DATA_DIR/cache/served")
    parser.add_argument("--terrain-dir", type=Path, default=None, help="default: LSS_DATA_DIR/cache/terrain")
    parser.add_argument("--nl-dir", type=Path, default=None, help="default: LSS_DATA_DIR/cache/nl")
    parser.add_argument("--check-api", metavar="URL", default=None, help="compare with the deployed API")
    args = parser.parse_args(argv)
    try:
        index = export(args.out_dir, args.served_dir, args.terrain_dir, args.nl_dir)
        if args.check_api:
            check_api(index, args.out_dir, args.check_api)
    except StaticExportError as e:
        print(f"static export failed: {e}", file=sys.stderr)
        return 1
    n_h = sum(1 for e in index.scenarios if e.horizon)
    checked = f"; matches {args.check_api}" if args.check_api else ""
    print(
        f"static fallback: {len(index.scenarios)} scenario(s), {n_h} with a horizon, "
        f"{len(index.terrain)} slope statistic(s), {len(index.nl_answers)} cached answer(s), "
        f"contract {CONTRACT_VERSION} -> {args.out_dir}{checked}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
