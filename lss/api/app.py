"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

FastAPI app: `GET /api/health`, `GET /api/sites` (served from the fixture), and the C1 thin slice:
`POST /api/metrics` and `POST /api/series`, which serve precomputed results (lss.api.served) for the scenarios
in `LSS_DATA_DIR/cache/served/` only, matched on `Scenario.key()`. Any other scenario gets a 422 with the
reason; nothing is computed live, so the API needs no DEMs or kernels.

Run locally:  uv run uvicorn lss.api.app:app --reload
"""

from __future__ import annotations

import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from lss.api.served import Served, ServedFileError, differences, load_all, served_dir
from lss.config import FIXTURES_DIR, get_settings
from lss.contract import (
    CONTRACT_VERSION,
    HealthResponse,
    MetricsResponse,
    Scenario,
    ScenarioRequest,
    SeriesResponse,
    SiteCategory,
    SitesResponse,
)


@lru_cache(maxsize=1)
def _fixture_sites() -> SitesResponse:
    data = json.loads((FIXTURES_DIR / "sites.json").read_text(encoding="utf-8"))
    return SitesResponse.model_validate(data)


@lru_cache(maxsize=1)
def _served() -> dict[str, Served]:
    return load_all()


def served_for(scenario: Scenario) -> Served:
    """The precomputed result for exactly this scenario, or an HTTP error saying why there is none."""
    try:
        served = _served()
    except ServedFileError as e:
        raise HTTPException(503, detail={"reason": f"precomputed results are unusable: {e}"}) from e
    if not served:
        raise HTTPException(503, detail={"reason": f"no precomputed results are installed ({served_dir()})"})
    key = scenario.key()
    if key in served:
        return served[key]
    raise HTTPException(
        422,
        detail={
            "reason": (
                "This version serves precomputed results only, for the scenarios listed in `served`. The "
                "request must match one of them exactly: location, unit height, window and step."
            ),
            "scenario_key": key,
            "served": [
                {
                    "scenario": sv.scenario.model_dump(mode="json"),
                    "scenario_key": k,
                    "differs_in": differences(scenario, sv.scenario),
                }
                for k, sv in served.items()
            ],
        },
    )


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

    unsupported = {
        422: {"description": "No precomputed result for this scenario (detail.reason, detail.served)"},
        503: {"description": "No usable precomputed results are installed (detail.reason)"},
    }

    @app.post(
        "/api/metrics", response_model=MetricsResponse, response_model_by_alias=True, responses=unsupported
    )
    def metrics(req: ScenarioRequest) -> MetricsResponse:
        return served_for(req.scenario).metrics

    @app.post(
        "/api/series", response_model=SeriesResponse, response_model_by_alias=True, responses=unsupported
    )
    def series(req: ScenarioRequest) -> SeriesResponse:
        return served_for(req.scenario).series

    return app


app = create_app()
