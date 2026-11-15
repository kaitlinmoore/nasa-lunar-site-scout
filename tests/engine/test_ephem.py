# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""lss.ephem: frames, time scales, topocentric az/el. Needs the SPICE kernels (skipped otherwise).

The JPL Horizons comparison is a separate validation test (step 4.7).
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from lss.datafiles import get as datafile
from lss.ephem import core as ephem

KERNELS_PRESENT = all(datafile(k).path.is_file() for k in ephem.KERNEL_IDS)
needs_kernels = pytest.mark.skipif(
    not KERNELS_PRESENT, reason="SPICE kernels missing: uv run python scripts/fetch_data.py kernels"
)

SITE01 = (-89.45, -137.31)


@pytest.mark.parametrize("lat, lon", [(0, 0), (45, 30), (-89.45, -137.31), (-90, 0), (90, 123), (-30, 200)])
def test_enu_basis_orthonormal_right_handed(lat, lon):
    e, n, u = ephem.enu_basis(lat, lon)
    m = np.vstack([e, n, u])
    assert np.allclose(m @ m.T, np.eye(3), atol=1e-12)
    assert np.allclose(np.cross(e, n), u, atol=1e-12)
    # up is the radial direction of planetocentric (lat, lon)
    phi, lam = np.radians(lat), np.radians(lon)
    assert np.allclose(u, [np.cos(phi) * np.cos(lam), np.cos(phi) * np.sin(lam), np.sin(phi)], atol=1e-12)
    # north points toward the north pole (or, at a pole, has no z component)
    if abs(lat) < 90:
        assert n[2] > 0


def test_site_position_on_sphere_normal():
    p = ephem.site_position_m(*SITE01, 1954.60 + 1.0)
    assert np.isclose(np.linalg.norm(p), ephem.MOON_RADIUS_M + 1955.60)


@needs_kernels
def test_coverage_is_the_orientation_kernel_end():
    import spiceypy as sp

    lo, hi = ephem.coverage_et()
    assert hi == pytest.approx(sp.str2et("2051-01-01 00:00:00 TDB"), abs=1e-6)
    assert lo == pytest.approx(sp.str2et("1900-01-01 00:00:00 TDB"), abs=1e-6)
    a, b = ephem.coverage_utc()
    assert b.isoformat().startswith("2050-12-31T23:58:50.816")


@needs_kernels
def test_utc_to_tdb_offset():
    # TDB - UTC = (TAI - UTC = 37 s) + 32.184 s + a periodic term of at most ~1.7 ms
    t = datetime(2028, 11, 15, tzinfo=UTC)
    et = ephem.utc_to_et(t)[0]
    j2000_utc = datetime(2000, 1, 1, 12, tzinfo=UTC)
    assert et - (t - j2000_utc).total_seconds() == pytest.approx(69.184 - 64.184 + 64.184, abs=0.002)


@needs_kernels
def test_out_of_coverage_and_naive_times_rejected():
    with pytest.raises(ephem.OutOfCoverage):
        ephem.utc_to_et(datetime(2051, 6, 1, tzinfo=UTC))
    with pytest.raises(ValueError):
        ephem.utc_to_et(datetime(2028, 1, 1))
    with pytest.raises(ephem.OutOfCoverage):
        ephem.topocentric("SUN", *SITE01, 0.0, np.array([ephem.coverage_et()[1] + 1.0]))


@needs_kernels
@pytest.mark.parametrize("body", ["SUN", "EARTH"])
# azlcpo cannot define its frame exactly at a pole; the pole itself is covered by the continuity test.
@pytest.mark.parametrize("site", [SITE01, (0.0, 0.0), (-45.0, 120.0), (-89.9999, 30.0)])
def test_topocentric_matches_spice_azlcpo(body, site):
    """Independent check of frame, ENU convention and aberration against SPICE's own az/el routine."""
    import spiceypy as sp

    h = 1955.60
    times = [datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=37 * i, hours=5 * i) for i in range(10)]
    et = ephem.utc_to_et(times)
    ours = ephem.topocentric(body, *site, h, et)
    obs_km = ephem.site_position_m(*site, h) / 1000.0
    for i, t in enumerate(et):
        azlsta, _lt = sp.azlcpo("ELLIPSOID", body, t, ephem.ABCORR, False, True, obs_km, "MOON", ephem.FRAME)
        rng, az, el = azlsta[:3]
        assert ours.distance_km[i] == pytest.approx(rng, rel=1e-12)
        assert ours.elevation_deg[i] == pytest.approx(np.degrees(el), abs=1e-7)
        d_az = (ours.azimuth_deg[i] - np.degrees(az) + 180.0) % 360.0 - 180.0
        assert abs(d_az) < 1e-6


@needs_kernels
def test_site01_year_is_physically_plausible():
    """At 89.45 S the Sun stays near the horizon and Earth is low on the near-side horizon."""
    start = datetime(2028, 1, 1, tzinfo=UTC)
    et = ephem.utc_to_et([start + timedelta(hours=6 * i) for i in range(4 * 366)])
    sun = ephem.topocentric("SUN", *SITE01, 1955.60, et)
    earth = ephem.topocentric("EARTH", *SITE01, 1955.60, et)
    # Sun: within (1.54 deg obliquity to the ecliptic + 0.55 deg from the pole + margin)
    assert np.abs(sun.elevation_deg).max() < 2.3
    # Earth: within libration in latitude (~6.7 deg) + 0.55 deg + margin; the Sun circles all azimuths
    assert np.abs(earth.elevation_deg).max() < 8.0
    assert np.ptp(sun.azimuth_deg) > 350
    # Apparent radii: Sun ~0.26-0.27 deg; Earth ~0.90-1.02 deg (lunar apogee ~406,700 km, perigee ~356,400 km)
    assert 0.258 < sun.angular_radius_deg.min() and sun.angular_radius_deg.max() < 0.275
    assert 0.89 < earth.angular_radius_deg.min() and earth.angular_radius_deg.max() < 1.03


@needs_kernels
@pytest.mark.parametrize("lon", [0.0, 77.0, -137.31])
def test_pole_azimuth_is_the_limit_along_the_meridian(lon):
    """At the exact pole, north is the limit of north approaching the pole along the given meridian."""
    et = ephem.utc_to_et([datetime(2028, 11, 15, tzinfo=UTC), datetime(2029, 3, 2, 7, tzinfo=UTC)])
    for body in ("SUN", "EARTH"):
        at = ephem.topocentric(body, -90.0, lon, 0.0, et)
        near = ephem.topocentric(body, -89.99999, lon, 0.0, et)
        d_az = (at.azimuth_deg - near.azimuth_deg + 180.0) % 360.0 - 180.0
        assert np.abs(d_az).max() < 1e-3
        assert np.abs(at.elevation_deg - near.elevation_deg).max() < 1e-4


def test_earth_radius_is_volumetric_mean():
    if not KERNELS_PRESENT:
        pytest.skip("kernels missing")
    assert ephem.body_radius_km("EARTH") == pytest.approx(6371.0, abs=0.01)
    assert ephem.body_radius_km("SUN") == 696_000.0
