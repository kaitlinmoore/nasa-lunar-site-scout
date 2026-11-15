"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Core NL vocabulary (step 4.2, decided by the project author 2026-11-15: "Option B").

The LLM may emit a structured query for these operations only. Each maps to the
contract request model its `params` must validate against. Everything else is
answered as unsupported, citing the dataset capability registry.

Unit-height proxies (project author's decision, 2026-11-15): "rover" -> 1 m and
"lander" -> 5 m. They are proxy values, and every answer that uses one says so.

Defaults (project author's decisions, 2026-11-15): with no height, no role and no selected
scenario, the lander proxy (5 m); with no dates and no selected scenario, a 30-day window
starting at the request's date (00:00 UTC). Both are disclosed in the answer.

Defaults for vague terms (project author's decisions, 2026-11-15): "safe" with no slope limit
means slope under 5 degrees (D-safe), and the echo names the terrain data the slope is measured
on; "nearby" with no distance means within 10 km (D-radius), stated in the echo. Both are
disclosed by code, not by the model.
"""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

from pydantic import BaseModel

from lss.contract import (
    CompareRequest,
    HorizonRequest,
    LocateRequest,
    Model,
    Operation,
    ProximityRequest,
    ScenarioRequest,
    SearchRequest,
    SiteCategory,
)


class SitesParams(Model):
    """Query parameters of `GET /api/sites`.

    Stopgap: the contract has no request model for this GET operation (contract gap C4,
    `SitesQuery`, held until Phase 2). Replace this with the contract model once it exists.
    """

    category: SiteCategory | None = None


# Operation -> model that `StructuredQuery.params` must validate against.
OPERATION_PARAMS: dict[Operation, type[BaseModel]] = {
    Operation.metrics: ScenarioRequest,
    Operation.series: ScenarioRequest,
    Operation.compare: CompareRequest,
    Operation.horizon: HorizonRequest,
    Operation.sites: SitesParams,
    Operation.locate: LocateRequest,
    Operation.proximity: ProximityRequest,
    Operation.search: SearchRequest,
}

ALLOWED_OPERATIONS: frozenset[Operation] = frozenset(OPERATION_PARAMS)


class HeightSource(StrEnum):
    """Where a structured query's `unit_height_m` came from."""

    user = "user"  # the user gave a height in meters
    selected_scenario = "selected_scenario"  # taken from the scenario selected in the UI
    rover_proxy = "rover_proxy"  # the user said "rover"; proxy height
    lander_proxy = "lander_proxy"  # the user said "lander"; proxy height
    default = "default"  # no height, role or selected scenario: the lander proxy (D-height)
    not_applicable = "not_applicable"  # the operation has no height


UNIT_HEIGHT_PROXIES_M: dict[HeightSource, float] = {
    HeightSource.rover_proxy: 1.0,
    HeightSource.lander_proxy: 5.0,
    HeightSource.default: 5.0,
}

PROXY_ASSUMPTION_TEXT: dict[HeightSource, str] = {
    HeightSource.rover_proxy: (
        "Height 1 m: a proxy value for a rover, not the height of any specific rover."
    ),
    HeightSource.lander_proxy: (
        "Height 5 m: a proxy value for a lander, not the height of any specific lander."
    ),
    HeightSource.default: (
        "Height 5 m: no height or unit was given, so the lander proxy value was used "
        "(not the height of any specific lander)."
    ),
}


class WindowSource(StrEnum):
    """Where a structured query's time window came from."""

    user = "user"  # the user gave dates
    selected_scenario = "selected_scenario"  # taken from the scenario selected in the UI
    default = "default"  # no dates: DEFAULT_WINDOW from the request's date (D-window)
    not_applicable = "not_applicable"  # the operation has no window


DEFAULT_WINDOW = timedelta(days=30)


def default_window_text(start_iso_date: str) -> str:
    return f"Window: 30 days from {start_iso_date} 00:00 UTC (default; no dates were given)."


class SlopeSource(StrEnum):
    """Where a structured query's slope limit (`max_slope_deg`) came from."""

    user = "user"  # the user gave a slope limit in degrees
    safe_default = "safe_default"  # the user said "safe" and gave no limit: SAFE_MAX_SLOPE_DEG (D-safe)
    not_applicable = "not_applicable"  # the query has no slope limit


class RadiusSource(StrEnum):
    """Where a structured query's search distance (`radius_m`, `max_feature_distance_m`) came from."""

    user = "user"  # the user gave a distance
    nearby_default = "nearby_default"  # the user said "nearby" (or similar) and gave none (D-radius)
    not_applicable = "not_applicable"  # the query has no search distance


SAFE_MAX_SLOPE_DEG = 5.0
NEARBY_RADIUS_M = 10_000.0

# Params that carry the slope limit / search distance, at any depth of `StructuredQuery.params`.
SLOPE_KEYS: frozenset[str] = frozenset({"max_slope_deg"})
RADIUS_KEYS: frozenset[str] = frozenset({"radius_m", "max_feature_distance_m"})

NEARBY_RADIUS_TEXT = "Nearby: within 10 km (default; no distance was given)."


def safe_slope_text(terrain: str) -> str:
    """The D-safe disclosure. `terrain` names the terrain data the slope is measured on (from the
    engine's result); the project author's rule is that the echo always states it."""
    return f"Safe: slope under 5°, measured on {terrain} (default; no slope limit was given)."
