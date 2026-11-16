"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

The schema the LLM fills (step 4.3). Internal to `lss.nl`; `lss.nl.validate` turns a
validated `NLOutput` into the contract's `NLAnswer` / `NLUnsupported`.

Design rules (plan section 4.5):
- The LLM never computes numbers. It transcribes the user's values (dates, heights,
  thresholds) into a structured query; the engine computes.
- Curated sites are referenced by id (`{"site_id": ...}`), never by coordinates the
  LLM supplies; `lss.nl.validate` substitutes the site's catalog location.
- Every limitation cites a registry entry (`dataset_id` + an exact `cannot_answer`
  string), so refusal reasons come from `datasets.yaml`, not from the model.
"""

from __future__ import annotations

import copy
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from lss.contract import Model, Operation
from lss.nl.vocabulary import OPERATION_PARAMS, HeightSource, RadiusSource, SlopeSource, WindowSource

SCHEMA_VERSION = "nl-output-5"


class Outcome(StrEnum):
    answer = "answer"  # fully answerable by the structured query
    partial = "partial"  # structured query answers part; limitations explain the rest
    unsupported = "unsupported"  # nothing answerable; limitations explain why
    clarify = "clarify"  # can't proceed until the user says more (e.g. which site); `question` asks


class SiteRef(Model):
    """Stands in for a `Location` anywhere one is expected: a curated site, by id."""

    site_id: str = Field(min_length=1)


class RegistryCitation(Model):
    dataset_id: str = Field(description="Registry dataset id")
    cannot_answer: str = Field(description="One `cannot_answer` entry of that dataset, verbatim")


class NLLimitation(Model):
    topic: str = Field(min_length=1, description="The part of the request that is not answered")
    citations: list[RegistryCitation] = Field(min_length=1)


class NLQuery(Model):
    operation: Operation
    params: dict[str, Any] = Field(default_factory=dict)


class NLOutput(Model):
    outcome: Outcome
    interpretation: str = Field(min_length=1, description="Plain-language echo of the request")
    query: NLQuery | None = None
    height_source: HeightSource = HeightSource.not_applicable
    window_source: WindowSource = WindowSource.not_applicable
    slope_source: SlopeSource = SlopeSource.not_applicable
    radius_source: RadiusSource = RadiusSource.not_applicable
    assumptions: list[str] = Field(
        default_factory=list, description="Defaults or readings the user didn't state, e.g. an assumed date"
    )
    limitations: list[NLLimitation] = Field(default_factory=list)
    question: str | None = Field(default=None, description="For outcome 'clarify': what to ask the user")

    @model_validator(mode="after")
    def _consistent(self) -> NLOutput:
        if self.outcome == Outcome.clarify:
            if self.query is not None or self.limitations:
                raise ValueError("a clarify outcome has no query and no limitations")
            if not (self.question or "").strip():
                raise ValueError("a clarify outcome needs a question")
            return self
        if self.question is not None:
            raise ValueError("only a clarify outcome has a question")
        if self.outcome == Outcome.unsupported:
            if self.query is not None:
                raise ValueError("an unsupported outcome has no query")
            if not self.limitations:
                raise ValueError("an unsupported outcome needs at least one limitation")
        else:
            if self.query is None:
                raise ValueError(f"outcome {self.outcome.value!r} needs a query")
            if self.outcome == Outcome.answer and self.limitations:
                raise ValueError("an answer has no limitations (use outcome 'partial')")
            if self.outcome == Outcome.partial and not self.limitations:
                raise ValueError("a partial outcome needs at least one limitation")
        return self


# ------------------------------------------------------------------ JSON schema


def _merge_defs(into: dict[str, Any], defs: dict[str, Any]) -> None:
    for name, schema in defs.items():
        if name in into and into[name] != schema:
            raise ValueError(f"conflicting JSON schema definitions for {name!r}")
        into[name] = schema


def llm_json_schema() -> dict[str, Any]:
    """JSON schema for the LLM's output, with `query.params` typed per operation.

    The per-operation `params` schemas come from the contract request models; the only
    change is that every `Location` may also be a `SiteRef`.
    """
    schema = copy.deepcopy(NLOutput.model_json_schema())
    defs: dict[str, Any] = schema.setdefault("$defs", {})
    defs.pop("NLQuery", None)

    variants = []
    for op, model in sorted(OPERATION_PARAMS.items(), key=lambda kv: kv[0].value):
        params = copy.deepcopy(model.model_json_schema())
        _merge_defs(defs, params.pop("$defs", {}))
        params_name = f"{model.__name__}"
        _merge_defs(defs, {params_name: params})
        variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "operation": {"const": op.value},
                    "params": {"$ref": f"#/$defs/{params_name}"},
                },
                "required": ["operation", "params"],
            }
        )
    schema["properties"]["query"] = {"anyOf": [*variants, {"type": "null"}], "default": None}

    if "Location" in defs:
        defs["LocationCoords"] = defs.pop("Location")
        _merge_defs(defs, {"SiteRef": SiteRef.model_json_schema()})
        defs["Location"] = {
            "anyOf": [{"$ref": "#/$defs/LocationCoords"}, {"$ref": "#/$defs/SiteRef"}],
            "description": "Coordinates for a custom point, or a curated site by id",
        }
    schema["title"] = "NLOutput"
    schema["x-schema-version"] = SCHEMA_VERSION
    return schema


# ------------------------------------------------------- two-step call (route, fill)
#
# One structured-output schema covering all eight operations is too large for the API to
# compile ("compiled grammar is too large", measured 2026-11-15), and strict tools hit the
# optional/union parameter limits. So the model answers in two calls, each with a small schema:
#   1. route: outcome, operation (or none), and any registry-cited limitations;
#   2. fill (only when there is an operation): that operation's params, the
#      height/window/slope/radius sources, and the interpretation, so the echo comes from the
#      call that wrote the params.
# `lss.nl.interpret` combines them into an `NLOutput`, which `lss.nl.validate` checks as before.


class NLRoute(Model):
    outcome: Outcome
    operation: Operation | None = None
    interpretation: str = Field(min_length=1)
    limitations: list[NLLimitation] = Field(default_factory=list)
    question: str | None = Field(default=None, description="For outcome 'clarify': what to ask the user")


class NLFill(Model):
    interpretation: str = Field(min_length=1, description="Plain-language echo of the query as filled")
    params: dict[str, Any]
    height_source: HeightSource = HeightSource.not_applicable
    window_source: WindowSource = WindowSource.not_applicable
    slope_source: SlopeSource = SlopeSource.not_applicable
    radius_source: RadiusSource = RadiusSource.not_applicable
    assumptions: list[str] = Field(default_factory=list)


def _refs(node: Any) -> set[str]:
    if isinstance(node, dict):
        found = {node["$ref"].rsplit("/", 1)[-1]} if "$ref" in node else set()
        return found.union(*(_refs(v) for v in node.values()))
    if isinstance(node, list):
        return set().union(*(_refs(v) for v in node))
    return set()


def _prune_defs(schema: dict[str, Any]) -> dict[str, Any]:
    """Drop `$defs` the schema doesn't reach: the API compiles every definition."""
    defs = schema.get("$defs", {})
    keep: set[str] = set()
    todo = list(_refs({k: v for k, v in schema.items() if k != "$defs"}))
    while todo:
        name = todo.pop()
        if name not in keep:
            keep.add(name)
            todo.extend(_refs(defs[name]))
    schema["$defs"] = {k: v for k, v in defs.items() if k in keep}
    return schema


def _formats_to_descriptions(node: Any) -> Any:
    """String formats enlarge the compiled grammar; state them in the description instead
    (`lss.nl.validate` enforces them through the contract models)."""
    if isinstance(node, dict):
        node = {k: _formats_to_descriptions(v) for k, v in node.items()}
        fmt = node.pop("format", None)
        if fmt is not None:
            hint = {
                "date-time": "ISO 8601 date-time in UTC, e.g. 2028-11-15T00:00:00Z",
                "duration": "ISO 8601 duration, e.g. PT1H",
            }.get(fmt, f"format {fmt}")
            node["description"] = f"{node['description']} ({hint})" if node.get("description") else hint
        return node
    if isinstance(node, list):
        return [_formats_to_descriptions(v) for v in node]
    return node


def _site_ref_locations(defs: dict[str, Any]) -> None:
    if "Location" in defs:
        defs["LocationCoords"] = defs.pop("Location")
        _merge_defs(defs, {"SiteRef": SiteRef.model_json_schema()})
        defs["Location"] = {
            "anyOf": [{"$ref": "#/$defs/LocationCoords"}, {"$ref": "#/$defs/SiteRef"}],
            "description": "Coordinates for a custom point, or a curated site by id",
        }


def route_json_schema() -> dict[str, Any]:
    schema = copy.deepcopy(NLRoute.model_json_schema())
    allowed = sorted(op.value for op in OPERATION_PARAMS)
    schema["properties"]["operation"] = {
        "anyOf": [{"type": "string", "enum": allowed}, {"type": "null"}],
        "default": None,
        "description": "The one operation that answers the request (or its answerable part); null if none",
    }
    schema["x-schema-version"] = SCHEMA_VERSION
    return _prune_defs(schema)


def fill_json_schema(op: Operation) -> dict[str, Any]:
    schema = copy.deepcopy(NLFill.model_json_schema())
    defs: dict[str, Any] = schema.setdefault("$defs", {})
    model = OPERATION_PARAMS[op]
    params = copy.deepcopy(model.model_json_schema())
    _merge_defs(defs, params.pop("$defs", {}))
    _merge_defs(defs, {model.__name__: params})
    schema["properties"]["params"] = {"$ref": f"#/$defs/{model.__name__}"}
    _site_ref_locations(defs)
    schema["x-schema-version"] = SCHEMA_VERSION
    return _prune_defs(_formats_to_descriptions(schema))
