# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""lss.horizon: synthetic-DEM tests (plan section 5.2) and real-data cross-checks.

Synthetic terrain is built from the standard spherical distance and bearing formulas (haversine,
initial bearing), independently of the ray caster's vector geometry, so the azimuth convention and the
curvature treatment are tested, not assumed.
"""

import time

import numpy as np
import pytest

from lss.horizon import (
    Horizon,
    HorizonParams,
    HorizonUnavailable,
    Segment,
    cached_horizon,
    compute_horizon,
    elevation_deg,
    horizon_at,
)
from lss.horizon import cache as hcache
from lss.horizon.core import ray_samples
from lss.registry.terrain import C1_LAYERS, resolve
from lss.terrain import MOON_RADIUS_M, Grid, latlon_from_ps, ps_from_latlon

R = MOON_RADIUS_M
SITE01 = (-89.45, -137.31)
HAVE_DEMS = all(spec.dem().path.is_file() for spec in C1_LAYERS)
needs_dems = pytest.mark.skipif(not HAVE_DEMS, reason="DEMs not downloaded (scripts/fetch_data.py)")


def dist_bearing(lat1, lon1, lat2, lon2):
    """Arc distance (m on the reference sphere) and initial bearing (deg clockwise from north)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    b = np.arctan2(np.sin(dl) * np.cos(p2), np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl))
    return R * c, np.degrees(b) % 360.0


def destination(lat1, lon1, az_deg, d_m):
    """Point at arc distance d along the great circle leaving (lat1, lon1) at bearing az."""
    p1, l1, a, t = np.radians(lat1), np.radians(lon1), np.radians(az_deg), np.asarray(d_m) / R
    p2 = np.arcsin(np.sin(p1) * np.cos(t) + np.cos(p1) * np.sin(t) * np.cos(a))
    l2 = l1 + np.arctan2(np.sin(a) * np.sin(t) * np.cos(p1), np.cos(t) - np.sin(p1) * np.sin(p2))
    return np.degrees(p2), np.degrees(l2)


def make_grid(lat0, lon0, pole, res, half, height_fn):
    """Square grid centred on the site; heights = height_fn(arc distance m, bearing deg) per pixel centre."""
    xc, yc = ps_from_latlon(lat0, lon0, pole)
    n = round(2 * half / res)
    xs = xc - half + (np.arange(n) + 0.5) * res
    ys = yc + half - (np.arange(n) + 0.5) * res
    lat, lon = latlon_from_ps(*np.meshgrid(xs, ys), pole)
    d, az = dist_bearing(lat0, lon0, lat, lon)
    return Grid(np.asarray(height_fn(d, az), dtype=np.float32), xc - half, yc + half, res, pole)


def bare_dip_deg(observer_height_m):
    return -np.degrees(np.arccos(R / (R + observer_height_m)))


# ----------------------------------------------------------------------------- synthetic


@pytest.mark.parametrize(
    "unit_h, res, half, max_range",
    [(1.0, 5.0, 4_000.0, 3_500.0), (1000.0, 100.0, 100_000.0, 90_000.0)],
)
def test_flat_sphere_gives_pure_curvature_dip(unit_h, res, half, max_range):
    lat, lon = -88.0, 40.0
    g = make_grid(lat, lon, "south", res, half, lambda d, az: np.zeros_like(d))
    h = compute_horizon(lat, lon, unit_h, [Segment(g, 0, max_range)], HorizonParams(1.0, 0.5, max_range))
    assert np.allclose(h.elevation_deg, bare_dip_deg(unit_h), atol=1e-5)
    tangent = R * np.arccos(R / (R + unit_h))  # 1.86 km for 1 m, 59 km for 1000 m
    assert np.allclose(h.distance_m, tangent, rtol=0.05)
    assert h.missing_samples == 0


def test_range_limit_cuts_the_dip():
    lat, lon = -88.0, 40.0
    g = make_grid(lat, lon, "south", 100.0, 40_000.0, lambda d, az: np.zeros_like(d))
    h = compute_horizon(lat, lon, 1000.0, [Segment(g, 0, 30_000)], HorizonParams(5.0, 0.5, 30_000))
    expected = elevation_deg(R, R + 1000.0, 30_000 / R)  # the last sample, before the tangent point
    assert np.allclose(h.elevation_deg, expected, atol=1e-9)


@pytest.mark.parametrize("pole, lat, lon", [("south", -88.0, 40.0), ("north", 87.5, -120.0)])
def test_ring_ridge_matches_analytic_maximum(pole, lat, lon):
    H, D, w = 800.0, 20_000.0, 2_000.0

    def ridge(d):
        return H * np.exp(-(((d - D) / w) ** 2))

    g = make_grid(lat, lon, pole, 50.0, 40_000.0, lambda d, az: ridge(d))
    h = compute_horizon(lat, lon, 2.0, [Segment(g, 0, 38_000)], HorizonParams(1.0, 0.5, 38_000))
    d = np.arange(1.0, 38_000.0, 0.5)
    expected = elevation_deg(R + ridge(d), R + 2.0, d / R).max()  # about 2.0 deg
    assert expected > 1.5
    assert np.abs(h.elevation_deg - expected).max() < 1e-3  # bilinear on a 50 m grid
    assert np.allclose(h.distance_m, d[np.argmax(elevation_deg(R + ridge(d), R + 2.0, d / R))], atol=100)


def test_azimuth_convention_clockwise_from_north():
    lat, lon = -88.0, 40.0  # north here points away from the south pole

    def terrain(d, az):
        east = (az >= 80) & (az <= 100) & (d >= 5_000) & (d <= 6_000)
        north = ((az >= 350) | (az <= 10)) & (d >= 8_000) & (d <= 9_000)
        return np.where(east, 400.0, np.where(north, 200.0, 0.0))

    g = make_grid(lat, lon, "south", 20.0, 15_000.0, terrain)
    h = compute_horizon(lat, lon, 1.0, [Segment(g, 0, 14_000)], HorizonParams(0.5, 0.5, 14_000))
    east_expected = elevation_deg(R + 400.0, R + 1.0, 5_000 / R)  # near edge of the plateau
    north_expected = elevation_deg(R + 200.0, R + 1.0, 8_000 / R)
    # Sharp plateau edges on a 20 m grid: bilinear ramps them over one pixel (measured error 0.03 deg).
    assert h.elevation_at(90.0) == pytest.approx(east_expected, abs=0.05)
    assert h.elevation_at(0.0) == pytest.approx(north_expected, abs=0.05)
    assert h.elevation_at(81.0) > 4.0 and h.elevation_at(99.0) > 4.0
    for az in (60.0, 79.0, 101.0, 180.0, 270.0, 340.0):
        assert h.elevation_at(az) == pytest.approx(bare_dip_deg(1.0), abs=1e-3)


def test_sharp_near_field_peak_is_not_missed():
    """A single raised 5 m pixel 18.3 m due north: bilinear makes it a sharp peak with a known apex.

    This is the Site01 failure mode found by the convergence study: with samples spaced by pixel size
    alone (2.5 m), the peak between samples was missed by 0.19 deg on real terrain. The analytic horizon
    is the apex itself: elevation of a point H high at the apex distance (the profile rises steeply to it
    and falls after it, so no other point is higher in angle).
    """
    lat, lon, res, H, D = -88.0, 40.0, 5.0, 3.0, 18.3
    plat, plon = destination(lat, lon, 0.0, D)  # the apex: a pixel centre exactly on the az = 0 ray
    xp, yp = ps_from_latlon(plat, plon)
    n, ic = 40, 20
    a = np.zeros((n, n), np.float32)
    a[ic, ic] = H
    g = Grid(a, float(xp) - (ic + 0.5) * res, float(yp) + (ic + 0.5) * res, res, "south")
    expected = elevation_deg(R + H, R + 1.0, D / R)  # about 6.24 deg
    p = HorizonParams(1.0, 0.5, 60.0)
    h = compute_horizon(lat, lon, 1.0, [Segment(g, 0, 60.0)], p)
    # Bound for spacing s = relative_step x d next to the apex: (slope - tan el) x s / (2 d) rad. Along an
    # oblique ray the bilinear slope can reach sqrt(2) x H / res (0.85): bound 0.049 deg; measured 0.038.
    bound = np.degrees(0.5 * p.relative_step * (np.sqrt(2) * H / res))
    assert abs(h.elevation_at(0.0) - expected) <= bound
    assert h.distance_m[0] == pytest.approx(D, abs=0.05)
    # Pixel-based spacing alone (the old scheme) misses the apex by 0.21 deg (0.19 deg on Site01 terrain):
    # over 4x the bound, so the test would see that bug come back.
    old = compute_horizon(
        lat, lon, 1.0, [Segment(g, 0, 60.0)], HorizonParams(1.0, 0.5, 60.0, relative_step=10.0)
    )
    assert expected - old.elevation_at(0.0) > 0.15


def test_layer_fallback_and_missing_samples():
    lat, lon = -87.0, 10.0
    patch = lambda d, az, lo, hi: (az >= 80) & (az <= 100) & (d >= lo) & (d <= hi)  # noqa: E731
    fine = make_grid(
        lat, lon, "south", 10.0, 3_000.0, lambda d, az: np.where(patch(d, az, 1200, 1800), np.nan, 0)
    )
    coarse = make_grid(
        lat, lon, "south", 50.0, 30_000.0, lambda d, az: np.where(patch(d, az, 1400, 1600), 150, 0)
    )
    segs = [Segment(fine, 0, 5_000), Segment(coarse, 5_000, 40_000)]

    h = compute_horizon(lat, lon, 1.0, segs, HorizonParams(1.0, 0.5, 25_000))
    assert h.missing_samples == 0  # the fine grid's hole and its outer part are filled from the coarse grid
    assert h.elevation_at(90.0) > 5.0  # the coarse grid's bump, seen through the fine grid's hole
    assert h.elevation_at(270.0) == pytest.approx(bare_dip_deg(1.0), abs=1e-3)

    h = compute_horizon(lat, lon, 1.0, segs, HorizonParams(1.0, 0.5, 40_000))
    assert h.missing_samples > 0  # beyond the coarse grid; counted, not silently dropped


def test_plan_formula_is_the_small_angle_limit():
    def plan(dh, d):
        return np.degrees(np.arctan((dh - d**2 / (2 * R)) / d))

    ro = R + 2_000.0
    assert abs(elevation_deg(ro + 300, ro, 5_000 / R) - plan(300, 5_000)) < 0.01
    diff = abs(elevation_deg(ro + 5_000, ro, 400_000 / R) - plan(5_000, 400_000))
    assert 0.01 < diff < 0.05  # why the exact form is used


def test_input_validation():
    g = make_grid(-88.0, 40.0, "south", 50.0, 5_000.0, lambda d, az: np.zeros_like(d))
    segs = [Segment(g, 0, 4_000)]
    p = HorizonParams(1.0, 0.5, 4_000)
    assert compute_horizon(-88.0, 40.0, 0.0, segs, p).unit_height_m == 0.0  # 0 m: internal product 69 check
    with pytest.raises(ValueError):
        compute_horizon(-88.0, 40.0, -1.0, segs, p)
    with pytest.raises(HorizonUnavailable):
        compute_horizon(-88.0, 40.0, 1.0, [], p)
    with pytest.raises(HorizonUnavailable):
        compute_horizon(-80.0, 40.0, 1.0, segs, p)  # site outside the near-field grid
    for bad in ({"azimuth_step_deg": 0.7}, {"sample_factor": 0}, {"max_range_m": -1}):
        with pytest.raises(ValueError):
            HorizonParams(**bad)


def test_elevation_at_is_linear_and_periodic():
    az = np.arange(4) * 90.0
    h = Horizon(0, 0, 1, 0, az, np.array([0.0, 1.0, 2.0, 3.0]), az * 0, 0, 0, HorizonParams(90.0))
    assert np.allclose(h.elevation_at([45, 90, 315, 360, -45, 720]), [0.5, 1.0, 1.5, 0.0, 1.5, 0.0])


def test_ray_samples_cover_each_segment_at_the_requested_spacing():
    g5 = Grid(np.zeros((2, 2), np.float32), 0, 0, 5.0)
    g80 = Grid(np.zeros((2, 2), np.float32), 0, 0, 80.0)
    p = HorizonParams()  # spacing <= min(0.5 x pixel, 0.002 x distance), first sample at 1 m
    dist, layer = ray_samples([Segment(g5, 0, 5_000), Segment(g80, 5_000, 100_000)], p)
    assert np.all(np.diff(dist) > 0)
    near, far = dist[layer == 0], dist[layer == 1]
    assert near[0] == 1.0 and near[-1] == pytest.approx(5_000) and far[-1] == pytest.approx(100_000)
    for d, res in ((near, 5.0), (np.concatenate([[near[-1]], far]), 80.0)):
        step = np.diff(d)
        assert np.all(step <= np.minimum(0.5 * res, 0.002 * d[1:]) + 1e-9)
    assert np.diff(near)[-1] == pytest.approx(2.5, rel=0.01)  # uniform once 0.002 d exceeds the cap
    assert np.diff(near)[0] == pytest.approx(0.002, rel=0.01)  # geometric close in


def test_cache_round_trip_and_key_mismatch(tmp_path):
    g = make_grid(-88.0, 40.0, "south", 50.0, 5_000.0, lambda d, az: np.zeros_like(d))
    p = HorizonParams(1.0, 0.5, 4_000)
    h = compute_horizon(-88.0, 40.0, 1.0, [Segment(g, 0, 4_000)], p)
    spec = {"version": 1, "lat": -88.0, "lon": 40.0, "unit_height_m": 1.0, "params": p.__dict__, "layers": []}
    path = hcache.cache_path(spec, tmp_path)
    hcache.save(h, spec, path)
    back = hcache.load(path, spec)
    assert np.array_equal(back.elevation_deg, h.elevation_deg) and back.params == p
    assert back.surface_height_m == h.surface_height_m
    assert hcache.load(path, {**spec, "unit_height_m": 2.0}) is None


# ----------------------------------------------------------------------------- real data (Site01)


@needs_dems
def test_site01_kernel_matches_plain_numpy_rays():
    """The numba kernel against an independent NumPy evaluation (destination formula + DemLayer)."""
    p = HorizonParams()
    h = horizon_at(*SITE01, 1.0, p)
    assert h.missing_samples == 0
    assert h.surface_height_m == pytest.approx(1954.60, abs=0.01)
    stack = resolve(*SITE01, p.max_range_m)
    dems = [sl.spec.dem() for sl in stack.layers]
    from lss.horizon.core import segments_for

    dist, layer = ray_samples(segments_for(stack), p)
    ro = R + h.surface_height_m + 1.0
    for az in (0.0, 45.0, 150.0, 270.0, 333.3):
        lat, lon = destination(*SITE01, az, dist)
        hts = np.full(dist.size, np.nan)
        for i, dem in enumerate(dems):  # designated layer, else the next coarser one
            todo = np.isnan(hts) & (layer <= i)
            hts[todo] = dem.height_at(lat[todo], lon[todo])
        expected = elevation_deg(R + hts, ro, dist / R).max()
        assert h.elevation_at(az) == pytest.approx(expected, abs=1e-6)


@needs_dems
def test_site01_cache(tmp_path, monkeypatch):
    t0 = time.monotonic()
    h1 = cached_horizon(*SITE01, 1.0, directory=tmp_path)
    assert len(list(tmp_path.glob("h_*.npz"))) == 1

    def fail(*a, **k):
        raise AssertionError("should have come from the cache")

    monkeypatch.setattr(hcache, "compute_horizon", fail)
    t1 = time.monotonic()
    h2 = cached_horizon(*SITE01, 1.0, directory=tmp_path)
    assert np.array_equal(h1.elevation_deg, h2.elevation_deg)
    assert time.monotonic() - t1 < (t1 - t0)
    with pytest.raises(AssertionError):  # another height is another key
        cached_horizon(*SITE01, 2.0, directory=tmp_path)
