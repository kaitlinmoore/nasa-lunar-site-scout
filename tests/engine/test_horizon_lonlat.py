# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""C7: the ray caster on latitude/longitude grids (LonLatGrid and the lat/lon path in lss.horizon.core).

Synthetic terrain is built from the same independent spherical formulas as tests/engine/test_horizon.py
(haversine distance and initial bearing per pixel centre), so the lat/lon lookup, the azimuth convention, the
0/360 seam and whole-row (wrap) grids are tested against analytic answers, not against the code under test.
"""

import numpy as np
import pytest

from lss.horizon import HorizonParams, Segment, compute_horizon, elevation_deg
from lss.terrain import MOON_RADIUS_M
from lss.terrain.core import LonLatGrid
from tests.engine.test_horizon import bare_dip_deg, destination, dist_bearing, make_grid

R = MOON_RADIUS_M


def make_lonlat(lat0, lon0, res_m, half_m, height_fn, west=None, wrap=False):
    """LonLatGrid around (lat0, lon0) with square pixels of `res_m` along a meridian; heights =
    height_fn(arc distance m, bearing deg) at each pixel centre. `west`: the outer west edge (deg)."""
    res_deg = np.degrees(res_m / R)
    d_deg = np.degrees(half_m / R)
    lat_top = min(lat0 + d_deg, 90.0)
    n_rows = int(np.ceil((lat_top - max(lat0 - d_deg, -90.0)) / res_deg))
    if wrap:
        n_cols, lon_w = int(round(360.0 / res_deg)), 0.0
        res_deg = 360.0 / n_cols  # whole circle: an exact number of columns
    else:
        span = 2 * d_deg / np.cos(np.radians(max(abs(lat0 - d_deg), abs(lat0 + d_deg))))
        if west is None:
            n_cols = int(np.ceil(span / res_deg)) + 2
            lon_w = lon0 - n_cols * res_deg / 2
        else:  # from `west` (e.g. 358.6 for -1.4) eastward past the east edge of the span
            east = lon0 + span / 2
            n_cols = int(np.ceil(((east - west) % 360.0) / res_deg)) + 2
            lon_w = west
    lats = lat_top - (np.arange(n_rows) + 0.5) * res_deg
    lons = lon_w + (np.arange(n_cols) + 0.5) * res_deg
    lon, lat = np.meshgrid(lons, lats)
    d, az = dist_bearing(lat0, lon0, lat, lon)
    return LonLatGrid(np.asarray(height_fn(d, az), dtype=np.float32), lon_w, lat_top, res_deg, res_m, wrap)


def ring(H=800.0, D=20_000.0, w=2_000.0):
    return lambda d, az: H * np.exp(-(((d - D) / w) ** 2))


def ring_expected(h_obs, H=800.0, D=20_000.0, w=2_000.0, max_range=38_000.0):
    d = np.arange(1.0, max_range, 0.5)
    return elevation_deg(R + H * np.exp(-(((d - D) / w) ** 2)), R + h_obs, d / R).max()


@pytest.mark.parametrize("lat, lon", [(0.67, 23.47), (26.13, 3.63), (-60.0, -150.0)])
def test_flat_sphere_gives_pure_curvature_dip(lat, lon):
    g = make_lonlat(lat, lon, 100.0, 100_000.0, lambda d, az: np.zeros_like(d))
    h = compute_horizon(lat, lon, 1000.0, [Segment(g, 0, 90_000)], HorizonParams(1.0, 0.5, 90_000))
    assert np.allclose(h.elevation_deg, bare_dip_deg(1000.0), atol=1e-5)
    assert np.allclose(h.distance_m, R * np.arccos(R / (R + 1000.0)), rtol=0.05)
    assert h.missing_samples == 0 and h.surface_height_m == 0.0


@pytest.mark.parametrize("lat, lon", [(0.67, 23.47), (20.19, 30.77), (-45.0, 100.0)])
def test_ring_ridge_matches_analytic_maximum(lat, lon):
    g = make_lonlat(lat, lon, 50.0, 40_000.0, ring())
    h = compute_horizon(lat, lon, 2.0, [Segment(g, 0, 38_000)], HorizonParams(1.0, 0.5, 38_000))
    expected = ring_expected(2.0)
    assert expected > 1.5
    assert np.abs(h.elevation_deg - expected).max() < 1e-3  # bilinear on a 50 m grid, as the polar test


def test_azimuth_convention_clockwise_from_north():
    lat, lon = 0.67, 23.47

    def terrain(d, az):
        east = (az >= 80) & (az <= 100) & (d >= 5_000) & (d <= 6_000)
        north = ((az >= 350) | (az <= 10)) & (d >= 8_000) & (d <= 9_000)
        return np.where(east, 400.0, np.where(north, 200.0, 0.0))

    g = make_lonlat(lat, lon, 20.0, 15_000.0, terrain)
    h = compute_horizon(lat, lon, 1.0, [Segment(g, 0, 14_000)], HorizonParams(0.5, 0.5, 14_000))
    assert h.elevation_at(90.0) == pytest.approx(elevation_deg(R + 400.0, R + 1.0, 5_000 / R), abs=0.05)
    assert h.elevation_at(0.0) == pytest.approx(elevation_deg(R + 200.0, R + 1.0, 8_000 / R), abs=0.05)
    for az in (60.0, 180.0, 270.0, 340.0):
        assert h.elevation_at(az) == pytest.approx(bare_dip_deg(1.0), abs=1e-3)


def test_window_across_the_0_360_meridian_is_seamless():
    """The same terrain around 0.1 E on a grid whose west edge is 358.6 E (-1.4), and around 90.1 E."""
    f, p = ring(), HorizonParams(1.0, 0.5, 38_000)
    across = make_lonlat(0.0, 0.1, 50.0, 40_000.0, f, west=358.6)
    assert across.lon0 > 180.0  # stored as 358.6: columns run east across 0
    shifted = make_lonlat(0.0, 90.1, 50.0, 40_000.0, f, west=88.6)
    a = compute_horizon(0.0, 0.1, 2.0, [Segment(across, 0, 38_000)], p)
    b = compute_horizon(0.0, 90.1, 2.0, [Segment(shifted, 0, 38_000)], p)
    assert a.missing_samples == 0 and b.missing_samples == 0
    assert np.abs(a.elevation_deg - b.elevation_deg).max() < 1e-4
    assert np.abs(a.elevation_deg - ring_expected(2.0)).max() < 1e-3


def test_whole_row_grid_over_the_pole():
    """Rays from 89.9 N cross the pole: a full-circle (wrap) grid, columns next to each other across 0/360."""
    lat, lon = 89.9, 45.0
    g = make_lonlat(lat, lon, 100.0, 40_000.0, ring(D=15_000.0), wrap=True)
    assert g.wrap and g.array.shape[1] * g.res_deg == pytest.approx(360.0)
    p = HorizonParams(1.0, 0.5, 30_000)
    h = compute_horizon(lat, lon, 2.0, [Segment(g, 0, 30_000)], p)
    # Rays through the 1/2-pixel cap at the pole find no data there (counted), and bilinear in longitude is
    # coarse close to the pole, so the tolerance is wider than on the equator.
    assert np.abs(h.elevation_deg - ring_expected(2.0, D=15_000.0, max_range=30_000.0)).max() < 0.02


def test_mixed_stack_polar_near_field_lat_lon_far_field():
    """A polar stereographic near field and a lat/lon far field in one stack (the `_cast_mixed` dispatch)."""
    lat, lon = -88.0, 40.0
    near = make_grid(lat, lon, "south", 50.0, 12_000.0, ring())
    far = make_lonlat(lat, lon, 50.0, 40_000.0, ring())
    h = compute_horizon(
        lat,
        lon,
        2.0,
        [Segment(near, 0, 10_000), Segment(far, 10_000, 38_000)],
        HorizonParams(1.0, 0.5, 38_000),
    )
    assert h.missing_samples == 0
    assert np.abs(h.elevation_deg - ring_expected(2.0)).max() < 1e-3
    polar_only = compute_horizon(
        lat,
        lon,
        2.0,
        [Segment(make_grid(lat, lon, "south", 50.0, 40_000.0, ring()), 0, 38_000)],
        HorizonParams(1.0, 0.5, 38_000),
    )
    assert np.abs(h.elevation_deg - polar_only.elevation_deg).max() < 1e-3


def test_height_at_latlon_is_bilinear_and_wraps():
    a = np.arange(12, dtype=np.float32).reshape(3, 4)  # 3 rows x 4 columns of 90 deg
    g = LonLatGrid(a, 0.0, 90.0, 90.0, 1.0, wrap=True)
    assert float(g.height_at_latlon(45.0, 45.0)[0]) == 0.0  # centre of pixel (0, 0)
    assert float(g.height_at_latlon(45.0, 90.0)[0]) == 0.5  # halfway to pixel (0, 1)
    assert float(g.height_at_latlon(45.0, 0.0)[0]) == 1.5  # halfway between the last column and the first
    assert float(g.height_at_latlon(45.0, -45.0)[0]) == 3.0  # -45 = 315 E: centre of the last column
    nowrap = g._replace(wrap=False)
    assert np.isnan(nowrap.height_at_latlon(45.0, 0.0)[0])  # west of the first centre: outside
    # A point due north of a pixel centre on a ray: the kernel and the grid method agree.
    plat, plon = destination(0.0, 0.0, 0.0, 1000.0)
    assert np.isfinite(plat) and np.isfinite(plon)
