"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

LLM provider interface (plan section 4.5: thin and swappable, e.g. NVIDIA NIM later).

A provider turns an `NLPrompt` into raw text that should be JSON matching
`lss.nl.schema.llm_json_schema()`. It does no validation: `lss.nl.validate` does.
Providers run server-side only. Unit tests use `FakeProvider` (no network).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class NLPrompt:
    system: str
    user: str
    json_schema: dict[str, Any]
    prompt_version: str
    meta: dict[str, Any] = field(default_factory=dict)  # e.g. the raw request text, for fakes


class Provider(Protocol):
    name: str
    model: str

    def complete(self, prompt: NLPrompt) -> str:
        """Return the model's raw output text (expected to be JSON)."""
        ...


class FakeProvider:
    """Returns canned outputs keyed by the request text; no network calls.

    `responses` maps request text -> output (dict, serialized to JSON, or a raw string).
    Alternatively pass `respond`, a function of the prompt.
    """

    name = "fake"

    def __init__(
        self,
        responses: Mapping[str, Any] | None = None,
        respond: Callable[[NLPrompt], Any] | None = None,
        model: str = "fake-1",
    ):
        self.responses = dict(responses or {})
        self.respond = respond
        self.model = model
        self.calls: list[NLPrompt] = []

    def complete(self, prompt: NLPrompt) -> str:
        self.calls.append(prompt)
        if self.respond is not None:
            out = self.respond(prompt)
        else:
            text = prompt.meta.get("text")
            if text not in self.responses:
                raise KeyError(f"FakeProvider has no response for {text!r}")
            out = self.responses[text]
        return out if isinstance(out, str) else json.dumps(out)
