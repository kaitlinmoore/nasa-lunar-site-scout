"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Claude provider for the NL layer (step 4.6). Server-side only; the key comes from
`get_settings().anthropic_api_key` and never reaches the browser.

- Structured outputs: `output_config.format` with the NL schema, passed through
  `anthropic.transform_schema` (the API doesn't accept numeric/length constraints;
  `lss.nl.validate` enforces them in code).
- Thinking can't be turned off on current models; `effort` controls depth and cost.
- Refusal fallback: on models that support it, the server-side fallback beta re-runs a
  safety-declined request on another model (`fallbacks="default"`). The model that
  actually answered is recorded in `last_meta["served_by"]`, so eval results stay honest.
"""

from __future__ import annotations

from typing import Any

import anthropic

from lss.config import get_settings
from lss.nl.provider import NLPrompt

FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Models that accept server-side `fallbacks` (Haiku 5.5 doesn't).
FALLBACK_MODELS = frozenset({"claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-2"})


class ProviderError(RuntimeError):
    """The model didn't return a usable answer (refusal, truncation, no text)."""


def api_schema(json_schema: dict[str, Any]) -> dict[str, Any]:
    """The NL schema in the form the structured-outputs API accepts."""
    schema = {k: v for k, v in json_schema.items() if not k.startswith("x-")}
    return anthropic.transform_schema(schema)


class ClaudeProvider:
    name = "claude"

    def __init__(
        self,
        model: str,
        effort: str = "low",
        fallbacks: bool = True,
        max_tokens: int = 16000,
        client: Any = None,
    ):
        self.model = model
        self.effort = effort
        self.fallbacks = fallbacks and model in FALLBACK_MODELS
        self.max_tokens = max_tokens
        if client is None:
            key = get_settings().anthropic_api_key
            if not key:
                raise ProviderError("ANTHROPIC_API_KEY is not set (see lss.config for the .env lookup)")
            client = anthropic.Anthropic(api_key=key)
        self.client = client
        self.last_meta: dict[str, Any] = {}

    def complete(self, prompt: NLPrompt) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": prompt.system,
            "messages": [{"role": "user", "content": prompt.user}],
            "output_config": {
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": api_schema(prompt.json_schema)},
            },
        }
        if self.fallbacks:
            response = self.client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
        else:
            response = self.client.messages.create(**kwargs)

        usage = getattr(response, "usage", None)
        self.last_meta = {
            "served_by": getattr(response, "model", self.model),
            "stop_reason": response.stop_reason,
            "request_id": getattr(response, "_request_id", None),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        }
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise ProviderError(f"refusal (category {getattr(details, 'category', None)})")
        if response.stop_reason == "max_tokens":
            raise ProviderError("output truncated at max_tokens")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise ProviderError("no text block in the response")
        return text
