"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

The NL layer's two-step call (see `lss.nl.schema`): route, then (if an operation was chosen)
fill. Returns an `NLOutput`-shaped dict for `lss.nl.validate.validate_output`, which checks it
against the vocabulary, contract and registry exactly as before.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from pydantic import BaseModel, ValidationError

from lss.nl.prompt import build_fill_prompt, build_route_prompt
from lss.nl.provider import Provider
from lss.nl.schema import NLFill, NLRoute, Outcome
from lss.nl.validate import NLContext, NLValidationError


def _parse[M: BaseModel](raw: str, model: type[M], stage: str) -> M:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise NLValidationError([f"{stage}: output is not JSON: {e}"]) from e
    try:
        return model.model_validate(data)
    except ValidationError as e:
        raise NLValidationError([f"{stage} schema: {err['loc']}: {err['msg']}" for err in e.errors()]) from e


def interpret(
    text: str,
    ctx: NLContext,
    provider: Provider,
    today: date,
    trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run route (+ fill) and return the combined NL output (not yet validated).

    `trace`, if given, receives one entry per provider call: stage, raw output, provider meta.
    Raises `NLValidationError` when a stage's output can't be parsed or the route is inconsistent.
    """
    trace = trace if trace is not None else []

    def call(prompt) -> str:
        raw = provider.complete(prompt)
        meta = getattr(provider, "last_meta", None)
        trace.append({"stage": prompt.meta["stage"], "raw": raw, "meta": dict(meta) if meta else None})
        return raw

    route = _parse(call(build_route_prompt(text, ctx, today)), NLRoute, "route")
    limitations = [lim.model_dump(mode="json") for lim in route.limitations]
    if route.outcome == Outcome.clarify:
        if route.operation is not None:
            raise NLValidationError(["route: a clarify outcome has no operation"])
        return {
            "outcome": "clarify",
            "interpretation": route.interpretation,
            "question": route.question,
            "limitations": limitations,
        }
    if route.outcome == Outcome.unsupported:
        if route.operation is not None:
            raise NLValidationError(["route: an unsupported outcome has no operation"])
        return {"outcome": "unsupported", "interpretation": route.interpretation, "limitations": limitations}
    if route.operation is None:
        raise NLValidationError([f"route: outcome {route.outcome.value!r} needs an operation"])

    fill = _parse(call(build_fill_prompt(text, ctx, today, route.operation)), NLFill, "fill")
    return {
        "outcome": route.outcome.value,
        "interpretation": fill.interpretation,  # the echo comes from the call that wrote the params
        "query": {"operation": route.operation.value, "params": fill.params},
        "height_source": fill.height_source.value,
        "window_source": fill.window_source.value,
        "slope_source": fill.slope_source.value,
        "radius_source": fill.radius_source.value,
        "assumptions": fill.assumptions,
        "limitations": limitations,
    }
