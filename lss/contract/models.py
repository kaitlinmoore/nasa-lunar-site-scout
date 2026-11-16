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

CONTRACT_VERSION = "0.14.0"

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
    name: str = Field(description="Full technical name, e.g. 'Site01 Connecting ridge (Barker 2021 RoI 4)'")
    short_name: str | None = Field(
        default=None,
        description="Short display name in title case, e.g. 'Connecting Ridge' (contract 0.9.0; Kaitlin, "
        "2026-11-16). Null: show name",
    )
    regions: list[str] = Field(
        default_factory=list,
        description="Region tags, e.g. 'shackleton' (contract 0.10.0; stream A's registry, Kaitlin approves)",
    )
    subtitle: str | None = Field(
        default=None, description="Small line under the display name, e.g. 'PGDA Site01 · Barker 2021 RoI 4'"
    )
    category: SiteCategory
    location: Location
    description: str | None = None
    dataset_ids: list[str] = Field(default_factory=list, description="Registry ids of DEMs etc.")
    has_dem_clones: bool = False
    source: str | None = Field(default=None, description="Citation or URL for the coordinates")


def display_name(site: Site) -> str:
    """What to call a site in text meant for people: its short name, else its full name."""
    return site.short_name or site.name


class ScenariosQuery(Model):
    """Query parameters of GET /api/scenarios (contract 0.11.0)."""

    site_id: str | None = Field(default=None, description="Only this curated site's scenarios")


class ScenarioEntry(Model):
    """One precomputed scenario, with the curated site it belongs to (matched on its exact location)."""

    site_id: str | None = Field(description="The curated site at this scenario's location; null if none")
    scenario_key: str
    scenario: Scenario
    has_horizon: bool = Field(description="POST /api/horizon has this location and unit height")


class ScenariosResponse(Response):
    """Every precomputed scenario this API version serves (stream B's site page picker, Kaitlin's option b):
    by site in the site list's order, then by unit height, window start, window end, step."""

    scenarios: list[ScenarioEntry]


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
    """Layers of the 2D site view's terrain images (GET /api/terrain/view/{site_id}/{view}/{layer}.png).
    Only hillshade and slope are precomputed (Kaitlin, 2026-11-16); elevation is reserved."""

    hillshade = "hillshade"
    slope = "slope"
    elevation = "elevation"


# ---- terrain images for the 2D site view (contract 0.13.0; A's cache/terrain_view/, methodology 5.7) ----


class TerrainViewSource(Model):
    dataset_id: str = Field(description="Registry id of the map the images were made from")
    url: str
    source_pixel_m: float | None = Field(default=None, description="The source map's pixel size, m")
    block_mean: int | None = Field(
        default=None, description="Source pixels averaged per image pixel, per axis"
    )


class TerrainViewHillshade(Model):
    light_azimuth_map_deg: float = Field(description="Light direction, deg clockwise from map up (grid +y)")
    light_altitude_deg: float
    note: str | None = None


class TerrainViewSlope(Model):
    definition: str
    class_edges_deg: list[float] = Field(
        description="Upper edges of the classes; the last class is open-ended"
    )
    class_labels: list[str] = Field(description="One label per class value 0..n (PNG pixel value = class)")
    nodata: int = Field(description="PNG pixel value with no slope (show transparent)")
    palette_light: list[str] = Field(description="Suggested colour per class, light theme (stream A)")
    palette_dark: list[str] = Field(description="Suggested colour per class, dark theme (stream A)")


class TerrainView(Model):
    """One precomputed square view around a site. The images are 8-bit greyscale PNGs (hillshade: shade;
    slope: class number) with no colour-profile chunks, so canvas reads the values exactly. The image's top
    edge is the polar stereographic grid's +y (`map_up`), not geographic north."""

    site_id: str
    view: str = Field(description="View name, e.g. '2km' (±1 km) or '20km' (±10 km)")
    center: Location = Field(
        description="The site's served point; the bounds snap to the pixel grid (≤ 1 px)"
    )
    bounds_ps_m: list[float] = Field(
        min_length=4, max_length=4, description="[left, bottom, right, top] in the projection below, m"
    )
    proj4: str = Field(
        description="The images' projection (south polar stereographic on the 1737.4 km sphere)"
    )
    map_up: str
    pixel_m: float
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    layers: list[TerrainViewLayer] = Field(
        description="Images available: GET /api/terrain/view/{site_id}/{view}/{layer}.png (static copy: "
        "terrain_view/{site_id}/{view}/{layer}.png)"
    )
    source: TerrainViewSource
    hillshade: TerrainViewHillshade | None = None
    slope: TerrainViewSlope | None = None


class TerrainViewsQuery(Model):
    """Query parameters of GET /api/terrain/views."""

    site_id: str | None = Field(default=None, description="Only this site's views")


class TerrainViewsResponse(Response):
    """Precomputed terrain views, by site in the site list's order, then by view size (smallest first).
    Sites without views (e.g. off the polar maps) are simply absent."""

    views: list[TerrainView]


class NotFoundDetail(Model):
    reason: str = Field(description="Plain-language explanation, suitable to show to visitors")


class NotFoundError(Model):
    """404 from GET /api/terrain/view/...: no such precomputed image."""

    detail: NotFoundDetail


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


# ---- filter and rank on compare (contract 0.10.0, NL gap C3; Kaitlin's decisions 2026-11-16) ----


class MetricName(StrEnum):
    """A numeric value a compare filter or rank can use: a dotted path into MetricsResponse, or the slope
    at the scenario's location (terrain.*, from the precomputed slope statistics on the finest map)."""

    illumination_fraction = "power.illumination_fraction"
    mean_visible_disk_fraction = "power.mean_visible_disk_fraction"
    sunlit_duration_h = "power.sunlit_duration_h"
    longest_sunlit_period_h = "power.longest_sunlit_period_h"
    longest_shadow_h = "power.longest_shadow_h"
    shadow_count = "power.shadow_count"
    time_to_sunset_h = "power.time_to_sunset_h"
    sun_elevation_min_deg = "power.sun_elevation_deg.min"
    sun_elevation_max_deg = "power.sun_elevation_deg.max"
    sun_elevation_mean_deg = "power.sun_elevation_deg.mean"
    earth_visibility_fraction = "comms.earth_visibility_fraction"
    earth_full_disc_fraction = "comms.earth_full_disc_fraction"
    longest_earth_gap_h = "comms.longest_earth_gap_h"
    earth_elevation_min_deg = "comms.earth_elevation_deg.min"
    earth_elevation_max_deg = "comms.earth_elevation_deg.max"
    earth_elevation_mean_deg = "comms.earth_elevation_deg.mean"
    earth_clearance_min_deg = "comms.earth_clearance_deg.min"
    earth_clearance_max_deg = "comms.earth_clearance_deg.max"
    earth_clearance_mean_deg = "comms.earth_clearance_deg.mean"
    sun_earth_overlap_fraction = "comms.sun_earth_overlap_fraction"
    time_to_earthset_h = "comms.time_to_earthset_h"
    slope_at_point_deg = "terrain.slope_at_point_deg"


class SunElevationBand(Model):
    """Fraction of the window with the Sun's disc-centre apparent elevation in [min_deg, max_deg] (k7). The
    elevation is above the local horizontal plane at the site, whether or not terrain hides the Sun (the
    terrain horizon is not applied), as for PowerMetrics.sun_elevation_deg. From stream A's Sun-elevation
    histogram in the served files (methodology 5.3); null (not computed) where a result has none."""

    kind: Literal["sun_elevation_band_fraction"] = "sun_elevation_band_fraction"
    min_deg: float = Field(ge=-90.0, le=90.0)
    max_deg: float = Field(ge=-90.0, le=90.0)

    @model_validator(mode="after")
    def _ordered(self) -> SunElevationBand:
        if self.max_deg <= self.min_deg:
            raise ValueError("max_deg must be above min_deg")
        return self

    def label(self) -> str:
        return f"sun_elevation_band_fraction[{self.min_deg:g},{self.max_deg:g}]"


CompareMetric = MetricName | SunElevationBand


class FilterOp(StrEnum):
    lt = "lt"
    le = "le"
    gt = "gt"
    ge = "ge"
    eq = "eq"


class MetricFilter(Model):
    """Keep a scenario only if `metric op value` holds. A null value never passes (it is listed as not
    computed)."""

    metric: CompareMetric
    op: FilterOp
    value: float


class RankOrder(StrEnum):
    desc = "desc"
    asc = "asc"


class CompareRank(Model):
    """Order the passing scenarios by `metric`; equal values keep their request order and are reported in
    `CompareResponse.rank_ties`. Null values are excluded and listed as not computed."""

    metric: CompareMetric
    order: RankOrder = RankOrder.desc
    limit: int | None = Field(default=None, ge=1, description="Keep the first `limit`; the rest are counted")


class CompareAcross(Model):
    """One scenario per curated site, expanded by the API (Kaitlin's C8 choice): the sites named, the sites
    tagged with `region`, or every curated site if neither is given."""

    site_ids: list[str] = Field(default_factory=list)
    region: str | None = Field(default=None, description="A Site.regions tag, e.g. 'shackleton'")
    unit_height_m: float = Field(gt=0.0)
    window_start: AwareDatetime
    window_end: AwareDatetime | None = None
    window_days: int | None = Field(
        default=None,
        ge=1,
        description="Instead of window_end: the window's length in days (computed by code)",
    )
    step: timedelta = Field(default=timedelta(hours=1), description="Sampling step (ISO 8601)")

    @model_validator(mode="after")
    def _one_of(self) -> CompareAcross:
        if self.site_ids and self.region:
            raise ValueError("give site_ids or region, not both")
        if (self.window_end is None) == (self.window_days is None):
            raise ValueError("give exactly one of window_end and window_days")
        return self


class CompareRequest(Model):
    """Scenarios to compare: `scenarios`, plus one per site of `across` (in that order). Optional filters and
    a rank are applied by the API to the served results, never by the LLM (contract 0.10.0)."""

    scenarios: list[Scenario] = Field(default_factory=list)
    across: CompareAcross | None = None
    filters: list[MetricFilter] = Field(default_factory=list)
    rank: CompareRank | None = None

    @model_validator(mode="after")
    def _something(self) -> CompareRequest:
        if not self.scenarios and self.across is None:
            raise ValueError("give scenarios, across, or both")
        return self


class EvaluatedValue(Model):
    scenario_key: str
    metric: str = Field(description="MetricName value, or SunElevationBand.label()")
    value: float | None = Field(description="Null: not computed")
    source: str | None = Field(
        default=None, description="Where a terrain value was measured, e.g. '5 m PGDA site map'"
    )


class CompareFilteredOut(Model):
    index: int = Field(ge=0, description="Position in the compared scenarios (see CompareResponse.compared)")
    scenario_key: str
    failed: list[str] = Field(default_factory=list, description="Metrics whose filter it did not pass")
    not_computed: list[str] = Field(default_factory=list, description="Metrics with no value for it")


class CompareNotServed(Model):
    """A compared scenario this API version has no precomputed result for."""

    index: int = Field(ge=0, description="Position in the compared scenarios (see CompareResponse.compared)")
    scenario_key: str = Field(description="Scenario.key() of that scenario")
    reason: str = Field(description="Plain-language explanation, suitable to show to visitors")


class CompareResponse(Response):
    """At least one compared scenario is served (otherwise 422 CompareNotServedError). Every served scenario
    may still fail the filters: then `items` is empty, which is an answer ("none qualifies"), not an error."""

    items: list[MetricsResponse] = Field(
        description=(
            "Metrics for every served scenario that passes the filters: in rank order if a rank was given, "
            "else in the compared order (match them by scenario_key). Scenarios without a result are in "
            "not_served; those removed by a filter are in filtered_out"
        )
    )
    not_served: list[CompareNotServed] = Field(
        default_factory=list, description="The request's scenarios with no precomputed result, in order"
    )
    compared: list[Scenario] = Field(
        default_factory=list,
        description="Every compared scenario in order: the request's scenarios, then one per `across` site "
        "(contract 0.10.0; always filled). Indexes in not_served and filtered_out refer to this list; items "
        "are matched to it by scenario_key",
    )
    evaluated: list[EvaluatedValue] = Field(
        default_factory=list, description="Every value a filter or the rank used, per served scenario"
    )
    filtered_out: list[CompareFilteredOut] = Field(
        default_factory=list, description="Served scenarios removed by a filter, or with no value to rank by"
    )
    rank_ties: list[list[str]] = Field(
        default_factory=list, description="Groups of scenario_keys with equal rank values, in rank order"
    )
    beyond_limit: int = Field(default=0, ge=0, description="Passing scenarios cut by rank.limit")
    compared_keys: list[str] = Field(
        default_factory=list,
        description="Scenario.key() of each entry of `compared`, same order (contract 0.13.0; stream B)",
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

    def key(self) -> str:
        """Stable hash of location (name excluded) and radius, for precomputed statistics."""
        payload = self.model_dump(mode="json", exclude={"location": {"name"}})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


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


# ---- IAU feature names for globe labels (contract 0.14.0; stream E's cache/features/iau_names.json) ----

FEATURE_LABEL_FIELDS = ("id", "name", "type", "lat", "lon", "diameter_km")
SATELLITE_TYPE = "SF"  # IAU "Satellite Feature": lettered craters such as "Marco Polo P"


class FeatureLabelsQuery(Model):
    """Query parameters of GET /api/features/labels. Every filter is optional; with none, every name except
    satellite features is returned."""

    types: list[str] = Field(
        default_factory=list, description="IAU type codes, e.g. AA (crater); empty = all"
    )
    min_diameter_km: float | None = Field(
        default=None, ge=0.0, description="Only features at least this wide"
    )
    include_satellite: bool = Field(
        default=False, description="Include satellite features (type SF; also included when `types` names SF)"
    )
    bbox: BBox | None = Field(
        default=None, description="Only centres inside; lon_min > lon_max means the box crosses ±180°"
    )
    limit: int | None = Field(default=None, ge=1, description="The largest N after the other filters")


class FeatureLabelsResponse(Response):
    """IAU-adopted names of lunar features, for labels only (positions identify features; about 300 m).
    Compact rows, largest first: [id, name, type, lat, lon, diameter_km] (`fields`). Coordinates are
    planetocentric, east longitude -180..180, mean Earth/polar axis (LOLA frame), as elsewhere in this API."""

    dataset_id: str = Field(description="Registry entry, e.g. iau_gazetteer_moon (citation, licence)")
    fields: list[str] = Field(description="Column names of each row: id, name, type, lat, lon, diameter_km")
    types: dict[str, str] = Field(description="IAU type code -> description, e.g. AA -> 'Crater, craters'")
    total: int = Field(ge=0, description="Names in the source before filtering")
    rows: list[tuple[int, str, str, float, float, float]] = Field(
        description="One feature per row, largest diameter first (ties by name)"
    )


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


class TerrainOption(Model):
    """One location and radius with precomputed slope statistics (contract 0.9.0)."""

    location: Location
    radius_m: float


class TerrainNotServedDetail(Model):
    reason: str = Field(description="Plain-language explanation, suitable to show to visitors")
    terrain_key: str = Field(description="TerrainRequest.key() of the request")
    served: list[TerrainOption] = Field(description="Every location and radius with precomputed statistics")


class TerrainNotServedError(Model):
    """422 from POST /api/terrain: no precomputed slope statistics for this location and radius."""

    detail: TerrainNotServedDetail


class TerrainUnprocessableError(RootModel[TerrainNotServedError | InvalidRequestError]):
    """422 from POST /api/terrain: tell the two apart by `detail` (an object vs a list)."""


# ------------------------------------------------------------- static fallback
# Plan section 4.7 (Kaitlin, 2026-11-15): the served results are also published as static files on the web
# host, for when the API is down. Paths are relative to the directory holding index.json.


class StaticEntry(Model):
    scenario: Scenario
    scenario_key: str
    site_id: str | None = Field(default=None, description="The curated site at this location (0.11.0)")
    metrics: str = Field(description="Path of this scenario's MetricsResponse file")
    series: str = Field(description="Path of this scenario's SeriesResponse file")
    horizon: str | None = Field(
        default=None, description="Path of the HorizonProfile for its location and unit height, if served"
    )


class StaticTerrainEntry(Model):
    location: Location
    radius_m: float
    terrain_key: str = Field(description="TerrainRequest.key() of this location and radius")
    path: str = Field(description="Path of the TerrainResponse file")


class StaticNLEntry(Model):
    """A cached showcase answer (C8): the request it answers and the path of its NL response file."""

    request: NLRequest
    path: str = Field(description="Path of the NLAnswer / NLUnsupported / NLClarification file")


class StaticIndex(Response):
    """index.json of the static fallback: every served scenario and where its files are."""

    scenarios: list[StaticEntry]
    terrain: list[StaticTerrainEntry] = Field(
        default_factory=list, description="Precomputed slope statistics (contract 0.9.0)"
    )
    sites: str = Field(description="Path of the SitesResponse file")
    feature_labels: str | None = Field(
        default=None,
        description="Path of a FeatureLabelsResponse with every name, satellite features included (0.14.0); "
        "filter it in the client",
    )
    terrain_views: str | None = Field(
        default=None,
        description="Path of the TerrainViewsResponse file; images at "
        "terrain_view/{site_id}/{view}/{layer}.png (0.13.0)",
    )
    nl_answers: list[StaticNLEntry] = Field(
        default_factory=list, description="Cached showcase answers, the same as POST /api/nl returns (0.12.0)"
    )
    scenario_list: str | None = Field(
        default=None,
        description="Path of the ScenariosResponse file, what GET /api/scenarios returns (0.11.0)",
    )
    datasets: str = Field(description="Path of the DatasetsResponse file")
