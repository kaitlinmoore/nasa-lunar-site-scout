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
    field_validator,
    model_validator,
)

CONTRACT_VERSION = "0.1.0"

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


class HorizonRequest(Model):
    location: Location
    unit_height_m: float = Field(gt=0.0)


class HorizonProfile(Response):
    location: Location
    unit_height_m: float
    azimuth_deg: list[float] = Field(description="Azimuths, deg clockwise from north")
    elevation_deg: list[float] = Field(description="Terrain horizon elevation per azimuth, deg")
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

    azimuth_deg: list[float]
    elevation_deg: list[float]
    visible_fraction: list[Fraction] = Field(description="Visible fraction of the disc, 0..1")
    clearance_deg: list[float] | None = Field(
        default=None, description="Disc centre elevation above the terrain horizon, deg"
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
    """F3. Nullable: null = not computed."""

    illumination_fraction: Fraction | None = Field(
        default=None, description="Time fraction with any part of the solar disc visible"
    )
    mean_visible_disk_fraction: Fraction | None = Field(
        default=None, description="Time-averaged visible fraction of the solar disc"
    )
    sunlit_duration_h: float | None = Field(default=None, description="Total sunlit time, h")
    longest_sunlit_period_h: float | None = None
    longest_shadow_h: float | None = Field(default=None, description="Longest shadow period, h")
    shadow_count: int | None = None
    sun_elevation_deg: Stat = Field(default_factory=Stat)
    sun_azimuth_deg: Stat = Field(default_factory=Stat)
    time_to_sunset_h: float | None = Field(
        default=None, description="From window_start to the first sunset, h"
    )


class CommsMetrics(Model):
    """F4 (direct-to-Earth at the unit height). Nullable: null = not computed."""

    earth_visibility_fraction: Fraction | None = Field(
        default=None, description="Time fraction with any part of the Earth disc visible"
    )
    earth_full_disc_fraction: Fraction | None = None
    longest_earth_gap_h: float | None = None
    earth_elevation_deg: Stat = Field(default_factory=Stat)
    earth_clearance_deg: Stat = Field(
        default_factory=Stat, description="Earth centre above the terrain horizon, deg"
    )
    sun_earth_overlap_fraction: Fraction | None = Field(
        default=None, description="Time fraction with Sun and Earth both visible"
    )
    time_to_earthset_h: float | None = Field(
        default=None, description="From window_start to the first Earthset, h"
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


class CompareResponse(Response):
    items: list[MetricsResponse] = Field(description="Same order as the request's scenarios")


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


class ProximityResponse(Response):
    location: Location
    results: list[FeatureDistance]


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


Area = Annotated[PointsArea | MaskArea, Field(discriminator="kind")]


class SearchCriteria(Model):
    """Terrain-only in v0; time-dependent criteria are added later (plan section 3.3)."""

    max_slope_deg: float | None = Field(default=None, gt=0.0)
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


class NLRequest(Model):
    text: str = Field(min_length=1)
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


class NLUnsupported(Response):
    unsupported: Limitation


NLResponse = NLAnswer | NLUnsupported
