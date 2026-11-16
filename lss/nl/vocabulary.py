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
on; "nearby" with no distance means within 10 km (D-radius), stated in the echo. Slope "at and
around" a site with no distance means within 1 km (D-around, 2026-11-15). All are disclosed by code,
not by the model.

Contract 0.7.0 added `terrain` (slope at and around a point) and `site_summary` (metrics, slope and
nearby features at one site; the project author's choice for her query #1) to the vocabulary.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel

from lss.contract import (
    CompareRequest,
    HorizonRequest,
    LocateRequest,
    Operation,
    ProximityRequest,
    ScenarioRequest,
    SearchRequest,
    SitesQuery,
    SiteSummaryRequest,
    TerrainRequest,
)

# Operation -> model that `StructuredQuery.params` must validate against.
OPERATION_PARAMS: dict[Operation, type[BaseModel]] = {
    Operation.metrics: ScenarioRequest,
    Operation.series: ScenarioRequest,
    Operation.compare: CompareRequest,
    Operation.horizon: HorizonRequest,
    Operation.sites: SitesQuery,
    Operation.locate: LocateRequest,
    Operation.proximity: ProximityRequest,
    Operation.search: SearchRequest,
    Operation.terrain: TerrainRequest,
    Operation.site_summary: SiteSummaryRequest,
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
    ranking_default = "ranking_default"  # a ranking with no dates: the precomputed year (Kaitlin's C5 choice)
    not_applicable = "not_applicable"  # the operation has no window


DEFAULT_WINDOW = timedelta(days=30)


# Ranking questions with no dates use the precomputed year (Kaitlin, 2026-11-16, C3 design option C5):
# exactly stream A's served 2028 window and step. Single-site questions keep DEFAULT_WINDOW (D-window).
RANKING_WINDOW = (datetime(2028, 1, 1, tzinfo=UTC), datetime(2029, 1, 1, tzinfo=UTC), timedelta(hours=6))
# Claude-drafted, approved by the project author (2026-11-16).
RANKING_WINDOW_TEXT = (
    "Window: the year 2028, the precomputed year (default for rankings; no dates were given)."
)

# A slope limit inside a compare filter (contract 0.10.0): the metric that carries it.
SLOPE_FILTER_METRIC = "terrain.slope_at_point_deg"


def _when(t: datetime) -> str:
    day = f"{t.day} {t:%b %Y}"
    return day if (t.hour, t.minute) == (0, 0) else f"{day} {t:%H:%M}"


def step_text(step: timedelta) -> str:
    """'every hour', 'every 6 hours', 'every 30 minutes', else the ISO-like duration."""
    secs = int(step.total_seconds())
    if secs % 3600 == 0:
        hours = secs // 3600
        return "every hour" if hours == 1 else f"every {hours} hours"
    if secs % 60 == 0:
        mins = secs // 60
        return "every minute" if mins == 1 else f"every {mins} minutes"
    return f"every {secs} s"


# Disclosures when a selected scenario's values were used (filled in by code, B's G2 recheck 2026-11-16).
# Claude-drafted, approved by the project author (2026-11-16).
def selected_height_text(height_m: float) -> str:
    return f"Height {height_m:g} m: from the selected scenario."


def selected_window_text(start: datetime, end: datetime, step: timedelta) -> str:
    return f"Window: {_when(start)} – {_when(end)} UTC, {step_text(step)}, from the selected scenario."


def default_window_text(start_iso_date: str) -> str:
    return f"Window: 30 days from {start_iso_date} 00:00 UTC (default; no dates were given)."


class SiteSource(StrEnum):
    """Where a structured query's site came from (nl-output-6, after stream B's NL box testing)."""

    user = "user"  # the user named the site (or gave coordinates)
    selected_site = "selected_site"  # the question named no site; the site selected in the UI was used
    not_applicable = "not_applicable"  # the query has no site


def selected_site_text(name: str) -> str:
    """Disclosure when the selected site stood in for an unnamed one (wording: the project author's choice,
    2026-11-16). Replaces the model's own note, so every disclosure comes from code."""
    return f"Using the selected site, {name}."


class SlopeSource(StrEnum):
    """Where a structured query's slope limit (`max_slope_deg`) came from."""

    user = "user"  # the user gave a slope limit in degrees
    safe_default = "safe_default"  # the user said "safe" and gave no limit: SAFE_MAX_SLOPE_DEG (D-safe)
    not_applicable = "not_applicable"  # the query has no slope limit


class RadiusSource(StrEnum):
    """Where a structured query's search distance (`radius_m`, `max_feature_distance_m`) came from."""

    user = "user"  # the user gave a distance
    nearby_default = "nearby_default"  # the user said "nearby" (or similar) and gave none (D-radius)
    around_default = "around_default"  # slope "at and around" a site, no distance given (D-around)
    not_applicable = "not_applicable"  # the query has no search distance


SAFE_MAX_SLOPE_DEG = 5.0
NEARBY_RADIUS_M = 10_000.0
AROUND_RADIUS_M = 1_000.0

# Params that carry the slope limit / search distance, at any depth of `StructuredQuery.params`.
SLOPE_KEYS: frozenset[str] = frozenset({"max_slope_deg"})
RADIUS_KEYS: frozenset[str] = frozenset({"radius_m", "max_feature_distance_m"})

NEARBY_RADIUS_TEXT = "Nearby: within 10 km (default; no distance was given)."
# Claude-drafted on the same pattern as the "nearby" text; approved by the project author 2026-11-16.
AROUND_RADIUS_TEXT = "Around: within 1 km (default; no distance was given)."

# Default distances: the value each default source requires, and its disclosure.
RADIUS_DEFAULTS: dict[RadiusSource, tuple[float, str]] = {
    RadiusSource.nearby_default: (NEARBY_RADIUS_M, NEARBY_RADIUS_TEXT),
    RadiusSource.around_default: (AROUND_RADIUS_M, AROUND_RADIUS_TEXT),
}


def safe_slope_text(terrain: str) -> str:
    """The D-safe disclosure. `terrain` names the terrain data the slope is measured on (from the
    engine's result); the project author's rule is that the echo always states it.

    "under 5°" matches the contract: `SearchCriteria.max_slope_deg` is a strict bound (slope < limit;
    the project author's decision, 2026-11-15, contract note C9).
    """
    return f"Safe: slope under 5°, measured on {terrain} (default; no slope limit was given)."


# Claude-drafted, approved by the project author (2026-11-16): the "safe" disclosure when the
# operation that would measure the slope is not available yet, so no terrain data can be named.
SAFE_NOT_MEASURED_TEXT = (
    "Safe: slope under 5° (default; no slope limit was given). Not measured: this version can't run "
    "that search yet."
)
