"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Served point for a Mazarico et al. (2011) site whose published coordinate does not reproduce Table 3
(rule approved by Kaitlin, 2026-11-16; docs/methodology.md section 1.4.1).

Table 3 gives each point to 0.01 deg, so the grid node Mazarico computed lies inside that rounding cell
(near the pole, about 303 m in latitude but only ~24 m in longitude at 85.4 S). The rule:
1. Trigger: the published coordinate misses Table 3 at 10 m by more than the section 6.7 tolerance
   (the Mazarico-matched setting), for average illumination or visibility.
2. Candidates: points of a 240 m polar stereographic lattice inside the rounding cell, under both possible
   registrations of Mazarico's grid (our 240 m map's pixel centres, at odd multiples of 120 m, and its pixel
   corners, at multiples of 240 m). For a registration with no point inside the cell, its point nearest the
   cell.
3. Each candidate is run with the Mazarico-matched setting of section 6.7 (scripts/validation_c3.py
   `maz_run`, variant "emulated": 240 m map only to 400 km, first ray sample 240 m, 0.5 deg azimuth step,
   1970-01-01 + 4 x 18.6 yr at 6 h, observer 0 m and 10 m, geometric disc area).
4. Selection: the smallest mean |difference| from Table 3 over the two 10 m values; ties: nearest to the
   published coordinate. 0 m values are reported, not used.
5. Acceptance: the chosen candidate is within the section 6.7 tolerance at 10 m for both quantities. If not,
   the published coordinate is kept (and its description revised).
6. The slope at the point on the site's 5 m map is reported (section 5.6), as for the other sites.

The section 6.7 tolerances and Table 3 are read from stream A's validation (tests/engine/fixtures/
validation_c3.json, scripts/validation_c3.py), unchanged. Output: LSS_DATA_DIR/cache/sites/
mazarico_node_rank<N>.json (horizons cached beside it).

    uv run python scripts/mazarico_node.py 20
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from lss.config import get_settings
from lss.datafiles import BY_ID
from lss.terrain.core import MOON_RADIUS_M, latlon_from_ps, ps_from_latlon
from lss.terrain.slope import slope_stats

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "engine" / "fixtures" / "validation_c3.json"
SPACING_M = 240.0
REGISTRATIONS = {"pixel_centres": 120.0, "pixel_corners": 0.0}  # lattice offset from multiples of 240 m
ROUNDING_DEG = 0.01


def _validation_c3():
    spec = importlib.util.spec_from_file_location("validation_c3", ROOT / "scripts" / "validation_c3.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def published(rank: int, table: dict) -> tuple[float, float]:
    lon_e, lat_s = table[rank][:2]
    return -lat_s, (lon_e - 360.0 if lon_e > 180.0 else lon_e)


def in_cell(lat: float, lon: float, lat0: float, lon0: float) -> bool:
    """Inside the half-open 0.01 deg cell of values that round to (lat0, lon0)."""
    h = ROUNDING_DEG / 2.0
    dlon = (lon - lon0 + 180.0) % 360.0 - 180.0
    return lat0 - h <= lat < lat0 + h and -h <= dlon < h


def distance_to_cell_m(lat: float, lon: float, lat0: float, lon0: float) -> float:
    """Distance (PS metres; true scale to < 0.1% here) from a point to the nearest point of the cell."""
    h = ROUNDING_DEG / 2.0
    dlon = (lon - lon0 + 180.0) % 360.0 - 180.0
    clat = min(max(lat, lat0 - h), lat0 + h)
    clon = lon0 + min(max(dlon, -h), h)
    x, y = ps_from_latlon(lat, lon, "south")
    cx, cy = ps_from_latlon(clat, clon, "south")
    return float(math.hypot(float(x) - float(cx), float(y) - float(cy)))


def candidates(lat0: float, lon0: float) -> list[dict]:
    x0, y0 = (float(v) for v in ps_from_latlon(lat0, lon0, "south"))
    out = []
    for reg, off in REGISTRATIONS.items():
        pts = []
        k0x, k0y = round((x0 - off) / SPACING_M), round((y0 - off) / SPACING_M)
        for i in range(k0x - 4, k0x + 5):
            for j in range(k0y - 4, k0y + 5):
                x, y = off + i * SPACING_M, off + j * SPACING_M
                lat, lon = (float(v) for v in latlon_from_ps(x, y, "south"))
                pts.append((x, y, lat, lon, distance_to_cell_m(lat, lon, lat0, lon0)))
        inside = [p for p in pts if in_cell(p[2], p[3], lat0, lon0)]
        chosen = inside or [min(pts, key=lambda p: p[4])]
        for x, y, lat, lon, d in chosen:
            out.append(
                {
                    "registration": reg,
                    "inside_cell": bool(inside),
                    "ps_m": [x, y],
                    "lat": lat,
                    "lon": lon,
                    "distance_to_cell_m": d,
                    "distance_to_published_m": float(math.hypot(x - x0, y - y0)),
                }
            )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("rank", type=int, help="Mazarico et al. (2011) Table 3 rank (= product 78 site number)")
    a = ap.parse_args(argv)
    v3 = _validation_c3()
    table = v3.MAZARICO_TABLE3
    row = table[a.rank]
    ref = {
        10.0: {"avg_ill_pct": row[4], "visibility_pct": row[5]},
        0.0: {"avg_ill_pct": row[2], "visibility_pct": row[3]},
    }
    emu = json.loads(FIXTURE.read_text(encoding="utf-8"))["mazarico_table3"]["emulated"]
    tol = {q: emu[f"10m_{q}"]["tolerance_pp_from_shifts"] for q in ("avg_ill_pct", "visibility_pct")}

    out_dir = get_settings().cache_dir / "sites"
    out_dir.mkdir(parents=True, exist_ok=True)
    hz_dir = out_dir / f"mazarico_node_rank{a.rank}_horizons"
    lat0, lon0 = published(a.rank, table)
    result = {
        "rank": a.rank,
        "published": {"lat": lat0, "lon": lon0},
        "table3": {f"{h:g}m": v for h, v in ref.items()},
        "tolerance_10m_pp": tol,
        "candidates": [],
    }
    for c in [
        {"registration": "published", "inside_cell": True, "lat": lat0, "lon": lon0},
        *candidates(lat0, lon0),
    ]:
        t0 = time.monotonic()
        for h in (0.0, 10.0):
            r = v3.maz_run(c["lat"], c["lon"], h, hz_dir, "emulated")
            c[f"{h:g}m"] = {q: r[q] for q in ("avg_ill_pct", "visibility_pct")}
            c[f"{h:g}m_diff_pp"] = {q: r[q] - ref[h][q] for q in ("avg_ill_pct", "visibility_pct")}
        d10 = c["10m_diff_pp"]
        c["mean_abs_diff_10m_pp"] = float(np.mean([abs(d10["avg_ill_pct"]), abs(d10["visibility_pct"])]))
        c["within_tolerance_10m"] = all(abs(d10[q]) <= tol[q] for q in tol)
        c["seconds"] = round(time.monotonic() - t0, 1)
        result["candidates"].append(c)
        print(json.dumps(c), flush=True)

    cands = [c for c in result["candidates"] if c["registration"] != "published"]
    best = min(cands, key=lambda c: (c["mean_abs_diff_10m_pp"], c["distance_to_published_m"]))
    result["chosen"] = best if best["within_tolerance_10m"] else None
    result["decision"] = "move" if best["within_tolerance_10m"] else "keep_published"
    tile = BY_ID[f"site{a.rank:02d}_dem"].path
    if tile.is_file():
        for c in [result["candidates"][0], best]:
            x, y = (float(v) for v in ps_from_latlon(c["lat"], c["lon"], "south"))
            c["slope_at_point_5m_deg"] = float(slope_stats(tile, x, y, 1_000.0).at_point_deg)
    result["moon_radius_m"] = MOON_RADIUS_M
    path = out_dir / f"mazarico_node_rank{a.rank}.json"
    path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"decision: {result['decision']}; best: {best['registration']} {best['lat']:.6f} {best['lon']:.6f}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
