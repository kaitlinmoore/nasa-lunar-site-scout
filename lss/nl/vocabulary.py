"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Core NL vocabulary (step 4.2, decided by the project author 2026-11-15: "Option B").

The LLM may emit a structured query for these operations only. Each maps to the
contract request model its `params` must validate against. Everything else is
answered as unsupported, citing the dataset capability registry.

Unit-height proxies (project author's decision, 2026-11-15): "rover" -> 1 m and
"lander" -> 5 m. They are proxy values, and every answer that uses one says so.
"""

from __future__ import annotations

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
    not_applicable = "not_applicable"  # the operation has no height


UNIT_HEIGHT_PROXIES_M: dict[HeightSource, float] = {
    HeightSource.rover_proxy: 1.0,
    HeightSource.lander_proxy: 5.0,
}

PROXY_ASSUMPTION_TEXT: dict[HeightSource, str] = {
    HeightSource.rover_proxy: (
        "Height 1 m: a proxy value for a rover, not the height of any specific rover."
    ),
    HeightSource.lander_proxy: (
        "Height 5 m: a proxy value for a lander, not the height of any specific lander."
    ),
}
