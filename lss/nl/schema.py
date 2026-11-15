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
from lss.nl.vocabulary import OPERATION_PARAMS, HeightSource

SCHEMA_VERSION = "nl-output-1"


class Outcome(StrEnum):
    answer = "answer"  # fully answerable by the structured query
    partial = "partial"  # structured query answers part; limitations explain the rest
    unsupported = "unsupported"  # nothing answerable; limitations explain why


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
    assumptions: list[str] = Field(
        default_factory=list, description="Defaults or readings the user didn't state, e.g. an assumed date"
    )
    limitations: list[NLLimitation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> NLOutput:
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
