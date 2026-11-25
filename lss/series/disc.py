"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Visible fraction of a disc (Sun or Earth) against the terrain horizon profile (methodology section 5.1).

The disc is treated in its tangent plane on the sky: x horizontal (towards increasing azimuth), y vertical,
both in degrees, centre at (azimuth az_c, elevation el_c), angular radius r. A disc point at horizontal offset
x lies at azimuth az_c + x / cos(el_c). It is visible if it is above the horizon elevation at that azimuth.
For a 0.27 deg Sun (or ~1 deg Earth) a few degrees above the horizontal plane the tangent-plane error is
below 1e-4 deg.

The disc is integrated column by column (columns of constant x). Along a column the visible part is the chord
above the horizon, and the integral along it is closed-form, for both a uniform disc and the limb-darkening
law. Across columns, the midpoint rule in phi with x = r sin(phi) (smooth at the limb; the horizon makes the
integrand kinked, so a high-order rule gains nothing). Fractions are normalised by the same quadrature of the
whole disc, so a fully visible disc gives exactly 1. Error against closed-form segments: < 1e-5 (tested).
"""

from __future__ import annotations

import numpy as np

# Solar limb darkening at 550 nm (the project author, 2026-11-15): I(mu)/I(1) = 1 - U2 - V2 + U2 mu + V2 mu^2,
# with mu the cosine of the angle between the solar surface normal and the line of sight. Allen, C. W. (1973),
# Astrophysical Quantities, 3rd ed., section 81 "Solar limb darkening", p. 171, row 0.55 um (u2, v2). The only
# place these coefficients are defined.
LIMB_U2 = 0.93
LIMB_V2 = -0.23
LIMB_WAVELENGTH_NM = 550.0

DISC_NODES = 192  # columns across the disc: max error 7e-6 vs closed-form segments (48: 1e-4)
MARGIN_NODES = 101  # columns for the any-part / whole-disc margins


def limb_darkening(mu):
    """Solar intensity relative to the disc centre, I(mu)/I(1), at 550 nm (Allen 1973)."""
    mu = np.asarray(mu, dtype=float)
    return 1.0 - LIMB_U2 - LIMB_V2 + LIMB_U2 * mu + LIMB_V2 * mu * mu


def limb_darkened_disc_mean() -> float:
    """Mean intensity over the disc relative to the centre: 1 - u2/3 - v2/2 (exact for this law)."""
    return 1.0 - LIMB_U2 / 3.0 - LIMB_V2 / 2.0


_PHI = (np.arange(DISC_NODES) + 0.5) / DISC_NODES * np.pi - np.pi / 2.0  # midpoints on [-pi/2, pi/2]
_W = np.full(DISC_NODES, np.pi / DISC_NODES)
_PHI_M = np.linspace(-np.pi / 2.0, np.pi / 2.0, MARGIN_NODES)


def _horizon_at_columns(horizon_at, az_c, el_c, x):
    """Horizon elevation at each column's azimuth. az_c, el_c: (n,); x: (n, m) offsets in deg."""
    az = az_c[:, None] + x / np.cos(np.radians(el_c))[:, None]
    return np.asarray(horizon_at(np.mod(az, 360.0)), dtype=float)


def visible_fraction(horizon_at, az_c, el_c, radius, limb_darkened: bool):
    """Visible fraction (0..1) of each disc.

    `horizon_at(az)`: terrain horizon elevation (deg) at azimuths (any shape), e.g. `Horizon.elevation_at`.
    `limb_darkened`: True = share of the disc's light (Sun, section 5.1); False = share of its area (Earth).
    """
    az_c, el_c, r = (np.atleast_1d(np.asarray(v, dtype=float)) for v in (az_c, el_c, radius))
    s, cphi = np.sin(_PHI), np.cos(_PHI)
    x = r[:, None] * s[None, :]
    c = r[:, None] * cphi[None, :]  # half-height of each column
    h = _horizon_at_columns(horizon_at, az_c, el_c, x)
    y0 = np.clip(h - el_c[:, None], -c, c)  # visible chord: y in [y0, c]
    col_w = (_W * cphi)[None, :] * r[:, None]  # dx = r cos(phi) dphi
    if not limb_darkened:
        area = np.sum(col_w * (c - y0), axis=1)
        return np.clip(area / np.sum(col_w * (2.0 * c), axis=1), 0.0, 1.0)
    a0, a1, a2 = 1.0 - LIMB_U2 - LIMB_V2, LIMB_U2, LIMB_V2
    # Along a column (fixed x): mu = sqrt(c^2 - y^2) / r.
    # int mu dy = [y sqrt(c^2 - y^2) + c^2 asin(y / c)] / (2 r);  int mu^2 dy = [c^2 y - y^3 / 3] / r^2.
    rr = r[:, None]

    def column_light(y0):
        u = np.clip(y0 / c, -1.0, 1.0)
        f_top = c * c * (np.pi / 2.0)  # value of [y sqrt(c^2-y^2) + c^2 asin(y/c)] at y = c
        g1 = (f_top - (y0 * c * np.sqrt(1.0 - u * u) + c * c * np.arcsin(u))) / (2.0 * rr)
        g2 = ((c**3 - c**3 / 3.0) - (c * c * y0 - y0**3 / 3.0)) / (rr * rr)
        return np.sum(col_w * (a0 * (c - y0) + a1 * g1 + a2 * g2), axis=1)

    return np.clip(column_light(y0) / column_light(-c), 0.0, 1.0)


def margins(horizon_at, az_c, el_c, radius):
    """(any_part, whole_disc) margins in deg, for each disc.

    any_part > 0 iff some part of the disc is above the horizon: max over columns of (column top - horizon).
    whole_disc >= 0 iff all of it is: min over columns of (column bottom - horizon). Both are continuous in
    time, so visibility changes are their zero crossings (found by root-finding in lss.series.core).
    """
    az_c, el_c, r = (np.atleast_1d(np.asarray(v, dtype=float)) for v in (az_c, el_c, radius))
    x = r[:, None] * np.sin(_PHI_M)[None, :]
    c = r[:, None] * np.cos(_PHI_M)[None, :]
    h = _horizon_at_columns(horizon_at, az_c, el_c, x)
    rel = h - el_c[:, None]
    return np.max(c - rel, axis=1), np.min(-c - rel, axis=1)
