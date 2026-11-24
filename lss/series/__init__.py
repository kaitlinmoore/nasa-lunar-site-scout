"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Visibility time series and event finding.
"""

from lss.series.core import (
    BODIES,
    SERIES_VERSION,
    BodyVisibility,
    Grid,
    Period,
    SeriesParams,
    SeriesResult,
    body_visibility,
    compute_series,
    compute_visibility,
    ephemeris_sampler,
    events,
    horizon_response,
    series_response,
)
from lss.series.disc import (
    LIMB_U2,
    LIMB_V2,
    LIMB_WAVELENGTH_NM,
    limb_darkened_disc_mean,
    limb_darkening,
    margins,
    visible_fraction,
)

__all__ = [
    "BODIES",
    "LIMB_U2",
    "LIMB_V2",
    "LIMB_WAVELENGTH_NM",
    "SERIES_VERSION",
    "BodyVisibility",
    "Grid",
    "Period",
    "SeriesParams",
    "SeriesResult",
    "body_visibility",
    "compute_series",
    "compute_visibility",
    "ephemeris_sampler",
    "events",
    "horizon_response",
    "limb_darkened_disc_mean",
    "limb_darkening",
    "margins",
    "series_response",
    "visible_fraction",
]
