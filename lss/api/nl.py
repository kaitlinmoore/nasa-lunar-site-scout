"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

POST /api/nl: a question in; the echo plus an answer, or "can't answer,
because…", out.

Flow per request:
1. A cached showcase answer for exactly this question and selection is returned as is (which
   questions are showcased is the project author's decision). Cached answers cost nothing and are
   not rate limited.
2. Live questions are limited per client IP (5 per minute, 30 per UTC day) and by a daily spend cap
   ($2, estimated from token counts at list prices); the project author's values, 2026-11-16. Both are
   kept in memory, per API instance, and reset when an instance restarts: soft limits. The hard limit is
   the Anthropic Console's monthly limit on the demo key.
3. `lss.nl.interpret` (route, then fill) with the refusal fallback on (the project author's decision for the
   demo), then `lss.nl.validate`. The LLM never computes numbers.
4. The structured query runs against the API's own precomputed results (the same functions as the
   endpoints). An operation the engine can't serve yet, or a scenario with no precomputed result, becomes
   a limitation on the answer; the echo and assumptions are still shown.

Logs record counts and costs only: never the question text or the client's address.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from lss.config import get_settings
from lss.contract import (
    Limitation,
    NLAnswer,
    NLClarification,
    NLRequest,
    NLUnsupported,
    Operation,
    RateLimitedDetail,
    UnavailableDetail,
)
from lss.nl.claude import ClaudeProvider, ProviderError, estimate_cost_usd
from lss.nl.interpret import interpret
from lss.nl.provider import Provider, ProviderFatalError
from lss.nl.validate import NLValidationError, default_context, to_response, validate_output
from lss.nl.vocabulary import OPERATION_PARAMS, SLOPE_FILTER_METRIC, SlopeSource

log = logging.getLogger("lss.api.nl")

NLResult = NLAnswer | NLUnsupported | NLClarification

# The project author's values (2026-11-16); env vars override them for a deployment.
RATE_PER_MINUTE = int(os.environ.get("LSS_NL_RATE_PER_MINUTE", "5"))
RATE_PER_DAY = int(os.environ.get("LSS_NL_RATE_PER_DAY", "30"))
DAILY_SPEND_USD = float(os.environ.get("LSS_NL_DAILY_SPEND_USD", "2.0"))
MODEL = os.environ.get("LSS_NL_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("LSS_NL_EFFORT", "low")

# Visitor-facing texts: Claude-drafted (2026-11-16), approved by the project author 2026-11-16.
RATE_LIMITED_REASON = "Too many questions from this connection. Please wait a little and try again."
PAUSED_REASON = "Live questions are paused until tomorrow (UTC): the demo's daily limit has been reached."
NL_UNAVAILABLE_REASON = "Live questions are temporarily unavailable. Please try again later."
# Appended only when cached example answers exist, so the text never promises examples that aren't there
# (2026-11-16). The short forms above: Claude-drafted, approved by the project author.
EXAMPLES_STILL_WORK = " The example questions still work."
NOT_UNDERSTOOD_REASON = (
    "The question couldn't be turned into a query this tool supports. Try rephrasing it, or ask about one "
    "of the listed sites."
)
NOT_AVAILABLE_YET = {
    Operation.proximity: "Distances to nearby features are not available in this version yet.",
    Operation.search: "Area search is not available in this version yet.",
    # Served since contract 0.9.0; kept for an API without terrain data installed.
    Operation.terrain: "Slope statistics are not available in this version yet.",
    Operation.site_summary: "Site summaries are not available in this version yet.",
}

Executor = Callable[[BaseModel], BaseModel]


# ------------------------------------------------------------------------- limits


class RateLimiter:
    """Per-client sliding one-minute window plus a per-UTC-day count, in memory."""

    def __init__(self, per_minute: int, per_day: int, clock: Callable[[], datetime] | None = None):
        self.per_minute, self.per_day = per_minute, per_day
        self.clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self._recent: dict[str, deque[datetime]] = {}
        self._day: date | None = None
        self._daily: dict[str, int] = {}

    def check(self, client: str) -> int | None:
        """Record one live question; None if allowed, else seconds until the client may ask again."""
        now = self.clock()
        with self._lock:
            if self._day != now.date():
                self._day, self._daily = now.date(), {}
            if self._daily.get(client, 0) >= self.per_day:
                midnight = datetime.combine(now.date(), datetime.min.time(), UTC).timestamp() + 86_400
                return max(1, int(midnight - now.timestamp()))
            recent = self._recent.setdefault(client, deque())
            while recent and (now - recent[0]).total_seconds() >= 60:
                recent.popleft()
            if len(recent) >= self.per_minute:
                return max(1, int(60 - (now - recent[0]).total_seconds()))
            recent.append(now)
            self._daily[client] = self._daily.get(client, 0) + 1
            return None


class SpendMeter:
    """Estimated spend per UTC day, in memory."""

    def __init__(self, cap_usd: float, clock: Callable[[], datetime] | None = None):
        self.cap_usd = cap_usd
        self.clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self._day: date | None = None
        self._spent = 0.0

    def _roll(self) -> None:
        today = self.clock().date()
        if self._day != today:
            self._day, self._spent = today, 0.0

    def exhausted(self) -> bool:
        with self._lock:
            self._roll()
            return self._spent >= self.cap_usd

    def add(self, usd: float) -> None:
        with self._lock:
            self._roll()
            self._spent += usd

    @property
    def spent(self) -> float:
        with self._lock:
            self._roll()
            return self._spent


# -------------------------------------------------------------------- showcase cache


def cache_key(req: NLRequest) -> tuple[str, str | None, str | None]:
    """Question text normalized (case, spacing, trailing punctuation), plus the selection."""
    text = re.sub(r"\s+", " ", req.text).strip().casefold().rstrip("?!. ")
    scenario = req.selected_scenario.key() if req.selected_scenario else None
    return text, req.selected_site_id, scenario


class CacheFileError(ValueError):
    """A cached answer that is inconsistent or made with an incompatible contract version."""


def response_model(body: dict) -> type[BaseModel]:
    return NLClarification if "question" in body else NLUnsupported if "unsupported" in body else NLAnswer


@dataclass(frozen=True)
class CachedAnswer:
    request: NLRequest
    response: NLResult
    path: Path


def load_cache_entries(directory: Path) -> dict[tuple, CachedAnswer]:
    """Cached showcase answers, one JSON file each: `{"format": 1, "request": NLRequest, "response":
    NLResponse, "provenance": {...}}` (written by `python -m lss.api.nl_cache`). The same version rules as
    served files: current or compatible contract version (re-stamped), no placeholder, no duplicate
    request."""
    from lss.api.served import COMPATIBLE_VERSIONS
    from lss.contract import CONTRACT_VERSION

    out: dict[tuple, CachedAnswer] = {}
    for p in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        data = json.loads(p.read_text(encoding="utf-8"))
        req = NLRequest.model_validate(data["request"])
        body = data["response"]
        resp = response_model(body).model_validate(body)
        if resp.placeholder:
            raise CacheFileError(f"{p.name}: placeholder answer")
        made_with = resp.contract_version
        if made_with != CONTRACT_VERSION and made_with not in COMPATIBLE_VERSIONS:
            raise CacheFileError(
                f"{p.name}: made with contract {made_with}, the API is {CONTRACT_VERSION}; record it again "
                "with python -m lss.api.nl_cache"
            )
        update: dict[str, Any] = {"contract_version": CONTRACT_VERSION}
        if isinstance(resp, NLAnswer) and isinstance(resp.result, dict) and "contract_version" in resp.result:
            update["result"] = _upgrade_result(resp, {**resp.result, "contract_version": CONTRACT_VERSION})
        key = cache_key(req)
        if key in out:
            raise CacheFileError(f"{p.name} and {out[key].path.name} answer the same request")
        out[key] = CachedAnswer(req, resp.model_copy(update=update), p)
    return out


def _upgrade_result(resp: NLAnswer, result: dict[str, Any]) -> dict[str, Any]:
    """Bring a cached result made under an older compatible contract up to the current shape: a compare answer
    from before 0.13.0 gets `compared_keys` (Scenario.key() of each `compared` entry, same order), which the
    web matches columns by (found in a walkthrough of the web client, 2026-11-16)."""
    from lss.contract import Operation, Scenario

    if (
        resp.structured_query.operation == Operation.compare
        and result.get("compared")
        and not result.get("compared_keys")
    ):
        result["compared_keys"] = [Scenario.model_validate(sc).key() for sc in result["compared"]]
    return result


def load_cache(directory: Path) -> dict[tuple, NLResult]:
    """The cache NLService uses: cache key -> response."""
    return {k: e.response for k, e in load_cache_entries(directory).items()}


# ---------------------------------------------------------------------------- service


@dataclass
class NLService:
    executors: Mapping[Operation, Executor]
    provider_factory: Callable[[], Provider]
    limiter: RateLimiter = field(default_factory=lambda: RateLimiter(RATE_PER_MINUTE, RATE_PER_DAY))
    meter: SpendMeter = field(default_factory=lambda: SpendMeter(DAILY_SPEND_USD))
    cache: Mapping[tuple, NLResult] = field(default_factory=dict)
    # Reasons that refer to "the list with this message" -> their list-free versions: an NL answer lists
    # nothing (2026-11-16).
    list_free_reasons: Mapping[str, str] = field(default_factory=dict)
    today: Callable[[], date] = field(default=lambda: datetime.now(UTC).date())
    _provider: Provider | None = None

    def provider(self) -> Provider:
        if self._provider is None:
            self._provider = self.provider_factory()
        return self._provider

    def answer(self, req: NLRequest, client: str) -> NLResult:
        cached = self.cache.get(cache_key(req))
        if cached is not None:
            log.info("nl: cached answer")
            return cached
        wait = self.limiter.check(client)
        if wait is not None:
            detail = RateLimitedDetail(reason=RATE_LIMITED_REASON, retry_after_s=wait)
            raise HTTPException(
                429, detail=detail.model_dump(mode="json"), headers={"Retry-After": str(wait)}
            )
        if self.meter.exhausted():
            raise _unavailable(
                self._reason(PAUSED_REASON), f"daily spend cap ${self.meter.cap_usd:g} reached"
            )

        today = self.today()
        ctx = default_context(req.selected_site_id, req.selected_scenario, today)
        trace: list[dict[str, Any]] = []
        try:
            provider = self.provider()
            raw = interpret(req.text, ctx, provider, today, trace=trace)
        except (ProviderError, ProviderFatalError) as e:
            self._charge(trace)
            log.warning("nl: provider failed: %s", type(e).__name__)
            raise _unavailable(self._reason(NL_UNAVAILABLE_REASON), f"{type(e).__name__}: {e}") from e
        except NLValidationError:
            self._charge(trace)
            return _not_understood()
        except Exception as e:  # network errors and the like: the demo keeps working with cached answers
            self._charge(trace)
            log.warning("nl: provider call failed: %s", type(e).__name__)
            raise _unavailable(self._reason(NL_UNAVAILABLE_REASON), f"{type(e).__name__}") from e
        cost = self._charge(trace)

        try:
            validated = validate_output(raw, ctx)
        except NLValidationError:
            log.info("nl: invalid output (cost $%.4f)", cost)
            return _not_understood()

        sq = validated.structured_query
        if sq is None:  # unsupported or clarify
            log.info("nl: %s (cost $%.4f)", validated.output.outcome.value, cost)
            return to_response(validated, ctx)

        result, limitation, slope_terrain, measured = self._run(sq.operation, sq.params)
        if result is not None and slope_terrain is None:
            slope_terrain = _slope_sources(result)
        safe = validated.output.slope_source == SlopeSource.safe_default
        if safe and measured and not slope_terrain:
            measured = False  # the result names no slope layer: say it wasn't measured, never guess
        resp = to_response(
            validated,
            ctx,
            slope_terrain=slope_terrain if safe else None,
            slope_measured=measured or not safe,
        )
        assert isinstance(resp, NLAnswer)
        update: dict[str, Any] = {"result": result}
        if limitation is not None:
            update["limitations"] = [*resp.limitations, limitation]
        log.info("nl: %s %s (cost $%.4f)", validated.output.outcome.value, sq.operation.value, cost)
        return resp.model_copy(update=update)

    def _reason(self, base: str) -> str:
        return base + EXAMPLES_STILL_WORK if self.cache else base

    def _charge(self, trace: list[dict[str, Any]]) -> float:
        cost = sum(estimate_cost_usd(c.get("meta")) or 0.0 for c in trace)
        self.meter.add(cost)
        return cost

    def _run(
        self, op: Operation, params: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, Limitation | None, str | None, bool]:
        """(result, limitation, slope terrain, slope measured) for a validated structured query."""
        run = self.executors.get(op)
        if run is None:
            return None, Limitation(reason=NOT_AVAILABLE_YET.get(op, "Not available yet.")), None, False
        try:
            body = run(OPERATION_PARAMS[op].model_validate(params))
        except HTTPException as e:
            reason = e.detail.get("reason") if isinstance(e.detail, dict) else None
            reason = self.list_free_reasons.get(reason, reason) if reason else None
            return None, Limitation(reason=reason or "No result for this request."), None, False
        except ValidationError:
            return None, Limitation(reason=NOT_UNDERSTOOD_REASON), None, False
        return body.model_dump(mode="json", by_alias=True), None, None, True


def _slope_sources(result: dict[str, Any]) -> str | None:
    """The map(s) a compare's slope filter was measured on (CompareResponse.evaluated sources), or None."""
    sources = sorted(
        {
            e["source"]
            for e in result.get("evaluated") or []
            if e.get("metric") == SLOPE_FILTER_METRIC and e.get("source")
        }
    )
    return " and ".join(sources) or None


def _unavailable(reason: str, technical: str) -> HTTPException:
    detail = UnavailableDetail(reason=reason, technical=technical)
    return HTTPException(503, detail=detail.model_dump(mode="json"))


def _not_understood() -> NLUnsupported:
    return NLUnsupported(unsupported=Limitation(reason=NOT_UNDERSTOOD_REASON))


def client_address(forwarded_for: str | None, peer: str | None) -> str:
    """The client's address for rate limiting: the last X-Forwarded-For entry (the one Cloud Run's front
    end appends; earlier entries are client-supplied), else the socket peer. Verified on the deployed API
    2026-11-16 (deploy/README.md): a made-up X-Forwarded-For value came first and was not used."""
    if forwarded_for:
        last = forwarded_for.split(",")[-1].strip()
        if last:
            return last
    return peer or "unknown"


def ca_certificates_available() -> bool:
    """Whether httpx2 (the anthropic SDK's HTTP client) will find CA certificates on Linux: the same
    lookup as `httpcore2.default_ssl_context` (SSL_CERT_FILE / SSL_CERT_DIR, OpenSSL's compiled-in file or
    hashed directory, then httpcore2's candidate files). Run at image build time (Dockerfile)."""
    import platform
    import ssl

    from httpcore2._ssl import CA_FILE_CANDIDATES

    if platform.system() in ("Windows", "Darwin"):
        return True  # httpx2 uses the OS certificate store there (truststore), not files
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return True
    paths = ssl.get_default_verify_paths()
    if paths.openssl_cafile and os.path.isfile(paths.openssl_cafile):
        return True
    capath = paths.openssl_capath
    if (
        capath
        and os.path.isdir(capath)
        and any(re.fullmatch(r"[0-9a-fA-F]{8}\.\d", f) for f in os.listdir(capath))
    ):
        return True
    return any(os.path.isfile(f) for f in CA_FILE_CANDIDATES)


def default_provider() -> Provider:
    if not get_settings().anthropic_api_key:
        raise ProviderError("ANTHROPIC_API_KEY is not set")
    return ClaudeProvider(MODEL, effort=EFFORT, fallbacks=True)


def cache_dir() -> Path:
    return get_settings().cache_dir / "nl"
