"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Terrain images for the 2D site view (plan F6; lss.terrain.views): for each curated site with a PGDA tile and
each view, a square centred on the served point, on the DEM's own south polar stereographic grid (map up = the
grid's +y axis, not geographic north):

  2km   2 x 2 km from the site's 5 m map (PGDA product 78)       -> 400 x 400 px
  10km  10 x 10 km from the 10 m polar map (PGDA product 90)     -> 1000 x 1000 px

The same maps as the slope statistics at 1 km and 10 km (scripts/precompute_terrain.py). Output per view, in
LSS_DATA_DIR/cache/terrain_view/<site id>/<view>/: hillshade.png (8-bit grey), slope.png (8-bit class number,
255 = no data), elevation.png (16-bit, height = offset + 0.1 m * value, 0 = no data) and view.json (bounds,
projection, pixel size, sources and the encodings).

    uv run python scripts/terrain_views.py [--sites pgda-site01 ...]
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings

import numpy as np

from lss.config import get_settings
from lss.datafiles import BY_ID
from lss.registry.sites import site_points
from lss.terrain import views as tv

FORMAT = 1
PS_SOUTH_PROJ4 = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
VIEWS = {"2km": (1_000.0, "tile"), "10km": (5_000.0, "10m")}


def source_file(tile: str, kind: str) -> str:
    n = tile[4:].lower()
    if kind == "tile":
        return f"site{n}_dem"
    return "ldem_83s_10m_site01_clip" if n == "01" else f"ldem_83s_10m_site{n}_clip"


def read_window(path, x: float, y: float, half: float):
    """The square of half-width `half` centred on (x, y), snapped to whole pixels, plus a 1-pixel margin for
    the gradients. Returns (z, left, top, step)."""
    import rasterio
    from rasterio.windows import Window

    with rasterio.open(path) as d:
        t = d.transform
        step = t.a
        n = int(round(2 * half / step))
        col0 = int(round((x - half - t.c) / step)) - 1
        row0 = int(round((t.f - (y + half)) / step)) - 1
        if col0 < 0 or row0 < 0 or col0 + n + 2 > d.width or row0 + n + 2 > d.height:
            raise ValueError(f"{path.name}: the view leaves the map")
        z = d.read(1, window=Window(col0, row0, n + 2, n + 2)).astype(np.float64)
        if d.nodata is not None and not np.isnan(d.nodata):
            z[z == d.nodata] = np.nan
    return z, t.c + (col0 + 1) * step, t.f - (row0 + 1) * step, step


def write_png(path, data: np.ndarray) -> None:
    import rasterio
    import rasterio.errors

    profile = {
        "driver": "PNG",
        "width": data.shape[1],
        "height": data.shape[0],
        "count": 1,
        "dtype": data.dtype,
    }
    with warnings.catch_warnings(), rasterio.Env(GDAL_PAM_ENABLED="NO"):
        # No georeferencing in the PNG and no .aux.xml sidecar: view.json carries the bounds and projection.
        warnings.simplefilter("ignore", rasterio.errors.NotGeoreferencedWarning)
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(data, 1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--sites", nargs="*")
    a = ap.parse_args(argv)
    points = site_points()
    for sid in a.sites or sorted(points):
        p = points[sid]
        for view, (half, kind) in VIEWS.items():
            fid = source_file(p.tile, kind)
            z, left, top, step = read_window(BY_ID[fid].path, *p.ps_m, half)
            rows, cols = z.shape
            k = tv.interior_scale_factor(left - step, top + step, step, rows, cols)
            elev, offset = tv.elevation_u16(z[1:-1, 1:-1])
            out = get_settings().cache_dir / "terrain_view" / sid / view
            out.mkdir(parents=True, exist_ok=True)
            write_png(out / "hillshade.png", tv.hillshade(z, step, k))
            write_png(out / "slope.png", tv.slope_classes(z, step, k))
            write_png(out / "elevation.png", elev)
            n = cols - 2
            meta = {
                "format": FORMAT,
                "site_id": sid,
                "view": view,
                "center_ps_m": list(p.ps_m),
                "bounds_ps_m": [left, top - n * step, left + n * step, top],  # left, bottom, right, top
                "proj4": PS_SOUTH_PROJ4,
                "map_up": "+y of the south polar stereographic grid (not geographic north)",
                "pixel_m": step,
                "width": n,
                "height": n,
                "source": {"file_id": fid, "dataset_id": BY_ID[fid].dataset_id, "url": BY_ID[fid].url},
                "hillshade": {
                    "file": "hillshade.png",
                    "light_azimuth_map_deg": tv.HILLSHADE_AZIMUTH_DEG,
                    "light_altitude_deg": tv.HILLSHADE_ALTITUDE_DEG,
                    "note": "cartographic shading for reading the relief, not the real Sun",
                },
                "slope": {
                    "file": "slope.png",
                    "definition": "central differences (docs/methodology.md section 5.6)",
                    "class_edges_deg": list(tv.SLOPE_CLASS_EDGES_DEG),
                    "class_labels": list(tv.SLOPE_CLASS_LABELS),
                    "nodata": tv.NODATA_CLASS,
                    "suggested_palette": {m: list(c) for m, c in tv.SLOPE_PALETTE.items()},
                },
                "elevation": {
                    "file": "elevation.png",
                    "offset_m": offset,
                    "scale_m": tv.ELEVATION_SCALE_M,
                    "nodata": 0,
                    "reference": "height above the 1737.4 km sphere",
                },
            }
            (out / "view.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8", newline="\n")
            sizes = sum(f.stat().st_size for f in out.glob("*.png"))
            print(f"  {sid} {view}: {n} x {n} px at {step:g} m, {sizes / 1e3:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
