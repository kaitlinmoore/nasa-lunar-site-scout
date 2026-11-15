"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Prompts for the NL layer's two calls (see `lss.nl.schema`, "two-step call"):
  route: what kind of answer, which operation, and registry-cited limits;
  fill:  that operation's parameters and the interpretation shown to the user.
DRAFT: iterated in step 4.7, and only run live with the project author's okay. System texts
are stable (cacheable); per-request values (today, selection, question) go in the user
message. Bump `PROMPT_VERSION` on every change, so eval results name the prompt they used.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from lss.contract import Operation
from lss.nl.provider import NLPrompt
from lss.nl.schema import fill_json_schema, route_json_schema
from lss.nl.validate import NLContext
from lss.nl.vocabulary import (
    ALLOWED_OPERATIONS,
    DEFAULT_WINDOW,
    NEARBY_RADIUS_M,
    SAFE_MAX_SLOPE_DEG,
    UNIT_HEIGHT_PROXIES_M,
    HeightSource,
)

PROMPT_VERSION = "p4-draft"

ROUTE_SYSTEM = """\
You are the first step of a natural-language interface to a terrain-aware lunar landing-site \
engine. Decide how a mission planner's question can be answered. A second step fills in the \
parameters, so don't produce any here.

Rules:
1. Operations the engine offers: {operations}.
   - metrics: power and Earth-visibility metrics at one site over a time window
   - series: Sun/Earth position and visibility over time at one site, with events \
(sunrise, sunset, Earthrise, Earthset)
   - compare: metrics for several sites and/or windows side by side
   - horizon: the terrain horizon profile at a site
   - sites: list curated sites, optionally by category
   - locate: which terrain data covers a point, and how detailed it is
   - proximity: straight-line distances from a site to nearby features (craters, permanently \
shadowed regions, ice detections, hazards, landing sites, named features)
   - search: terrain-only area search (slope, flat area, distance to features) over an area
2. outcome: "answer" = one operation answers the whole question; "partial" = one operation \
answers part of it, and limitations say what's missing; "unsupported" = no operation helps \
(operation null), and limitations say why.
   If a registry entry says the data the operation relies on can't cover part of what the \
question asks for (part of its size range, resolution, area or time span), the operation \
answers only part of it: the outcome is "partial", and that entry is cited.
3. Every limitation cites registry entries from the context: a dataset_id and one of its \
cannot_answer strings, copied exactly. Never invent a reason that isn't in the registry. \
"topic" names the part of the question that isn't answered.
   Cite only entries that directly explain why that part can't be answered: limits of the \
data or tool the engine would actually need for it. Don't cite other datasets' limits, even \
if they sound related.
4. Never compute or estimate any result. The engine computes everything.
5. "interpretation" restates the question as you understood it, in one or two plain sentences.

Return only JSON matching the schema."""

FILL_SYSTEM = """\
You are the second step of a natural-language interface to a terrain-aware lunar landing-site \
engine. The operation is already chosen. Fill in its parameters from the planner's question.

Rules:
1. Never compute or estimate numbers. Copy the user's own values (dates, heights, distances, \
thresholds) into the parameters; the engine computes every result.
2. Refer to curated sites by id, as {{"site_id": "..."}}, never by coordinates. Use coordinates \
only when the user gives them.
3. Heights (unit_height_m) and height_source, first match wins:
   - the user gave a height -> that value, "user";
   - the user said rover -> {rover} m, "rover_proxy"; lander -> {lander} m, "lander_proxy";
   - a scenario is selected -> its height, "selected_scenario";
   - otherwise -> {default_height} m, "default";
   - the operation has no height -> "not_applicable".
4. Windows (window_start, window_end) and window_source, first match wins:
   - the user gave dates -> those, "user";
   - a scenario is selected -> its window, "selected_scenario";
   - otherwise -> {default_days} days from today at 00:00 UTC, "default";
   - the operation has no window -> "not_applicable".
   A named end date includes that day: the window ends at 00:00 UTC the next day. "During \
<month>" is the whole month (00:00 UTC on the 1st to 00:00 UTC on the 1st of the next month).
   Times are UTC, ISO 8601 with "Z". "Today" is given in the context. Leave "step" out unless \
the user asks for a sampling step.
5. Slope limits (max_slope_deg) and slope_source:
   - the user gave a slope limit -> that value, "user";
   - the user asked for "safe" terrain and gave no slope limit -> {safe_slope} degrees, \
"safe_default";
   - the query has no slope limit -> "not_applicable".
6. Search distances (radius_m, max_feature_distance_m) and radius_source:
   - the user gave a distance -> that value in meters, "user";
   - the user said "nearby", "near" or "around" and gave no distance -> {nearby_m} m, \
"nearby_default";
   - the query has no search distance -> "not_applicable".
7. Put any other reading you chose (e.g. how you interpreted a vague term) in "assumptions". \
Proxy heights, default windows, the "safe" slope limit and the "nearby" distance are disclosed \
automatically; don't repeat them.
8. "interpretation" restates the query exactly as you filled it (site, height, dates, \
thresholds), in one or two plain sentences.

Return only JSON matching the schema."""


def _registry_digest(ctx: NLContext) -> list[dict]:
    return [{"dataset_id": d.id, "name": d.name, "cannot_answer": d.cannot_answer} for d in ctx.datasets]


def route_system_prompt() -> str:
    return ROUTE_SYSTEM.format(operations=", ".join(sorted(op.value for op in ALLOWED_OPERATIONS)))


def fill_system_prompt() -> str:
    return FILL_SYSTEM.format(
        rover=UNIT_HEIGHT_PROXIES_M[HeightSource.rover_proxy],
        lander=UNIT_HEIGHT_PROXIES_M[HeightSource.lander_proxy],
        default_height=UNIT_HEIGHT_PROXIES_M[HeightSource.default],
        default_days=DEFAULT_WINDOW.days,
        safe_slope=f"{SAFE_MAX_SLOPE_DEG:g}",
        nearby_m=f"{NEARBY_RADIUS_M:g}",
    )


def _context(ctx: NLContext, today: date, registry: bool) -> dict[str, Any]:
    out: dict[str, Any] = {
        "today": today.isoformat(),
        "sites": [{"site_id": s.id, "name": s.name, "category": s.category.value} for s in ctx.sites],
        "selected_site_id": ctx.selected_site_id,
        "selected_scenario": (
            ctx.selected_scenario.model_dump(mode="json") if ctx.selected_scenario else None
        ),
    }
    if registry:
        out["registry"] = _registry_digest(ctx)
    return out


def build_route_prompt(text: str, ctx: NLContext, today: date) -> NLPrompt:
    user = f"Context:\n{json.dumps(_context(ctx, today, registry=True), indent=1)}\n\nQuestion:\n{text}"
    return NLPrompt(
        system=route_system_prompt(),
        user=user,
        json_schema=route_json_schema(),
        prompt_version=PROMPT_VERSION,
        meta={"stage": "route", "text": text, "selected_site_id": ctx.selected_site_id},
    )


def build_fill_prompt(text: str, ctx: NLContext, today: date, operation: Operation) -> NLPrompt:
    context = _context(ctx, today, registry=False)
    user = f"Context:\n{json.dumps(context, indent=1)}\n\nQuestion:\n{text}\n\nOperation: {operation.value}"
    return NLPrompt(
        system=fill_system_prompt(),
        user=user,
        json_schema=fill_json_schema(operation),
        prompt_version=PROMPT_VERSION,
        meta={
            "stage": "fill",
            "text": text,
            "selected_site_id": ctx.selected_site_id,
            "operation": operation.value,
        },
    )
