# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Slope on latitude/longitude grids (lss.terrain.slope.slope_deg_lonlat / slope_stats_lonlat, and
lss.terrain.global_layer.global_slope_stats; docs/methodology.md section 5.6.1).

Synthetic terrain is defined from ground distances computed here independently (spherical law of cosines,
local east/north offsets), so the expected slopes do not come from the code under test. The seam test reads a
synthetic LDEM_128-shaped image through the real `window` code, which splits windows at the 0/360 meridian.
"""

import math

import numpy as np
import pytest

from lss.datafiles import BY_ID
from lss.terrain.core import LonLatGrid
from lss.terrain.global_layer import LDEM_128, window
from lss.terrain.slope import slope_deg_lonlat, slope_stats_lonlat

R = 1_737_400.0


def central_dist_m(lat0, lon0, lat, lon):
    """Great-circle distance by the spherical law of cosines (independent of the code's haversine)."""
    p0, p, dl = np.radians(lat0), np.radians(lat), np.radians(np.asarray(lon) - lon0)
    c = np.sin(p0) * np.sin(p) + np.cos(p0) * np.cos(p) * np.cos(dl)
    return R * np.arccos(np.clip(c, -1.0, 1.0))


def grid_around(lat0, lon0, res_deg, half_deg, height_fn):
    """A LonLatGrid of n x m pixels around (lat0, lon0); heights = height_fn(lat, lon) at pixel centres."""
    n = int(round(2 * half_deg / res_deg))
    m = int(round(2 * half_deg / res_deg / math.cos(math.radians(lat0)))) + 4
    lat_top, lon_w = lat0 + n * res_deg / 2, lon0 - m * res_deg / 2
    lats = lat_top - (np.arange(n) + 0.5) * res_deg
    lons = lon_w + (np.arange(m) + 0.5) * res_deg
    lon, lat = np.meshgrid(lons, lats)
    z = np.asarray(height_fn(lat, lon), dtype=np.float32)
    return LonLatGrid(z, lon_w, lat_top, res_deg, math.radians(res_deg) * R), lats, lons


# ----------------------------------------------------------------------------- the pixel slope


@pytest.mark.parametrize("lat0", [0.5, 45.0, -60.0, 70.0])
def test_north_tilted_plane_exact_everywhere(lat0):
    """z rises northward by tan(a) per metre of meridian arc: every interior pixel has slope a."""
    a = math.radians(9.0)
    g, lats, _ = grid_around(
        lat0, 20.0, 1 / 128, 0.2, lambda lat, lon: math.tan(a) * R * np.radians(lat - lat0)
    )
    s = slope_deg_lonlat(np.asarray(g.array, float), g.res_deg, lats)
    assert np.allclose(s, 9.0, atol=1e-3)  # float32 heights


@pytest.mark.parametrize("lat0", [0.5, 26.1, -60.0, 70.0])
def test_east_tilted_rows_use_their_own_ground_step(lat0):
    """z = tan(a) x (east distance along each row, R cos(lat) dlon): along every row the slope is a. Using the
    north-south step east-west instead would give atan(tan(a) cos(lat)) (half the gradient at 60 deg)."""
    a = math.radians(12.0)

    def f(lat, lon):
        return math.tan(a) * R * np.cos(np.radians(lat)) * np.radians(lon - 20.0)

    g, lats, lons = grid_around(lat0, 20.0, 1 / 128, 0.2, f)
    s = slope_deg_lonlat(np.asarray(g.array, float), g.res_deg, lats)
    centre = int(np.argmin(np.abs(lons[1:-1] - 20.0)))  # the north-south term vanishes on the 20 E column
    assert np.allclose(s[:, centre], 12.0, atol=2e-3)


@pytest.mark.parametrize("lat0, theta", [(0.67, 0.0), (0.67, 1.0), (26.13, 2.2), (-45.0, 4.0), (70.0, 5.5)])
def test_plane_in_any_direction_at_the_point(lat0, theta):
    """A plane of slope a facing any direction in local east/north metres: the slope at the point is a."""
    a = math.radians(7.0)

    def f(lat, lon):
        east = R * math.cos(math.radians(lat0)) * np.radians(lon - 20.0)
        north = R * np.radians(lat - lat0)
        return math.tan(a) * (east * math.cos(theta) + north * math.sin(theta))

    g, _, _ = grid_around(lat0, 20.0, 1 / 128, 0.1, f)
    s = slope_stats_lonlat(g, lat0, 20.0, 1_000.0)
    assert s.at_point_deg == pytest.approx(7.0, abs=0.01)
    assert s.mean_deg == pytest.approx(7.0, abs=0.02)


# ----------------------------------------------------------------------------- statistics within a radius


@pytest.mark.parametrize("lat0", [0.67, 26.13, -60.0])
def test_cone_statistics_count_the_right_pixels(lat0):
    """A cone of slope 15 deg out to 5 km, flat beyond: the 3 km circle holds the pixels whose centres are
    within 3 km (counted here independently); the cone's flanks have its slope."""
    res = 1 / 512  # ~59 m
    g, lats, lons = grid_around(
        lat0,
        20.0,
        res,
        0.25,
        lambda lat, lon: (
            math.tan(math.radians(15.0)) * np.minimum(central_dist_m(lat0, 20.0, lat, lon), 5_000.0)
        ),
    )
    s = slope_stats_lonlat(g, lat0, 20.0, 3_000.0)
    lon, lat = np.meshgrid(lons[1:-1], lats[1:-1])
    assert s.pixels == int((central_dist_m(lat0, 20.0, lat, lon) <= 3_000.0).sum())
    assert s.max_deg == pytest.approx(15.0, abs=0.2)
    assert s.mean_deg > 14.9  # every pixel but the apex is on a flank
    # the apex pixel (its neighbours lie on both flanks) is the least steep, to float32 noise
    assert s.at_point_deg == pytest.approx(s.min_deg, abs=1e-4) and s.at_point_deg < 14.0
    assert s.resolution_m == pytest.approx(math.radians(res) * R)


def test_refuses_circles_leaving_the_grid_and_polar_windows():
    g, _, _ = grid_around(10.0, 20.0, 1 / 128, 0.05, lambda lat, lon: np.zeros_like(lat))
    with pytest.raises(ValueError, match="leaves the grid"):
        slope_stats_lonlat(g, 10.0, 20.0, 10_000.0)
    with pytest.raises(ValueError, match="pole"):
        slope_stats_lonlat(g._replace(wrap=True), 10.0, 20.0, 1_000.0)
    nan = g._replace(array=np.where(np.arange(g.array.shape[1]) % 7 == 0, np.nan, g.array).astype(np.float32))
    with pytest.raises(ValueError, match="no data"):
        slope_stats_lonlat(nan, 10.0, 20.0, 1_000.0)


# ------------------------------------------------------------ the 0/360 seam, through `window`


class ComputedImage:
    """An LDEM_128-shaped image whose DNs are computed on demand from a height function of (lat, lon), so
    `window` reads it exactly as it reads the memory-mapped file (including the two-slice seam read)."""

    shape = (LDEM_128.lines, LDEM_128.samples)

    def __init__(self, height_fn):
        self.f = height_fn

    def __getitem__(self, key):
        rs, cs = key
        rows = np.arange(*rs.indices(self.shape[0]))
        cols = np.arange(*cs.indices(self.shape[1]))
        lat = (LDEM_128.line_offset - rows) / LDEM_128.ppd
        lon = LDEM_128.center_lon + (cols - LDEM_128.sample_offset) / LDEM_128.ppd
        lon2, lat2 = np.meshgrid(lon, lat)
        return self.f(lat2, lon2) / LDEM_128.scale  # DN (unrounded, so no quantisation in the test)


def cone_at(lat0, lon0, slope_deg=10.0, radius_m=6_000.0):
    t = math.tan(math.radians(slope_deg))
    return lambda lat, lon: t * np.minimum(central_dist_m(lat0, lon0, lat, lon), radius_m)


@pytest.mark.parametrize("lat0", [0.0, 26.0])
def test_seam_window_gives_the_same_statistics(lat0):
    """The same cone at 0.05 E (window straddles 0/360) and at 90.05 E (no seam): identical statistics."""
    across_img, plain_img = ComputedImage(cone_at(lat0, 0.05)), ComputedImage(cone_at(lat0, 90.05))
    g_across = window(across_img, lat0, 0.05, 10_000.0)
    g_plain = window(plain_img, lat0, 90.05, 10_000.0)
    assert g_across.lon0 < 0.0 and not g_across.wrap  # west edge west of 0 E: read as two slices
    for r in (1_000.0, 10_000.0):
        a = slope_stats_lonlat(g_across, lat0, 0.05, r)
        b = slope_stats_lonlat(g_plain, lat0, 90.05, r)
        assert a.pixels == b.pixels
        assert (a.at_point_deg, a.min_deg, a.max_deg, a.mean_deg) == pytest.approx(
            (b.at_point_deg, b.min_deg, b.max_deg, b.mean_deg), abs=1e-4
        )
    # and the cone's flanks have its slope (237 m central differences on a 10 deg cone)
    assert slope_stats_lonlat(g_across, lat0, 0.05, 5_000.0).max_deg == pytest.approx(10.0, abs=0.1)


def test_seam_window_at_negative_longitude():
    """-0.02 E is 359.98 E: the window and the statistics are the same either way."""
    img = ComputedImage(cone_at(-3.0, -0.02))
    a = slope_stats_lonlat(window(img, -3.0, -0.02, 3_000.0), -3.0, -0.02, 3_000.0)
    b = slope_stats_lonlat(window(img, -3.0, 359.98, 3_000.0), -3.0, 359.98, 3_000.0)
    assert a == b


# ----------------------------------------------------------------------------- the real map

IMG, LBL = BY_ID["ldem_128_img"].path, BY_ID["ldem_128_lbl"].path
needs_ldem = pytest.mark.skipif(not (IMG.is_file() and LBL.is_file()), reason="LDEM_128 not downloaded")


@needs_ldem
@pytest.mark.parametrize("lat, lon", [(0.67416, 23.47314), (26.13239, 3.6333), (20.1911, 30.7723)])
def test_apollo_sites_on_ldem_128(lat, lon):
    from lss.terrain.global_layer import global_slope_stats

    for r in (1_000.0, 10_000.0):
        s = global_slope_stats(lat, lon, r)
        px_area = (math.radians(1 / 128) * R) ** 2 * math.cos(math.radians(lat))
        assert s.pixels == pytest.approx(math.pi * r**2 / px_area, rel=0.15)
        assert s.resolution_m == 236.901 and 0.0 <= s.min_deg <= s.mean_deg <= s.max_deg < 60.0


@needs_ldem
@pytest.mark.skipif(not BY_ID["ldem_60s_240m"].path.is_file(), reason="240 m polar map not downloaded")
@pytest.mark.parametrize("lat, lon", [(-65.0, 0.0), (-65.0, 120.0), (-70.0, 45.0)])
def test_mean_slope_agrees_with_the_polar_path_on_the_240m_map(lat, lon):
    """Where the 240 m polar map and LDEM_128 overlap, the two paths' 10 km mean slopes agree within 10%
    (measured 2026-11-16: 2-5% at these points; LDEM_128 slightly higher: its east-west step is shorter)."""
    from lss.terrain.core import ps_from_latlon
    from lss.terrain.global_layer import global_slope_stats
    from lss.terrain.slope import slope_stats

    x, y = (float(v) for v in ps_from_latlon(lat, lon, "south"))
    polar = slope_stats(BY_ID["ldem_60s_240m"].path, x, y, 10_000.0)
    cyl = global_slope_stats(lat, lon, 10_000.0)
    assert cyl.mean_deg == pytest.approx(polar.mean_deg, rel=0.10)
