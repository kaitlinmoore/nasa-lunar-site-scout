# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Data catalog and download-script logic. Offline: no network, no LSS_DATA_DIR needed."""

import importlib.util
import json

import pytest
from rasterio.transform import Affine

from lss.config import REPO_ROOT
from lss.datafiles import FILES, MAGIC, Clip, Group, Kind, looks_like
from lss.registry.loader import load_datasets


def _load_fetch_script():
    spec = importlib.util.spec_from_file_location("fetch_data", REPO_ROOT / "scripts" / "fetch_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fetch_data = _load_fetch_script()


def test_catalog_ids_and_paths_unique():
    assert len({f.id for f in FILES}) == len(FILES)
    assert len({f.relpath for f in FILES}) == len(FILES)


def test_catalog_entries_point_at_registry_and_https():
    registry = {d.id for d in load_datasets()}
    for f in FILES:
        assert f.dataset_id in registry, f.id
        assert f.url.startswith("https://"), f.id
        assert not f.relpath.startswith(("/", "\\")) and ".." not in f.relpath, f.id


def test_every_group_has_files():
    assert {f.group for f in FILES} == set(Group)


@pytest.mark.parametrize(
    "kind, head, ok",
    [
        (Kind.daf, b"DAF/SPK \x00\x00", True),
        (Kind.text_kernel, b"KPL/LSK\n", True),
        (Kind.tiff, b"II*\x00\x08\x00", True),
        (Kind.tiff, b"II+\x00\x08\x00", True),  # BigTIFF
        (Kind.gzip, b"\x1f\x8b\x08", True),
        # The PGDA server answers a missing file with HTTP 200 and an HTML page:
        (Kind.tiff, b"<!DOCTYPE html>", False),
        (Kind.daf, b"<html><head>", False),
    ],
)
def test_looks_like(kind, head, ok):
    assert looks_like(kind, head) is ok


def test_every_kind_has_magic():
    assert set(MAGIC) == set(Kind)


# A 5 m grid like the Site01 tile: x from -19000, y from -4000 (top), 3200 x 3200 px.
SITE_TILE = Affine(5.0, 0.0, -19000.0, 0.0, -5.0, -4000.0)


def test_clip_window_snaps_to_pixels():
    col0, col1, row0, row1 = fetch_data.clip_window(SITE_TILE, 3200, 3200, Clip(-11000, -12000, 1000))
    # x -12000..-10000 -> cols 1400..1800; y -11000..-13000 -> rows 1400..1800
    assert (col0, col1, row0, row1) == (1400, 1800, 1400, 1800)
    t = SITE_TILE @ (col0, row0)
    assert t == (-12000.0, -11000.0)


def test_clip_window_snaps_outward_on_fractional_bounds():
    col0, col1, row0, row1 = fetch_data.clip_window(SITE_TILE, 3200, 3200, Clip(-11002.5, -12002.5, 1000))
    assert (col0, col1) == (1399, 1800)
    assert (row0, row1) == (1400, 1801)


def test_clip_window_is_limited_to_raster():
    assert fetch_data.clip_window(SITE_TILE, 3200, 3200, Clip(-19000, -4000, 2000)) == (0, 400, 0, 400)


def test_clip_window_rejects_no_overlap_and_rotation():
    with pytest.raises(ValueError):
        fetch_data.clip_window(SITE_TILE, 3200, 3200, Clip(50_000, 50_000, 100))
    with pytest.raises(ValueError):
        fetch_data.clip_window(Affine(5, 1, 0, 0, -5, 0), 10, 10, Clip(0, 0, 1))


def test_is_current_requires_matching_url_clip_and_size(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path))
    from lss.config import get_settings

    get_settings.cache_clear()
    try:
        f = next(x for x in FILES if x.clip is not None)
        f.path.parent.mkdir(parents=True)
        f.path.write_bytes(b"II*\x00" + b"\x00" * 12)
        entry = {**fetch_data.spec(f), "size": 16}
        assert fetch_data.is_current(f, {f.id: entry})
        assert not fetch_data.is_current(f, {f.id: {**entry, "size": 17}})
        assert not fetch_data.is_current(f, {f.id: {**entry, "url": "https://example.org/other.tif"}})
        moved = {**entry, "clip": {**entry["clip"], "half_width_m": 1.0}}
        assert not fetch_data.is_current(f, {f.id: moved})
        assert not fetch_data.is_current(f, {})
        # spec() is JSON-serializable (it is stored in MANIFEST.json)
        json.dumps(fetch_data.spec(f))
    finally:
        get_settings.cache_clear()


def test_nodata_fraction_counts_nan_and_sentinel():
    import numpy as np

    a = np.array([[1.0, np.nan], [np.nan, 4.0]], dtype=np.float32)
    assert fetch_data.nodata_fraction(a, np.nan) == 0.5
    assert fetch_data.nodata_fraction(a, None) == 0.5
    assert fetch_data.nodata_fraction(a, 4.0) == 0.75  # sentinel plus NaN
    assert fetch_data.nodata_fraction(np.array([[0, 7]], dtype=np.int16), 0) == 0.5


def _serve(payload: bytes, honour_ranges: bool):
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            rng = self.headers.get("Range")
            if rng and honour_ranges:
                start = int(rng.removeprefix("bytes=").split("-")[0])
                body = payload[start:]
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{len(payload) - 1}/{len(payload)}")
            else:
                body = payload
                self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/f.bin"


@pytest.mark.parametrize("honour_ranges", [True, False])
def test_download_resumes_or_restarts(tmp_path, honour_ranges):
    payload = bytes(range(256)) * 4000  # ~1 MB
    server, url = _serve(payload, honour_ranges)
    try:
        part = tmp_path / "f.bin.part"
        part.write_bytes(payload[:300_000])  # an interrupted earlier download
        fetch_data.download_url(url, part, "test", resume=True)
        assert part.read_bytes() == payload
        # without resume, an existing part is overwritten
        part.write_bytes(b"junk")
        fetch_data.download_url(url, part, "test")
        assert part.read_bytes() == payload
    finally:
        server.shutdown()


def test_pinned_sha256_is_checked(tmp_path):
    """A catalog entry that pins a SHA-256 keeps a download only with exactly that hash; others keep any."""
    import dataclasses
    import hashlib

    from lss.datafiles import get

    pinned = [f for f in FILES if f.sha256]
    assert [f.id for f in pinned] == ["ldem_83s_10m"]
    assert all(len(f.sha256) == 64 and int(f.sha256, 16) >= 0 for f in pinned)
    p = tmp_path / "x.tif"
    p.write_bytes(b"II*\x00 some bytes")
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    f = get("ldem_83s_10m")
    with pytest.raises(RuntimeError, match="differs from the catalog"):
        fetch_data.check_sha256(f, p)
    assert fetch_data.check_sha256(dataclasses.replace(f, sha256=digest), p) == digest
    assert fetch_data.check_sha256(dataclasses.replace(f, sha256=""), p) == digest
