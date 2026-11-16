"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Terrain images for the 2D site view (plan F6; lss.terrain.views): for each curated site with a PGDA tile and
each view, a square centred on the served point, on the DEM's own south polar stereographic grid (map up = the
grid's +y axis, not geographic north):

  2km   2 x 2 km from the site's 5 m map (PGDA product 78)                     -> 400 x 400 px at 5 m
  20km  20 x 20 km from the 10 m polar map (PGDA product 90), 2 x 2 block means  -> 1000 x 1000 px at 20 m

(Kaitlin, 2026-11-16.) Output per view, in LSS_DATA_DIR/cache/terrain_view/<site id>/<view>/: hillshade.png
(8-bit grey), slope.png (8-bit class number, 255 = no data) and view.json (bounds, projection, pixel size,
source and the encodings). The slope classes are computed at the view's own pixel size.

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
from lss.registry.sites import load_sites, site_points
from lss.terrain import views as tv

FORMAT = 1
PS_SOUTH_PROJ4 = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
# view: (half-width m, source, block size: pixels of the source averaged into one image pixel)
VIEWS = {"2km": (1_000.0, "tile", 1), "20km": (10_000.0, "10m", 2)}


def source_file(tile: str, kind: str) -> str:
    n = tile[4:].lower()
    if kind == "tile":
        return f"site{n}_dem"
    return "ldem_83s_10m_site01_clip" if n == "01" else f"ldem_83s_10m_site{n}_clip"


def other_site_sources(site) -> tuple[tuple[float, float], dict[str, tuple[str, int]]]:
    """A site without a PGDA site point (the Artemis III regions): its point from its coordinates; the 2 km
    view from the 5 m site map if the point lies on one, else from the 10 m map at 10 m/pixel; the 20 km view
    from the 10 m map (2 x 2 block means). Returns (point, {view: (file id, block)})."""
    from lss.registry.terrain import resolve
    from lss.terrain.core import ps_from_latlon

    loc = site.location
    ps = tuple(float(v) for v in ps_from_latlon(loc.lat, loc.lon, "south"))
    clip = f"ldem_83s_10m_{site.id.replace('-', '_')}_clip"
    near = resolve(loc.lat, loc.lon).layers[0].spec
    return ps, {"2km": (near.file_id if near.site_tile else clip, 1), "20km": (clip, 2)}


def read_window(path, x: float, y: float, half: float, block: int = 1):
    """The square of half-width `half` centred on (x, y), snapped to whole source pixels, averaged over
    `block` x `block` source pixels, plus a 1-pixel margin (in output pixels) for the gradients. A block with
    any pixel without data has no data. Returns (z, left, top, step), step = block x the source pixel."""
    import rasterio
    from rasterio.windows import Window

    with rasterio.open(path) as d:
        t = d.transform
        src = t.a
        step = src * block
        n = int(round(2 * half / step))  # output pixels across the view
        col0 = int(round((x - half - t.c) / src)) - block
        row0 = int(round((t.f - (y + half)) / src)) - block
        w = (n + 2) * block
        if col0 < 0 or row0 < 0 or col0 + w > d.width or row0 + w > d.height:
            raise ValueError(f"{path.name}: the view leaves the map")
        z = d.read(1, window=Window(col0, row0, w, w)).astype(np.float64)
        if d.nodata is not None and not np.isnan(d.nodata):
            z[z == d.nodata] = np.nan
    if block > 1:
        z = z.reshape(n + 2, block, n + 2, block).mean(axis=(1, 3))
    return z, t.c + col0 * src + step, t.f - row0 * src - step, step


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
    sites = {s.id: s for s in load_sites()}
    for sid in a.sites or sorted(points):
        if sid in points:
            ps = points[sid].ps_m
            sources = {
                v: (source_file(points[sid].tile, kind), block) for v, (_, kind, block) in VIEWS.items()
            }
        else:
            ps, sources = other_site_sources(sites[sid])
        for view, (half, _kind, _block) in VIEWS.items():
            fid, block = sources[view]
            z, left, top, step = read_window(BY_ID[fid].path, *ps, half, block)
            rows, cols = z.shape
            k = tv.interior_scale_factor(left - step, top + step, step, rows, cols)
            out = get_settings().cache_dir / "terrain_view" / sid / view
            out.mkdir(parents=True, exist_ok=True)
            for old in out.glob("*.png"):  # an earlier spec's layers (e.g. elevation) must not linger
                old.unlink()
            write_png(out / "hillshade.png", tv.hillshade(z, step, k))
            write_png(out / "slope.png", tv.slope_classes(z, step, k))
            n = cols - 2
            meta = {
                "format": FORMAT,
                "site_id": sid,
                "view": view,
                "center_ps_m": list(ps),
                "bounds_ps_m": [left, top - n * step, left + n * step, top],  # left, bottom, right, top
                "proj4": PS_SOUTH_PROJ4,
                "map_up": "+y of the south polar stereographic grid (not geographic north)",
                "pixel_m": step,
                "width": n,
                "height": n,
                "source": {
                    "file_id": fid,
                    "dataset_id": BY_ID[fid].dataset_id,
                    "url": BY_ID[fid].url,
                    "source_pixel_m": step / block,
                    "block_mean": block,  # source pixels averaged per image pixel, per axis
                },
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
            }
            (out / "view.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8", newline="\n")
            sizes = sum(f.stat().st_size for f in out.glob("*.png"))
            print(f"  {sid} {view}: {n} x {n} px at {step:g} m, {sizes / 1e3:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
