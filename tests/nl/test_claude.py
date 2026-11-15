# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Claude provider (step 4.6) against a stand-in client: no network calls, no API key needed."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from lss.nl.claude import FALLBACK_BETA, ClaudeProvider, ProviderError, api_schema
from lss.nl.prompt import build_prompt
from lss.nl.validate import default_context, validate_output

OUTPUT = {
    "outcome": "answer",
    "interpretation": "Terrain data at 85 S, 30 E.",
    "query": {"operation": "locate", "params": {"lat": -85.0, "lon": 30.0}},
}


OUTPUT_TEXT = json.dumps(OUTPUT)


def response(stop_reason="end_turn", text=OUTPUT_TEXT, model="claude-opus-5-5"):
    content = [SimpleNamespace(type="thinking", thinking="")]
    if text is not None:
        content.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(
        model=model,
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        content=content,
        usage=SimpleNamespace(input_tokens=4000, output_tokens=300),
        _request_id="req_test",
    )


class StandInClient:
    def __init__(self, resp):
        self.calls: list[tuple[str, dict]] = []
        outer = self

        class _Messages:
            def __init__(self, kind):
                self.kind = kind

            def create(self, **kwargs):
                outer.calls.append((self.kind, kwargs))
                return resp

        self.messages = _Messages("messages")
        self.beta = SimpleNamespace(messages=_Messages("beta"))


def prompt():
    return build_prompt("What terrain data covers 85 S, 30 E?", default_context(), date(2026, 11, 15))


def test_request_shape_with_fallbacks():
    client = StandInClient(response())
    provider = ClaudeProvider("claude-opus-5-5", effort="low", client=client)
    text = provider.complete(prompt())
    kind, kwargs = client.calls[0]
    assert kind == "beta" and kwargs["betas"] == [FALLBACK_BETA] and kwargs["fallbacks"] == "default"
    assert kwargs["output_config"]["effort"] == "low"
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert "thinking" not in kwargs and "temperature" not in kwargs
    assert validate_output(text, default_context()).structured_query.params == {"lat": -85.0, "lon": 30.0}
    assert provider.last_meta["served_by"] == "claude-opus-5-5"
    assert provider.last_meta["request_id"] == "req_test"


def test_haiku_has_no_server_side_fallback():
    client = StandInClient(response(model="claude-haiku-5-5"))
    ClaudeProvider("claude-haiku-5-5", client=client).complete(prompt())
    kind, kwargs = client.calls[0]
    assert kind == "messages" and "fallbacks" not in kwargs


def test_served_by_records_a_fallback_model():
    client = StandInClient(response(model="claude-opus-4-8"))
    provider = ClaudeProvider("claude-opus-5-5", client=client)
    provider.complete(prompt())
    assert provider.last_meta["served_by"] == "claude-opus-4-8"


@pytest.mark.parametrize(
    ("resp", "match"),
    [
        (response(stop_reason="refusal"), "refusal"),
        (response(stop_reason="max_tokens"), "truncated"),
        (response(text=None), "no text block"),
    ],
)
def test_unusable_responses_raise(resp, match):
    with pytest.raises(ProviderError, match=match):
        ClaudeProvider("claude-opus-5-5", client=StandInClient(resp)).complete(prompt())


def test_api_schema_drops_unsupported_constraints():
    sent = json.dumps(api_schema(prompt().json_schema))
    assert '"minimum"' not in sent and '"exclusiveMinimum"' not in sent and '"oneOf"' not in sent
    assert "x-schema-version" not in sent


def test_missing_key_fails_before_any_call(monkeypatch):
    from lss import config

    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(anthropic_api_key=None))
    monkeypatch.setattr("lss.nl.claude.get_settings", config.get_settings)
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        ClaudeProvider("claude-opus-5-5")
