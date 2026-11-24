# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""lss.terrain (projection, DEM sampling) and the lss.registry terrain-stack resolver."""

import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import transform as proj_transform

from lss.contract import FidelityTier
from lss.datafiles import get as datafile
from lss.ephem.core import MOON_RADIUS_M as EPHEM_R
from lss.registry import terrain as reg
from lss.terrain import MOON_RADIUS_M, DemLayer, bilinear, latlon_from_ps, ps_from_latlon

STERE = "+proj=stere +lat_0={0} +lat_ts={0} +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
SOUTH = CRS.from_proj4(STERE.format(-90))
NORTH = CRS.from_proj4(STERE.format(90))
GEO = CRS.from_proj4("+proj=longlat +R=1737400 +no_defs")
SITE01 = (-89.45, -137.31)


def test_one_reference_sphere():
    assert MOON_RADIUS_M == EPHEM_R == 1_737_400.0


@pytest.mark.parametrize(
    "pole, crs, lats", [("south", SOUTH, [-89.45, -85, -80, -60]), ("north", NORTH, [89.9, 85, 70])]
)
def test_polar_stereographic_matches_proj(pole, crs, lats):
    lons = [-179.0, -137.31, 0.0, 45.0, 120.0]
    lat, lon = np.meshgrid(lats, lons)
    x, y = ps_from_latlon(lat.ravel(), lon.ravel(), pole)
    xp, yp = proj_transform(GEO, crs, lon.ravel().tolist(), lat.ravel().tolist())
    assert np.allclose(x, xp, atol=1e-4) and np.allclose(y, yp, atol=1e-4)
    lat2, lon2 = latlon_from_ps(x, y, pole)
    assert np.allclose(lat2, lat.ravel(), atol=1e-10)
    assert np.allclose(lon2, lon.ravel(), atol=1e-10)


def test_site01_ps_coordinates():
    from lss.datafiles import SITE01_PS

    x, y = ps_from_latlon(*SITE01)
    assert (float(x), float(y)) == pytest.approx((-11308.19, -12258.86), abs=0.01)
    assert np.hypot(x - SITE01_PS[0], y - SITE01_PS[1]) < 1.2  # the rounded clip centre


def test_bilinear_exact_on_planes_and_nan_outside():
    rows, cols = np.mgrid[0:6, 0:8]
    a = (3.0 * cols - 2.0 * rows + 7.0).astype(np.float32)
    c, r = np.array([0.0, 2.5, 6.25, 7.0]), np.array([0.0, 1.5, 4.75, 5.0])
    assert np.allclose(bilinear(a, c, r), 3 * c - 2 * r + 7, atol=1e-5)
    assert np.isnan(bilinear(a, [-0.01, 7.01, 3.0], [1.0, 1.0, 5.01])).all()
    a[2, 3] = np.nan
    assert np.isnan(bilinear(a, [2.5, 3.0], [1.5, 2.0])).all()  # next to the no-data pixel
    assert np.isfinite(bilinear(a, [5.5], [4.5])).all()


def _write_tif(path, data, x0, y0, res, nodata=np.nan):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=data.shape[1],
        height=data.shape[0],
        count=1,
        dtype="float32",
        crs=SOUTH,
        transform=from_origin(x0, y0, res, res),
        nodata=nodata,
    ) as d:
        d.write(data.astype(np.float32), 1)


def test_dem_layer_pixel_registration(tmp_path):
    """A value belongs to its pixel's centre: x = x0 + (col + 0.5) res."""
    data = np.arange(20, dtype=np.float32).reshape(4, 5) * 10.0
    p = tmp_path / "t.tif"
    _write_tif(p, data, x0=1000.0, y0=2000.0, res=5.0)
    dem = DemLayer("test", p)
    assert dem.resolution_m == 5.0 and dem.bounds == (1000.0, 1980.0, 1025.0, 2000.0)
    # centre of pixel (row 1, col 2) is x = 1012.5, y = 1992.5
    assert dem.height_at_ps(1012.5, 1992.5)[0] == pytest.approx(data[1, 2])
    # halfway to the right neighbour
    assert dem.height_at_ps(1015.0, 1992.5)[0] == pytest.approx((data[1, 2] + data[1, 3]) / 2)
    # outside the outer pixel centres -> no value
    assert np.isnan(dem.height_at_ps(1001.0, 1992.5)[0])


def test_dem_layer_sentinel_nodata(tmp_path):
    data = np.full((3, 3), 5.0, dtype=np.float32)
    data[1, 1] = -9999.0
    p = tmp_path / "n.tif"
    _write_tif(p, data, 0.0, 30.0, 10.0, nodata=-9999.0)
    assert np.isnan(DemLayer("t", p).array[1, 1])


# ------------------------------------------------------------------ resolver


def test_resolver_site01_full_stack():
    stack = reg.resolve(*SITE01)
    assert [(sl.spec.resolution_m, sl.role, sl.min_range_m, sl.max_range_m) for sl in stack.layers] == [
        (5.0, "near_field", 0.0, 5_000.0),
        (80.0, "far_field", 5_000.0, 100_000.0),
        (240.0, "far_field", 100_000.0, reg.MAX_RANGE_M),
    ]
    fid = stack.fidelity()
    assert fid.tier == FidelityTier.high
    assert fid.near_field_resolution_m == 5.0 and fid.far_field_resolution_m == 240.0
    assert [layer.dataset_id for layer in stack.contract_layers()] == [
        "pgda_78_site_dems",
        "pgda_90_south_pole_dems",
        "pgda_90_south_pole_dems",
    ]


def test_resolver_skips_site_tile_near_its_edge():
    # 2 km inside the Site01 tile's left edge: rays would leave the 5 m map before 5 km
    lat, lon = latlon_from_ps(-17_000.0, -12_000.0)
    stack = reg.resolve(float(lat), float(lon))
    assert stack.layers[0].spec.resolution_m == 80.0
    assert stack.fidelity().tier == FidelityTier.medium


def test_resolver_polar_maps_only_and_unsupported():
    s85 = reg.resolve(-85.0, 30.0)
    assert [sl.spec.resolution_m for sl in s85.layers] == [80.0, 240.0]
    assert s85.layers[0].max_range_m == 100_000.0 and s85.layers[-1].max_range_m == reg.MAX_RANGE_M
    s74 = reg.resolve(-74.0, 30.0)  # the 240 m map holds the whole 400 km ray range
    assert [(sl.spec.resolution_m, sl.max_range_m) for sl in s74.layers] == [(240.0, reg.MAX_RANGE_M)]
    s70 = reg.resolve(-70.0, 30.0)  # it does not: the global layer beyond its full reach
    assert [sl.spec.dataset_id for sl in s70.layers] == ["pgda_90_south_pole_dems", "lola_ldem_128"]
    assert s70.fidelity().tier == FidelityTier.low
    for lat, lon in [(0.0, 0.0), (45.0, 10.0), (89.0, 0.0)]:  # off the polar maps: the global layer (C7)
        s = reg.resolve(lat, lon)
        assert [sl.spec.dataset_id for sl in s.layers] == ["lola_ldem_128"]
        assert s.fidelity().tier == FidelityTier.low


def _destination(lat, lon, bearing_deg, dist_m):
    """Great-circle destination (standard spherical formula; independent of the resolver's cap geometry)."""
    p1, l1, b, d = np.radians(lat), np.radians(lon), np.radians(bearing_deg), dist_m / MOON_RADIUS_M
    p2 = np.arcsin(np.sin(p1) * np.cos(d) + np.cos(p1) * np.sin(d) * np.cos(b))
    l2 = l1 + np.arctan2(np.sin(b) * np.sin(d) * np.cos(p1), np.cos(d) - np.sin(p1) * np.sin(p2))
    return np.degrees(p2), np.degrees(l2)


def _ring_on_map(spec, lat, lon, dist_m):
    """True if every point of a 3600-bearing ring at dist_m lies one pixel inside the map (brute force)."""
    x, y = ps_from_latlon(*_destination(lat, lon, np.arange(3600) * 0.1, dist_m), spec.pole)
    left, bottom, right, top = spec.bounds_m
    m = spec.resolution_m
    return bool(np.all((x >= left + m) & (x <= right - m) & (y >= bottom + m) & (y <= top - m)))


@pytest.mark.parametrize(
    "lat, lon", [(-70.0, 0.0), (-65.0, 20.0), (-61.0, 45.0), (-72.0, -90.0), (-62.0, 170.0)]
)
def test_full_reach_matches_brute_force(lat, lon):
    """The closed-form reach of the 240 m map (stereographic image of a cap is a circle) against rings of
    great-circle destinations: every ring point is on the map at the reach; some leaves it 50 m further."""
    reach = reg.full_reach_m(reg.POLAR_240M, lat, lon, reg.MAX_RANGE_M)
    assert 0.0 < reach < reg.MAX_RANGE_M
    assert _ring_on_map(reg.POLAR_240M, lat, lon, reach)
    assert not _ring_on_map(reg.POLAR_240M, lat, lon, reach + 50.0)


def test_full_reach_at_the_pole_and_off_the_map():
    assert reg.full_reach_m(reg.POLAR_240M, -90.0, 0.0, reg.MAX_RANGE_M) == reg.MAX_RANGE_M
    assert reg.full_reach_m(reg.POLAR_240M, -74.0, 0.0, reg.MAX_RANGE_M) == reg.MAX_RANGE_M
    assert reg.full_reach_m(reg.POLAR_240M, -59.0, 0.0, reg.MAX_RANGE_M) == 0.0  # off the map


@pytest.mark.parametrize("lat", [-70.0, -65.0, -61.0])
def test_resolver_global_far_field_where_rays_leave_the_polar_maps(lat):
    """Handoff 14 item 1: between about 73 S and 60 S, 400 km rays leave the 240 m map. The map is used out
    to the distance it holds in every direction, then the global layer to the maximum range."""
    st = reg.resolve(lat, 0.0)
    reach = reg.full_reach_m(reg.POLAR_240M, lat, 0.0, reg.MAX_RANGE_M)
    got = [(sl.spec.file_id, sl.role, sl.min_range_m, sl.max_range_m) for sl in st.layers]
    assert got == [
        ("ldem_60s_240m", "near_field", 0.0, reach),
        ("ldem_128_img", "far_field", reach, reg.MAX_RANGE_M),
    ]
    assert st.layers[1].spec.centre == (lat, 0.0) and st.layers[1].spec.window_m == reg.MAX_RANGE_M
    fid = st.fidelity()
    assert fid.tier == FidelityTier.low and fid.near_field_resolution_m == 240.0
    assert fid.summary == "240 m polar map near field, 237 m global map (LOLA LDEM_128) far field"


def test_resolver_refuses_short_rays_without_a_global_layer():
    from lss.horizon import HorizonUnavailable, horizon_at

    st = reg.resolve(-70.0, 0.0, layers=reg.C1_LAYERS)
    assert not st.supported and st.fidelity() is None
    assert "leave the 240 m polar map after 303.1 km" in st.reason and "no global layer" in st.reason
    with pytest.raises(HorizonUnavailable, match="leave the 240 m polar map"):  # before any DEM is read
        horizon_at(-70.0, 0.0, 1.0, layers=reg.C1_LAYERS)
    assert reg.resolve(-74.0, 0.0, layers=reg.C1_LAYERS).supported  # full reach: no global layer needed


def test_resolver_short_max_range_uses_fewer_layers():
    stack = reg.resolve(*SITE01, max_range_m=50_000.0)
    got = [(sl.spec.resolution_m, sl.max_range_m) for sl in stack.layers]
    assert got == [(5.0, 5_000.0), (80.0, 50_000.0)]


@pytest.mark.parametrize(
    "spec", [s for s in reg.LAYERS if not isinstance(s, reg.GlobalLayerSpec)], ids=lambda s: s.file_id
)
def test_layer_metadata_matches_files(spec):
    path = datafile(spec.file_id).path
    if not path.is_file():
        pytest.skip(f"{path} not downloaded")
    dem = DemLayer(spec.dataset_id, path, spec.pole)
    assert dem.resolution_m == spec.resolution_m
    assert dem.bounds == pytest.approx(spec.bounds_m)
    with rasterio.open(path) as d:
        crs = d.crs.to_dict()
    assert crs["proj"] == "stere" and crs["lat_0"] == -90 and crs["lat_ts"] == -90
    assert crs["R"] == 1737400 and crs.get("lon_0", 0) == 0


def test_site01_height_agrees_across_layers():
    paths = [datafile(s.file_id).path for s in reg.C1_LAYERS]
    if not all(p.is_file() for p in paths):
        pytest.skip("terrain files not downloaded")
    heights = [float(s.dem().height_at(*SITE01)[0]) for s in reg.C1_LAYERS]
    assert heights[0] == pytest.approx(1954.60, abs=0.01)  # bilinear on the 5 m map
    assert abs(heights[1] - heights[0]) < 1.0  # 80 m map
    assert abs(heights[2] - heights[0]) < 5.0  # 240 m map: pixels average over the ridge (~4 m lower)
