# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""POST /api/nl (C7b): fake providers only, no network calls."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import lss.api.app as app_module
from lss.api import nl
from lss.config import get_settings
from lss.contract import (
    CONTRACT_VERSION,
    NL_MAX_TEXT_CHARS,
    NLAnswer,
    NLClarification,
    NLUnsupported,
    RateLimitedError,
    UnavailableError,
)
from lss.contract.export import build_openapi
from lss.nl.claude import ProviderError
from lss.nl.provider import FakeProvider
from lss.nl.vocabulary import PROXY_ASSUMPTION_TEXT, SAFE_NOT_MEASURED_TEXT, HeightSource
from tests.api.test_thin_slice import WEB_SCENARIO, write_served

SITE = {"site_id": "pgda-site01"}
TODAY = date(2026, 11, 15)

SERVED_METRICS = {
    "outcome": "answer",
    "interpretation": "Power and Earth-visibility metrics at Connecting ridge, 1 m, 15 May - 14 Jun 2028.",
    "query": {
        "operation": "metrics",
        "params": {
            "scenario": {
                "location": SITE,
                "unit_height_m": 1.0,
                "window_start": WEB_SCENARIO["window_start"],
                "window_end": WEB_SCENARIO["window_end"],
            }
        },
    },
    "height_source": "user",
    "window_source": "user",
}
DEFAULT_METRICS = {
    "outcome": "answer",
    "interpretation": "Power metrics at Connecting ridge.",
    "query": {
        "operation": "metrics",
        "params": {
            "scenario": {
                "location": SITE,
                "unit_height_m": 5.0,
                "window_start": "2026-11-15T00:00:00Z",
                "window_end": "2026-12-15T00:00:00Z",
            }
        },
    },
    "height_source": "default",
    "window_source": "default",
}
REFUSAL = {
    "outcome": "unsupported",
    "interpretation": "Boulders in a landing ellipse.",
    "limitations": [
        {
            "topic": "Boulders",
            "citations": [
                {
                    "dataset_id": "aussel_2025_boulders",
                    "cannot_answer": "Any boulder information at the poles",
                }
            ],
        }
    ],
}
CLARIFY = {
    "outcome": "clarify",
    "interpretation": "A site summary; no site selected.",
    "question": "Which site?",
}
PROXIMITY = {
    "outcome": "answer",
    "interpretation": "Craters within 5 km of Connecting ridge.",
    "query": {
        "operation": "proximity",
        "params": {"location": SITE, "types": ["crater"], "radius_m": 5000.0},
    },
    "radius_source": "user",
}
SAFE_SEARCH = {
    "outcome": "answer",
    "interpretation": "Safe terrain anywhere the data covers.",
    "query": {"operation": "search", "params": {"area": {"kind": "all"}, "criteria": {"max_slope_deg": 5.0}}},
    "slope_source": "safe_default",
}
OUTPUTS = {
    "served": SERVED_METRICS,
    "default": DEFAULT_METRICS,
    "boulders": REFUSAL,
    "summary": CLARIFY,
    "craters": PROXIMITY,
    "safe": SAFE_SEARCH,
    "nonsense": {"outcome": "answer", "interpretation": "x", "query": {"operation": "metrics", "params": {}}},
}


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)

    def __call__(self):
        return self.now


class PricedFake(FakeProvider):
    """A fake that reports Opus token usage, so the spend cap can be tested ($0.40 per call)."""

    def complete(self, prompt):
        out = super().complete(prompt)
        self.last_meta = {"served_by": "claude-opus-5-5", "input_tokens": 100_000, "output_tokens": 0}
        return out


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    app_module._served.cache_clear()
    write_served(tmp_path / "cache" / "served")
    clock = Clock()
    fake = FakeProvider(OUTPUTS)

    def make(provider=fake, cache=None, cap=2.0, factory=None):
        service = nl.NLService(
            executors=app_module.NL_EXECUTORS,
            provider_factory=factory or (lambda: provider),
            limiter=nl.RateLimiter(5, 30, clock),
            meter=nl.SpendMeter(cap, clock),
            cache=cache or {},
            today=lambda: TODAY,
        )
        app = app_module.create_app()
        app.dependency_overrides[app_module.get_nl_service] = lambda: service
        return TestClient(app), service

    yield make, clock
    get_settings.cache_clear()
    app_module._served.cache_clear()


def ask(client, text, site="pgda-site01", ip="203.0.113.7"):
    body = {"text": text} | ({"selected_site_id": site} if site else {})
    return client.post("/api/nl", json=body, headers={"X-Forwarded-For": ip})


def test_served_scenario_gets_the_engine_result(setup):
    client, _ = setup[0]()
    r = ask(client, "served")
    assert r.status_code == 200
    body = NLAnswer.model_validate(r.json())
    assert body.result["_placeholder"] is False and body.result["scenario_key"] == "00010cfa5fef681c"
    assert body.limitations == [] and body.contract_version == CONTRACT_VERSION


def test_unserved_scenario_is_a_limitation_with_the_echo_and_disclosures(setup):
    client, _ = setup[0]()
    body = NLAnswer.model_validate(ask(client, "default").json())
    assert body.result is None
    assert body.limitations[-1].reason == app_module.NOT_SERVED_REASON
    assert PROXY_ASSUMPTION_TEXT[HeightSource.default] in body.assumptions
    assert body.interpretation == "Power metrics at Connecting ridge."


def test_refusal_and_clarification(setup):
    client, _ = setup[0]()
    refusal = NLUnsupported.model_validate(ask(client, "boulders").json())
    assert "boulder" in refusal.unsupported.reason and refusal.interpretation
    clar = NLClarification.model_validate(ask(client, "summary", site=None).json())
    assert clar.question == "Which site?"


def test_operations_without_engine_data_say_not_available_yet(setup):
    client, _ = setup[0]()
    body = NLAnswer.model_validate(ask(client, "craters").json())
    assert body.result is None and body.limitations[-1].reason == nl.NOT_AVAILABLE_YET[nl.Operation.proximity]


def test_safe_without_a_measurement_says_so(setup):
    client, _ = setup[0]()
    body = NLAnswer.model_validate(ask(client, "safe").json())
    assert body.assumptions[0] == SAFE_NOT_MEASURED_TEXT
    assert body.limitations[-1].reason == nl.NOT_AVAILABLE_YET[nl.Operation.search]


def test_invalid_model_output_is_not_understood(setup):
    client, _ = setup[0]()
    body = NLUnsupported.model_validate(ask(client, "nonsense").json())
    assert body.unsupported.reason == nl.NOT_UNDERSTOOD_REASON


def test_rate_limit_per_minute_and_per_day(setup):
    make, clock = setup
    client, _ = make()
    for _ in range(5):
        assert ask(client, "boulders").status_code == 200
    r = ask(client, "boulders")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert RateLimitedError.model_validate(r.json()).detail.reason == nl.RATE_LIMITED_REASON
    assert ask(client, "boulders", ip="198.51.100.1").status_code == 200  # another client
    for _ in range(5):  # 25 more over five minutes: 30 in the day
        clock.now += timedelta(minutes=1)
        for _ in range(5):
            assert ask(client, "boulders").status_code == 200
    clock.now += timedelta(minutes=1)
    assert ask(client, "boulders").status_code == 429  # the day's 30 are used
    clock.now += timedelta(hours=12)  # next UTC day
    assert ask(client, "boulders").status_code == 200


def test_spend_cap_pauses_live_questions_but_not_cached_ones(setup):
    from lss.contract import NLRequest

    cached = NLUnsupported(unsupported={"reason": "cached"}, interpretation="cached")
    cache = {nl.cache_key(NLRequest(text="Example question?", selected_site_id="pgda-site01")): cached}
    client, service = setup[0](provider=PricedFake(OUTPUTS), cache=cache, cap=1.0)
    assert ask(client, "boulders").status_code == 200  # one call (refusal): $0.40
    assert ask(client, "boulders").status_code == 200  # $0.80
    assert ask(client, "boulders").status_code == 200  # $1.20: over the cap after this one
    r = ask(client, "boulders")
    assert r.status_code == 503
    # Cached examples exist here, so the reason says they still work; without them it doesn't (below).
    assert (
        UnavailableError.model_validate(r.json()).detail.reason == nl.PAUSED_REASON + nl.EXAMPLES_STILL_WORK
    )
    assert service.meter.spent == pytest.approx(1.2)
    r = ask(client, "  example QUESTION ")  # normalized text, same selection
    assert r.status_code == 200 and r.json()["unsupported"]["reason"] == "cached"


def test_provider_failure_is_503_with_the_cause_for_developers(setup):
    def broken():
        raise ProviderError("ANTHROPIC_API_KEY is not set")

    client, _ = setup[0](factory=broken)
    r = ask(client, "boulders")
    assert r.status_code == 503
    d = UnavailableError.model_validate(r.json()).detail
    assert d.reason == nl.NL_UNAVAILABLE_REASON and "ANTHROPIC_API_KEY" in d.technical


def test_too_long_a_question_is_rejected(setup):
    client, _ = setup[0]()
    assert ask(client, "x" * (NL_MAX_TEXT_CHARS + 1)).status_code == 422


@pytest.mark.parametrize(
    "header, peer, want",
    [
        ("1.2.3.4", "9.9.9.9", "1.2.3.4"),
        ("6.6.6.6, 1.2.3.4", "9.9.9.9", "1.2.3.4"),
        (None, "9.9.9.9", "9.9.9.9"),
    ],
)
def test_client_address_uses_the_last_forwarded_entry(header, peer, want):
    assert nl.client_address(header, peer) == want


def test_cache_files_load(tmp_path):
    resp = NLClarification(interpretation="i", question="Which site?")
    (tmp_path / "a.json").write_text(
        json.dumps(
            {"request": {"text": "What is here?"}, "response": resp.model_dump(mode="json", by_alias=True)}
        ),
        encoding="utf-8",
    )
    from lss.contract import NLRequest

    cache = nl.load_cache(tmp_path)
    assert cache[nl.cache_key(NLRequest(text="what is here"))] == resp


def test_openapi_documents_nl_errors():
    responses = build_openapi()["paths"]["/api/nl"]["post"]["responses"]
    assert {"200", "422", "429", "503"} <= set(responses)
    assert responses["429"]["content"]["application/json"]["schema"]["$ref"].endswith("RateLimitedError")


def test_ca_check_follows_httpcore2_lookup(tmp_path, monkeypatch):
    import platform
    import ssl

    import httpcore2._ssl

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    for var in ("SSL_CERT_FILE", "SSL_CERT_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(httpcore2._ssl, "CA_FILE_CANDIDATES", [str(tmp_path / "none.pem")])
    empty = ssl.DefaultVerifyPaths(None, None, "", str(tmp_path / "nofile.pem"), "", str(tmp_path / "nodir"))
    monkeypatch.setattr(ssl, "get_default_verify_paths", lambda: empty)
    assert nl.ca_certificates_available() is False  # an image with no CA certificates fails the build
    (tmp_path / "certs").mkdir()
    (tmp_path / "certs" / "0123abcd.0").write_text("x")
    hashed = ssl.DefaultVerifyPaths(None, None, "", str(tmp_path / "nofile.pem"), "", str(tmp_path / "certs"))
    monkeypatch.setattr(ssl, "get_default_verify_paths", lambda: hashed)
    assert nl.ca_certificates_available() is True


def test_debug_client_route_only_when_turned_on(monkeypatch):
    monkeypatch.delenv("LSS_DEBUG_CLIENT_IP", raising=False)
    assert TestClient(app_module.create_app()).get("/api/_debug/client").status_code == 404
    monkeypatch.setenv("LSS_DEBUG_CLIENT_IP", "1")
    app = app_module.create_app()
    r = TestClient(app).get("/api/_debug/client", headers={"X-Forwarded-For": "203.0.113.9, 198.51.100.2"})
    assert r.json()["used_for_rate_limit"] == "198.51.100.2"
    assert "/api/_debug/client" not in app.openapi()["paths"]


def test_unavailable_reasons_mention_examples_only_when_there_are_some(setup):
    def broken():
        raise ProviderError("down")

    client, _ = setup[0](factory=broken)  # no cached examples
    d = UnavailableError.model_validate(ask(client, "boulders").json()).detail
    assert d.reason == nl.NL_UNAVAILABLE_REASON and "example" not in d.reason
