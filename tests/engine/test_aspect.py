# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Aspect and gradient (lss.terrain.slope: aspect_deg, gradient_ps, slope_aspect, gradient_lonlat,
slope_aspect_lonlat; docs/methodology.md section 5.6.2).

Planes are defined in the local tangent frame of a point (east and north from its unit vector), independently
of the code under test, and rise towards a chosen azimuth: their aspect (the downhill azimuth) is that azimuth
plus 180 deg. The slopes returned with the aspect must equal the existing slope functions' exactly.
"""

import math

import numpy as np
import pytest

from lss.terrain.core import latlon_from_ps, ps_from_latlon
from lss.terrain.slope import (
    aspect_deg,
    gradient_lonlat,
    gradient_ps,
    scale_factor,
    slope_aspect,
    slope_aspect_lonlat,
    slope_deg,
    slope_deg_lonlat,
)

R = 1_737_400.0


def unit_vector(lat, lon):
    p, lam = np.radians(lat), np.radians(lon)
    return np.stack([np.cos(p) * np.cos(lam), np.cos(p) * np.sin(lam), np.sin(p)], axis=-1)


def tangent_plane(lat0, lon0, slope_deg_, uphill_az_deg):
    """Heights (m) of a plane through (lat0, lon0) rising at `slope_deg_` towards `uphill_az_deg`."""
    lam0, phi0 = math.radians(lon0), math.radians(lat0)
    east = np.array([-math.sin(lam0), math.cos(lam0), 0.0])
    north = np.array([-math.sin(phi0) * math.cos(lam0), -math.sin(phi0) * math.sin(lam0), math.cos(phi0)])
    t, a = math.tan(math.radians(slope_deg_)), math.radians(uphill_az_deg)

    def f(lat, lon):
        u = unit_vector(lat, lon)
        return 100.0 + t * R * ((u @ east) * math.sin(a) + (u @ north) * math.cos(a))

    return f


def az_diff(a, b):
    """Smallest angle between two azimuths (deg)."""
    return abs((np.asarray(a) - b + 180.0) % 360.0 - 180.0)


def test_aspect_of_simple_gradients():
    east = np.array([1.0, 0.0, -1.0, 0.0, -1.0, 0.0, np.nan])
    north = np.array([0.0, 1.0, 0.0, -1.0, -1.0, 0.0, 0.0])
    got = aspect_deg(east, north)
    # rising east: downhill west (270); rising north: downhill south (180); rising SW: downhill NE (45)
    assert np.allclose(got[:5], [270.0, 180.0, 90.0, 0.0, 45.0])
    assert np.isnan(got[5]) and np.isnan(got[6])  # flat, and no data


# ----------------------------------------------------------------------------- latitude/longitude grids


def lonlat_grid(lat0, lon0, res_deg, half_deg, height_fn):
    n = int(round(2 * half_deg / res_deg))
    m = int(round(2 * half_deg / res_deg / math.cos(math.radians(lat0)))) + 4
    lats = lat0 + n * res_deg / 2 - (np.arange(n) + 0.5) * res_deg
    lons = lon0 - m * res_deg / 2 + (np.arange(m) + 0.5) * res_deg
    lon, lat = np.meshgrid(lons, lats)
    return np.asarray(height_fn(lat, lon), dtype=float), lats, lons


@pytest.mark.parametrize("lat0", [0.5, 26.1, -45.0, 70.0, 89.0, -89.0])
@pytest.mark.parametrize("uphill_az", [0.0, 75.0, 200.0])
def test_lonlat_aspect_of_a_plane(lat0, uphill_az):
    """The pixel at the point has the plane's aspect (uphill + 180) within 0.05 deg and its slope within
    0.01 deg; slope_aspect_lonlat's slope is slope_deg_lonlat's exactly, NaN where it is NaN."""
    res = 1 / 128
    z, lats, lons = lonlat_grid(lat0, 20.0, res, 0.08, tangent_plane(lat0, 20.0, 7.0, uphill_az))
    slope, aspect = slope_aspect_lonlat(z, res, lats)
    assert np.array_equal(slope, slope_deg_lonlat(z, res, lats), equal_nan=True)
    assert np.array_equal(np.isnan(aspect), np.isnan(slope))
    r = int(np.argmin(np.abs(lats[1:-1] - lat0)))
    c = int(np.argmin(np.abs(lons[1:-1] - 20.0)))
    assert slope[r, c] == pytest.approx(7.0, abs=0.01)
    assert az_diff(aspect[r, c], (uphill_az + 180.0) % 360.0) < 0.05


def test_lonlat_gradient_components():
    """A plane rising 0.1 m per metre to the east and 0.05 to the north, at 30 N."""
    t, a = math.hypot(0.1, 0.05), math.degrees(math.atan2(0.1, 0.05))
    res = 1 / 128
    z, lats, lons = lonlat_grid(
        30.0, 20.0, res, 0.05, tangent_plane(30.0, 20.0, math.degrees(math.atan(t)), a)
    )
    east, north = gradient_lonlat(z, res, lats)
    r = int(np.argmin(np.abs(lats[1:-1] - 30.0)))
    c = int(np.argmin(np.abs(lons[1:-1] - 20.0)))
    assert east[r, c] == pytest.approx(0.1, abs=1e-4) and north[r, c] == pytest.approx(0.05, abs=1e-4)


# ----------------------------------------------------------------------------- polar stereographic maps


def ps_grid(x0, y0, step, half_px, height_fn, pole):
    """A north-up PS grid of (2 half_px + 1)^2 pixels centred on (x0, y0); heights at the pixel centres;
    returns z and the interior pixels' centre coordinates."""
    off = (np.arange(-half_px, half_px + 1)) * step
    X, Y = np.meshgrid(x0 + off, y0 - off)  # rows run down the map
    lat, lon = latlon_from_ps(X, Y, pole)
    return np.asarray(height_fn(lat, lon), dtype=float), X[1:-1, 1:-1], Y[1:-1, 1:-1]


@pytest.mark.parametrize(
    "pole, lat0, lon0", [("south", -85.3, 37.07), ("south", -89.5, -120.0), ("north", 86.0, 200.0)]
)
@pytest.mark.parametrize("uphill_az", [0.0, 75.0, 200.0, 300.0])
def test_ps_aspect_of_a_plane(pole, lat0, lon0, uphill_az):
    """The pixel at the point has the plane's aspect within 0.01 deg. Elsewhere on the 5 m grid the plane's
    aspect differs from it by the turn of the meridians, |dlon| sin|lat| (0.2 deg at 89.5 S, 50 m from the
    point); every pixel is within that bound. The slope is 7 deg within 0.01 deg and equals slope_deg's
    exactly."""
    x0, y0 = (float(v) for v in ps_from_latlon(lat0, lon0, pole))
    z, X, Y = ps_grid(x0, y0, 5.0, 10, tangent_plane(lat0, lon0, 7.0, uphill_az), pole)
    slope, aspect = slope_aspect(z, 5.0, X, Y, pole)
    assert np.array_equal(slope, slope_deg(z, 5.0, scale_factor(X, Y)))
    assert np.allclose(slope, 7.0, atol=0.01)
    want = (uphill_az + 180.0) % 360.0
    assert az_diff(aspect[9, 9], want) < 0.01  # the centre pixel (10 of 21, less the edge row and column)
    _, lon = latlon_from_ps(X, Y, pole)
    turn = az_diff(lon, lon0) * math.sin(math.radians(abs(lat0)))
    assert (az_diff(aspect, want) <= turn + 0.01).all()


def test_ps_gradient_matches_slope_deg_and_map_axes():
    """gradient_ps: a plane rising along map +x and +y; hypot of the two is slope_deg's tangent."""
    rng = np.random.default_rng(3)
    z = rng.normal(0.0, 5.0, (30, 40))
    k = scale_factor(np.full((28, 38), 150_000.0), 0.0)
    gx, gy = gradient_ps(z, 10.0, k)
    assert np.array_equal(np.degrees(np.arctan(np.hypot(gx, gy))), slope_deg(z, 10.0, k))
    cols, rows = np.meshgrid(np.arange(40), np.arange(30))
    gx, gy = gradient_ps(0.2 * cols * 10.0 - 0.1 * rows * 10.0, 10.0)  # up the map = against rows
    assert np.allclose(gx, 0.2) and np.allclose(gy, 0.1)


@pytest.mark.parametrize("pole", ["south", "north"])
def test_ps_aspect_undefined_at_the_pole(pole):
    """A pixel centred on the pole has a slope but no aspect; its neighbours have both."""
    z, X, Y = ps_grid(0.0, 0.0, 5.0, 3, lambda lat, lon: 0.01 * (lat + 90.0) * 30_000.0, pole)
    slope, aspect = slope_aspect(z, 5.0, X, Y, pole)
    assert np.isnan(aspect[2, 2]) and np.isfinite(slope[2, 2])
    assert np.isfinite(np.delete(aspect.ravel(), 2 * 5 + 2)).all()


def test_ps_rejects_an_unknown_pole():
    with pytest.raises(ValueError, match="pole"):
        slope_aspect(np.zeros((3, 3)), 5.0, np.zeros((1, 1)), np.zeros((1, 1)), "east")
