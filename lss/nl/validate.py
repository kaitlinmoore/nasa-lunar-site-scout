"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Validation of the LLM's output (step 4.3), and conversion to the contract's NL responses.

`validate_output` rejects anything the contract wouldn't accept:
- the schema itself (`NLOutput`: unknown fields, inconsistent outcome);
- operations outside the Core NL vocabulary;
- `params` that the operation's contract request model rejects (after site ids are
  replaced by catalog locations);
- unit heights that don't match the declared `height_source` (proxy heights must be
  exactly the proxy value);
- limitations whose citations aren't in the dataset capability registry.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from lss.config import FIXTURES_DIR
from lss.contract import (
    DatasetCapability,
    Limitation,
    NLAnswer,
    NLUnsupported,
    Scenario,
    Site,
    SitesResponse,
    StructuredQuery,
)
from lss.nl.schema import NLOutput, Outcome, SiteRef
from lss.nl.vocabulary import (
    ALLOWED_OPERATIONS,
    OPERATION_PARAMS,
    PROXY_ASSUMPTION_TEXT,
    UNIT_HEIGHT_PROXIES_M,
    HeightSource,
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


def default_context(
    selected_site_id: str | None = None, selected_scenario: Scenario | None = None
) -> NLContext:
    """Context from the committed site list (`fixtures/sites.json`) and the registry.

    Phase 1 only: from C7b the site list comes from the API's site catalog instead.
    """
    data = json.loads((FIXTURES_DIR / "sites.json").read_text(encoding="utf-8"))
    return NLContext(
        sites=SitesResponse.model_validate(data).sites,
        datasets=load_datasets(),
        selected_site_id=selected_site_id,
        selected_scenario=selected_scenario,
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


def validate_output(raw: str | Mapping[str, Any] | NLOutput, ctx: NLContext) -> ValidatedOutput:
    """Validate the LLM's output against the vocabulary, contract and registry; raise on any problem."""
    output = raw if isinstance(raw, NLOutput) else parse_output(raw)
    problems: list[str] = []
    structured: StructuredQuery | None = None

    if output.query is not None:
        op = output.query.operation
        if op not in ALLOWED_OPERATIONS:
            problems.append(f"operation {op.value!r} is not in the Core NL vocabulary")
        else:
            sites = {s.id: s for s in ctx.sites}
            params = _resolve_site_refs(output.query.params, sites, problems)
            _check_heights(output, params, ctx, problems)
            try:
                model = OPERATION_PARAMS[op].model_validate(params)
            except ValidationError as e:
                problems.extend(f"params ({op.value}): {err['loc']}: {err['msg']}" for err in e.errors())
            else:
                structured = StructuredQuery(
                    operation=op, params=model.model_dump(mode="json", exclude_none=False)
                )
    elif output.height_source != HeightSource.not_applicable:
        problems.append("height_source is set but there is no query")

    _check_citations(output, ctx, problems)
    if problems:
        raise NLValidationError(problems)

    assumptions = list(output.assumptions)
    if output.height_source in PROXY_ASSUMPTION_TEXT:
        assumptions.insert(0, PROXY_ASSUMPTION_TEXT[output.height_source])
    return ValidatedOutput(output=output, structured_query=structured, assumptions=assumptions)


# --------------------------------------------------------------- to the contract


def _reason(topic: str, citations: Sequence[tuple[DatasetCapability, str]]) -> str:
    parts = "; ".join(f"{ds.name} can't answer: {text}" for ds, text in citations)
    return f"{topic.rstrip('.')}. Not answerable with the available data, because {parts}."


def to_limitations(output: NLOutput, ctx: NLContext) -> list[Limitation]:
    """Contract `Limitation`s with reason text built from the registry entries cited."""
    registry = {d.id: d for d in ctx.datasets}
    result = []
    for lim in output.limitations:
        cited = [(registry[c.dataset_id], c.cannot_answer) for c in lim.citations]
        ids = list(dict.fromkeys(c.dataset_id for c in lim.citations))
        result.append(Limitation(reason=_reason(lim.topic, cited), datasets_considered=ids))
    return result


def interpretation_text(validated: ValidatedOutput) -> str:
    """The echo shown to the user.

    Assumptions are appended here until the contract has a field for them (contract gap C8, Phase 2).
    """
    text = validated.output.interpretation.strip()
    if validated.assumptions:
        text += " Assumed: " + " ".join(a.strip() for a in validated.assumptions)
    return text


def to_response(validated: ValidatedOutput, ctx: NLContext) -> NLAnswer | NLUnsupported:
    """Build the contract response. `result` stays None: the engine fills it, never the LLM."""
    limitations = to_limitations(validated.output, ctx)
    if validated.output.outcome == Outcome.unsupported:
        ids = list(dict.fromkeys(i for lim in limitations for i in lim.datasets_considered))
        merged = Limitation(reason=" ".join(lim.reason for lim in limitations), datasets_considered=ids)
        return NLUnsupported(unsupported=merged)
    assert validated.structured_query is not None
    return NLAnswer(
        interpretation=interpretation_text(validated),
        structured_query=validated.structured_query,
        result=None,
        limitations=limitations,
    )
