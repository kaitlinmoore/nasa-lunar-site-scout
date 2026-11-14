"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

FastAPI app (C0 skeleton): `GET /api/health` and `GET /api/sites` (served from the fixture).

Run locally:  uv run uvicorn lss.api.app:app --reload
"""

from __future__ import annotations

import json
from functools import lru_cache

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lss.config import FIXTURES_DIR, get_settings
from lss.contract import CONTRACT_VERSION, HealthResponse, SiteCategory, SitesResponse


@lru_cache(maxsize=1)
def _fixture_sites() -> SitesResponse:
    data = json.loads((FIXTURES_DIR / "sites.json").read_text(encoding="utf-8"))
    return SitesResponse.model_validate(data)


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

    return app


app = create_app()
