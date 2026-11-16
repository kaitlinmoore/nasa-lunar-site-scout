"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Contract v0: pydantic models for every request and response in plan section 4.3.

Conventions (fixed here so every stream agrees):
- Coordinates are planetocentric degrees in the MOON_ME frame (DE421).
  Latitude is -90..90; longitude is east-positive, -180..180.
- Times are timezone-aware UTC (ISO 8601 with "Z" or an offset).
- Durations (`step`) are ISO 8601 durations in JSON, e.g. "PT1H".
- Angles are degrees and distances meters unless the field name says otherwise
  (`_km`, `_h`). Heights are meters above the DEM surface.
- Metric values are nullable: null means "not computed" (or not computable
  with the data available), never zero.

Only the contract owner edits this file (plan section 10.3). Prefer additive changes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_validator,
    model_validator,
)

CONTRACT_VERSION = "0.8.0"

Latitude = Annotated[float, Field(ge=-90.0, le=90.0, description="Planetocentric latitude, deg")]
Longitude = Annotated[
    float, Field(ge=-180.0, le=180.0, description="East-positive longitude, deg, -180..180")
]
Fraction = Annotated[float, Field(ge=0.0, le=1.0)]


class Model(BaseModel):
    """Base for request/value models: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Response(Model):
    """Base for every top-level response.

    `_placeholder` / `_note` mark example data that is not a real result.
    The UI should show a visible "placeholder data" notice when `_placeholder` is true.
    """

    contract_version: str = CONTRACT_VERSION
    placeholder: bool = Field(
        default=False,
        alias="_placeholder",
        description="True when the values are placeholders, not computed results.",
    )
    note: str | None = Field(default=None, alias="_note")


# --------------------------------------------------------------------------- core


class Location(Model):
    lat: Latitude
    lon: Longitude
    name: str | None = None


class Scenario(Model):
    """The unit of everything (plan section 3.1): results are keyed by `Scenario.key()`."""

    location: Location
    unit_height_m: float = Field(gt=0.0, description="Observer height above the DEM surface, m")
    window_start: AwareDatetime
    window_end: AwareDatetime
    step: timedelta = Field(default=timedelta(hours=1), description="Sampling step (ISO 8601)")

    @field_validator("window_start", "window_end")
    @classmethod
    def _to_utc(cls, v: datetime) -> datetime:
        return v.astimezone(UTC)

    @model_validator(mode="after")
    def _check_window(self) -> Scenario:
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        if self.step <= timedelta(0):
            raise ValueError("step must be positive")
        return self

    def key(self) -> str:
        """Stable hash of the scenario (location name excluded), for caching and saved items."""
        payload = self.model_dump(mode="json", exclude={"location": {"name"}})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class SiteCategory(StrEnum):
    pgda = "pgda"
    apollo = "apollo"
    artemis_iii = "artemis_iii"
    clps = "clps"
    commercial = "commercial"
    international = "international"
    custom = "custom"


class Site(Model):
    id: str
    name: str
    category: SiteCategory
    location: Location
    description: str | None = None
    dataset_ids: list[str] = Field(default_factory=list, description="Registry ids of DEMs etc.")
    has_dem_clones: bool = False
    source: str | None = Field(default=None, description="Citation or URL for the coordinates")


class SitesResponse(Response):
    sites: list[Site]


class HealthResponse(Response):
    status: Literal["ok"] = "ok"


# ------------------------------------------------------------ registry and terrain


class DatasetStatus(StrEnum):
    planned = "planned"
    used = "used"
    dropped = "dropped"


class Coverage(Model):
    description: str
    lat_min: Latitude | None = None
    lat_max: Latitude | None = None
    lon_min: Longitude | None = None
    lon_max: Longitude | None = None
    sites_only: bool = Field(default=False, description="Covers listed sites only, not an area")


class DatasetCapability(Model):
    id: str
    name: str
    kind: Literal["terrain", "illumination", "thermal", "features", "ephemeris", "other"]
    provider: str
    url: str
    coverage: Coverage
    resolution_m: float | None = Field(default=None, description="Nominal ground resolution, m")
    resolution_note: str | None = None
    can_answer: list[str] = Field(default_factory=list)
    cannot_answer: list[str] = Field(default_factory=list)
    citation: str
    license: str
    status: DatasetStatus = DatasetStatus.planned
    notes: str | None = None


class DatasetsResponse(Response):
    datasets: list[DatasetCapability]


class FidelityTier(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class FidelityLabel(Model):
    tier: FidelityTier
    summary: str = Field(description="Short user-facing text, e.g. '5 m polar DEM near field'")
    near_field_resolution_m: float | None = None
    far_field_resolution_m: float | None = None


class TerrainLayer(Model):
    dataset_id: str
    role: Literal["near_field", "far_field"]
    resolution_m: float
    max_range_km: float | None = None


class LocateRequest(Model):
    lat: Latitude
    lon: Longitude


class LocateResponse(Response):
    location: Location
    terrain_stack: list[TerrainLayer]
    fidelity: FidelityLabel


class TerrainViewLayer(StrEnum):
    """`layer` query values for GET /api/terrain/view (the response is an image)."""

    hillshade = "hillshade"
    slope = "slope"
    elevation = "elevation"


# ------------------------------------------------------------------------ horizon

# One topocentric frame for the horizon profile and the Sun/Earth tracks (docs/methodology.md sections 2-3),
# so a client can overlay them directly: a disc centre is above the terrain where its elevation exceeds the
# horizon elevation at the same azimuth. Both are built from lss.ephem.enu_basis.
AZIMUTH_CONVENTION = (
    "deg, 0-360, clockwise from north, in the site's topocentric frame (east-north-up at the site, from the "
    "normal to the 1737.4 km reference sphere, MOON_ME_DE421); the same frame as "
)
ELEVATION_CONVENTION = (
    "deg, measured from the local horizontal plane: the plane through the observer (DEM surface + unit "
    "height) normal to the reference sphere's radius at the site; the same plane as "
)


class HorizonRequest(Model):
    location: Location
    unit_height_m: float = Field(gt=0.0)

    def key(self) -> str:
        """Stable hash of location (name excluded) and unit height: a horizon depends on nothing else."""
        payload = self.model_dump(mode="json", exclude={"location": {"name"}})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class HorizonProfile(Response):
    location: Location
    unit_height_m: float
    azimuth_deg: list[float] = Field(
        description="Azimuth of each horizon sample, "
        + AZIMUTH_CONVENTION
        + "the Sun/Earth tracks (BodyTrack.azimuth_deg). Interpolate linearly between samples, "
        "periodic over 360"
    )
    elevation_deg: list[float] = Field(
        description="Terrain horizon elevation at each azimuth, "
        + ELEVATION_CONVENTION
        + "the Sun/Earth tracks (BodyTrack.elevation_deg)"
    )
    max_range_km: float | None = None
    terrain_stack: list[TerrainLayer] = Field(default_factory=list)
    fidelity: FidelityLabel | None = None

    @model_validator(mode="after")
    def _same_length(self) -> HorizonProfile:
        if len(self.azimuth_deg) != len(self.elevation_deg):
            raise ValueError("azimuth_deg and elevation_deg must have the same length")
        return self


# ---------------------------------------------------------------- series, events


class ScenarioRequest(Model):
    """Body of POST /api/series and POST /api/metrics."""

    scenario: Scenario


class EventKind(StrEnum):
    sunrise = "sunrise"
    sunset = "sunset"
    earthrise = "earthrise"
    earthset = "earthset"


class Event(Model):
    kind: EventKind
    time: AwareDatetime
    refined: bool = Field(default=False, description="Refined between samples by root-finding")
    note: str | None = None


class BodyTrack(Model):
    """Per-sample values for one body; every list has the length of `SeriesResponse.time`."""

    azimuth_deg: list[float] = Field(
        description="Apparent azimuth of the disc centre (light time + stellar aberration), "
        + AZIMUTH_CONVENTION
        + "the horizon profile (HorizonProfile.azimuth_deg)"
    )
    elevation_deg: list[float] = Field(
        description="Apparent elevation of the disc centre (light time + stellar aberration), "
        + ELEVATION_CONVENTION
        + "the horizon profile (HorizonProfile.elevation_deg). Not the elevation above the terrain: "
        "see clearance_deg"
    )
    visible_fraction: list[Fraction] = Field(
        description="Visible fraction of the disc, 0..1, against the terrain horizon: Sun = share of "
        "the disc's light (limb-darkened, 550 nm), Earth = share of its area (methodology section 5.1)"
    )
    clearance_deg: list[float] | None = Field(
        default=None,
        description="Disc centre elevation minus the terrain horizon elevation at its azimuth, deg",
    )


class SeriesResponse(Response):
    scenario: Scenario
    scenario_key: str
    time: list[AwareDatetime]
    sun: BodyTrack
    earth: BodyTrack
    events: list[Event] = Field(default_factory=list)
    downsampled: bool = Field(default=False, description="Plotted series thinned for display")

    @model_validator(mode="after")
    def _aligned(self) -> SeriesResponse:
        n = len(self.time)
        for body in (self.sun, self.earth):
            lists = [body.azimuth_deg, body.elevation_deg, body.visible_fraction]
            if body.clearance_deg is not None:
                lists.append(body.clearance_deg)
            if any(len(v) != n for v in lists):
                raise ValueError("every track list must match the length of time")
        return self


# ------------------------------------------------------------------------ metrics


class Stat(Model):
    min: float | None = None
    max: float | None = None
    mean: float | None = None


class PowerMetrics(Model):
    """F3. Nullable: null = not computed. Exact definitions: docs/methodology.md section 5.

    Sunlit = any part of the solar disc above the terrain horizon; shadow = no part of it above. Sunlit and
    shadow periods tile the window. Periods that start before window_start or run past window_end are
    clipped to the window and still counted.
    """

    illumination_fraction: Fraction | None = Field(
        default=None,
        description="Fraction of the window that is sunlit (any part of the solar disc visible)",
    )
    mean_visible_disk_fraction: Fraction | None = Field(
        default=None,
        description=(
            "Time average over the window of the visible share of the solar disc's light, weighted by limb "
            "darkening at 550 nm (a light-weighted fraction, not a geometric area fraction)"
        ),
    )
    sunlit_duration_h: float | None = Field(
        default=None, description="Total sunlit time in the window (any part of the solar disc visible), h"
    )
    longest_sunlit_period_h: float | None = Field(
        default=None,
        description=(
            "Longest continuous sunlit period (any part of the solar disc visible), clipped to the window, h"
        ),
    )
    longest_shadow_h: float | None = Field(
        default=None,
        description=(
            "Longest continuous shadow period (no part of the solar disc visible), clipped to the window, h"
        ),
    )
    longest_shadow_clipped: bool | None = Field(
        default=None,
        description=(
            "True if the longest shadow period starts before window_start or runs past window_end, so its "
            "full length is longer than longest_shadow_h; false if it lies inside the window or there is none"
        ),
    )
    shadow_count: int | None = Field(
        default=None,
        description=(
            "Number of shadow periods (no part of the solar disc visible) in the window, with no minimum "
            "duration; periods clipped to the window count. Partial loss of the disc is not a shadow"
        ),
    )
    sun_elevation_deg: Stat = Field(
        default_factory=Stat,
        description=(
            "Apparent elevation of the Sun's disc centre above the local horizontal plane (not the terrain "
            "horizon): min, max and time mean over the whole window, whether or not the Sun is visible, deg"
        ),
    )
    sun_azimuth_deg: Stat = Field(
        default_factory=Stat,
        description=(
            "Apparent azimuth of the Sun's disc centre, deg clockwise from north, over the whole window, "
            "whether or not the Sun is visible. min and max are the ends of the smallest arc containing the "
            "track, read clockwise from min to max (min > max when the arc crosses north). A full circle is "
            "reported as min 0, max 360. mean is always null: an average azimuth has no meaning here"
        ),
    )
    time_to_sunset_h: float | None = Field(
        default=None,
        description=(
            "From window_start to the first sunset (the last part of the solar disc going below the "
            "terrain horizon), h. Null if not computed, or if there is no sunset in the window "
            "(sunset_in_window false)"
        ),
    )
    sunset_in_window: bool | None = Field(
        default=None,
        description=(
            "True if at least one sunset occurs in the window, false if none does (time_to_sunset_h is then "
            "null). Null only if not computed"
        ),
    )


class CommsMetrics(Model):
    """F4 (direct-to-Earth at the unit height). Nullable: null = not computed. See methodology section 5.

    Earth visible = any part of the Earth disc above the terrain horizon; a gap = no part of it above.
    Gaps that start before window_start or run past window_end are clipped to the window.
    """

    earth_visibility_fraction: Fraction | None = Field(
        default=None, description="Fraction of the window with any part of the Earth disc visible"
    )
    earth_full_disc_fraction: Fraction | None = Field(
        default=None, description="Fraction of the window with the whole Earth disc above the terrain horizon"
    )
    longest_earth_gap_h: float | None = Field(
        default=None,
        description=(
            "Longest continuous period with no part of the Earth disc visible, clipped to the window, h"
        ),
    )
    longest_earth_gap_clipped: bool | None = Field(
        default=None,
        description=(
            "True if the longest Earth gap starts before window_start or runs past window_end, so its "
            "full length is longer than longest_earth_gap_h; false if it lies inside the window or there "
            "is none"
        ),
    )
    earth_elevation_deg: Stat = Field(
        default_factory=Stat,
        description=(
            "Apparent elevation of the Earth's disc centre above the local horizontal plane (not the terrain "
            "horizon): min, max and time mean over the whole window, whether or not the Earth is visible, deg"
        ),
    )
    earth_clearance_deg: Stat = Field(
        default_factory=Stat,
        description=(
            "Earth disc centre elevation minus the terrain horizon elevation at its azimuth: min, max and "
            "time mean over the whole window, deg"
        ),
    )
    sun_earth_overlap_fraction: Fraction | None = Field(
        default=None,
        description="Fraction of the window with any part of both the solar and the Earth disc visible",
    )
    time_to_earthset_h: float | None = Field(
        default=None,
        description=(
            "From window_start to the first Earthset (the last part of the Earth disc going below the "
            "terrain horizon), h. Null if not computed, or if there is no Earthset in the window "
            "(earthset_in_window false)"
        ),
    )
    earthset_in_window: bool | None = Field(
        default=None,
        description=(
            "True if at least one Earthset occurs in the window, false if none does (time_to_earthset_h is "
            "then null). Null only if not computed"
        ),
    )


class MetricsResponse(Response):
    scenario: Scenario
    scenario_key: str
    power: PowerMetrics
    comms: CommsMetrics
    events: list[Event] = Field(default_factory=list)
    fidelity: FidelityLabel | None = None


class CompareRequest(Model):
    scenarios: list[Scenario] = Field(min_length=1)


class CompareNotServed(Model):
    """A compared scenario this API version has no precomputed result for."""

    index: int = Field(ge=0, description="Position of the scenario in the request's `scenarios`")
    scenario_key: str = Field(description="Scenario.key() of that scenario")
    reason: str = Field(description="Plain-language explanation, suitable to show to visitors")


class CompareResponse(Response):
    """At least one compared scenario is served (otherwise 422 CompareNotServedError)."""

    items: list[MetricsResponse] = Field(
        description=(
            "Metrics for every served scenario, in the request's order (match them to the request by "
            "scenario_key). Scenarios without a result are in not_served instead"
        )
    )
    not_served: list[CompareNotServed] = Field(
        default_factory=list, description="The request's scenarios with no precomputed result, in order"
    )


# ---------------------------------------------------------------------- features


class FeatureType(StrEnum):
    crater = "crater"
    psr = "psr"
    ice_detection = "ice_detection"
    hazard = "hazard"
    landing_site = "landing_site"
    named_feature = "named_feature"


class Feature(Model):
    id: str
    type: FeatureType
    name: str | None = None
    location: Location
    diameter_m: float | None = None
    dataset_id: str
    properties: dict[str, Any] = Field(default_factory=dict)


class FeaturesResponse(Response):
    features: list[Feature]


class ProximityRequest(Model):
    location: Location
    types: list[FeatureType] = Field(min_length=1)
    radius_m: float = Field(gt=0.0)


class FeatureDistance(Model):
    feature: Feature
    distance_m: float = Field(description="Straight-line surface distance, m (not a drive route)")


# The most features a proximity result lists (Kaitlin, 2026-11-15); `total` says how many there are.
PROXIMITY_MAX_RESULTS = 10


class ProximityResponse(Response):
    location: Location
    results: list[FeatureDistance] = Field(
        description=f"Closest first, at most {PROXIMITY_MAX_RESULTS} (PROXIMITY_MAX_RESULTS)"
    )
    total: int | None = Field(
        default=None,
        ge=0,
        description="How many features of the requested types lie within radius_m (results: the closest)",
    )


# ------------------------------------------------------- terrain statistics, site summary (contract 0.7.0)


class TerrainRequest(Model):
    """Body of POST /api/terrain: slope at a point and around it."""

    location: Location
    radius_m: float = Field(gt=0.0, description="Radius of the circle the slope statistics cover, m")


class TerrainResponse(Response):
    location: Location
    radius_m: float
    slope_at_point_deg: float | None = Field(
        default=None, description="Slope at the location, deg (definition: docs/methodology.md)"
    )
    slope_deg: Stat = Field(
        default_factory=Stat, description="Slope over the DEM pixels within radius_m: min, max and mean, deg"
    )
    slope_layer: TerrainLayer | None = Field(
        default=None,
        description="The DEM the slopes were measured on (its resolution sets what they can show)",
    )
    limitations: list[str] = Field(default_factory=list)


class SiteSummaryRequest(Model):
    """Body of POST /api/site_summary: what is known at and around one location."""

    location: Location
    radius_m: float = Field(gt=0.0, description="Radius for the slope statistics and the nearby features, m")
    feature_types: list[FeatureType] = Field(
        default_factory=list, description="Feature types to list; empty = every type"
    )
    scenario: Scenario | None = Field(
        default=None, description="For the metrics part; its location must be this request's location"
    )

    @model_validator(mode="after")
    def _same_location(self) -> SiteSummaryRequest:
        sc = self.scenario
        if sc is not None and (sc.location.lat, sc.location.lon) != (self.location.lat, self.location.lon):
            raise ValueError("scenario.location must be the request's location")
        return self


class SiteSummaryResponse(Response):
    """Each part is null when it was not requested or has no result; limitations say which and why."""

    location: Location
    radius_m: float
    metrics: MetricsResponse | None = None
    terrain: TerrainResponse | None = None
    features: ProximityResponse | None = None
    limitations: list[str] = Field(default_factory=list)


class SitesQuery(Model):
    """Query parameters of GET /api/sites."""

    category: SiteCategory | None = None


class BBox(Model):
    lat_min: Latitude
    lat_max: Latitude
    lon_min: Longitude
    lon_max: Longitude


class FeaturesQuery(Model):
    """Query parameters of GET /api/features (bbox as lat_min,lat_max,lon_min,lon_max)."""

    bbox: BBox | None = None
    types: list[FeatureType] = Field(default_factory=list, description="Empty = every type")


# ------------------------------------------------------------- areas, search, jobs


class PointsArea(Model):
    kind: Literal["points"] = "points"
    points: list[Location] = Field(min_length=1)


class MaskArea(Model):
    """A raster mask defined by a polygon (user-drawn or listed area), sampled at `resolution_m`."""

    kind: Literal["mask"] = "mask"
    polygon: list[Location] = Field(min_length=3)
    resolution_m: float = Field(gt=0.0)
    area_id: str | None = Field(default=None, description="Id of a listed area, if any")


class CircleArea(Model):
    """Everything within radius_m of a centre, at the terrain data's own resolution (contract 0.7.0)."""

    kind: Literal["circle"] = "circle"
    center: Location
    radius_m: float = Field(gt=0.0)


class CapArea(Model):
    """A polar cap: everything within max_colatitude_deg of a pole (e.g. 6 = poleward of 84°)."""

    kind: Literal["cap"] = "cap"
    pole: Literal["south", "north"]
    max_colatitude_deg: float = Field(gt=0.0, le=90.0)


class AllArea(Model):
    """Wherever the terrain data covers (Kaitlin, 2026-11-15); the result states the coverage used."""

    kind: Literal["all"] = "all"


Area = Annotated[PointsArea | MaskArea | CircleArea | CapArea | AllArea, Field(discriminator="kind")]


class SearchCriteria(Model):
    """Terrain-only in v0; time-dependent criteria are added later (plan section 3.3)."""

    max_slope_deg: float | None = Field(
        default=None,
        gt=0.0,
        description="Strict bound: candidates have slope < max_slope_deg (Kaitlin, 2026-11-15)",
    )
    min_flat_area_m2: float | None = Field(default=None, gt=0.0)
    near_feature_types: list[FeatureType] = Field(default_factory=list)
    max_feature_distance_m: float | None = Field(default=None, gt=0.0)


class SearchRequest(Model):
    area: Area
    criteria: SearchCriteria


class SearchCandidate(Model):
    location: Location
    slope_deg: float | None = None
    flat_area_m2: float | None = None
    nearest_feature_m: float | None = None


class SearchResult(Model):
    candidates: list[SearchCandidate]
    fidelity: FidelityLabel | None = None
    slope_layer: TerrainLayer | None = Field(default=None, description="The DEM the slopes were measured on")
    coverage: str | None = Field(
        default=None, description="Where the search ran, in words (required for an AllArea search)"
    )
    limitations: list[str] = Field(default_factory=list)


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Job(Response):
    id: str
    status: JobStatus
    progress: Fraction = 0.0
    created_at: AwareDatetime
    updated_at: AwareDatetime | None = None
    result: SearchResult | None = None
    error: str | None = None


# ---------------------------------------------------------------------- NL (F11)


# Longest NL question accepted (contract 0.8.0): bounds the cost of one request.
NL_MAX_TEXT_CHARS = 1000


class NLRequest(Model):
    text: str = Field(min_length=1, max_length=NL_MAX_TEXT_CHARS)
    selected_site_id: str | None = None
    selected_scenario: Scenario | None = None


class Operation(StrEnum):
    """API operations a structured query can target; `params` = that endpoint's request."""

    sites = "sites"
    locate = "locate"
    horizon = "horizon"
    series = "series"
    metrics = "metrics"
    compare = "compare"
    features = "features"
    proximity = "proximity"
    search = "search"
    terrain = "terrain"
    site_summary = "site_summary"


class StructuredQuery(Model):
    operation: Operation
    params: dict[str, Any] = Field(
        default_factory=dict, description="Request body or query for the operation's endpoint"
    )


class Limitation(Model):
    reason: str
    datasets_considered: list[str] = Field(default_factory=list)


class NLAnswer(Response):
    interpretation: str = Field(description="Echo of how the request was understood")
    structured_query: StructuredQuery
    result: dict[str, Any] | None = Field(
        default=None, description="The operation's response body, as the endpoint returns it"
    )
    limitations: list[Limitation] = Field(
        default_factory=list, description="For partial answers: what was not answered and why"
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Defaults and readings the user didn't state (e.g. a proxy height), shown with the echo",
    )


class NLUnsupported(Response):
    unsupported: Limitation
    interpretation: str | None = Field(default=None, description="Echo of how the request was understood")


class NLClarification(Response):
    """The request can't be answered until the user says more (e.g. which site); nothing was run."""

    interpretation: str = Field(description="Echo of how the request was understood")
    question: str = Field(description="What the user needs to say or select")


NLResponse = NLAnswer | NLUnsupported | NLClarification


# ------------------------------------------------------------------- error bodies
# The API serves precomputed results only (plan section 4.6). These are the bodies of its error responses
# (contract 0.6.0), in FastAPI's `{"detail": ...}` shape. They are not `Response`s: no contract_version or
# placeholder flag.


class ScenarioField(StrEnum):
    """The parts of a scenario that `Scenario.key()` covers (the location name is not one of them)."""

    location = "location"
    unit_height_m = "unit_height_m"
    window_start = "window_start"
    window_end = "window_end"
    step = "step"


class ServedScenario(Model):
    """One scenario this API version has a precomputed result for."""

    scenario: Scenario
    scenario_key: str
    differs_in: list[ScenarioField] = Field(
        description="The parts of the requested scenario that differ from this one"
    )


class NotServedDetail(Model):
    reason: str = Field(description="Plain-language explanation, suitable to show to visitors")
    scenario_key: str = Field(
        description="Scenario.key() of the requested scenario (HorizonRequest.key() for /api/horizon)"
    )
    served: list[ServedScenario] = Field(
        description=(
            "Every scenario this API version serves (for /api/horizon: one per served location and unit "
            "height, and differs_in names only location and unit_height_m)"
        )
    )


class NotServedError(Model):
    """422: a valid request for a scenario (or location and height) with no precomputed result."""

    detail: NotServedDetail


class ValidationIssue(BaseModel):
    """One item of FastAPI's request-validation error list (extra keys such as `input`, `ctx` may appear)."""

    model_config = ConfigDict(extra="allow")

    loc: list[str | int] = Field(description="Where in the request the problem is")
    msg: str
    type: str


class InvalidRequestError(Model):
    """422: FastAPI rejected a malformed request (a client bug, not a scenario without results)."""

    detail: list[ValidationIssue]


class UnavailableDetail(Model):
    reason: str = Field(description="Plain-language explanation, suitable to show to visitors")
    technical: str | None = Field(
        default=None, description="The technical cause, for developers (not meant for visitors)"
    )


class UnavailableError(Model):
    """503: no usable precomputed results are installed on the server."""

    detail: UnavailableDetail


class CompareNotServedDetail(Model):
    reason: str = Field(description="Plain-language explanation, suitable to show to visitors")
    not_served: list[CompareNotServed] = Field(description="Every scenario of the request")


class CompareNotServedError(Model):
    """422 from POST /api/compare: none of the compared scenarios has a precomputed result."""

    detail: CompareNotServedDetail


class NoTerrainDetail(Model):
    reason: str = Field(description="Plain-language explanation, suitable to show to visitors")


class NoTerrainError(Model):
    """422 from POST /api/locate: no terrain data in this version covers the location."""

    detail: NoTerrainDetail


class RateLimitedDetail(Model):
    reason: str = Field(description="Plain-language explanation, suitable to show to visitors")
    retry_after_s: int = Field(ge=1, description="Seconds until this client may ask again")


class RateLimitedError(Model):
    """429 from POST /api/nl: this client asked too many live questions (contract 0.8.0)."""

    detail: RateLimitedDetail


class UnprocessableError(RootModel[NotServedError | InvalidRequestError]):
    """422 from /api/metrics, /api/series, /api/horizon: tell the two apart by `detail` (object vs list)."""


class CompareUnprocessableError(RootModel[CompareNotServedError | InvalidRequestError]):
    """422 from POST /api/compare: tell the two apart by `detail` (an object vs a list)."""


class LocateUnprocessableError(RootModel[NoTerrainError | InvalidRequestError]):
    """422 from POST /api/locate: tell the two apart by `detail` (an object vs a list)."""


# ------------------------------------------------------------- static fallback
# Plan section 4.7 (Kaitlin, 2026-11-15): the served results are also published as static files on the web
# host, for when the API is down. Paths are relative to the directory holding index.json.


class StaticEntry(Model):
    scenario: Scenario
    scenario_key: str
    metrics: str = Field(description="Path of this scenario's MetricsResponse file")
    series: str = Field(description="Path of this scenario's SeriesResponse file")
    horizon: str | None = Field(
        default=None, description="Path of the HorizonProfile for its location and unit height, if served"
    )


class StaticIndex(Response):
    """index.json of the static fallback: every served scenario and where its files are."""

    scenarios: list[StaticEntry]
    sites: str = Field(description="Path of the SitesResponse file")
    datasets: str = Field(description="Path of the DatasetsResponse file")
