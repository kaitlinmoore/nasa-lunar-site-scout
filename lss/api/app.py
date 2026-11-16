"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

FastAPI app, API v0 (plan section 4.3). Results are precomputed only (plan section 4.6; lss.api.served):
nothing is computed live, so the API needs no DEMs, kernels or numba.

- `GET /api/health`; `GET /api/sites` (the curated list in fixtures/sites.json); `GET /api/datasets` (the
  capability registry).
- `POST /api/locate`: the terrain stack and fidelity label from the registry's resolver, which uses static
  layer extents only (no DEM reads).
- `POST /api/metrics`, `/api/series`: the precomputed result for a scenario, matched on `Scenario.key()`.
- `POST /api/horizon`: the precomputed horizon profile for a location and unit height.
- `POST /api/compare`: metrics for every served scenario of the request; the rest are listed as not served.

A valid request with no precomputed result gets a 422 with a plain-language reason and what is served; no
usable results installed gets a 503 (contract error models in lss.contract).

Run locally:  uv run uvicorn lss.api.app:app --reload
"""

from __future__ import annotations

import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from lss.api.served import (
    Served,
    ServedFileError,
    differences,
    horizon_key,
    horizons,
    load_all,
    served_dir,
)
from lss.config import FIXTURES_DIR, get_settings
from lss.contract import (
    CONTRACT_VERSION,
    CompareNotServed,
    CompareNotServedDetail,
    CompareRequest,
    CompareResponse,
    CompareUnprocessableError,
    DatasetsResponse,
    HealthResponse,
    HorizonProfile,
    HorizonRequest,
    LocateRequest,
    LocateResponse,
    LocateUnprocessableError,
    MetricsResponse,
    NoTerrainDetail,
    NotServedDetail,
    Scenario,
    ScenarioRequest,
    SeriesResponse,
    ServedScenario,
    SiteCategory,
    SitesResponse,
    UnavailableDetail,
    UnavailableError,
    UnprocessableError,
)

# Visitor-facing wording. NOT_SERVED_REASON and UNAVAILABLE_REASON: Kaitlin, 2026-11-15.
# HORIZON_NOT_SERVED_REASON and NO_TERRAIN_REASON: Claude-drafted on the same pattern, pending her review.
# A 503's technical cause goes in `detail.technical`, never in the reason.
NOT_SERVED_REASON = (
    "This version has precomputed results only for the scenarios listed with this message. A request must "
    "match one of them exactly: the same location, unit height, time window and time step."
)
HORIZON_NOT_SERVED_REASON = (
    "This version has precomputed horizon profiles only for the locations and unit heights listed with this "
    "message. A request must match one of them exactly: the same location and unit height."
)
NO_TERRAIN_REASON = "No terrain data in this version covers this location."
UNAVAILABLE_REASON = (
    "Results are temporarily unavailable: the server has no usable precomputed results installed."
)


@lru_cache(maxsize=1)
def _fixture_sites() -> SitesResponse:
    data = json.loads((FIXTURES_DIR / "sites.json").read_text(encoding="utf-8"))
    return SitesResponse.model_validate(data)


@lru_cache(maxsize=1)
def _datasets() -> DatasetsResponse:
    from lss.registry.loader import load_datasets

    return DatasetsResponse(datasets=list(load_datasets()))


@lru_cache(maxsize=1)
def _served() -> dict[str, Served]:
    return load_all()


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


def compare_served(req: CompareRequest) -> CompareResponse:
    """Metrics for the served scenarios in request order; a 422 only when none is served."""
    served = served_results()
    items, missing = [], []
    for i, sc in enumerate(req.scenarios):
        key = sc.key()
        if key in served:
            items.append(served[key].metrics)
        else:
            missing.append(CompareNotServed(index=i, scenario_key=key, reason=NOT_SERVED_REASON))
    if not items:
        detail = CompareNotServedDetail(reason=NOT_SERVED_REASON, not_served=missing)
        raise HTTPException(422, detail=detail.model_dump(mode="json"))
    return CompareResponse(items=items, not_served=missing)


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
LOCATE_ERRORS = {
    422: {
        "model": LocateUnprocessableError,
        "description": "No terrain data covers the location (NoTerrainError), or a malformed request",
    }
}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Lunar Site Scout API",
        version=CONTRACT_VERSION,
        description="Contract v0. Not affiliated with or endorsed by NASA.",
        separate_input_output_schemas=False,
    )
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
        resp = _fixture_sites()
        if category is None:
            return resp
        return resp.model_copy(update={"sites": [s for s in resp.sites if s.category == category]})

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

    return app


app = create_app()
