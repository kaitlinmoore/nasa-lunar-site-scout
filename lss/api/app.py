"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

FastAPI app, API v0. Results are precomputed only (lss.api.served):
nothing is computed live, so the API needs no DEMs, kernels or numba.

- `GET /api/health`; `GET /api/sites` (the curated site registry, lss/registry/sites.yaml);
  `GET /api/scenarios` (every precomputed scenario, by site);
  `GET /api/datasets` (the capability registry).
- `POST /api/locate`: the terrain stack and fidelity label from the registry's resolver, which uses static
  layer extents only (no DEM reads).
- `POST /api/metrics`, `/api/series`: the precomputed result for a scenario, matched on `Scenario.key()`.
- `POST /api/horizon`: the precomputed horizon profile for a location and unit height.
- `POST /api/compare`: metrics for every served scenario of the request; the rest are listed as not served.
- `POST /api/terrain`: precomputed slope statistics for a location and radius (cache/terrain/).
- `POST /api/site_summary`: slope statistics, metrics for a served scenario, and (later) nearby features.
- `GET /api/terrain/views`, `GET /api/terrain/view/{site_id}/{view}/{layer}.png`: precomputed terrain
  images for the 2D site view (cache/terrain_view/; contract 0.13.0).
- `GET /api/features/labels`: IAU feature names for the globe labels, filtered (cache/features/;
  contract 0.14.0).

A valid request with no precomputed result gets a 422 with a plain-language reason and what is served; no
usable results installed gets a 503 (contract error models in lss.contract).

Run locally:  uv run uvicorn lss.api.app:app --reload
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse

from lss.api import compare as compare_rules
from lss.api import nl as nl_service
from lss.api.feature_labels import FeatureLabelsError, Labels, load_labels, select
from lss.api.served import (
    Served,
    ServedFileError,
    ServedTerrain,
    band_fraction,
    differences,
    horizon_key,
    horizons,
    load_all,
    load_terrain,
    served_dir,
    terrain_dir,
    terrain_key,
)
from lss.api.terrain_views import ServedView, TerrainViewError, load_views
from lss.config import get_settings
from lss.contract import (
    CONTRACT_VERSION,
    BBox,
    CompareNotServed,
    CompareNotServedDetail,
    CompareRequest,
    CompareResponse,
    CompareUnprocessableError,
    DatasetsResponse,
    FeatureLabelsQuery,
    FeatureLabelsResponse,
    HealthResponse,
    HorizonProfile,
    HorizonRequest,
    InvalidRequestError,
    LocateRequest,
    LocateResponse,
    LocateUnprocessableError,
    MetricsResponse,
    NLAnswer,
    NLClarification,
    NLRequest,
    NLUnsupported,
    NoTerrainDetail,
    NotFoundDetail,
    NotFoundError,
    NotServedDetail,
    Operation,
    RateLimitedError,
    Scenario,
    ScenarioEntry,
    ScenarioRequest,
    ScenariosQuery,
    ScenariosResponse,
    SeriesResponse,
    ServedScenario,
    SiteCategory,
    SitesQuery,
    SitesResponse,
    SiteSummaryRequest,
    SiteSummaryResponse,
    TerrainNotServedDetail,
    TerrainOption,
    TerrainRequest,
    TerrainResponse,
    TerrainUnprocessableError,
    TerrainViewLayer,
    TerrainViewsQuery,
    TerrainViewsResponse,
    UnavailableDetail,
    UnavailableError,
    UnprocessableError,
)

# Visitor-facing wording. NOT_SERVED_REASON and UNAVAILABLE_REASON: the project author, 2026-11-15.
# HORIZON_NOT_SERVED_REASON and NO_TERRAIN_REASON: Claude-drafted, approved by the project author 2026-11-15.
# COMPARE_NOT_SERVED_REASON: Claude-drafted, approved by the project author 2026-11-16. A compare answer lists
# no served scenarios (2026-11-16), so its reason must not refer to a list.
# A 503's technical cause goes in `detail.technical`, never in the reason.
NOT_SERVED_REASON = (
    "This version has precomputed results only for the scenarios listed with this message. A request must "
    "match one of them exactly: the same location, unit height, time window and time step."
)
HORIZON_NOT_SERVED_REASON = (
    "This version has precomputed horizon profiles only for the locations and unit heights listed with this "
    "message. A request must match one of them exactly: the same location and unit height."
)
COMPARE_NOT_SERVED_REASON = (
    "This version has no precomputed result for this scenario. Results exist only for precomputed "
    "scenarios, matched exactly on location, unit height, time window and time step."
)
NO_TERRAIN_REASON = "No terrain data in this version covers this location."
# TERRAIN_NOT_SERVED_REASON (with the list): the project author's wording, 2026-11-16.
# SUMMARY_NO_TERRAIN_REASON (inside a site summary, no list): Claude-drafted, approved by the project author
# 2026-11-16.
TERRAIN_NOT_SERVED_REASON = "Slope statistics are available only for the locations and radii listed here."
# Inside an NL answer nothing is listed, so the reasons that refer to a list are replaced by list-free ones
# (2026-11-16; as for the comparison). HORIZON_NO_LIST_REASON: Claude-drafted, approved.
HORIZON_NO_LIST_REASON = "This version has no precomputed horizon profile for this location and unit height."
SUMMARY_NO_TERRAIN_REASON = "This version has no precomputed slope statistics for this location and radius."
UNAVAILABLE_REASON = (
    "Results are temporarily unavailable: the server has no usable precomputed results installed."
)


@lru_cache(maxsize=1)
def _sites() -> SitesResponse:
    """The curated site registry; fixtures/sites.json is generated from the same function."""
    from lss.contract.examples import sites

    return sites()


@lru_cache(maxsize=1)
def _datasets() -> DatasetsResponse:
    from lss.registry.loader import load_datasets

    return DatasetsResponse(datasets=list(load_datasets()))


@lru_cache(maxsize=1)
def _served() -> dict[str, Served]:
    return load_all()


@lru_cache(maxsize=1)
def _terrain() -> dict[str, ServedTerrain]:
    return load_terrain()


def terrain_results() -> dict[str, ServedTerrain]:
    """Every installed slope statistic, or a 503 saying why there are none."""
    try:
        found = _terrain()
    except ServedFileError as e:
        raise unavailable(f"precomputed slope statistics are unusable: {e}") from e
    if not found:
        raise unavailable(f"no precomputed slope statistics are installed ({terrain_dir()})")
    return found


def terrain_for(req: TerrainRequest) -> TerrainResponse:
    """Precomputed slope statistics for exactly this location and radius, or an HTTP error saying why not."""
    found = terrain_results()
    key = terrain_key(req.location.lat, req.location.lon, req.radius_m)
    if key in found:
        return found[key].body
    detail = TerrainNotServedDetail(
        reason=TERRAIN_NOT_SERVED_REASON,
        terrain_key=key,
        served=[TerrainOption(location=t.body.location, radius_m=t.body.radius_m) for t in found.values()],
    )
    raise HTTPException(422, detail=detail.model_dump(mode="json"))


# Claude-drafted, approved by the project author (2026-11-16).
NO_TERRAIN_IMAGE_REASON = "This version has no precomputed terrain image for this site, view and layer."


@lru_cache(maxsize=1)
def _terrain_views() -> dict[tuple[str, str], ServedView]:
    return load_views(sites=_sites().sites)


def terrain_views_for(query: TerrainViewsQuery) -> TerrainViewsResponse:
    try:
        views = _terrain_views()
    except TerrainViewError as e:
        raise unavailable(f"precomputed terrain images are unusable: {e}") from e
    return TerrainViewsResponse(
        views=[sv.view for sv in views.values() if query.site_id is None or sv.view.site_id == query.site_id]
    )


def terrain_image(site_id: str, view: str, layer: str) -> Path:
    try:
        views = _terrain_views()
    except TerrainViewError as e:
        raise unavailable(f"precomputed terrain images are unusable: {e}") from e
    sv = views.get((site_id, view))
    path = (
        sv.image(TerrainViewLayer(layer))
        if sv is not None and layer in TerrainViewLayer._value2member_map_
        else None
    )
    if path is None:
        raise HTTPException(
            404, detail=NotFoundDetail(reason=NO_TERRAIN_IMAGE_REASON).model_dump(mode="json")
        )
    return path


# Already-compressed media types the gzip middleware passes through as they are (the terrain PNGs above all).
# Stated here rather than left to Starlette's default list, which could change between versions.
GZIP_EXCLUDED_TYPES = (
    "image/*",
    "audio/*",
    "video/*",
    "font/woff",
    "font/woff2",
    "application/gzip",
    "application/x-gzip",
    "application/zip",
    "text/event-stream",
)


@lru_cache(maxsize=1)
def _labels() -> Labels | None:
    return load_labels()


def feature_labels_for(query: FeatureLabelsQuery) -> FeatureLabelsResponse:
    try:
        labels = _labels()
    except FeatureLabelsError as e:
        raise unavailable(f"the IAU feature names are unusable: {e}") from e
    return select(labels, query)


def parse_bbox(text: str | None) -> BBox | None:
    """`lat_min,lat_max,lon_min,lon_max` (degrees) -> BBox; a malformed value is FastAPI's usual 422."""
    if text is None:
        return None
    try:
        lat_min, lat_max, lon_min, lon_max = (float(v) for v in text.split(","))
        box = BBox(lat_min=lat_min, lat_max=lat_max, lon_min=lon_min, lon_max=lon_max)
        if box.lat_min > box.lat_max:
            raise ValueError("lat_min is above lat_max")
    except ValueError as e:
        msg = f"bbox must be lat_min,lat_max,lon_min,lon_max in degrees ({e})"
        raise RequestValidationError(
            [{"type": "value_error", "loc": ("query", "bbox"), "msg": msg, "input": text}]
        ) from e
    return box


def site_summary(req: SiteSummaryRequest) -> SiteSummaryResponse:
    """What is known at and around one location. Each missing part is null, with a limitation saying why."""
    limitations: list[str] = []
    try:
        found = _terrain()
    except ServedFileError:
        found = {}
    hit = found.get(terrain_key(req.location.lat, req.location.lon, req.radius_m))
    if hit is None:
        limitations.append(SUMMARY_NO_TERRAIN_REASON)
    metrics = None
    if req.scenario is not None:
        try:
            metrics = served_for(req.scenario).metrics
        except HTTPException as e:
            limitations.append(COMPARE_NOT_SERVED_REASON if e.status_code == 422 else UNAVAILABLE_REASON)
    limitations.append(nl_service.NOT_AVAILABLE_YET[Operation.proximity])  # nearby features: not served yet
    return SiteSummaryResponse(
        location=req.location,
        radius_m=req.radius_m,
        metrics=metrics,
        terrain=hit.body if hit else None,
        features=None,
        limitations=limitations,
    )


def unavailable(technical: str) -> HTTPException:
    """503 with the contract's UnavailableDetail body."""
    detail = UnavailableDetail(reason=UNAVAILABLE_REASON, technical=technical)
    return HTTPException(503, detail=detail.model_dump(mode="json"))


def served_results() -> dict[str, Served]:
    """Every installed precomputed result, or a 503 saying why there are none."""
    try:
        served = _served()
    except ServedFileError as e:
        raise unavailable(f"precomputed results are unusable: {e}") from e
    if not served:
        raise unavailable(f"no precomputed results are installed ({served_dir()})")
    return served


def not_served(asked: Scenario | HorizonRequest, key: str, options: dict[str, Served]) -> HTTPException:
    """422 NotServedError: what was asked, and every served option with how it differs."""
    reason = HORIZON_NOT_SERVED_REASON if isinstance(asked, HorizonRequest) else NOT_SERVED_REASON
    served = [
        ServedScenario(
            scenario=sv.scenario,
            scenario_key=sv.scenario.key(),
            differs_in=differences(asked, sv.scenario),
        )
        for sv in options.values()
    ]
    detail = NotServedDetail(reason=reason, scenario_key=key, served=served)
    return HTTPException(422, detail=detail.model_dump(mode="json"))


def served_for(scenario: Scenario) -> Served:
    """The precomputed result for exactly this scenario, or an HTTP error saying why there is none."""
    served = served_results()
    key = scenario.key()
    if key in served:
        return served[key]
    raise not_served(scenario, key, served)


def horizon_for(req: HorizonRequest) -> HorizonProfile:
    """The precomputed horizon for exactly this location and unit height, or an HTTP error saying why not.

    `scenario_key` in the 422 body is then the request's HorizonRequest.key().
    """
    by_horizon = horizons(served_results())
    key = horizon_key(req.location.lat, req.location.lon, req.unit_height_m)
    if key in by_horizon:
        return by_horizon[key].horizon
    raise not_served(req, key, by_horizon)


def _layer_label(dataset_id: str, resolution_m: float) -> str:
    """The terrain resolver's short label for a layer (e.g. '5 m PGDA site map'), else '<res> m map'."""
    from lss.registry.terrain import LAYERS

    for spec in LAYERS:
        if spec.dataset_id == dataset_id and spec.resolution_m == resolution_m:
            return spec.label
    return f"{resolution_m:g} m map"


def slope_at_point(lat: float, lon: float) -> tuple[float, str] | None:
    """(slope, map label) at a location from the precomputed statistics on the finest map there (5 m at
    the PGDA sites, the project author's choice), or None."""
    try:
        found = _terrain()
    except ServedFileError:
        return None
    here = [t.body for t in found.values() if (t.body.location.lat, t.body.location.lon) == (lat, lon)]
    here = [b for b in here if b.slope_at_point_deg is not None and b.slope_layer is not None]
    if not here:
        return None
    best = min(here, key=lambda b: b.slope_layer.resolution_m)
    return best.slope_at_point_deg, _layer_label(best.slope_layer.dataset_id, best.slope_layer.resolution_m)


def compare_served(req: CompareRequest) -> CompareResponse:
    """Served metrics for the compared scenarios, filtered and ranked (lss.api.compare); a 422 only when
    none is served. Scenarios = the request's, then one per `across` site."""
    compared = list(req.scenarios)
    if req.across is not None:
        try:
            compared += compare_rules.expand(req.across, _sites().sites)
        except compare_rules.UnknownSitesError as e:
            issue = {"loc": ["body", "across"], "msg": str(e), "type": "value_error"}
            raise HTTPException(422, detail=[issue]) from e
    served = served_results()
    hits, missing = [], []
    for i, sc in enumerate(compared):
        key = sc.key()
        if key in served:
            hits.append((i, served[key].metrics))
        else:
            missing.append(CompareNotServed(index=i, scenario_key=key, reason=COMPARE_NOT_SERVED_REASON))
    if not hits:
        detail = CompareNotServedDetail(reason=COMPARE_NOT_SERVED_REASON, not_served=missing)
        raise HTTPException(422, detail=detail.model_dump(mode="json"))

    def band_at(key: str, min_deg: float, max_deg: float) -> float | None:
        return band_fraction(served[key], min_deg, max_deg) if key in served else None

    out = compare_rules.apply(hits, req.filters, req.rank, slope_at_point, band_at)
    return CompareResponse(
        items=out.items,
        not_served=missing,
        compared=compared,  # always, so a client can take its columns from the response
        evaluated=out.evaluated,
        filtered_out=out.filtered_out,
        rank_ties=out.rank_ties,
        beyond_limit=out.beyond_limit,
        compared_keys=[sc.key() for sc in compared],
    )


def locate(req: LocateRequest) -> LocateResponse:
    """Terrain stack and fidelity from the registry's resolver (static extents; no DEM is read)."""
    from lss.registry.terrain import resolve

    stack = resolve(req.lat, req.lon)
    fidelity = stack.fidelity()
    if not stack.supported or fidelity is None:
        detail = NoTerrainDetail(reason=NO_TERRAIN_REASON)
        raise HTTPException(422, detail=detail.model_dump(mode="json"))
    return LocateResponse(location=stack.location, terrain_stack=stack.contract_layers(), fidelity=fidelity)


def _errors(unprocessable: type, what: str) -> dict:
    return {
        422: {
            "model": unprocessable,
            "description": f"{what}, or a malformed request (InvalidRequestError, FastAPI validation)",
        },
        503: {"model": UnavailableError, "description": "No usable precomputed results are installed"},
    }


NOT_SERVED_ERRORS = _errors(UnprocessableError, "No precomputed result for this request (NotServedError)")
COMPARE_ERRORS = _errors(CompareUnprocessableError, "None of the scenarios is served (CompareNotServedError)")
TERRAIN_ERRORS = _errors(
    TerrainUnprocessableError,
    "No precomputed slope statistics for this location and radius (TerrainNotServedError)",
)
LOCATE_ERRORS = {
    422: {
        "model": LocateUnprocessableError,
        "description": "No terrain data covers the location (NoTerrainError), or a malformed request",
    }
}


def site_of(sv: Served, sites) -> str | None:
    """The curated site at a served scenario's exact location, or None."""
    point = (sv.scenario.location.lat, sv.scenario.location.lon)
    return next((s.id for s in sites if (s.location.lat, s.location.lon) == point), None)


def build_scenarios(served: dict[str, Served], sites, site_id: str | None = None) -> list[ScenarioEntry]:
    """ScenarioEntry for every served scenario (optionally one site's), in site-list order, then by unit
    height and window. Shared by GET /api/scenarios and the static copy."""
    order = {s.id: i for i, s in enumerate(sites)}
    with_horizon = set(horizons(served))
    entries = []
    for key, sv in served.items():
        sid = site_of(sv, sites)
        if site_id is not None and sid != site_id:
            continue
        entries.append(
            ScenarioEntry(
                site_id=sid,
                scenario_key=key,
                scenario=sv.scenario,
                has_horizon=sv.horizon_key in with_horizon,
            )
        )
    entries.sort(
        key=lambda e: (
            order.get(e.site_id, len(order)),
            e.scenario.unit_height_m,
            e.scenario.window_start,
            e.scenario.window_end,
            e.scenario.step,
        )
    )
    return entries


def scenarios_for(query: ScenariosQuery) -> ScenariosResponse:
    """Every served scenario, with its curated site (exact location match), in site-list order."""
    return ScenariosResponse(scenarios=build_scenarios(served_results(), _sites().sites, query.site_id))


def sites_for(query: SitesQuery) -> SitesResponse:
    resp = _sites()
    if query.category is None:
        return resp
    return resp.model_copy(update={"sites": [s for s in resp.sites if s.category == query.category]})


# What /api/nl can run: the same functions as the endpoints, on precomputed results only. Operations not
# listed here (proximity, search, terrain, site_summary) are answered "not available yet".
NL_EXECUTORS = {
    Operation.metrics: lambda r: served_for(r.scenario).metrics,
    Operation.series: lambda r: served_for(r.scenario).series,
    Operation.compare: compare_served,
    Operation.horizon: horizon_for,
    Operation.sites: sites_for,
    Operation.locate: locate,
    Operation.terrain: terrain_for,
    Operation.site_summary: site_summary,
}


LIST_FREE_REASONS = {
    NOT_SERVED_REASON: COMPARE_NOT_SERVED_REASON,
    HORIZON_NOT_SERVED_REASON: HORIZON_NO_LIST_REASON,
    TERRAIN_NOT_SERVED_REASON: SUMMARY_NO_TERRAIN_REASON,
}


@lru_cache(maxsize=1)
def get_nl_service() -> nl_service.NLService:
    return nl_service.NLService(
        executors=NL_EXECUTORS,
        provider_factory=nl_service.default_provider,
        list_free_reasons=LIST_FREE_REASONS,
        cache=nl_service.load_cache(nl_service.cache_dir()),
    )


NL_SERVICE = Depends(get_nl_service)  # tests override get_nl_service (app.dependency_overrides)

NL_ERRORS = {
    429: {"model": RateLimitedError, "description": "Too many live questions from this client"},
    503: {
        "model": UnavailableError,
        "description": "Live questions unavailable (daily spend cap reached, or the model can't be reached)",
    },
}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Lunar Site Scout API",
        version=CONTRACT_VERSION,
        description="Contract v0. Not affiliated with or endorsed by NASA.",
        separate_input_output_schemas=False,
    )
    # Compress JSON over 1 KB (the label list, series, scenario lists); never recompress what already is.
    app.add_middleware(GZipMiddleware, minimum_size=1000, exclude_content_types=GZIP_EXCLUDED_TYPES)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse, response_model_by_alias=True)
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/api/sites", response_model=SitesResponse, response_model_by_alias=True)
    def sites(category: SiteCategory | None = None) -> SitesResponse:
        return sites_for(SitesQuery(category=category))

    @app.get(
        "/api/scenarios",
        response_model=ScenariosResponse,
        response_model_by_alias=True,
        responses={
            503: {"model": UnavailableError, "description": "No usable precomputed results are installed"}
        },
    )
    def scenarios(site_id: str | None = None) -> ScenariosResponse:
        return scenarios_for(ScenariosQuery(site_id=site_id))

    @app.get("/api/datasets", response_model=DatasetsResponse, response_model_by_alias=True)
    def datasets() -> DatasetsResponse:
        return _datasets()

    @app.post(
        "/api/locate", response_model=LocateResponse, response_model_by_alias=True, responses=LOCATE_ERRORS
    )
    def locate_endpoint(req: LocateRequest) -> LocateResponse:
        return locate(req)

    @app.post(
        "/api/horizon",
        response_model=HorizonProfile,
        response_model_by_alias=True,
        responses=NOT_SERVED_ERRORS,
    )
    def horizon(req: HorizonRequest) -> HorizonProfile:
        return horizon_for(req)

    @app.post(
        "/api/metrics",
        response_model=MetricsResponse,
        response_model_by_alias=True,
        responses=NOT_SERVED_ERRORS,
    )
    def metrics(req: ScenarioRequest) -> MetricsResponse:
        return served_for(req.scenario).metrics

    @app.post(
        "/api/series",
        response_model=SeriesResponse,
        response_model_by_alias=True,
        responses=NOT_SERVED_ERRORS,
    )
    def series(req: ScenarioRequest) -> SeriesResponse:
        return served_for(req.scenario).series

    @app.post(
        "/api/compare", response_model=CompareResponse, response_model_by_alias=True, responses=COMPARE_ERRORS
    )
    def compare(req: CompareRequest) -> CompareResponse:
        return compare_served(req)

    @app.post(
        "/api/terrain", response_model=TerrainResponse, response_model_by_alias=True, responses=TERRAIN_ERRORS
    )
    def terrain(req: TerrainRequest) -> TerrainResponse:
        return terrain_for(req)

    @app.get(
        "/api/terrain/views",
        response_model=TerrainViewsResponse,
        response_model_by_alias=True,
        responses={
            503: {"model": UnavailableError, "description": "Precomputed terrain images are unusable"}
        },
    )
    def terrain_views(site_id: str | None = None) -> TerrainViewsResponse:
        return terrain_views_for(TerrainViewsQuery(site_id=site_id))

    @app.get(
        "/api/terrain/view/{site_id}/{view}/{layer}.png",
        response_class=FileResponse,
        responses={
            200: {"content": {"image/png": {}}, "description": "8-bit greyscale PNG (see TerrainView)"},
            404: {"model": NotFoundError, "description": "No such precomputed image"},
        },
    )
    def terrain_view_image(site_id: str, view: str, layer: str) -> FileResponse:
        return FileResponse(terrain_image(site_id, view, layer), media_type="image/png")

    @app.get(
        "/api/features/labels",
        response_model=FeatureLabelsResponse,
        response_model_by_alias=True,
        responses={
            422: {"model": InvalidRequestError, "description": "A malformed filter (FastAPI validation)"},
            503: {"model": UnavailableError, "description": "The installed IAU names file is unusable"},
        },
    )
    def feature_labels(
        types: Annotated[list[str] | None, Query(description="IAU type codes, e.g. AA, ME; repeat")] = None,
        min_diameter_km: Annotated[float | None, Query(ge=0.0)] = None,
        include_satellite: bool = False,
        bbox: Annotated[str | None, Query(description="lat_min,lat_max,lon_min,lon_max (degrees)")] = None,
        limit: Annotated[int | None, Query(ge=1)] = None,
    ) -> FeatureLabelsResponse:
        query = FeatureLabelsQuery(
            types=types or [],
            min_diameter_km=min_diameter_km,
            include_satellite=include_satellite,
            bbox=parse_bbox(bbox),
            limit=limit,
        )
        return feature_labels_for(query)

    @app.post("/api/site_summary", response_model=SiteSummaryResponse, response_model_by_alias=True)
    def site_summary_endpoint(req: SiteSummaryRequest) -> SiteSummaryResponse:
        return site_summary(req)

    @app.post(
        "/api/nl",
        response_model=NLAnswer | NLUnsupported | NLClarification,
        response_model_by_alias=True,
        responses=NL_ERRORS,
    )
    def nl(
        req: NLRequest, request: Request, service: nl_service.NLService = NL_SERVICE
    ) -> NLAnswer | NLUnsupported | NLClarification:
        client = nl_service.client_address(
            request.headers.get("x-forwarded-for"), request.client.host if request.client else None
        )
        return service.answer(req, client)

    if os.environ.get("LSS_DEBUG_CLIENT_IP") == "1":
        # Off by default; on for one deploy to check which X-Forwarded-For entry Cloud Run's front end adds
        # (deploy/README.md). Shows callers only their own request's header and address.
        @app.get("/api/_debug/client", include_in_schema=False)
        def debug_client(request: Request) -> dict:
            forwarded = request.headers.get("x-forwarded-for")
            peer = request.client.host if request.client else None
            return {
                "x_forwarded_for": forwarded,
                "peer": peer,
                "used_for_rate_limit": nl_service.client_address(forwarded, peer),
            }

    return app


app = create_app()
