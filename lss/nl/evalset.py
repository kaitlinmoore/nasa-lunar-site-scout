"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Loader for the NL eval set (`tests/nl/eval_set.yaml`, step 4.4).
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from lss.config import REPO_ROOT
from lss.contract import Model
from lss.nl.schema import NLQuery, Outcome, RegistryCitation
from lss.nl.vocabulary import HeightSource, WindowSource

EVAL_SET_PATH = REPO_ROOT / "tests" / "nl" / "eval_set.yaml"

# `blocked_on` id prefix -> label. Contract gaps are held until Phase 2 (this stream owns the
# contract then); registry requests go to stream A as one batch after its C1 work merges.
BLOCKER_KINDS: tuple[tuple[str, str], ...] = (
    ("C", "blocked on contract"),
    ("G-R", "blocked on registry"),
    ("D-", "blocked on a default (project author's decision)"),
)


class Source(StrEnum):
    kaitlin = "kaitlin"  # the project author's queries and labels
    si_supplied = "si_supplied"  # Claude-drafted, approved by the project author


class Split(StrEnum):
    dev = "dev"  # used for prompt tuning
    holdout = "holdout"  # never used for tuning; scored separately


class ItemStatus(StrEnum):
    ready = "ready"
    blocked = "blocked"


class EvalContext(Model):
    selected_site_id: str | None = None


class Expected(Model):
    outcome: Outcome
    query: NLQuery | None = None
    params_match: Literal["exact", "subset"] = "exact"
    height_source: HeightSource | None = None
    window_source: WindowSource | None = None
    citations: list[RegistryCitation] = Field(default_factory=list)
    citations_optional: list[RegistryCitation] = Field(default_factory=list)


class EvalItem(Model):
    id: str
    source: Source
    split: Split = Split.dev
    text: str = Field(min_length=1)
    context: EvalContext = Field(default_factory=EvalContext)
    target: str
    status: ItemStatus
    blocked_on: list[str] = Field(default_factory=list)
    expected: Expected | None = None
    notes: str | None = None

    @property
    def blocked_reasons(self) -> list[str]:
        """Human-readable blocker kinds, e.g. ["blocked on contract", "blocked on registry"]."""
        kinds = []
        for prefix, label in BLOCKER_KINDS:
            if any(b.startswith(prefix) for b in self.blocked_on):
                kinds.append(label)
        return kinds

    @model_validator(mode="after")
    def _status(self) -> EvalItem:
        if self.status == ItemStatus.ready:
            if self.blocked_on:
                raise ValueError(f"{self.id}: a ready item has no blocked_on")
            if self.expected is None:
                raise ValueError(f"{self.id}: a ready item needs expected")
            if self.expected.outcome != Outcome.unsupported and self.expected.query is None:
                raise ValueError(f"{self.id}: a ready answer/partial item needs expected.query")
            if self.expected.outcome != Outcome.answer and not self.expected.citations:
                raise ValueError(f"{self.id}: a ready partial/unsupported item needs citations")
        elif not self.blocked_on:
            raise ValueError(f"{self.id}: a blocked item must say what it is blocked on")
        return self


class EvalSet(Model):
    version: int
    reference_date: date
    items: list[EvalItem] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> EvalSet:
        ids = [i.id for i in self.items]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate eval item ids: {dupes}")
        return self


def load_eval_set(path: Path = EVAL_SET_PATH) -> EvalSet:
    return EvalSet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def label_output(item: EvalItem) -> dict | None:
    """The NL output a perfect model would return for this label, or None if the label is incomplete
    (no `expected`, or `params_match: subset`). Used by the oracle provider and label self-checks."""
    exp = item.expected
    if exp is None or exp.params_match == "subset":
        return None
    out: dict = {
        "outcome": exp.outcome.value,
        "interpretation": item.text,
        "height_source": (exp.height_source or HeightSource.not_applicable).value,
        "window_source": (exp.window_source or WindowSource.not_applicable).value,
    }
    if exp.query is not None:
        out["query"] = exp.query.model_dump(mode="json")
    if exp.outcome != Outcome.answer:
        cites = [c.model_dump() for c in exp.citations]
        out["limitations"] = [{"topic": item.text, "citations": cites}]
    return out
