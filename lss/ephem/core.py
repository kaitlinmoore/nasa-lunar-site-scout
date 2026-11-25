"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Ephemeris and frames: Sun and Earth as seen from a site on the Moon.

Conventions (also in docs/methodology.md section 2):
- Frame: MOON_ME_DE421 (named explicitly; `MOON_ME` is only an alias for it). The PGDA elevation
  maps use this frame, so terrain and ephemeris need no alignment.
- Kernels: DE421 era (see lss/datafiles.py). Supported instants are limited by the lunar orientation
  kernel, 1900-01-01 to 2051-01-01 00:00:00 TDB; requests outside raise `OutOfCoverage`.
- Time: input UTC (timezone-aware datetimes); SPICE ephemeris time (TDB) inside, converted by SPICE with
  the naif0012 leapseconds kernel. No leap seconds after 2016-12-31 are assumed.
- Site: planetocentric latitude / east longitude on the 1737.4 km reference sphere. The observer is on
  the sphere's normal (= radial direction) at radius R + h, where h = DEM surface height + unit height.
- Local frame: east-north-up from the sphere normal. Azimuth is degrees clockwise from north, 0..360;
  elevation is degrees above the local horizontal plane (the geometric horizon of the sphere normal,
  not the terrain horizon). The formulas stay defined at the poles: there the given longitude fixes
  which horizontal direction is called north (see `enu_basis`).
- Aberration: apparent directions, corrected for light time and stellar aberration (SPICE "LT+S"),
  computed by `spkcpo` for an observer fixed on the rotating Moon, so the observer's velocity due to
  lunar rotation is included in the aberration. The Moon has no atmosphere: no refraction.
- Disc sizes: apparent angular radius = asin(R_body / distance). Sun R = 696,000 km (pck00010).
  Earth R = 6371.0 km, the volumetric mean radius (a^2 c)^(1/3) of pck00010's ellipsoid (6371.0 km).
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import spiceypy as sp

from lss.datafiles import get as datafile

FRAME = "MOON_ME_DE421"
MOON_RADIUS_M = 1_737_400.0  # PGDA reference sphere
ABCORR = "LT+S"
KERNEL_IDS = ("naif0012", "pck00010", "de421_spk", "moon_pa_de421", "moon_fk", "moon_assoc_me")

_lock = threading.Lock()
_loaded = False
_coverage: tuple[float, float] | None = None


class OutOfCoverage(ValueError):
    """The requested time is outside the loaded kernels' coverage."""


class KernelsMissing(FileNotFoundError):
    """A kernel file is missing; run `uv run python scripts/fetch_data.py kernels`."""


def load_kernels() -> None:
    """Load the DE421-era kernels once per process (thread-safe, idempotent)."""
    global _loaded, _coverage
    with _lock:
        if _loaded:
            return
        paths = [datafile(k).path for k in KERNEL_IDS]
        missing = [str(p) for p in paths if not p.is_file()]
        if missing:
            raise KernelsMissing(
                f"missing SPICE kernels: {missing}. Run: uv run python scripts/fetch_data.py kernels"
            )
        for p in paths:
            sp.furnsh(str(p))
        _coverage = _measure_coverage()
        _loaded = True


def _measure_coverage() -> tuple[float, float]:
    """Intersection of the lunar orientation PCK and the DE421 SPK coverage (TDB seconds past J2000)."""
    pck = str(datafile("moon_pa_de421").path)
    frames = sp.cell_int(10)
    sp.pckfrm(pck, frames)
    lo, hi = -np.inf, np.inf
    for fid in frames:
        cov = sp.cell_double(2000)
        sp.pckcov(pck, fid, cov)
        a, b = sp.wnfetd(cov, 0)
        lo, hi = max(lo, a), min(hi, sp.wnfetd(cov, sp.wncard(cov) - 1)[1])
    spk = str(datafile("de421_spk").path)
    for body in (10, 301, 399):  # Sun, Moon, Earth
        cov = sp.spkcov(spk, body)
        a, _ = sp.wnfetd(cov, 0)
        _, b = sp.wnfetd(cov, sp.wncard(cov) - 1)
        lo, hi = max(lo, a), min(hi, b)
    return float(lo), float(hi)


def coverage_et() -> tuple[float, float]:
    load_kernels()
    assert _coverage is not None
    return _coverage


def coverage_utc() -> tuple[datetime, datetime]:
    """Supported span as UTC datetimes (the last instant rounds down to the millisecond)."""
    lo, hi = coverage_et()
    return et_to_utc(lo), et_to_utc(hi)


def utc_to_et(times: Sequence[datetime] | datetime) -> np.ndarray:
    """UTC datetimes (timezone-aware) -> TDB seconds past J2000, via SPICE (leap seconds from naif0012)."""
    load_kernels()
    if isinstance(times, datetime):
        times = [times]
    strings = []
    for t in times:
        if t.tzinfo is None:
            raise ValueError("times must be timezone-aware (UTC)")
        u = t.astimezone(UTC)
        strings.append(u.strftime("%Y-%m-%dT%H:%M:%S.") + f"{u.microsecond:06d}")
    et = np.atleast_1d(np.asarray(sp.str2et(strings), dtype=float))
    lo, hi = coverage_et()
    if et.min() < lo or et.max() > hi:
        a, b = coverage_utc()
        raise OutOfCoverage(
            f"time outside the ephemeris coverage {a.isoformat()} to {b.isoformat()} "
            "(DE421-era lunar orientation kernel)"
        )
    return et


def et_to_utc(et: float) -> datetime:
    s = sp.et2utc(float(et), "ISOC", 6)
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def site_position_m(lat_deg: float, lon_deg: float, height_m: float) -> np.ndarray:
    """Site position in MOON_ME (m): on the reference-sphere normal at radius R + height_m."""
    return (MOON_RADIUS_M + height_m) * enu_basis(lat_deg, lon_deg)[2]


def enu_basis(lat_deg: float, lon_deg: float) -> np.ndarray:
    """Rows: east, north, up unit vectors in MOON_ME at (lat, lon) on the reference sphere.

    Right-handed (east x north = up). Defined at the poles too: there the given longitude fixes
    the direction called north (along that meridian, toward the pole's far side for the south pole).
    """
    phi, lam = np.radians(lat_deg), np.radians(lon_deg)
    sphi, cphi, slam, clam = np.sin(phi), np.cos(phi), np.sin(lam), np.cos(lam)
    east = np.array([-slam, clam, 0.0])
    north = np.array([-sphi * clam, -sphi * slam, cphi])
    up = np.array([cphi * clam, cphi * slam, sphi])
    return np.vstack([east, north, up])


@dataclass(frozen=True)
class Topocentric:
    """Apparent direction of one body from the site, per sample."""

    et: np.ndarray  # TDB seconds past J2000
    azimuth_deg: np.ndarray  # clockwise from north, 0..360
    elevation_deg: np.ndarray  # above the local horizontal plane
    distance_km: np.ndarray
    angular_radius_deg: np.ndarray


BODY_RADIUS_KM = {"SUN": 696_000.0}  # Earth's is computed from the PCK on first use


def body_radius_km(body: str) -> float:
    body = body.upper()
    if body not in BODY_RADIUS_KM:
        load_kernels()
        a, _, c = sp.bodvrd(body, "RADII", 3)[1]
        BODY_RADIUS_KM[body] = float((a * a * c) ** (1.0 / 3.0))  # volumetric mean radius
    return BODY_RADIUS_KM[body]


def topocentric(body: str, lat_deg: float, lon_deg: float, height_m: float, et: np.ndarray) -> Topocentric:
    """Apparent az/el/distance of `body` ("SUN" or "EARTH") from a site fixed on the Moon.

    `height_m` is the observer's height above the 1737.4 km sphere (DEM surface + unit height).
    `height_m` may be 0 or negative (terrain below the sphere); only the API restricts unit heights.
    """
    load_kernels()
    et = np.atleast_1d(np.asarray(et, dtype=float))
    lo, hi = coverage_et()
    if et.min() < lo or et.max() > hi:
        raise OutOfCoverage("ephemeris time outside kernel coverage")
    obs_km = site_position_m(lat_deg, lon_deg, height_m) / 1000.0
    enu = enu_basis(lat_deg, lon_deg)
    vec = np.empty((et.size, 3))
    for i, t in enumerate(et):
        state, _lt = sp.spkcpo(body.upper(), t, FRAME, "OBSERVER", ABCORR, obs_km, "MOON", FRAME)
        vec[i] = state[:3]
    dist = np.linalg.norm(vec, axis=1)
    local = (vec / dist[:, None]) @ enu.T  # columns: east, north, up components
    el = np.degrees(np.arcsin(np.clip(local[:, 2], -1.0, 1.0)))
    az = np.degrees(np.arctan2(local[:, 0], local[:, 1])) % 360.0
    radius = np.degrees(np.arcsin(body_radius_km(body) / dist))
    return Topocentric(et=et, azimuth_deg=az, elevation_deg=el, distance_km=dist, angular_radius_deg=radius)
