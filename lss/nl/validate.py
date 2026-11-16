"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Validation of the LLM's output (step 4.3), and conversion to the contract's NL responses.

`validate_output` rejects anything the contract wouldn't accept:
- the schema itself (`NLOutput`: unknown fields, inconsistent outcome);
- operations outside the Core NL vocabulary;
- `params` that the operation's contract request model rejects (after site ids are
  replaced by catalog locations);
- unit heights that don't match the declared `height_source` (proxy and default heights
  must be exactly that value), and windows that don't match `window_source` (the default
  window must be exactly 30 days from the request's date);
- slope limits and search distances that don't match `slope_source` / `radius_source` (the
  "safe", "nearby" and "around" defaults must be exactly 5 degrees, 10 km and 1 km);
- limitations whose citations aren't in the dataset capability registry.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from pydantic import ValidationError

from lss.contract import (
    DatasetCapability,
    Limitation,
    NLAnswer,
    NLClarification,
    NLUnsupported,
    Scenario,
    Site,
    StructuredQuery,
    display_name,
)
from lss.nl.schema import NLOutput, NLQuery, Outcome, SiteRef
from lss.nl.vocabulary import (
    ALLOWED_OPERATIONS,
    DEFAULT_WINDOW,
    OPERATION_PARAMS,
    PROXY_ASSUMPTION_TEXT,
    RADIUS_DEFAULTS,
    RADIUS_KEYS,
    SAFE_MAX_SLOPE_DEG,
    SAFE_NOT_MEASURED_TEXT,
    SLOPE_KEYS,
    UNIT_HEIGHT_PROXIES_M,
    HeightSource,
    SiteSource,
    SlopeSource,
    WindowSource,
    default_window_text,
    safe_slope_text,
    selected_site_text,
)
from lss.registry.loader import load_datasets


class NLValidationError(ValueError):
    def __init__(self, problems: Sequence[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


@dataclass(frozen=True)
class NLContext:
    """What the validator checks against: the site catalog, the registry and the UI selection."""

    sites: Sequence[Site]
    datasets: Sequence[DatasetCapability]
    selected_site_id: str | None = None
    selected_scenario: Scenario | None = None
    today: date | None = None  # the request's date: start of the default window


def default_context(
    selected_site_id: str | None = None,
    selected_scenario: Scenario | None = None,
    today: date | None = None,
) -> NLContext:
    """Context from the curated site registry (what /api/sites serves) and the dataset registry."""
    from lss.registry.sites import load_sites

    return NLContext(
        sites=list(load_sites()),
        datasets=load_datasets(),
        selected_site_id=selected_site_id,
        selected_scenario=selected_scenario,
        today=today,
    )


@dataclass(frozen=True)
class ValidatedOutput:
    output: NLOutput
    structured_query: StructuredQuery | None
    assumptions: list[str] = field(default_factory=list)


def parse_output(raw: str | Mapping[str, Any]) -> NLOutput:
    try:
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except json.JSONDecodeError as e:
        raise NLValidationError([f"output is not JSON: {e}"]) from e
    try:
        return NLOutput.model_validate(data)
    except ValidationError as e:
        raise NLValidationError([f"schema: {err['loc']}: {err['msg']}" for err in e.errors()]) from e


def _resolve_site_refs(value: Any, sites: Mapping[str, Site], problems: list[str]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"site_id"}:
            ref = SiteRef.model_validate(value)
            site = sites.get(ref.site_id)
            if site is None:
                problems.append(f"unknown site_id {ref.site_id!r}")
                return value
            return site.location.model_dump(mode="json")
        return {k: _resolve_site_refs(v, sites, problems) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_site_refs(v, sites, problems) for v in value]
    return value


def _unit_heights(value: Any) -> list[float]:
    found: list[float] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k == "unit_height_m" and isinstance(v, int | float):
                found.append(float(v))
            else:
                found.extend(_unit_heights(v))
    elif isinstance(value, list):
        for v in value:
            found.extend(_unit_heights(v))
    return found


def _check_heights(output: NLOutput, params: dict[str, Any], ctx: NLContext, problems: list[str]) -> None:
    heights = _unit_heights(params)
    src = output.height_source
    if src == HeightSource.not_applicable:
        if heights:
            problems.append("params set unit_height_m but height_source is 'not_applicable'")
        return
    if not heights:
        problems.append(f"height_source is {src.value!r} but params have no unit_height_m")
        return
    if src in UNIT_HEIGHT_PROXIES_M:
        want = UNIT_HEIGHT_PROXIES_M[src]
        if any(h != want for h in heights):
            problems.append(f"height_source {src.value!r} requires unit_height_m = {want} m, got {heights}")
    elif src == HeightSource.selected_scenario:
        if ctx.selected_scenario is None:
            problems.append("height_source is 'selected_scenario' but no scenario is selected")
        elif any(h != ctx.selected_scenario.unit_height_m for h in heights):
            problems.append("unit_height_m differs from the selected scenario's height")
    if src == HeightSource.default and ctx.selected_scenario is not None:
        problems.append("height_source is 'default' but a scenario is selected (use its height)")


def _windows(value: Any) -> list[tuple[datetime, datetime]]:
    found: list[tuple[datetime, datetime]] = []
    if isinstance(value, dict):
        if "window_start" in value and "window_end" in value:
            start, end = value["window_start"], value["window_end"]
            found.append((datetime.fromisoformat(start), datetime.fromisoformat(end)))
        for v in value.values():
            found.extend(_windows(v))
    elif isinstance(value, list):
        for v in value:
            found.extend(_windows(v))
    return found


def _check_windows(output: NLOutput, params: dict[str, Any], ctx: NLContext, problems: list[str]) -> None:
    windows = _windows(params)
    src = output.window_source
    if src == WindowSource.not_applicable:
        if windows:
            problems.append("params set a window but window_source is 'not_applicable'")
        return
    if not windows:
        problems.append(f"window_source is {src.value!r} but params have no window")
        return
    if src == WindowSource.default:
        if ctx.selected_scenario is not None:
            problems.append("window_source is 'default' but a scenario is selected (use its window)")
        if any(end - start != DEFAULT_WINDOW for start, end in windows):
            problems.append("window_source 'default' requires a 30-day window")
        if ctx.today is not None:
            start = datetime(ctx.today.year, ctx.today.month, ctx.today.day, tzinfo=UTC)
            if any(s != start for s, _ in windows):
                problems.append(f"the default window starts at {start.isoformat()} (the request's date)")
    elif src == WindowSource.selected_scenario:
        sc = ctx.selected_scenario
        if sc is None:
            problems.append("window_source is 'selected_scenario' but no scenario is selected")
        elif any((s, e) != (sc.window_start, sc.window_end) for s, e in windows):
            problems.append("window differs from the selected scenario's window")


def _values(value: Any, keys: frozenset[str]) -> list[float]:
    """Every non-null number under one of `keys`, at any depth."""
    found: list[float] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k in keys and isinstance(v, int | float):
                found.append(float(v))
            else:
                found.extend(_values(v, keys))
    elif isinstance(value, list):
        for v in value:
            found.extend(_values(v, keys))
    return found


def _check_default_value(
    name: str, src: Any, defaults: Mapping[Any, float], values: list[float], problems: list[str]
) -> None:
    """Shared check for `slope_source` / `radius_source` (`defaults`: default member -> required value)."""
    if src.value == "not_applicable":
        if values:
            problems.append(f"params set a {name} but {name}_source is 'not_applicable'")
        return
    if not values:
        problems.append(f"{name}_source is {src.value!r} but params have no {name}")
    elif src in defaults and any(v != defaults[src] for v in values):
        problems.append(f"{name}_source {src.value!r} requires {name} = {defaults[src]:g}, got {values}")


def _check_slope_radius(output: NLOutput, params: dict[str, Any], problems: list[str]) -> None:
    slopes, radii = _values(params, SLOPE_KEYS), _values(params, RADIUS_KEYS)
    _check_default_value(
        "slope", output.slope_source, {SlopeSource.safe_default: SAFE_MAX_SLOPE_DEG}, slopes, problems
    )
    radius_defaults = {src: value for src, (value, _) in RADIUS_DEFAULTS.items()}
    _check_default_value("radius", output.radius_source, radius_defaults, radii, problems)


def _site_ids(value: Any) -> list[str]:
    """Every `{"site_id": ...}` reference in the (unresolved) params."""
    if isinstance(value, dict):
        if set(value) == {"site_id"}:
            return [str(value["site_id"])]
        return [i for v in value.values() for i in _site_ids(v)]
    if isinstance(value, list):
        return [i for v in value for i in _site_ids(v)]
    return []


def _check_site(output: NLOutput, ctx: NLContext, problems: list[str]) -> None:
    if output.site_source != SiteSource.selected_site or output.query is None:
        return
    ids = _site_ids(output.query.params)
    if ctx.selected_site_id is None:
        problems.append("site_source is 'selected_site' but no site is selected")
    elif not ids or any(i != ctx.selected_site_id for i in ids):
        problems.append("site_source 'selected_site' requires the params to use the selected site's id")


def _check_citations(output: NLOutput, ctx: NLContext, problems: list[str]) -> None:
    registry = {d.id: d for d in ctx.datasets}
    for lim in output.limitations:
        for c in lim.citations:
            ds = registry.get(c.dataset_id)
            if ds is None:
                problems.append(f"citation: unknown dataset_id {c.dataset_id!r}")
            elif c.cannot_answer not in ds.cannot_answer:
                problems.append(
                    f"citation: {c.cannot_answer!r} is not a cannot_answer entry of {c.dataset_id!r}"
                )


def resolve_site_refs(params: dict[str, Any], ctx: NLContext) -> dict[str, Any]:
    """Replace every `{"site_id": ...}` with the site's catalog location; raise on unknown ids."""
    problems: list[str] = []
    resolved = _resolve_site_refs(params, {s.id: s for s in ctx.sites}, problems)
    if problems:
        raise NLValidationError(problems)
    return resolved


def normalize_query(query: NLQuery, ctx: NLContext) -> StructuredQuery:
    """Check the operation is in the vocabulary, resolve site ids, and validate `params`
    against the operation's contract request model. Returns the query as the API receives it."""
    op = query.operation
    if op not in ALLOWED_OPERATIONS:
        raise NLValidationError([f"operation {op.value!r} is not in the Core NL vocabulary"])
    params = resolve_site_refs(query.params, ctx)
    try:
        model = OPERATION_PARAMS[op].model_validate(params)
    except ValidationError as e:
        raise NLValidationError(
            [f"params ({op.value}): {err['loc']}: {err['msg']}" for err in e.errors()]
        ) from e
    return StructuredQuery(operation=op, params=model.model_dump(mode="json"))


def validate_output(raw: str | Mapping[str, Any] | NLOutput, ctx: NLContext) -> ValidatedOutput:
    """Validate the LLM's output against the vocabulary, contract and registry; raise on any problem."""
    output = raw if isinstance(raw, NLOutput) else parse_output(raw)
    problems: list[str] = []
    structured: StructuredQuery | None = None

    if output.query is not None:
        try:
            structured = normalize_query(output.query, ctx)
        except NLValidationError as e:
            problems.extend(e.problems)
        else:
            _check_heights(output, structured.params, ctx, problems)
            _check_windows(output, structured.params, ctx, problems)
            _check_slope_radius(output, structured.params, problems)
            _check_site(output, ctx, problems)
    else:
        for name in ("height_source", "window_source", "slope_source", "radius_source", "site_source"):
            if getattr(output, name).value != "not_applicable":
                problems.append(f"{name} is set but there is no query")

    _check_citations(output, ctx, problems)
    if problems:
        raise NLValidationError(problems)

    # Every disclosure is built here, never by the model (nl-output-6): the selected site, the default
    # window, proxy/default heights, then the "nearby" / "around" radius. The "safe" slope disclosure
    # needs the terrain data the slope is measured on, which comes with the engine's result: `to_response`
    # adds it.
    assumptions: list[str] = []
    if output.radius_source in RADIUS_DEFAULTS:
        assumptions.insert(0, RADIUS_DEFAULTS[output.radius_source][1])
    if output.height_source in PROXY_ASSUMPTION_TEXT:
        assumptions.insert(0, PROXY_ASSUMPTION_TEXT[output.height_source])
    if output.window_source == WindowSource.default and structured is not None:
        start = _windows(structured.params)[0][0]
        assumptions.insert(0, default_window_text(start.date().isoformat()))
    if output.site_source == SiteSource.selected_site:
        site = next(s for s in ctx.sites if s.id == ctx.selected_site_id)
        assumptions.insert(0, selected_site_text(display_name(site)))
    return ValidatedOutput(output=output, structured_query=structured, assumptions=assumptions)


# --------------------------------------------------------------- to the contract


def _fragment(text: str) -> str:
    """A registry `cannot_answer` entry as part of a sentence: no final period; first letter lower case
    unless the word is an acronym or name (second letter upper case or not a letter)."""
    text = text.strip().rstrip(".")
    if len(text) > 1 and text[0].isupper() and text[1].islower():
        text = text[0].lower() + text[1:]
    return text


def _reason(topic: str, citations: Sequence[tuple[DatasetCapability, str]]) -> str:
    """One sentence (stream B, 2026-11-16; wording Claude-drafted, approved by the project author):
    "<topic>: not answerable with the available data and tools, which don't cover <a>, <b> or <c>."
    The registry entries cited are in `Limitation.datasets_considered`, so sources aren't repeated here."""
    parts = list(dict.fromkeys(_fragment(text) for _, text in citations))
    listed = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " or " + parts[-1]
    lead = topic.strip().rstrip(".")
    return f"{lead}: not answerable with the available data and tools, which don't cover {listed}."


def to_limitations(output: NLOutput, ctx: NLContext) -> list[Limitation]:
    """Contract `Limitation`s with reason text built from the registry entries cited."""
    registry = {d.id: d for d in ctx.datasets}
    result = []
    for lim in output.limitations:
        cited = [(registry[c.dataset_id], c.cannot_answer) for c in lim.citations]
        ids = list(dict.fromkeys(c.dataset_id for c in lim.citations))
        result.append(Limitation(reason=_reason(lim.topic, cited), datasets_considered=ids))
    return result


def _all_assumptions(
    validated: ValidatedOutput, slope_terrain: str | None, slope_measured: bool = True
) -> list[str]:
    assumptions = list(validated.assumptions)
    if validated.output.slope_source == SlopeSource.safe_default:
        if not slope_measured:
            assumptions.insert(0, SAFE_NOT_MEASURED_TEXT)
            return assumptions
        if not slope_terrain:
            raise NLValidationError(
                [
                    "'safe' was read as the default slope limit: name the terrain data the slope is "
                    "measured on (slope_terrain), so the echo states it"
                ]
            )
        assumptions.insert(0, safe_slope_text(slope_terrain))
    return assumptions


def to_response(
    validated: ValidatedOutput,
    ctx: NLContext,
    slope_terrain: str | None = None,
    slope_measured: bool = True,
) -> NLAnswer | NLUnsupported | NLClarification:
    """Build the contract response. `result` stays None: the engine fills it, never the LLM.

    The disclosures go in `NLAnswer.assumptions` (contract 0.7.0, gap C8), shown with the echo.
    `slope_terrain` names the terrain data the slope was measured on; it is required when "safe" was
    read as the default slope limit (D-safe). It comes from the engine's result (the terrain layer the
    slope was computed on), so a "safe" query is only answered once that result exists.
    `slope_measured=False`: the operation could not run (not available yet), so no slope was measured
    and the disclosure says so instead of naming terrain data.
    """
    out = validated.output
    interpretation = out.interpretation.strip()
    if out.outcome == Outcome.clarify:
        assert out.question is not None
        return NLClarification(interpretation=interpretation, question=out.question.strip())
    limitations = to_limitations(out, ctx)
    if out.outcome == Outcome.unsupported:
        ids = list(dict.fromkeys(i for lim in limitations for i in lim.datasets_considered))
        merged = Limitation(reason=" ".join(lim.reason for lim in limitations), datasets_considered=ids)
        return NLUnsupported(unsupported=merged, interpretation=interpretation)
    assert validated.structured_query is not None
    return NLAnswer(
        interpretation=interpretation,
        structured_query=validated.structured_query,
        result=None,
        limitations=limitations,
        assumptions=[a.strip() for a in _all_assumptions(validated, slope_terrain, slope_measured)],
    )
