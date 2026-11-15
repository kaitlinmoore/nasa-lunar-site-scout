"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Ray-cast horizon mask per (location, unit height). Conventions: see `core`; caching: see `cache`.
"""

from lss.horizon.cache import cached_horizon
from lss.horizon.core import (
    HORIZON_VERSION,
    Horizon,
    HorizonParams,
    HorizonUnavailable,
    Segment,
    compute_horizon,
    elevation_deg,
    horizon_at,
)

__all__ = [
    "HORIZON_VERSION",
    "Horizon",
    "HorizonParams",
    "HorizonUnavailable",
    "Segment",
    "cached_horizon",
    "compute_horizon",
    "elevation_deg",
    "horizon_at",
]
