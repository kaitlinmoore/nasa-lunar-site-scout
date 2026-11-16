# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Terrain images for the 2D site view (contract 0.13.0): the loader's checks, the routes, the static copy;
and CompareResponse.compared_keys. Small synthetic PNGs; no real data needed."""

import json
import os
import struct
import zlib

import pytest
from fastapi.testclient import TestClient

import lss.api.app as app_module
from lss.api import static_export
from lss.api.terrain_views import TerrainViewError, load_views
from lss.config import get_settings
from lss.contract import CompareResponse, NotFoundError, Scenario, StaticIndex, TerrainViewsResponse
from lss.registry.sites import load_sites
from lss.terrain.core import ps_from_latlon
from tests.api.test_thin_slice import WEB_SCENARIO, write_served

SITES = load_sites()
SITE01 = next(s for s in SITES if s.id == "pgda-site01")


def png(width, height, depth=8, extra_chunk=None, noise=False):
    """A greyscale PNG (colour type 0) of zeros, or of random bytes (`noise`, so it doesn't compress)."""

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    def row():
        return b"\x00" + (os.urandom(width * depth // 8) if noise else bytes(width * depth // 8))

    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, 0, 0, 0, 0))
    if extra_chunk:
        out += chunk(extra_chunk, b"\x00\x00\x00\x01")
    return out + chunk(b"IDAT", zlib.compress(b"".join(row() for _ in range(height)))) + chunk(b"IEND", b"")


def write_view(
    root, site=SITE01, view="2km", size=8, pixel=5.0, folder_view=None, depth=8, extra=None, shift=0.0
):
    x, y = (float(v) for v in ps_from_latlon(site.location.lat, site.location.lon, "south"))
    half = size * pixel / 2
    folder = root / site.id / (folder_view or view)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "hillshade.png").write_bytes(png(size, size, depth, extra))
    (folder / "slope.png").write_bytes(png(size, size))
    data = {
        "format": 1,
        "site_id": site.id,
        "view": view,
        "center_ps_m": [x + shift, y],
        "bounds_ps_m": [x - half, y - half, x + half, y + half],
        "proj4": "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs",
        "map_up": "+y of the south polar stereographic grid (not geographic north)",
        "pixel_m": pixel,
        "width": size,
        "height": size,
        "source": {"file_id": "f", "dataset_id": "pgda_78_site_dems", "url": "https://example.test/map.tif"},
        "hillshade": {"file": "hillshade.png", "light_azimuth_map_deg": 315.0, "light_altitude_deg": 45.0},
        "slope": {
            "file": "slope.png",
            "definition": "central differences",
            "class_edges_deg": [5.0, 10.0, 15.0, 20.0],
            "class_labels": ["under 5°", "5–10°", "10–15°", "15–20°", "20° or more"],
            "nodata": 255,
            "suggested_palette": {"light": ["#111111"] * 5, "dark": ["#eeeeee"] * 5},
        },
    }
    (folder / "view.json").write_text(json.dumps(data), encoding="utf-8")
    return folder


# ------------------------------------------------------------------------------------ the loader


def test_loader_reads_views_in_site_then_size_order(tmp_path):
    write_view(tmp_path, view="20km", size=10, pixel=20.0)
    write_view(tmp_path, view="2km")
    views = load_views(tmp_path, sites=SITES)
    assert list(views) == [("pgda-site01", "2km"), ("pgda-site01", "20km")]
    v = views[("pgda-site01", "2km")].view
    assert v.center == SITE01.location and [layer.value for layer in v.layers] == ["hillshade", "slope"]
    assert v.slope.palette_light == ["#111111"] * 5 and v.hillshade.light_azimuth_map_deg == 315.0


@pytest.mark.parametrize(
    "kwargs, why",
    [
        ({"depth": 16}, "8-bit greyscale"),
        ({"extra": b"gAMA"}, "gAMA"),
        ({"folder_view": "other"}, "in folder"),
        ({"shift": 50.0}, "more than one pixel"),
    ],
)
def test_loader_refuses_what_a_browser_or_the_contract_couldnt_use(tmp_path, kwargs, why):
    write_view(tmp_path, **kwargs)
    with pytest.raises(TerrainViewError, match=why):
        load_views(tmp_path, sites=SITES)


def test_loader_refuses_a_size_mismatch_and_an_unknown_site(tmp_path):
    folder = write_view(tmp_path)
    (folder / "slope.png").write_bytes(png(4, 4))
    with pytest.raises(TerrainViewError, match="view.json says"):
        load_views(tmp_path, sites=SITES)
    with pytest.raises(TerrainViewError, match="not a curated site"):
        load_views(tmp_path, sites=[s for s in SITES if s.id != "pgda-site01"])


# ------------------------------------------------------------------------------------- the routes


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path))
    caches = (get_settings, app_module._served, app_module._terrain, app_module._terrain_views)
    for f in caches:
        f.cache_clear()
    write_served(tmp_path / "cache" / "served")
    write_view(tmp_path / "cache" / "terrain_view")
    yield tmp_path
    for f in caches:
        f.cache_clear()


def test_views_route_lists_a_sites_views(data_dir):
    c = TestClient(app_module.create_app())
    body = TerrainViewsResponse.model_validate(
        c.get("/api/terrain/views", params={"site_id": "pgda-site01"}).json()
    )
    assert [v.view for v in body.views] == ["2km"]
    assert c.get("/api/terrain/views", params={"site_id": "apollo-11"}).json()["views"] == []


def test_image_route_serves_the_png_and_404s_the_rest(data_dir):
    c = TestClient(app_module.create_app())
    r = c.get("/api/terrain/view/pgda-site01/2km/slope.png")
    assert (
        r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content.startswith(b"\x89PNG")
    )
    for path in ("pgda-site01/2km/elevation.png", "pgda-site01/9km/slope.png", "apollo-11/2km/slope.png"):
        r = c.get(f"/api/terrain/view/{path}")
        assert r.status_code == 404
        assert NotFoundError.model_validate(r.json()).detail.reason == app_module.NO_TERRAIN_IMAGE_REASON


def test_images_are_not_recompressed_but_json_is(data_dir):
    folder = write_view(data_dir / "cache" / "terrain_view", size=64)
    (folder / "slope.png").write_bytes(png(64, 64, noise=True))  # over the 1 KB gzip threshold
    app_module._terrain_views.cache_clear()
    c = TestClient(app_module.create_app())
    r = c.get("/api/terrain/view/pgda-site01/2km/slope.png", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and len(r.content) > 1000
    assert "content-encoding" not in r.headers and r.content == (folder / "slope.png").read_bytes()
    r = c.post("/api/series", json={"scenario": WEB_SCENARIO}, headers={"Accept-Encoding": "gzip"})
    assert len(r.content) > 1000 and r.headers.get("content-encoding") == "gzip"


def test_unusable_views_are_a_503(data_dir):
    (data_dir / "cache" / "terrain_view" / "pgda-site01" / "2km" / "slope.png").write_bytes(png(4, 4))
    assert TestClient(app_module.create_app()).get("/api/terrain/views").status_code == 503


def test_static_copy_has_the_images_and_checks_the_list(data_dir, monkeypatch):
    client = TestClient(app_module.create_app())

    def fake_get_json(url, body=None):
        path = url.removeprefix("https://api.example")
        r = client.post(path, json=body) if body is not None else client.get(path)
        r.raise_for_status()
        return r.json()

    monkeypatch.setattr(static_export, "_get_json", fake_get_json)
    out = data_dir / "static"
    assert static_export.main([str(out), "--check-api", "https://api.example"]) == 0
    index = StaticIndex.model_validate(json.loads((out / "index.json").read_text(encoding="utf-8")))
    assert index.terrain_views == "terrain_views.json"
    assert (
        json.loads((out / "terrain_views.json").read_text(encoding="utf-8"))
        == client.get("/api/terrain/views").json()
    )
    static_png = (out / "terrain_view" / "pgda-site01" / "2km" / "slope.png").read_bytes()
    assert static_png == client.get("/api/terrain/view/pgda-site01/2km/slope.png").content


# ------------------------------------------------------------------------------ compared_keys


def test_compared_keys_match_compared(data_dir):
    sc2 = dict(WEB_SCENARIO, unit_height_m=2.0)
    r = TestClient(app_module.create_app()).post("/api/compare", json={"scenarios": [WEB_SCENARIO, sc2]})
    body = CompareResponse.model_validate(r.json())
    assert body.compared_keys == [sc.key() for sc in body.compared]
    assert body.compared_keys == [Scenario.model_validate(s).key() for s in (WEB_SCENARIO, sc2)]
