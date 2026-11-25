"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Official IAU names of lunar surface features, for labels on the 3D globe (the project author, 2026-11-16;
registry entry `iau_gazetteer_moon` in lss/registry/datasets.yaml).

Downloads the Moon centre-point shapefile of the Gazetteer of Planetary Nomenclature (IAU Working Group for
Planetary System Nomenclature, maintained by the USGS Astrogeology Science Center; public domain) and writes
LSS_DATA_DIR/cache/features/iau_names.json:

    {"format": 1, "source": {...}, "coordinates": "...", "approval": "Adopted by IAU",
     "types": {code: descriptor}, "fields": ["id", "name", "type", "lat", "lon", "diameter_km"],
     "features": [[id, name, type code, lat, lon, diameter km], ...]}

- Only names with approval status "Adopted by IAU" are kept (the download holds only those today; checked).
- `id` is the Gazetteer feature number (https://planetarynames.wr.usgs.gov/Feature/<id>).
- `name` is the published name with its diacritical marks (the `name` field, not `clean_name`).
- Coordinates as published: planetocentric latitude and east longitude (stored -180..180, the Gazetteer's
  system for the Moon), 4 decimals (lossless), on a sphere. The Gazetteer states that lunar coordinates are in
  the LOLA reference frame, "referred to the mean Earth/polar axis reference coordinate system for the Moon"
  (Gazetteer news, 2012-06-04): the engine's MOON_ME frame, so no transformation is applied. Positions are for
  identifying features ("expected precision ... 2 decimal places"): labels only.
- `--exclude-satellite` drops "Satellite Feature" names (lettered craters such as "Marco Polo P").

    uv run python scripts/fetch_iau_names.py [--zip PATH] [--exclude-satellite]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import struct
import sys
import urllib.request
import zipfile
from datetime import UTC, datetime

URL = "https://asc-planetarynames-data.s3.us-west-2.amazonaws.com/MOON_nomenclature_center_pts.zip"
STEM = "MOON_nomenclature_center_pts"
FORMAT = 1
ADOPTED = "Adopted by IAU"
SATELLITE = "SF"  # descriptor code of "Satellite Feature"
FIELDS = ["id", "name", "type", "lat", "lon", "diameter_km"]
LINK = re.compile(r"https?://planetarynames\.wr\.usgs\.gov/Feature/(\d+)")
COORDINATES = (
    "Planetocentric latitude and east longitude (-180..180), degrees, on a sphere; LOLA reference frame, "
    "mean Earth/polar axis (Gazetteer of Planetary Nomenclature); for identifying features, expected "
    "precision 2 decimal places."
)
CITATION = (
    "International Astronomical Union Working Group for Planetary System Nomenclature. "
    '"Gazetteer of Planetary Nomenclature." Accessed {date}. https://planetarynames.wr.usgs.gov/'
)


# ----------------------------------------------------------------------------- shapefile parts


def read_dbf(data: bytes, encoding: str = "utf-8") -> list[dict[str, str]]:
    """Records of a dBASE III table as {field: stripped text}; records flagged deleted are skipped."""
    if len(data) < 32 or data[0] not in (0x03, 0x83):
        raise ValueError("not a dBASE III table")
    n, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields, p = [], 32
    while data[p] != 0x0D:
        name = data[p : p + 11].split(b"\0")[0].decode("ascii")
        fields.append((name, data[p + 16]))
        p += 32
    if sum(length for _, length in fields) + 1 != record_len:
        raise ValueError("field lengths do not add up to the record length")
    if header_len + n * record_len > len(data):
        raise ValueError("table is shorter than its header says")
    out = []
    for i in range(n):
        r = data[header_len + i * record_len : header_len + (i + 1) * record_len]
        if r[:1] == b"*":
            continue
        rec, q = {}, 1
        for name, length in fields:
            rec[name] = r[q : q + length].decode(encoding).strip()
            q += length
        out.append(rec)
    return out


def read_points(data: bytes) -> list[tuple[float, float] | None]:
    """(x, y) of each record of a point shapefile (None for a null shape), in file order."""
    if struct.unpack(">i", data[:4])[0] != 9994 or struct.unpack("<i", data[32:36])[0] != 1:
        raise ValueError("not a point shapefile")
    pts, p = [], 100
    while p < len(data):
        _, words = struct.unpack(">ii", data[p : p + 8])
        shape_type = struct.unpack("<i", data[p + 8 : p + 12])[0]
        pts.append(struct.unpack("<2d", data[p + 12 : p + 28]) if shape_type == 1 else None)
        p += 8 + 2 * words
    return pts


def read_zip(zip_bytes: bytes) -> list[dict[str, str]]:
    """The Gazetteer's records, each checked against its point geometry (the same centre to 1e-9 deg)."""
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = set(z.namelist())
    encoding = z.read(f"{STEM}.cpg").decode("ascii").strip().lower() if f"{STEM}.cpg" in names else "utf-8"
    if encoding not in ("utf-8", "utf8"):
        raise ValueError(f"unexpected encoding {encoding!r}")
    if "GCS_Moon" not in z.read(f"{STEM}.prj").decode("ascii", "replace"):
        raise ValueError("unexpected coordinate system in the .prj")
    recs = read_dbf(z.read(f"{STEM}.dbf"))
    pts = read_points(z.read(f"{STEM}.shp"))
    if len(pts) != len(recs):
        raise ValueError(f"{len(pts)} shapes for {len(recs)} records")
    for rec, pt in zip(recs, pts, strict=True):
        lon, lat = float(rec["center_lon"]), float(rec["center_lat"])
        if pt is None or abs((pt[0] - lon + 180.0) % 360.0 - 180.0) > 1e-9 or abs(pt[1] - lat) > 1e-9:
            raise ValueError(f"{rec['name']}: point geometry differs from center_lon/center_lat")
    return recs


# ----------------------------------------------------------------------------- the compact file


def east_180(lon: float) -> float:
    """East longitude in -180..180."""
    return lon - 360.0 if lon > 180.0 else lon


def features(recs: list[dict[str, str]], include_satellite: bool = True) -> tuple[dict[str, str], list[list]]:
    """(type code -> descriptor, rows [id, name, type code, lat, lon, diameter km]) for the adopted names,
    sorted by id."""
    types: dict[str, str] = {}
    rows, seen = [], set()
    for r in recs:
        if r["approval"] != ADOPTED or (not include_satellite and r["code"] == SATELLITE):
            continue
        m = LINK.fullmatch(r["link"])
        if not m:
            raise ValueError(f"{r['name']}: unexpected link {r['link']!r}")
        fid = int(m.group(1))
        if fid in seen:
            raise ValueError(f"duplicate feature id {fid}")
        seen.add(fid)
        if types.setdefault(r["code"], r["type"]) != r["type"]:
            raise ValueError(f"code {r['code']} has two descriptors")
        lat, lon, diam = float(r["center_lat"]), east_180(float(r["center_lon"])), float(r["diameter"])
        if not (r["name"] and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0 and diam >= 0.0):
            raise ValueError(f"{r['name']!r}: value out of range")
        rows.append([fid, r["name"], r["code"], round(lat, 4), round(lon, 4), round(diam, 8)])
    rows.sort(key=lambda row: row[0])
    return dict(sorted(types.items())), rows


def build(zip_bytes: bytes, source: dict, include_satellite: bool = True) -> dict:
    recs = read_zip(zip_bytes)
    types, rows = features(recs, include_satellite)
    accessed = source.get("downloaded_utc", "")[:10]
    return {
        "format": FORMAT,
        "source": {
            **source,
            "sha256": hashlib.sha256(zip_bytes).hexdigest(),
            "records_in_file": len(recs),
            "citation": CITATION.format(date=accessed),
            "license": "Public domain (Gazetteer FAQ; metadata use constraints)",
        },
        "coordinates": COORDINATES,
        "approval": ADOPTED,
        "satellite_features_included": include_satellite,
        "types": types,
        "fields": FIELDS,
        "features": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="IAU lunar feature names -> cache/features/iau_names.json")
    ap.add_argument("--zip", help="read this downloaded zip instead of downloading")
    ap.add_argument("--exclude-satellite", action="store_true", help='drop "Satellite Feature" names')
    a = ap.parse_args(argv)

    from lss.config import get_settings

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if a.zip:
        data = open(a.zip, "rb").read()
        source = {"url": URL, "downloaded_utc": now, "read_from": "local zip"}
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": "lunar-site-scout data script"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
            source = {
                "url": URL,
                "downloaded_utc": now,
                "last_modified": resp.headers.get("Last-Modified"),
                "etag": (resp.headers.get("ETag") or "").strip('"'),
            }
    body = build(data, source, include_satellite=not a.exclude_satellite)
    out = get_settings().cache_dir / "features" / "iau_names.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    n_sf = sum(1 for row in body["features"] if row[2] == SATELLITE)
    total = body["source"]["records_in_file"]
    print(f"{len(body['features'])} features ({n_sf} satellite features) of {total}")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
