"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Precomputed terrain images for the 2D site view (contract 0.13.0; stream A's images, methodology 5.7).

Stream A writes `LSS_DATA_DIR/cache/terrain_view/<site id>/<view>/` with `view.json` (format 1) and one
8-bit greyscale PNG per layer (`hillshade.png`, `slope.png`). This module loads them into contract
`TerrainView`s and checks every file the API will serve:
- the folder names match `site_id` / `view`, and the site is a curated site;
- every layer's PNG exists, is 8-bit greyscale at the stated width and height, and carries no colour-profile
  chunks (gAMA, iCCP, sRGB, cHRM), so browsers decode the values unchanged (slope class numbers);
- the site's served point lies within one pixel of the view's centre (the bounds snap to the pixel grid).
`center` in the contract is the site's own location (the served point). Nothing here reads a DEM.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from lss.config import get_settings
from lss.contract import (
    Site,
    TerrainView,
    TerrainViewHillshade,
    TerrainViewLayer,
    TerrainViewSlope,
    TerrainViewSource,
)

VIEW_FORMAT = 1
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
COLOUR_CHUNKS = {b"gAMA", b"iCCP", b"sRGB", b"cHRM"}


class TerrainViewError(ValueError):
    """A terrain view that is inconsistent or unreadable."""


@dataclass(frozen=True)
class ServedView:
    view: TerrainView
    folder: Path

    def image(self, layer: TerrainViewLayer) -> Path | None:
        return self.folder / f"{layer.value}.png" if layer in self.view.layers else None


def terrain_view_dir() -> Path:
    return get_settings().cache_dir / "terrain_view"


def _check_png(path: Path, width: int, height: int) -> None:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise TerrainViewError(f"{path}: not a PNG")
    w, h, depth, colour = struct.unpack(">IIBB", data[16:26])
    if (w, h) != (width, height):
        raise TerrainViewError(f"{path}: {w} × {h} px, view.json says {width} × {height}")
    if (depth, colour) != (8, 0):
        raise TerrainViewError(f"{path}: bit depth {depth}, colour type {colour}; expected 8-bit greyscale")
    i = 8
    while i + 8 <= len(data):
        n, kind = struct.unpack(">I4s", data[i : i + 8])
        if kind in COLOUR_CHUNKS:
            raise TerrainViewError(
                f"{path}: has a {kind.decode()} chunk (browsers may change decoded values)"
            )
        i += 12 + n


def _load_one(view_json: Path, sites: dict[str, Site]) -> ServedView:
    from lss.terrain.core import ps_from_latlon  # numpy only

    data = json.loads(view_json.read_text(encoding="utf-8"))
    folder = view_json.parent
    if data.get("format") != VIEW_FORMAT:
        raise TerrainViewError(f"{view_json}: format {data.get('format')}, expected {VIEW_FORMAT}")
    site_id, name = data["site_id"], data["view"]
    if (folder.parent.name, folder.name) != (site_id, name):
        raise TerrainViewError(
            f"{view_json}: in folder {folder.parent.name}/{folder.name}, says {site_id}/{name}"
        )
    site = sites.get(site_id)
    if site is None:
        raise TerrainViewError(f"{view_json}: {site_id} is not a curated site")
    width, height, pixel = int(data["width"]), int(data["height"]), float(data["pixel_m"])
    layers = []
    for layer in TerrainViewLayer:
        spec = data.get(layer.value)
        if spec is None:
            continue
        png = folder / spec.get("file", f"{layer.value}.png")
        if png.name != f"{layer.value}.png" or not png.is_file():
            raise TerrainViewError(f"{view_json}: the {layer.value} image is missing or misnamed")
        _check_png(png, width, height)
        layers.append(layer)
    x, y = ps_from_latlon(site.location.lat, site.location.lon, "south")
    cx, cy = (float(v) for v in data["center_ps_m"])
    if max(abs(float(x) - cx), abs(float(y) - cy)) > pixel:
        raise TerrainViewError(f"{view_json}: centre is more than one pixel from {site_id}'s served point")
    slope = data.get("slope")
    palette = (slope or {}).get("suggested_palette") or {}
    view = TerrainView(
        site_id=site_id,
        view=name,
        center=site.location,
        bounds_ps_m=[float(v) for v in data["bounds_ps_m"]],
        proj4=data["proj4"],
        map_up=data["map_up"],
        pixel_m=pixel,
        width=width,
        height=height,
        layers=layers,
        source=TerrainViewSource(
            dataset_id=data["source"]["dataset_id"],
            url=data["source"]["url"],
            source_pixel_m=data["source"].get("source_pixel_m"),
            block_mean=data["source"].get("block_mean"),
        ),
        hillshade=TerrainViewHillshade(
            light_azimuth_map_deg=data["hillshade"]["light_azimuth_map_deg"],
            light_altitude_deg=data["hillshade"]["light_altitude_deg"],
            note=data["hillshade"].get("note"),
        )
        if data.get("hillshade")
        else None,
        slope=TerrainViewSlope(
            definition=slope["definition"],
            class_edges_deg=slope["class_edges_deg"],
            class_labels=slope["class_labels"],
            nodata=slope["nodata"],
            palette_light=palette.get("light", []),
            palette_dark=palette.get("dark", []),
        )
        if slope
        else None,
    )
    return ServedView(view, folder)


def load_views(
    directory: Path | None = None, sites: Sequence[Site] = ()
) -> dict[tuple[str, str], ServedView]:
    """Every terrain view in the directory, by (site_id, view), in site-list order then by size (smallest
    first). Empty if the directory is missing. Raises TerrainViewError on an inconsistent view."""
    d = directory or terrain_view_dir()
    by_id = {s.id: s for s in sites}
    order = {s.id: i for i, s in enumerate(sites)}
    found = [_load_one(p, by_id) for p in sorted(d.glob("*/*/view.json"))] if d.is_dir() else []
    found.sort(key=lambda sv: (order.get(sv.view.site_id, len(order)), sv.view.width * sv.view.pixel_m))
    return {(sv.view.site_id, sv.view.view): sv for sv in found}
