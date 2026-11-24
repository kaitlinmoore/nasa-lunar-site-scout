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
from lss.terrain.global_layer import LDEM_128, image_slope_stats, window
from lss.terrain.slope import ew_offset_px, slope_deg_lonlat, slope_stats_lonlat

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
    """z rises northward by tan(a) per metre of meridian arc: every interior pixel has slope a, except the
    n - 1 columns at each end whose east-west neighbours (n = ew_offset_px) are outside the grid (NaN)."""
    a = math.radians(9.0)
    g, lats, _ = grid_around(
        lat0, 20.0, 1 / 128, 0.2, lambda lat, lon: math.tan(a) * R * np.radians(lat - lat0)
    )
    s = slope_deg_lonlat(np.asarray(g.array, float), g.res_deg, lats)
    n = int(ew_offset_px(lat0))  # 1 at 0.5 and 45 deg, 2 at 60 deg, 3 at 70 deg (the same in every row here)
    assert np.isnan(s[:, : n - 1]).all() and np.isnan(s[:, s.shape[1] - n + 1 :]).all()
    assert np.allclose(s[:, n - 1 : s.shape[1] - n + 1], 9.0, atol=1e-3)  # float32 heights


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


# --------------------------------------------- the matched east-west baseline, up to the poles


def test_ew_offset_matches_the_north_south_baseline():
    """n = round(1 / cos(lat)), at least 1: the east-west baseline 2 n R cos(lat) dlambda stays within 2/3 to
    4/3 of the north-south one, 2 R dphi, at every pixel row of LDEM_128 from the equator to the last row
    before each pole; and n = 1 (the plain central difference) below 48.19 deg."""
    lats = (LDEM_128.line_offset - np.arange(LDEM_128.lines)) / LDEM_128.ppd
    n = ew_offset_px(lats)
    ratio = n * np.cos(np.radians(lats))
    assert ratio.min() >= 2 / 3 - 1e-12 and ratio.max() <= 4 / 3 + 1e-12
    assert np.array_equal(n, ew_offset_px(-lats))  # the same in both hemispheres
    assert (n[np.abs(lats) < 48.19] == 1).all() and (n[np.abs(lats) > 48.2] >= 2).all()
    assert [int(ew_offset_px(a)) for a in (0.0, 26.2, 60.0, 85.0, 88.0, 89.0, -89.0)] == [
        1,
        1,
        2,
        11,
        29,
        57,
        57,
    ]
    assert int(ew_offset_px(90.0)) == 2**31  # finite at the pole itself


def test_plain_central_difference_below_48_deg():
    """Rows below 48.19 deg use exactly the 2-pixel central difference (bit for bit), so the Apollo sites'
    statistics (|latitude| <= 26.2 deg) do not depend on the matched baseline."""
    rng = np.random.default_rng(7)
    z = rng.normal(0.0, 50.0, (60, 80))
    res = 1 / 128
    lats = 48.18 - np.arange(60) * 1.6  # 48.18 N to 46.2 S
    step = math.radians(res) * R
    dx = step * np.cos(np.radians(lats[1:-1]))[:, None]
    plain = np.degrees(
        np.arctan(
            np.hypot(
                (z[1:-1, 2:] - z[1:-1, :-2]) / (2.0 * dx),
                (z[2:, 1:-1] - z[:-2, 1:-1]) / (2.0 * step),
            )
        )
    )
    assert np.array_equal(slope_deg_lonlat(z, res, lats), plain)


def unit_vector(lat, lon):
    p, lam = np.radians(lat), np.radians(lon)
    return np.stack([np.cos(p) * np.cos(lam), np.cos(p) * np.sin(lam), np.sin(p)], axis=-1)


def quantised_plane(lat0, lon0, slope_deg, uphill_az_deg, quantum_m=0.5):
    """Heights of a plane through (lat0, lon0) in its local tangent frame (east and north metres from the
    point's unit vector, independent of the code under test), rising towards azimuth `uphill_az_deg`, rounded
    to `quantum_m` as LDEM_128's 0.5 m counts are."""
    lam0, phi0 = math.radians(lon0), math.radians(lat0)
    east = np.array([-math.sin(lam0), math.cos(lam0), 0.0])
    north = np.array([-math.sin(phi0) * math.cos(lam0), -math.sin(phi0) * math.sin(lam0), math.cos(phi0)])
    t, a = math.tan(math.radians(slope_deg)), math.radians(uphill_az_deg)

    def f(lat, lon):
        u = unit_vector(lat, lon)
        z = 100.0 + t * R * ((u @ east) * math.sin(a) + (u @ north) * math.cos(a))
        return np.round(z / quantum_m) * quantum_m

    return f


@pytest.mark.parametrize("lat0", [85.0, 88.0, 89.0, -89.0])
@pytest.mark.parametrize("uphill_az", [90.0, 30.0])
def test_quantised_plane_near_the_poles(lat0, uphill_az):
    """A 5 deg plane with heights in 0.5 m steps, read through `window` like LDEM_128: every pixel within 1 km
    and 10 km has slope 5 +- 0.15 deg, the mean 5 +- 0.01 deg. The plain 2-pixel east-west difference
    (2 R cos(lat) dlambda: 41 m at 85 deg, 8 m at 89 deg) turns the 0.5 m steps into larger errors, beyond
    that bound."""
    img = ComputedImage(quantised_plane(lat0, 40.0, 5.0, uphill_az))
    for r in (1_000.0, 10_000.0):
        s = image_slope_stats(img, lat0, 40.0, r)
        assert 4.85 <= s.min_deg <= s.max_deg <= 5.15
        assert abs(s.at_point_deg - 5.0) <= 0.15
        assert s.mean_deg == pytest.approx(5.0, abs=0.01)
    g = window(img, lat0, 40.0, 10_000.0)
    z = np.asarray(g.array, dtype=float)
    lats = g.lat0 - (np.arange(z.shape[0]) + 0.5) * g.res_deg
    step = math.radians(g.res_deg) * R
    plain_east = (z[1:-1, 2:] - z[1:-1, :-2]) / (2.0 * step * np.cos(np.radians(lats[1:-1]))[:, None])
    plain = np.degrees(np.arctan(np.hypot(plain_east, (z[2:, 1:-1] - z[:-2, 1:-1]) / (2.0 * step))))
    assert np.abs(plain - 5.0).max() > 0.3


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_refused_where_the_circle_reaches_the_pole(sign):
    """At the pole east and north are undefined. Statistics are computed until the circle reaches the pixel
    row next to the pole (radius + about 0.004 deg), and refused from there on, in both hemispheres."""
    img = ComputedImage(lambda lat, lon: np.zeros_like(lat))
    for r, ok, refused in ((1_000.0, 89.963, 89.964), (10_000.0, 89.665, 89.666)):
        assert image_slope_stats(img, sign * ok, 10.0, r).max_deg == 0.0
        with pytest.raises(ValueError, match="leaves the grid|pole"):
            image_slope_stats(img, sign * refused, 10.0, r)
    with pytest.raises(ValueError, match="pole"):
        image_slope_stats(img, sign * 90.0, 10.0, 1_000.0)


def test_refuses_east_west_neighbours_outside_the_grid():
    """A grid at 85 N (n = 11) wide enough for the 1 km circle (48 columns each way) but not for its pixels'
    east-west neighbours; 11 more columns on each side are enough."""
    res = 1 / 128

    def grid(half_cols):
        lat_top, lon_w = 85.0 + 8 * res, 20.0 - half_cols * res
        return LonLatGrid(
            np.zeros((16, 2 * half_cols), np.float32), lon_w, lat_top, res, math.radians(res) * R
        )

    with pytest.raises(ValueError, match="east-west neighbours"):
        slope_stats_lonlat(grid(52), 85.0, 20.0, 1_000.0)
    assert slope_stats_lonlat(grid(52 + 11), 85.0, 20.0, 1_000.0).max_deg == 0.0


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
@pytest.mark.parametrize(
    "lat, lon",
    [
        (-65.0, 0.0),
        (-65.0, 120.0),
        (-70.0, 45.0),
        (-85.0, 200.0),
        (-88.0, 0.0),
        (-89.0, 90.0),
        (-89.0, 300.0),
    ],
)
def test_mean_slope_agrees_with_the_polar_path_on_the_240m_map(lat, lon):
    """Where the 240 m polar map and LDEM_128 overlap, the two paths' 10 km mean slopes agree within 5%, up to
    1 deg from the pole (measured 2026-11-24: -2.8% to +3.4% at these points). With a 2-pixel east-west
    difference at every latitude, LDEM_128 was 11% higher at 85 S, 25% at 88 S and 66-140% at 89 S."""
    from lss.terrain.core import ps_from_latlon
    from lss.terrain.global_layer import global_slope_stats
    from lss.terrain.slope import slope_stats

    x, y = (float(v) for v in ps_from_latlon(lat, lon, "south"))
    polar = slope_stats(BY_ID["ldem_60s_240m"].path, x, y, 10_000.0)
    cyl = global_slope_stats(lat, lon, 10_000.0)
    assert cyl.mean_deg == pytest.approx(polar.mean_deg, rel=0.05)
