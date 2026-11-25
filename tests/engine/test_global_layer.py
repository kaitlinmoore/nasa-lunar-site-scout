# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""The global coarse layer (LOLA LDEM_128): label checks, pixel mapping, windows, resolver path, and
spot checks on the real map at the Apollo sites (skipped when LDEM_128 is not downloaded)."""

import numpy as np
import pytest

import lss.registry.terrain as reg
from lss.contract import FidelityTier
from lss.datafiles import BY_ID
from lss.horizon import HorizonParams, compute_horizon
from lss.horizon.core import segments_for
from lss.registry.sites import load_sites
from lss.terrain.global_layer import (
    LDEM_128,
    LDEM_128_LABEL,
    CylindricalMap,
    check_label,
    open_image,
    read_label,
    window,
)

IMG, LBL = BY_ID["ldem_128_img"].path, BY_ID["ldem_128_lbl"].path
HAVE_LDEM = IMG.is_file() and LBL.is_file()
needs_ldem = pytest.mark.skipif(not HAVE_LDEM, reason="LDEM_128 not downloaded (fetch_data.py global)")

# Wagner et al. (2017) Lunar Module descent stages (LROC PDS ANTHROPOGENIC_OBJECTS table: LATITUDE,
# LONGITUDE, RADIUS in m from the Moon's centre; heights NAC DTM based, independent of LOLA gridding).
APOLLO_LM = {
    11: (0.67416, 23.47314, 1735473.711),
    12: (-3.0128, -23.4219, 1735977.760),
    14: (-3.64589, -17.47194, 1736337.964),
    15: (26.13239, 3.63330, 1735468.715),
    16: (-8.9734, 15.5011, 1737408.350),
    17: (20.1911, 30.7723, 1734773.720),
}


# ----------------------------------------------------------------------------- pixel mapping (from the label)


def test_ldem_128_pixel_centres_follow_the_label():
    m = LDEM_128
    assert m.nbytes == 2_123_366_400  # the file size on the PDS server
    assert float(m.row_of(90.0 - 0.5 / 128)) == pytest.approx(0.0)  # line 0 centred 1/256 deg below 90 N
    assert float(m.row_of(-90.0 + 0.5 / 128)) == pytest.approx(m.lines - 1)
    assert float(m.col_of(0.5 / 128)) == pytest.approx(0.0)  # sample 0 centred 1/256 deg east of 0 E
    assert float(m.col_of(360.0 - 0.5 / 128)) == pytest.approx(m.samples - 1)
    assert float(m.col_of(-23.4219)) == pytest.approx(float(m.col_of(336.5781)))  # -180..180 or 0..360
    assert m.map_scale_m == pytest.approx(np.radians(1 / 128) * 1_737_400.0, abs=1e-3)


def test_label_parser_and_check(tmp_path):
    good = "\n".join(f'{k} = "{v}"' if " " in v else f"{k} = {v}" for k, v in LDEM_128_LABEL.items())
    p = tmp_path / "x.lbl"
    p.write_text(
        "PDS_VERSION_ID = PDS3\n" + good.replace("MAP_SCALE = 236.901", "MAP_SCALE = 236.901 <m/pix>")
    )
    assert read_label(p)["MAP_SCALE"] == "236.901"
    check_label(p)
    p.write_text(good.replace("MEAN EARTH/POLAR AXIS OF DE421", "PRINCIPAL AXIS"))
    with pytest.raises(ValueError, match="COORDINATE_SYSTEM_NAME"):
        check_label(p)


@needs_ldem
def test_real_label_matches_what_the_reader_assumes():
    check_label(LBL)


# ------------------------------------------------------------------- windows on a small synthetic map

SMALL = CylindricalMap(
    lines=180,
    samples=360,
    ppd=1.0,
    line_offset=89.5,
    sample_offset=179.5,
    center_lon=180.0,
    scale=0.5,
    map_scale_m=30_323.6,
)  # 1 deg pixels, same conventions as LDEM_128


def small_image():
    """DN = 1000 x line + sample, so every window value identifies its source pixel."""
    rows, cols = np.mgrid[0 : SMALL.lines, 0 : SMALL.samples]
    return (rows * 1000 + cols).astype("<i4")


def test_window_contents_and_geometry():
    img = small_image()
    g = window(img, 10.0, 100.0, 200_000.0, SMALL, margin_px=1)  # 200 km = 6.6 deg
    assert not g.wrap and g.res_deg == 1.0
    # Every pixel centre in the window carries its own source value (x 0.5 m).
    r0 = int(round(SMALL.line_offset - (g.lat0 - 0.5)))
    c0 = int(round(SMALL.col_of(g.lon0 + 0.5)))
    assert g.array[0, 0] == pytest.approx(0.5 * img[r0, c0 % 360])
    for lat, lon in [(10.5, 100.5), (4.5, 95.5), (16.5, 106.5)]:
        r, c = int(round(float(SMALL.row_of(lat)))), int(round(float(SMALL.col_of(lon))))
        assert float(g.height_at_latlon(lat, lon)[0]) == pytest.approx(0.5 * img[r, c])


def test_window_straddling_0_360_reads_both_sides():
    img = small_image()
    g = window(img, 0.0, 0.5, 200_000.0, SMALL, margin_px=1)
    assert not g.wrap
    for lon in (-5.5, -0.5, 0.5, 5.5):
        r, c = int(round(float(SMALL.row_of(0.5)))), int(round(float(SMALL.col_of(lon))))
        assert float(g.height_at_latlon(0.5, lon)[0]) == pytest.approx(0.5 * img[r, c])


def test_window_containing_a_pole_takes_whole_rows():
    img = small_image()
    g = window(img, 88.0, 10.0, 200_000.0, SMALL, margin_px=1)
    assert g.wrap and g.array.shape[1] == SMALL.samples and g.lon0 == pytest.approx(0.0)
    assert g.lat0 == pytest.approx(90.0)


def test_open_image_checks_label_and_size(tmp_path):
    lbl = tmp_path / "small.lbl"
    lbl.write_text("PRODUCT_ID = SMALL\n")
    img = tmp_path / "small.img"
    np.zeros((SMALL.lines, SMALL.samples), "<i2").tofile(img)
    mm = open_image(img, lbl, SMALL, {"PRODUCT_ID": "SMALL"})
    assert mm.shape == (180, 360) and mm.dtype == np.dtype("<i2")
    del mm  # Windows: release the mapping
    short = tmp_path / "short.img"
    np.zeros(10, "<i2").tofile(short)
    with pytest.raises(ValueError, match="bytes"):
        open_image(short, lbl, SMALL, {"PRODUCT_ID": "SMALL"})


# ----------------------------------------------------------------------------- resolver path


def test_polar_sites_keep_exactly_their_stacks():
    """Results at the curated polar sites must not change: the global layer never enters their stacks."""
    polar_only = tuple(s for s in reg.LAYERS if not isinstance(s, reg.GlobalLayerSpec))
    for s in load_sites():
        if s.category != "pgda":
            continue
        a = reg.resolve(s.location.lat, s.location.lon)
        b = reg.resolve(s.location.lat, s.location.lon, layers=polar_only)
        assert a == b and all(not isinstance(sl.spec, reg.GlobalLayerSpec) for sl in a.layers)


def test_off_the_polar_maps_the_global_layer_alone():
    for s in load_sites():
        if s.category != "apollo":
            continue
        st = reg.resolve(s.location.lat, s.location.lon)
        assert len(st.layers) == 1
        sl = st.layers[0]
        assert isinstance(sl.spec, reg.GlobalLayerSpec) and sl.spec.centre == (s.location.lat, s.location.lon)
        assert (sl.role, sl.min_range_m, sl.max_range_m) == ("near_field", 0.0, reg.MAX_RANGE_M)
        f = st.fidelity()
        assert f.tier == FidelityTier.low and f.near_field_resolution_m == 236.901
        assert f.summary == "237 m global map (LOLA LDEM_128) near field"
    with pytest.raises(ValueError, match="around a point"):
        reg.GLOBAL_128.dem()


# ------------------------------------------------------------------- the real map at the Apollo sites


@needs_ldem
@pytest.mark.parametrize("mission", sorted(APOLLO_LM))
def test_ldem_128_height_at_the_apollo_lunar_modules(mission):
    """LDEM_128 (237 m) against Wagner et al.'s NAC-DTM heights of the LM descent stages: within 10 m
    (measured 2026-11-16: -8.6, -2.1, +0.1, +6.1, +2.0, -2.5 m for Apollo 11, 12, 14, 15, 16, 17)."""
    lat, lon, radius = APOLLO_LM[mission]
    g = window(open_image(IMG, LBL), lat, lon, 5_000.0)
    assert abs(float(g.height_at_latlon(lat, lon)[0]) - (radius - 1_737_400.0)) < 10.0


@needs_ldem
def test_horizon_at_apollo_11_on_the_global_layer():
    lat, lon = APOLLO_LM[11][:2]
    st = reg.resolve(lat, lon)
    h = compute_horizon(lat, lon, 2.0, segments_for(st), HorizonParams())
    assert h.missing_samples == 0 and h.elevation_deg.size == 3600
    assert h.surface_height_m == pytest.approx(APOLLO_LM[11][2] - 1_737_400.0, abs=10.0)
    assert h.layers[0]["resolution_m"] == 236.901
    # Mare Tranquillitatis is flat: the horizon stays within a few degrees of the bare-sphere dip.
    assert -1.0 < h.elevation_deg.min() and h.elevation_deg.max() < 5.0


HAVE_240M = BY_ID[reg.POLAR_240M.file_id].path.is_file()


@pytest.mark.skipif(not (HAVE_LDEM and HAVE_240M), reason="LDEM_128 or the 240 m polar map not downloaded")
@pytest.mark.parametrize("lat", [-70.0, -65.0])
def test_no_missing_samples_where_rays_leave_the_polar_maps(lat):
    """On the real maps, with the global layer beyond the 240 m map's full reach, no 1 m ray sample is
    missing. With the 240 m map alone to 400 km, 1.5% (70 S) and 7.1% (65 S) of them had no terrain."""
    st = reg.resolve(lat, 0.0)
    h = compute_horizon(lat, 0.0, 1.0, segments_for(st), HorizonParams())
    assert h.missing_samples == 0 and h.elevation_deg.size == 3600
    old = reg.TerrainStack(st.location, (reg.StackLayer(reg.POLAR_240M, "near_field", 0.0, reg.MAX_RANGE_M),))
    h_old = compute_horizon(lat, 0.0, 1.0, segments_for(old), HorizonParams())
    assert h_old.missing_samples / h_old.total_samples > 0.01  # what the fix removes
    assert h.surface_height_m == h_old.surface_height_m  # same near field


# ------------------------------------------------------------------- the deployed API (no DEM files)


def test_locate_off_the_polar_maps_needs_no_dem_files(tmp_path, monkeypatch):
    """The deployed container has no DEMs (only served results, terrain and NL caches): /api/locate and the
    resolver must answer from registry metadata alone, never opening LDEM_128."""
    from fastapi.testclient import TestClient

    import lss.api.app as app_module
    import lss.terrain.global_layer as gl
    from lss.config import get_settings
    from lss.contract import LocateResponse

    def refuse(*args, **kwargs):
        raise AssertionError("LDEM_128 was opened")

    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path / "empty"))  # no data/, cache/ or kernels/
    monkeypatch.setattr(gl, "open_image", refuse)
    monkeypatch.setattr(gl, "cached_window", refuse)
    for f in (get_settings, app_module._served, app_module._terrain):
        f.cache_clear()
    try:
        assert not BY_ID["ldem_128_img"].path.exists()
        for lat, lon in [(0.67416, 23.47314), (26.13239, 3.6333), (45.0, -170.0), (89.5, 0.0), (-50.0, 0.0)]:
            st = reg.resolve(lat, lon)
            assert st.supported and st.fidelity().tier == FidelityTier.low
            assert [tl.dataset_id for tl in st.contract_layers()] == ["lola_ldem_128"]
            r = TestClient(app_module.create_app()).post("/api/locate", json={"lat": lat, "lon": lon})
            assert r.status_code == 200, r.text
            body = LocateResponse.model_validate(r.json())
            assert body.fidelity.tier == "low" and body.terrain_stack[0].resolution_m == 236.901
            assert body.terrain_stack[0].max_range_km == 400.0
    finally:
        for f in (get_settings, app_module._served, app_module._terrain):
            f.cache_clear()
