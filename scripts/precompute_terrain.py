"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Precomputed slope statistics for the curated sites (C api's request RA4; docs/methodology.md section 5.6), for
the `terrain` and `site_summary` operations.

For each site in lss/registry/sites.yaml, one file LSS_DATA_DIR/cache/terrain/<site id>.json:

    {"format": 1, "site_id": ..., "terrain": [TerrainResponse at 1 km, TerrainResponse at 10 km],
     "provenance": {...}}

1 km is measured on the site's 5 m tile (PGDA product 78); 10 km on a clip of the 10 m polar map (PGDA product
90, LDEM_83S_10MPP_ADJ), over the whole circle (Kaitlin, 2026-11-15). Sites whose files are missing are
skipped with a message.

    uv run python scripts/precompute_terrain.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from lss.config import get_settings
from lss.contract import CONTRACT_VERSION, Stat, TerrainLayer, TerrainResponse
from lss.datafiles import BY_ID
from lss.registry.sites import load_sites, site_points
from lss.terrain.slope import SLOPE_VERSION, slope_stats

FORMAT = 1
RADII_M = (1_000.0, 10_000.0)  # the "around" and "nearby" defaults (C api)
LIMIT_MAX = (
    "The maximum is the steepest single pixel within the radius (often a crater wall), not a typical value."
)
LIMIT_5M = (
    "About 90% of 5 m pixels are interpolated between LOLA tracks (Barker et al. 2021): single-pixel slopes "
    "are low confidence (median RMS slope error 1.9 deg)."
)
LIMIT_10M = (
    "Measured on a 10 m map: slopes are gentler than on the 5 m site map, and features smaller than about "
    "20 m are not resolved."
)


def layer_files(tile: str) -> dict[float, tuple[str, str, float]]:
    """Per radius: (file id, dataset id, resolution)."""
    n = tile[4:].lower()
    clip = "ldem_83s_10m_site01_clip" if n == "01" else f"ldem_83s_10m_site{n}_clip"
    return {
        1_000.0: (f"site{n}_dem", "pgda_78_site_dems", 5.0),
        10_000.0: (clip, "pgda_90_south_pole_dems", 10.0),
    }


def terrain_dir():
    return get_settings().cache_dir / "terrain"


def main() -> int:
    sites = {s.id: s for s in load_sites()}
    for sid, p in site_points().items():
        files = layer_files(p.tile)
        missing = [fid for fid, _, _ in files.values() if not BY_ID[fid].path.is_file()]
        if missing:
            print(f"  skip {sid}: missing {missing} (scripts/fetch_data.py)")
            continue
        out = []
        for radius in RADII_M:
            fid, dataset_id, res = files[radius]
            s = slope_stats(BY_ID[fid].path, *p.ps_m, radius)
            assert s.resolution_m == res
            out.append(
                TerrainResponse(
                    location=sites[sid].location,
                    radius_m=radius,
                    slope_at_point_deg=s.at_point_deg,
                    slope_deg=Stat(min=s.min_deg, max=s.max_deg, mean=s.mean_deg),
                    slope_layer=TerrainLayer(
                        dataset_id=dataset_id,
                        role="near_field",
                        resolution_m=res,
                        max_range_km=radius / 1000.0,
                    ),
                    limitations=[LIMIT_5M if res == 5.0 else LIMIT_10M, LIMIT_MAX],
                ).model_dump(mode="json", by_alias=True)
            )
            print(
                f"  {sid} {radius / 1000:g} km on {res:g} m: point {s.at_point_deg:.2f}, "
                f"min {s.min_deg:.2f} max {s.max_deg:.2f} mean {s.mean_deg:.2f} deg ({s.pixels} px)"
            )
        body = {
            "format": FORMAT,
            "site_id": sid,
            "terrain": out,
            "provenance": {
                "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "contract_version": CONTRACT_VERSION,
                "slope_version": SLOPE_VERSION,
                "point_ps_m": list(p.ps_m),
                "files": {files[r][0]: BY_ID[files[r][0]].url for r in RADII_M},
            },
        }
        path = terrain_dir() / f"{sid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"  written {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
