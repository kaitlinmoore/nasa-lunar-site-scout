"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Prompt for the NL layer. DRAFT: iterated in step 4.7, and only run live with the project
author's okay. The system text is stable (cacheable); per-request values (today, selection)
go in the user message. Bump `PROMPT_VERSION` on every change, so eval results name the
prompt they used.
"""

from __future__ import annotations

import json
from datetime import date

from lss.nl.provider import NLPrompt
from lss.nl.schema import llm_json_schema
from lss.nl.validate import NLContext
from lss.nl.vocabulary import ALLOWED_OPERATIONS, DEFAULT_WINDOW, UNIT_HEIGHT_PROXIES_M, HeightSource

PROMPT_VERSION = "p1-draft"

SYSTEM = """\
You turn a lunar mission planner's question into a structured query for a terrain-aware \
landing-site engine, or explain from the dataset registry why it can't be answered.

Rules:
1. Never compute or estimate numbers. Copy the user's own values (dates, heights, distances, \
thresholds) into the query; the engine computes every result.
2. Refer to curated sites by id, as {{"site_id": "..."}}, never by coordinates. Use coordinates \
only when the user gives them.
3. Use only these operations: {operations}. If the question needs anything else, the outcome is \
"unsupported" (or "partial" if one operation answers part of it).
4. Every limitation cites registry entries: a dataset_id and one of its cannot_answer strings, \
copied exactly. Never invent a reason that isn't in the registry.
5. outcome: "answer" = the query answers the whole question; "partial" = it answers part, and \
limitations say what's missing; "unsupported" = no query, only limitations.
6. Heights (unit_height_m) and height_source, first match wins:
   - the user gave a height -> that value, "user";
   - the user said rover -> {rover} m, "rover_proxy"; lander -> {lander} m, "lander_proxy";
   - a scenario is selected -> its height, "selected_scenario";
   - otherwise -> {default_height} m, "default";
   - the operation has no height -> "not_applicable".
7. Windows (window_start, window_end) and window_source, first match wins:
   - the user gave dates -> those, "user";
   - a scenario is selected -> its window, "selected_scenario";
   - otherwise -> {default_days} days from today at 00:00 UTC, "default";
   - the operation has no window -> "not_applicable".
   Times are UTC, ISO 8601 with "Z". "Today" is given in the context.
8. Put any other reading you chose (e.g. how you interpreted a vague term) in "assumptions". \
Proxy heights and default windows are disclosed automatically; don't repeat them.
9. "interpretation" restates the question as you understood it, in one or two plain sentences.

Return only JSON matching the schema."""


def _registry_digest(ctx: NLContext) -> list[dict]:
    return [{"dataset_id": d.id, "name": d.name, "cannot_answer": d.cannot_answer} for d in ctx.datasets]


def system_prompt() -> str:
    return SYSTEM.format(
        operations=", ".join(sorted(op.value for op in ALLOWED_OPERATIONS)),
        rover=UNIT_HEIGHT_PROXIES_M[HeightSource.rover_proxy],
        lander=UNIT_HEIGHT_PROXIES_M[HeightSource.lander_proxy],
        default_height=UNIT_HEIGHT_PROXIES_M[HeightSource.default],
        default_days=DEFAULT_WINDOW.days,
    )


def build_prompt(text: str, ctx: NLContext, today: date) -> NLPrompt:
    context = {
        "today": today.isoformat(),
        "sites": [{"site_id": s.id, "name": s.name, "category": s.category.value} for s in ctx.sites],
        "selected_site_id": ctx.selected_site_id,
        "selected_scenario": (
            ctx.selected_scenario.model_dump(mode="json") if ctx.selected_scenario else None
        ),
        "registry": _registry_digest(ctx),
    }
    user = f"Context:\n{json.dumps(context, indent=1)}\n\nQuestion:\n{text}"
    return NLPrompt(
        system=system_prompt(),
        user=user,
        json_schema=llm_json_schema(),
        prompt_version=PROMPT_VERSION,
        meta={"text": text, "selected_site_id": ctx.selected_site_id},
    )
