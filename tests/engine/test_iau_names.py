# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""scripts/fetch_iau_names.py: the Gazetteer of Planetary Nomenclature parser (dBASE table, point shapefile,
zip) and the compact file, on a small synthetic shapefile written here; plus checks of the real file when
LSS_DATA_DIR/cache/features/iau_names.json is on this machine."""

import importlib.util
import io
import json
import math
import struct
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def script():
    spec = importlib.util.spec_from_file_location("fetch_iau_names", ROOT / "scripts" / "fetch_iau_names.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


F = script()

# The real file's layout (field, type, length) for the fields the parser reads, plus one it ignores.
FIELDS = [
    ("name", "C", 60),
    ("clean_name", "C", 60),
    ("diameter", "N", 24),
    ("center_lon", "N", 24),
    ("center_lat", "N", 24),
    ("type", "C", 40),
    ("code", "C", 4),
    ("approval", "C", 30),
    ("link", "C", 80),
]


def rec(
    fid, name, lat, lon, diam, code="AA", typ="Crater, craters", approval="Adopted by IAU", deleted=False
):
    return {
        "name": name,
        "clean_name": name,
        "diameter": f"{diam:.15f}",
        "center_lon": f"{lon:.15f}",
        "center_lat": f"{lat:.15f}",
        "type": typ,
        "code": code,
        "approval": approval,
        "link": f"http://planetarynames.wr.usgs.gov/Feature/{fid}",
        "_deleted": deleted,
    }


def dbf_bytes(recs):
    record_len = 1 + sum(length for _, _, length in FIELDS)
    header_len = 32 + 32 * len(FIELDS) + 1
    out = bytearray(struct.pack("<BBBBIHH20x", 0x03, 126, 11, 16, len(recs), header_len, record_len))
    for name, typ, length in FIELDS:
        out += struct.pack("<11sc4xBB14x", name.encode(), typ.encode(), length, 15 if typ == "N" else 0)
    out += b"\x0d"
    for r in recs:
        row = bytearray(b"*" if r["_deleted"] else b" ")
        for name, _, length in FIELDS:
            v = r[name].encode("utf-8")
            assert len(v) <= length
            row += v.ljust(length, b" ")
        out += row
    return bytes(out + b"\x1a")


def shp_bytes(points):
    body = b""
    for i, (x, y) in enumerate(points, 1):
        body += struct.pack(">ii", i, 10) + struct.pack("<i2d", 1, x, y)
    header = struct.pack(">i20xi", 9994, (100 + len(body)) // 2) + struct.pack(
        "<ii4d32x", 1000, 1, 0, 0, 0, 0
    )
    return header + body


def make_zip(recs, points=None, prj='GEOGCS["GCS_Moon_2000",DATUM["D_Moon_2000"]]', cpg="UTF-8"):
    points = (
        points if points is not None else [(float(r["center_lon"]), float(r["center_lat"])) for r in recs]
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{F.STEM}.dbf", dbf_bytes(recs))
        z.writestr(f"{F.STEM}.shp", shp_bytes(points))
        z.writestr(f"{F.STEM}.prj", prj)
        z.writestr(f"{F.STEM}.cpg", cpg)
    return buf.getvalue()


RECS = [
    rec(948, "Bürg", 45.0734, 28.2081, 41.04228),
    rec(11150, "Marco Polo P", 16.9673, 359.6815, 28.06208, code="SF", typ="Satellite Feature"),
    rec(5684, "Statio Tranquillitatis", 0.6741, 23.4732, 0.009, code="ST", typ="Statio"),
    rec(5450, "Shackleton", -89.67, 129.78, 20.924982),
    rec(99, "Dropped name", 10.0, 10.0, 5.0, approval="Dropped, disallowed"),
    rec(98, "Deleted row", 11.0, 11.0, 5.0, deleted=True),
]


# ----------------------------------------------------------------------------- parser


def test_dbf_reads_utf8_names_and_skips_deleted_records():
    recs = F.read_dbf(dbf_bytes(RECS))
    assert [r["name"] for r in recs] == [
        "Bürg",
        "Marco Polo P",
        "Statio Tranquillitatis",
        "Shackleton",
        "Dropped name",
    ]
    assert float(recs[0]["center_lat"]) == 45.0734 and recs[1]["code"] == "SF"


def test_dbf_rejects_inconsistent_headers():
    data = bytearray(dbf_bytes(RECS))
    with pytest.raises(ValueError, match="dBASE"):
        F.read_dbf(b"\x00" + bytes(data[1:]))
    data[10] += 1  # record length no longer the sum of the field lengths
    with pytest.raises(ValueError, match="record length"):
        F.read_dbf(bytes(data))


def test_points_and_geometry_check():
    pts = F.read_points(shp_bytes([(1.0, 2.0), (359.5, -89.0)]))
    assert pts == [(1.0, 2.0), (359.5, -89.0)]
    good = [r for r in RECS if not r["_deleted"]]
    assert (
        len(F.read_zip(make_zip(RECS, [(float(r["center_lon"]), float(r["center_lat"])) for r in good]))) == 5
    )
    moved = [(float(r["center_lon"]), float(r["center_lat"])) for r in good]
    moved[2] = (moved[2][0] + 0.001, moved[2][1])
    with pytest.raises(ValueError, match="geometry differs"):
        F.read_zip(make_zip(RECS, moved))
    with pytest.raises(ValueError, match="encoding"):
        F.read_zip(make_zip(RECS, moved, cpg="LATIN1"))
    with pytest.raises(ValueError, match="coordinate system"):
        F.read_zip(make_zip(RECS, moved, prj='GEOGCS["GCS_Mars_2000"]'))


# ----------------------------------------------------------------------------- the compact file


def good_zip():
    good = [r for r in RECS if not r["_deleted"]]
    return make_zip(RECS, [(float(r["center_lon"]), float(r["center_lat"])) for r in good])


def test_only_adopted_names_sorted_by_id_with_east_longitudes_in_180():
    body = F.build(good_zip(), {"url": F.URL, "downloaded_utc": "2026-11-16T10:00:00Z"})
    assert body["fields"] == ["id", "name", "type", "lat", "lon", "diameter_km"]
    assert body["features"] == [
        [948, "Bürg", "AA", 45.0734, 28.2081, 41.04228],
        [5450, "Shackleton", "AA", -89.67, 129.78, 20.924982],
        [5684, "Statio Tranquillitatis", "ST", 0.6741, 23.4732, 0.009],
        [11150, "Marco Polo P", "SF", 16.9673, -0.3185, 28.06208],  # 359.6815 E
    ]
    assert body["types"] == {"AA": "Crater, craters", "SF": "Satellite Feature", "ST": "Statio"}
    assert body["approval"] == "Adopted by IAU" and body["satellite_features_included"] is True
    assert body["source"]["records_in_file"] == 5 and len(body["source"]["sha256"]) == 64
    assert "Accessed 2026-11-16." in body["source"]["citation"]
    assert "mean Earth/polar axis" in body["coordinates"]


def test_satellite_features_can_be_left_out():
    body = F.build(
        good_zip(), {"url": F.URL, "downloaded_utc": "2026-11-16T10:00:00Z"}, include_satellite=False
    )
    assert [row[1] for row in body["features"]] == ["Bürg", "Shackleton", "Statio Tranquillitatis"]
    assert body["satellite_features_included"] is False and "SF" not in body["types"]


def test_east_180():
    assert [F.east_180(v) for v in (0.0, 180.0, 180.0001, 359.9936)] == pytest.approx(
        [0.0, 180.0, -179.9999, -0.0064]
    )


def test_rejects_duplicate_ids_bad_links_and_out_of_range_values():
    def body_of(recs):
        good = [r for r in recs if not r["_deleted"]]
        return F.build(make_zip(recs, [(float(r["center_lon"]), float(r["center_lat"])) for r in good]), {})

    with pytest.raises(ValueError, match="duplicate"):
        body_of([rec(1, "A", 0.0, 0.0, 1.0), rec(1, "B", 1.0, 1.0, 1.0)])
    bad_link = rec(2, "C", 0.0, 0.0, 1.0)
    bad_link["link"] = "http://example.org/Feature/2"
    with pytest.raises(ValueError, match="link"):
        body_of([bad_link])
    with pytest.raises(ValueError, match="out of range"):
        body_of([rec(3, "D", 0.0, 0.0, -1.0)])


# ----------------------------------------------------------------------------- the real file, if present


def real_file():
    from lss.config import get_settings

    p = get_settings().cache_dir / "features" / "iau_names.json"
    if not p.is_file():
        pytest.skip("cache/features/iau_names.json not on this machine (scripts/fetch_iau_names.py)")
    return json.loads(p.read_text(encoding="utf-8"))


def test_real_file_is_consistent():
    body = real_file()
    rows = body["features"]
    assert body["format"] == F.FORMAT and body["fields"] == F.FIELDS and body["approval"] == "Adopted by IAU"
    assert len({r[0] for r in rows}) == len(rows) and all(r[2] in body["types"] for r in rows)
    assert all(-90 <= r[3] <= 90 and -180 <= r[4] <= 180 and r[5] >= 0 for r in rows)
    by_name = {r[1]: r for r in rows}
    assert by_name["Mons Mouton"] == [16070, "Mons Mouton", "MO", -84.6, 31.0, 130.0]  # its Gazetteer page


def test_real_file_frame_agrees_with_the_engine_at_apollo_11():
    """Statio Tranquillitatis (the Apollo 11 landing site's IAU name) against Wagner et al. (2017)'s LM
    position in the registry (mean Earth/polar axis, DE421): a few metres (the Gazetteer gives 4 decimals)."""
    from lss.registry.sites import get_site

    lat, lon = next(r for r in real_file()["features"] if r[1] == "Statio Tranquillitatis")[3:5]
    s = get_site("apollo-11")
    p1, p2 = math.radians(lat), math.radians(s.location.lat)
    dl = math.radians(s.location.lon - lon)
    d = (
        2
        * 1_737_400.0
        * math.asin(
            math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
        )
    )
    assert d < 5.0
