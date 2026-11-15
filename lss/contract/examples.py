"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Example responses for `fixtures/` (contract v0).

Every example except health, the dataset registry and the site list is PLACEHOLDER data: synthetic curves and
round numbers, flagged with `_placeholder: true` and a `_note`. They exist so the web
and NL streams can build against the contract before the engine produces real results.
They are NOT computed results and must never be presented as such.

Scope (C1 thin slice, handoff 03): one PGDA site (Site01, Connecting ridge), one unit
height (1 m, chosen by Kaitlin to match Barker et al. 2021), one window (30 days from
2028-05-15 UTC, covering one full 29.53-day synodic month; chosen by Kaitlin so the window has
shadow periods: from mid-July to mid-January every 30-day window is fully sunlit at RoI 4).

The served Site01 point is the centroid of region of interest (RoI) 4 of Barker et al. (2021, Table 2),
a real published location, so `sites.json` is not a placeholder. It replaces the Mazarico et al. (2011)
Site01 coordinate (89.45 S, 222.69 E), which was picked on a 240 m map and lies on an 8.6 deg slope on
the 5 m map (docs/methodology.md section 1.3).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from lss.contract.models import (
    BodyTrack,
    CommsMetrics,
    CompareResponse,
    DatasetsResponse,
    Event,
    EventKind,
    Feature,
    FeatureDistance,
    FeaturesResponse,
    FeatureType,
    FidelityLabel,
    FidelityTier,
    HealthResponse,
    HorizonProfile,
    Job,
    JobStatus,
    Limitation,
    LocateResponse,
    Location,
    MetricsResponse,
    NLAnswer,
    NLUnsupported,
    Operation,
    PowerMetrics,
    ProximityResponse,
    Response,
    Scenario,
    SearchCandidate,
    SearchResult,
    SeriesResponse,
    Site,
    SiteCategory,
    SitesResponse,
    Stat,
    StructuredQuery,
    TerrainLayer,
)

PLACEHOLDER_NOTE = (
    "PLACEHOLDER: synthetic example values for contract v0, not computed results. "
    "Do not use for any analysis or display them as real."
)
SITE01_NAME = "Site01 Connecting ridge (Barker 2021 RoI 4)"
SITE01_SOURCE = (
    "Barker, M. K., et al. (2021), Planet. Space Sci. 203, 105119, doi:10.1016/j.pss.2020.105119, Table 2: "
    "centroid of Site01 region of interest 4, polar stereographic x = -11.2875 km, y = -12.1675 km "
    "(89.452675 S, 222.851347 E), in the PGDA product 78 Site01 DEM tile. Site01 (Connecting ridge) is "
    "site 1 of Mazarico, E., et al. (2011), Icarus 211, 1066-1081, doi:10.1016/j.icarus.2010.10.030."
)

# Barker et al. (2021) Table 2, RoI 4 centroid (PS -11287.5, -12167.5 m), converted on the 1737.4 km sphere.
SITE01 = Location(lat=-89.452675, lon=-137.148653, name=SITE01_NAME)
# The C1 thin-slice scenario. Exactly this scenario is precomputed and served by the deployed endpoint, which
# matches requests on SCENARIO.key() (location without name, height, window and step). Window: Kaitlin,
# 2026-11-15 (was 2028-11-15, which is fully sunlit at RoI 4). Step: 1 h, the plan's default sampling
# (plan section 4.2; events are refined between samples).
WINDOW_START = datetime(2028, 5, 15, tzinfo=UTC)
WINDOW_END = WINDOW_START + timedelta(days=30)
STEP = timedelta(hours=1)
SCENARIO = Scenario(
    location=SITE01,
    unit_height_m=1.0,
    window_start=WINDOW_START,
    window_end=WINDOW_END,
    step=STEP,
)
STACK = [
    TerrainLayer(dataset_id="pgda_78_site_dems", role="near_field", resolution_m=5, max_range_km=10),
    TerrainLayer(dataset_id="pgda_90_south_pole_dems", role="far_field", resolution_m=20, max_range_km=300),
]
FIDELITY = FidelityLabel(
    tier=FidelityTier.high,
    summary="5 m PGDA site DEM near field, 20 m polar DEM far field",
    near_field_resolution_m=5,
    far_field_resolution_m=20,
)
MARK = {"_placeholder": True, "_note": PLACEHOLDER_NOTE}


def _round(xs: list[float], nd: int = 3) -> list[float]:
    return [round(x, nd) for x in xs]


def health() -> HealthResponse:
    return HealthResponse()


def sites() -> SitesResponse:
    site = Site(
        id="pgda-site01",
        name=SITE01_NAME,
        category=SiteCategory.pgda,
        location=SITE01,
        description=(
            "PGDA south-pole site 01 (Connecting ridge; Mazarico et al. 2011 numbering), at the centroid of "
            "Barker et al. (2021) region of interest 4."
        ),
        dataset_ids=["pgda_78_site_dems", "pgda_81_mosaic_5m", "pgda_90_south_pole_dems"],
        has_dem_clones=True,
        source=SITE01_SOURCE,
    )
    return SitesResponse(sites=[site], _note="Curated site list (C1: Site01 only).")


def datasets() -> DatasetsResponse:
    from lss.registry.loader import load_datasets

    return DatasetsResponse(
        datasets=list(load_datasets()),
        _note="Generated from lss/registry/datasets.yaml (real registry content).",
    )


def locate() -> LocateResponse:
    return LocateResponse(location=SITE01, terrain_stack=STACK, fidelity=FIDELITY, **MARK)


def horizon() -> HorizonProfile:
    az = [i * 1.0 for i in range(360)]  # placeholder 1 deg; the engine will be finer
    el = [0.8 + 0.6 * math.sin(math.radians(2 * a)) + 0.3 * math.cos(math.radians(5 * a)) for a in az]
    return HorizonProfile(
        location=SITE01,
        unit_height_m=SCENARIO.unit_height_m,
        azimuth_deg=az,
        elevation_deg=_round(el),
        max_range_km=300,
        terrain_stack=STACK,
        fidelity=FIDELITY,
        **MARK,
    )


def _times() -> list[datetime]:
    n = int((WINDOW_END - WINDOW_START) / STEP) + 1
    return [WINDOW_START + i * STEP for i in range(n)]


def series() -> SeriesResponse:
    times = _times()
    hours = [(t - WINDOW_START).total_seconds() / 3600 for t in times]
    synodic_h = 29.53 * 24
    sun_az = [(h / synodic_h * 360.0) % 360.0 for h in hours]
    sun_el = [0.4 + 1.2 * math.sin(2 * math.pi * h / (14 * 24)) for h in hours]
    sun_vis = [min(1.0, max(0.0, (e - 0.2) / 0.5)) for e in sun_el]
    earth_az = [(135.0 + 6.0 * math.sin(2 * math.pi * h / (27.3 * 24))) % 360.0 for h in hours]
    earth_el = [1.5 + 6.5 * math.sin(2 * math.pi * h / (27.3 * 24)) for h in hours]
    earth_clear = [e - 0.8 for e in earth_el]
    earth_vis = [min(1.0, max(0.0, (c + 1.0) / 2.0)) for c in earth_clear]
    return SeriesResponse(
        scenario=SCENARIO,
        scenario_key=SCENARIO.key(),
        time=times,
        sun=BodyTrack(
            azimuth_deg=_round(sun_az),
            elevation_deg=_round(sun_el),
            visible_fraction=_round(sun_vis),
        ),
        earth=BodyTrack(
            azimuth_deg=_round(earth_az),
            elevation_deg=_round(earth_el),
            visible_fraction=_round(earth_vis),
            clearance_deg=_round(earth_clear),
        ),
        events=_events(),
        **MARK,
    )


def _events() -> list[Event]:
    return [
        Event(kind=EventKind.sunset, time=WINDOW_START + timedelta(days=8, hours=6)),
        Event(kind=EventKind.sunrise, time=WINDOW_START + timedelta(days=13, hours=18)),
        Event(kind=EventKind.earthset, time=WINDOW_START + timedelta(days=13, hours=12)),
    ]


def metrics() -> MetricsResponse:
    return MetricsResponse(
        scenario=SCENARIO,
        scenario_key=SCENARIO.key(),
        power=PowerMetrics(
            illumination_fraction=0.5,
            mean_visible_disk_fraction=0.4,
            sunlit_duration_h=168.0,
            longest_sunlit_period_h=150.0,
            longest_shadow_h=100.0,
            longest_shadow_clipped=False,
            shadow_count=2,
            sun_elevation_deg=Stat(min=-0.8, max=1.6, mean=0.4),
            sun_azimuth_deg=Stat(min=0.0, max=360.0, mean=None),
            time_to_sunset_h=198.0,
        ),
        comms=CommsMetrics(
            earth_visibility_fraction=0.6,
            earth_full_disc_fraction=0.5,
            longest_earth_gap_h=120.0,
            longest_earth_gap_clipped=False,
            earth_elevation_deg=Stat(min=-5.0, max=8.0, mean=1.5),
            earth_clearance_deg=Stat(min=-5.8, max=7.2, mean=0.7),
            sun_earth_overlap_fraction=0.3,
            time_to_earthset_h=324.0,
        ),
        events=_events(),
        fidelity=FIDELITY,
        **MARK,
    )


def compare() -> CompareResponse:
    return CompareResponse(items=[metrics()], **MARK)


def _crater() -> Feature:
    return Feature(
        id="placeholder-crater-1",
        type=FeatureType.crater,
        name="Placeholder crater",
        location=Location(lat=-89.40, lon=-140.0),
        diameter_m=2500,
        dataset_id="robbins_craters",
    )


def features() -> FeaturesResponse:
    return FeaturesResponse(features=[_crater()], **MARK)


def proximity() -> ProximityResponse:
    return ProximityResponse(
        location=SITE01, results=[FeatureDistance(feature=_crater(), distance_m=2100.0)], **MARK
    )


def job() -> Job:
    return Job(
        id="placeholder-job-1",
        status=JobStatus.succeeded,
        progress=1.0,
        created_at=WINDOW_START,
        updated_at=WINDOW_START + timedelta(seconds=30),
        result=SearchResult(
            candidates=[
                SearchCandidate(
                    location=Location(lat=-89.46, lon=-137.0),
                    slope_deg=3.0,
                    flat_area_m2=400.0,
                    nearest_feature_m=1800.0,
                )
            ],
            fidelity=FIDELITY,
            limitations=["~90% of 5 m mosaic pixels are interpolated; flat-area results are low confidence."],
        ),
        **MARK,
    )


def nl_answer() -> NLAnswer:
    return NLAnswer(
        interpretation=(
            f"Power and Earth-visibility metrics for {SITE01_NAME} at 1 m height, "
            f"{WINDOW_START:%Y-%m-%d} to {WINDOW_END:%Y-%m-%d} UTC."
        ),
        structured_query=StructuredQuery(
            operation=Operation.metrics,
            params={"scenario": SCENARIO.model_dump(mode="json")},
        ),
        result=metrics().model_dump(mode="json", by_alias=True),
        **MARK,
    )


def nl_unsupported() -> NLUnsupported:
    return NLUnsupported(
        unsupported=Limitation(
            reason=(
                "Boulders >0.5 m are below the resolution of every available dataset, and no "
                "boulder map covers the south pole."
            ),
            datasets_considered=["pgda_81_mosaic_5m", "aussel_2025_boulders"],
        ),
        **MARK,
    )


# file name in fixtures/ -> (builder, model class used to validate it)
EXAMPLES: dict[str, tuple] = {
    "health.json": (health, HealthResponse),
    "sites.json": (sites, SitesResponse),
    "datasets.json": (datasets, DatasetsResponse),
    "locate.json": (locate, LocateResponse),
    "horizon.json": (horizon, HorizonProfile),
    "series.json": (series, SeriesResponse),
    "metrics.json": (metrics, MetricsResponse),
    "compare.json": (compare, CompareResponse),
    "features.json": (features, FeaturesResponse),
    "proximity.json": (proximity, ProximityResponse),
    "job.json": (job, Job),
    "nl_answer.json": (nl_answer, NLAnswer),
    "nl_unsupported.json": (nl_unsupported, NLUnsupported),
}


def dump(model: Response) -> dict:
    return model.model_dump(mode="json", by_alias=True)
