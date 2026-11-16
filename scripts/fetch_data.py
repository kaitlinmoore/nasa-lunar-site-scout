"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Download the engine's external data into LSS_DATA_DIR (reproducible, idempotent).

    uv run python scripts/fetch_data.py                 # everything
    uv run python scripts/fetch_data.py kernels site01  # some groups
    uv run python scripts/fetch_data.py --list          # show the catalog and local status
    uv run python scripts/fetch_data.py --verify        # re-hash local files against the manifest

The file catalog lives in `lss/datafiles.py`. Each file is written to `<name>.part`, checked
(HTTP status, byte count, leading bytes: some servers answer a missing file with HTTP 200 and an
HTML page), then renamed into place. `LSS_DATA_DIR/MANIFEST.json` records URL, size, SHA-256 and
retrieval time; a rerun skips files that are present and match their manifest entry.

Files with a `clip` are cut from a large GeoTIFF: the whole source is downloaded (one plain
HTTP stream) to `LSS_DATA_DIR/tmp/`, the window is cut locally and saved as a tiled,
deflate-compressed GeoTIFF aligned to the source pixel grid, and the source is deleted
(`--keep-source` keeps it). An interrupted source download is resumed on the next run (HTTP Range).
Remote windowed reads (GDAL /vsicurl/) are NOT used: on the PGDA
server some range requests were refused (HTTP 403), and GDAL then filled the affected tiles with
no-data without raising an error (2026-11-14). Every clip is therefore also checked for no-data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from lss.config import get_settings
from lss.datafiles import FILES, Clip, DataFile, Group, looks_like

USER_AGENT = "lss-fetch/0.1 (lunar site scout data script)"
CHUNK = 1 << 20
RETRIES = 3


def manifest_path() -> Path:
    return get_settings().data_dir / "MANIFEST.json"


def load_manifest() -> dict:
    p = manifest_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def save_manifest(m: dict) -> None:
    p = manifest_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.part")
    tmp.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(p)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def spec(f: DataFile) -> dict:
    """What identifies a file's content: source URL and, for clips, the window."""
    s: dict = {"url": f.url}
    if f.clip:
        s["clip"] = {"x_m": f.clip.x_m, "y_m": f.clip.y_m, "half_width_m": f.clip.half_width_m}
        if f.clip.label_url:  # only when set, so existing clips keep their manifest identity
            s["clip"] |= {"label_url": f.clip.label_url, "scale": f.clip.scale}
    return s


def is_current(f: DataFile, manifest: dict) -> bool:
    entry = manifest.get(f.id)
    if not entry or not f.path.is_file():
        return False
    return all(entry.get(k) == v for k, v in spec(f).items()) and entry.get("size") == f.path.stat().st_size


def check_head(f: DataFile, path: Path) -> None:
    with path.open("rb") as fh:
        head = fh.read(16)
    if not looks_like(f.kind, head):
        raise RuntimeError(f"{f.id}: downloaded bytes are not a {f.kind} file (starts {head[:16]!r})")


def download_url(url: str, part: Path, label: str, resume: bool = False) -> None:
    """Stream `url` into `part`. With `resume`, continue an existing `part` with an HTTP Range request.

    A server that ignores the range (HTTP 200) restarts the file from zero; the final size is always
    checked against the total the server reported.
    """
    have = part.stat().st_size if resume and part.is_file() else 0
    headers = {"User-Agent": USER_AGENT}
    if have:
        headers["Range"] = f"bytes={have}-"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        if r.status == 206 and have:
            content_range = r.headers.get("Content-Range", "")  # "bytes START-END/TOTAL"
            if not content_range.startswith(f"bytes {have}-"):
                raise RuntimeError(f"{label}: unexpected Content-Range {content_range!r}")
            total = int(content_range.rsplit("/", 1)[1])
            mode, n = "ab", have
            print(f"    resuming at {have / 1e6:.1f} MB")
        elif r.status == 200:
            length = r.headers.get("Content-Length")
            total = int(length) if length is not None else None
            mode, n = "wb", 0
        else:
            raise RuntimeError(f"{label}: HTTP {r.status}")
        t0, start = time.monotonic(), n
        with part.open(mode) as out:
            while chunk := r.read(CHUNK):
                out.write(chunk)
                n += len(chunk)
                if total and n % (256 * CHUNK) < CHUNK:
                    print(f"    {n / 1e6:8.1f} / {total / 1e6:.1f} MB", flush=True)
    if total is not None and n != total:
        raise RuntimeError(f"{label}: got {n} bytes, expected {total}")
    print(f"    {(n - start) / 1e6:.1f} MB in {time.monotonic() - t0:.0f} s")


def download(f: DataFile, part: Path, keep_source: bool = False) -> None:
    download_url(f.url, part, f.id)


def clip_window(transform, width: int, height: int, c: Clip) -> tuple[int, int, int, int]:
    """Pixel window (col0, col1, row0, row1), half-open, covering the clip square on the source grid.

    Snapped outward to whole source pixels (so the clip keeps the source grid exactly) and
    limited to the raster. `transform` is a north-up affine (x = c + a*col, y = f + e*row, e < 0).
    """
    t = transform
    if t.b != 0 or t.d != 0 or t.a <= 0 or t.e >= 0:
        raise ValueError("only north-up, unrotated grids are supported")
    col0 = max(0, math.floor((c.x_m - c.half_width_m - t.c) / t.a))
    col1 = min(width, math.ceil((c.x_m + c.half_width_m - t.c) / t.a))
    row0 = max(0, math.floor((c.y_m + c.half_width_m - t.f) / t.e))
    row1 = min(height, math.ceil((c.y_m - c.half_width_m - t.f) / t.e))
    if col1 <= col0 or row1 <= row0:
        raise ValueError("clip window does not overlap the raster")
    return col0, col1, row0, row1


def nodata_fraction(data, nodata) -> float:
    import numpy as np

    bad = np.isnan(data) if nodata is None or np.isnan(nodata) else (data == nodata)
    if np.issubdtype(data.dtype, np.floating):
        bad |= np.isnan(data)
    return float(bad.mean())


def clip(f: DataFile, part: Path, keep_source: bool = False) -> None:
    import numpy as np
    import rasterio
    from rasterio.windows import Window

    assert f.clip is not None
    tmp = get_settings().data_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    source = tmp / f.url.rsplit("/", 1)[-1]
    label = tmp / f.clip.label_url.rsplit("/", 1)[-1] if f.clip.label_url else None
    if label is not None and not label.is_file():
        download_url(f.clip.label_url, label, f.id + " label")
        if not label.read_bytes().startswith(b"PDS_VERSION_ID"):
            label.unlink()
            raise RuntimeError(f"{f.id}: label is not a PDS3 label")
    if not source.is_file():
        src_part = source.with_name(source.name + ".part")
        print(f"    downloading the source to {source} (clipped locally, then deleted)")
        # A partial download is kept and resumed on the next run (the sources are GB-sized).
        download_url(f.url, src_part, f.id + " source", resume=True)
        with src_part.open("rb") as fh:
            if label is None and not looks_like(f.kind, fh.read(16)):  # raw PDS images have no magic
                src_part.unlink()
                raise RuntimeError(f"{f.id}: source is not a {f.kind} file")
        src_part.replace(source)
    with rasterio.open(label or source) as src:
        col0, col1, row0, row1 = clip_window(src.transform, src.width, src.height, f.clip)
        win = Window(col0, row0, col1 - col0, row1 - row0)
        print(f"    window cols {col0}:{col1} rows {row0}:{row1} ({win.width} x {win.height} px)")
        data = src.read(1, window=win)
        frac = nodata_fraction(data, src.nodata)
        if f.clip.scale != 1.0:  # stored counts -> metres, as float32 like the other DEMs
            nan = np.isnan(data) if data.dtype.kind == "f" else data == src.nodata
            data = np.where(nan, np.nan, data.astype(np.float32) * np.float32(f.clip.scale))
            data = data.astype(np.float32)
        if frac > f.clip.max_nodata_fraction:
            raise RuntimeError(
                f"{f.id}: clip is {frac:.2%} no-data (allowed {f.clip.max_nodata_fraction:.2%}); "
                "the source is incomplete or the window is wrong"
            )
        profile = src.profile.copy()
        if f.clip.scale != 1.0:
            profile.update(dtype="float32", nodata=np.nan)
        profile.update(
            driver="GTiff",
            width=win.width,
            height=win.height,
            transform=src.window_transform(win),
            tiled=True,
            blockxsize=512,
            blockysize=512,
            compress="deflate",
            predictor=3,
            BIGTIFF="IF_SAFER",
        )
        tags = src.tags()
    with rasterio.open(part, "w", **profile) as dst:
        dst.write(data, 1)
        dst.update_tags(**tags, LSS_SOURCE_URL=f.url, LSS_CLIP=json.dumps(spec(f)["clip"]))
    if not keep_source:
        source.unlink()
        if label is not None:
            label.unlink()


def fetch(f: DataFile, manifest: dict, force: bool, keep_source: bool = False) -> bool:
    """Fetch one file. Returns True if it was (re)written."""
    if not force and is_current(f, manifest):
        print(f"  ok    {f.id}  ({f.relpath})")
        return False
    print(f"  fetch {f.id}  <- {f.url}" + ("  [clip]" if f.clip else ""))
    f.path.parent.mkdir(parents=True, exist_ok=True)
    part = f.path.with_name(f.path.name + ".part")
    for attempt in range(1, RETRIES + 1):
        try:
            (clip if f.clip else download)(f, part, keep_source)
            check_head(f, part)
            break
        except Exception as e:  # noqa: BLE001 - report and retry any transport/parse failure
            part.unlink(missing_ok=True)
            if attempt == RETRIES:
                raise
            print(f"    attempt {attempt} failed: {e}; retrying")
            time.sleep(5 * attempt)
    part.replace(f.path)
    manifest[f.id] = {
        **spec(f),
        "relpath": f.relpath,
        "dataset_id": f.dataset_id,
        "size": f.path.stat().st_size,
        "sha256": sha256(f.path),
        "retrieved_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_manifest(manifest)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[1], formatter_class=argparse.RawTextHelpFormatter
    )
    ap.add_argument("groups", nargs="*", choices=[g.value for g in Group], help="default: all groups")
    ap.add_argument("--list", action="store_true", help="show the catalog and local status, download nothing")
    ap.add_argument("--verify", action="store_true", help="re-hash local files against the manifest")
    ap.add_argument("--force", action="store_true", help="re-download even if current")
    ap.add_argument("--only", action="append", metavar="ID", help="only these file ids (repeatable)")
    ap.add_argument("--keep-source", action="store_true", help="keep the full source file of clips")
    args = ap.parse_args(argv)

    groups = set(args.groups) or {g.value for g in Group}
    files = [f for f in FILES if f.group.value in groups]
    if args.only:
        unknown = set(args.only) - {f.id for f in FILES}
        if unknown:
            ap.error(f"unknown file id(s): {sorted(unknown)}")
        files = [f for f in files if f.id in args.only]
    manifest = load_manifest()
    print(f"LSS_DATA_DIR = {get_settings().data_dir}")

    if args.list:
        for f in files:
            state = "current" if is_current(f, manifest) else ("present" if f.path.is_file() else "missing")
            print(f"  {state:8s} {f.group.value:10s} {f.id:22s} {f.relpath}")
        return 0

    if args.verify:
        bad = 0
        for f in files:
            entry = manifest.get(f.id)
            if not entry or not f.path.is_file():
                print(f"  MISSING  {f.id}")
                bad += 1
            elif sha256(f.path) != entry["sha256"]:
                print(f"  CHANGED  {f.id}")
                bad += 1
            else:
                print(f"  ok       {f.id}")
        return 1 if bad else 0

    for f in files:
        fetch(f, manifest, args.force, args.keep_source)
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
