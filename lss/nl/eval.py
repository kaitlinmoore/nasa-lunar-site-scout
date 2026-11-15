"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

NL eval harness (step 4.5; plan section 4.5).

    uv run python -m lss.nl.eval                   # oracle provider: label self-check, no network
    uv run python -m lss.nl.eval --provider claude --live --model <id>   # needs the author's okay
    uv run python -m lss.nl.eval --rescore tests/nl/results/<file>.json   # current labels, no API

Scores (plan section 4.5, the project author's two measures), over `ready` items only:
  (a) structured-query correctness, for items expecting a query (answer / partial):
      output is valid, outcome matches, operation matches, params match (exact, or the
      label's keys for `subset`), and the height / window / slope / radius sources match when
      the label gives them.
  (b) refusal/partial-reason correctness, for items expecting limitations (partial / unsupported):
      output is valid, outcome matches, and the cited registry entries include every required
      citation and nothing outside required + optional.
Blocked items are skipped unless `--include-blocked` (then run and recorded, never scored).
Scores are reported for all scored items and per split: dev (tuning) and holdout (never used
for tuning; project author's rule, 2026-11-15).
Writes a dated JSON results file to tests/nl/results/.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lss.config import REPO_ROOT
from lss.nl.evalset import EvalItem, EvalSet, ItemStatus, Split, label_output, load_eval_set
from lss.nl.interpret import interpret
from lss.nl.prompt import PROMPT_VERSION
from lss.nl.provider import FakeProvider, NLPrompt, Provider, ProviderFatalError
from lss.nl.schema import SCHEMA_VERSION, Outcome
from lss.nl.validate import (
    NLValidationError,
    ValidatedOutput,
    default_context,
    normalize_query,
    resolve_site_refs,
    validate_output,
)

RESULTS_DIR = REPO_ROOT / "tests" / "nl" / "results"

# USD per million tokens (input, output), standard rates. Source: Anthropic pricing as cached in
# the claude-api skill, 2026-11-03. Used only to estimate a run's spend; check the Console for the bill.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


def _usage(results: list[ItemResult]) -> dict[str, Any]:
    """Token totals and estimated cost, priced by the model that actually served each item."""
    tin = tout = 0
    cost = 0.0
    unpriced: set[str] = set()
    metas = [c["meta"] or {} for r in results for c in r.calls]
    for meta in metas:
        i, o = meta.get("input_tokens") or 0, meta.get("output_tokens") or 0
        tin, tout = tin + i, tout + o
        model = meta.get("served_by")
        if model in PRICES_PER_MTOK:
            pin, pout = PRICES_PER_MTOK[model]
            cost += (i * pin + o * pout) / 1e6
        elif i or o:
            unpriced.add(str(model))
    return {
        "input_tokens": tin,
        "output_tokens": tout,
        "est_cost_usd": round(cost, 4),
        "unpriced_models": sorted(unpriced),
    }


@dataclass
class ItemResult:
    id: str
    source: str
    status: str
    blocked_reasons: list[str]
    scored: bool
    expected_outcome: str | None
    split: str = "dev"
    outcome: str | None = None
    valid: bool = False
    problems: list[str] = field(default_factory=list)
    query_correct: bool | None = None  # (a); None = not applicable
    reason_correct: bool | None = None  # (b); None = not applicable
    error: str | None = None
    output: dict[str, Any] | None = None  # combined route + fill output, before validation
    calls: list[dict[str, Any]] = field(default_factory=list)  # per provider call: stage, raw, meta


def _is_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and _is_subset(v, actual[k]) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(_is_subset(e, a) for e, a in zip(expected, actual, strict=True))
        )
    return expected == actual


def _score_query(item: EvalItem, v: ValidatedOutput, ctx) -> tuple[bool, list[str]]:
    exp = item.expected
    notes: list[str] = []
    sq = v.structured_query
    if sq is None or exp.query is None:
        return False, ["no structured query"]
    if sq.operation != exp.query.operation:
        notes.append(f"operation {sq.operation.value} != expected {exp.query.operation.value}")
    elif exp.params_match == "exact":
        if sq.params != normalize_query(exp.query, ctx).params:
            notes.append("params differ from the label")
    elif not _is_subset(resolve_site_refs(exp.query.params, ctx), sq.params):
        notes.append("params don't contain the label's values")
    for name in ("window_source", "height_source", "slope_source", "radius_source"):
        want, got = getattr(exp, name), getattr(v.output, name)
        if want is not None and got != want:
            notes.append(f"{name} {got.value} != expected {want.value}")
    return not notes, notes


def _score_reason(item: EvalItem, v: ValidatedOutput) -> tuple[bool, list[str]]:
    exp = item.expected
    cited = {(c.dataset_id, c.cannot_answer) for lim in v.output.limitations for c in lim.citations}
    required = {(c.dataset_id, c.cannot_answer) for c in exp.citations}
    allowed = required | {(c.dataset_id, c.cannot_answer) for c in exp.citations_optional}
    notes = [f"missing citation {c}" for c in sorted(required - cited)]
    notes += [f"unexpected citation {c}" for c in sorted(cited - allowed)]
    return not notes, notes


def _new_result(item: EvalItem) -> ItemResult:
    exp = item.expected
    return ItemResult(
        id=item.id,
        source=item.source.value,
        status=item.status.value,
        blocked_reasons=item.blocked_reasons,
        scored=item.status == ItemStatus.ready,
        expected_outcome=exp.outcome.value if exp else None,
        split=item.split.value,
    )


def _context(item: EvalItem, eval_set: EvalSet):
    return default_context(selected_site_id=item.context.selected_site_id, today=eval_set.reference_date)


def run_item(item: EvalItem, provider: Provider, eval_set: EvalSet) -> ItemResult:
    res = _new_result(item)
    try:
        res.output = interpret(
            item.text, _context(item, eval_set), provider, eval_set.reference_date, trace=res.calls
        )
    except ProviderFatalError:
        raise  # would fail the same way on every item: stop the run
    except NLValidationError as e:  # a stage's output didn't parse
        res.problems = e.problems
    except Exception as e:  # other provider failures are recorded, not fatal
        res.error = f"{type(e).__name__}: {e}"
    else:
        score_output(res, item, eval_set)
    _finalize(res, item)
    return res


def score_output(res: ItemResult, item: EvalItem, eval_set: EvalSet) -> None:
    """Validate `res.output` and score it against the item's label (current labels)."""
    exp = item.expected
    ctx = _context(item, eval_set)
    try:
        v = validate_output(res.output, ctx)
    except NLValidationError as e:
        res.problems = e.problems
        return
    res.valid = True
    res.outcome = v.output.outcome.value
    if exp is None:
        return
    if v.output.outcome != exp.outcome:
        res.problems.append(f"outcome {res.outcome} != expected {exp.outcome.value}")
    if exp.outcome != Outcome.unsupported:
        ok, notes = _score_query(item, v, ctx)
        res.query_correct = ok and v.output.outcome == exp.outcome
        res.problems += notes
    if exp.outcome != Outcome.answer:
        ok, notes = _score_reason(item, v)
        res.reason_correct = ok and v.output.outcome == exp.outcome
        res.problems += notes


def _finalize(res: ItemResult, item: EvalItem) -> None:
    exp = item.expected
    if res.valid is False and exp is not None:
        res.query_correct = False if exp.outcome != Outcome.unsupported else None
        res.reason_correct = False if exp.outcome != Outcome.answer else None


def _score(results: list[ItemResult], attr: str) -> dict[str, Any]:
    vals = [getattr(r, attr) for r in results if r.scored and getattr(r, attr) is not None]
    correct = sum(vals)
    return {"correct": correct, "total": len(vals), "score": correct / len(vals) if vals else None}


def run_eval(
    provider: Provider, eval_set: EvalSet | None = None, include_blocked: bool = False
) -> dict[str, Any]:
    eval_set = eval_set or load_eval_set()
    items = [i for i in eval_set.items if include_blocked or i.status == ItemStatus.ready]
    results = [run_item(i, provider, eval_set) for i in items]
    return {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "provider": provider.name,
        "model": provider.model,
        "effort": getattr(provider, "effort", None),
        "fallbacks": getattr(provider, "fallbacks", None),
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        **_summary(results, eval_set),
    }


def _scores(results: list[ItemResult]) -> dict[str, Any]:
    scored = [r for r in results if r.scored]
    return {
        "a_structured_query": _score(results, "query_correct"),
        "b_refusal_reason": _score(results, "reason_correct"),
        "valid_output": {
            "correct": sum(r.valid for r in scored),
            "total": len(scored),
            "score": sum(r.valid for r in scored) / len(scored) if scored else None,
        },
    }


def _summary(results: list[ItemResult], eval_set: EvalSet) -> dict[str, Any]:
    """Counts and scores. `scores` covers every scored item; `scores_by_split` reports the tuning
    (dev) and held-out items separately. Holdout items are never used for tuning."""
    return {
        "eval_set_version": eval_set.version,
        "reference_date": eval_set.reference_date.isoformat(),
        "counts": {
            "items_in_set": len(eval_set.items),
            "run": len(results),
            "scored": sum(r.scored for r in results),
            "blocked": sum(i.status == ItemStatus.blocked for i in eval_set.items),
        },
        "scores": _scores(results),
        "scores_by_split": {s.value: _scores([r for r in results if r.split == s.value]) for s in Split},
        "usage": _usage(results),
        "items": [asdict(r) for r in results],
    }


def rescore(path: Path, eval_set: EvalSet | None = None) -> dict[str, Any]:
    """Score a saved run's outputs against the current labels and splits. No API calls; the
    usage (spend) is the original run's.

    Only for runs saved under the current output schema: an older run's outputs lack fields the
    current validation requires (e.g. `radius_source`, added in nl-output-4), so its rescore would
    count misses the model was never asked to avoid.
    """
    eval_set = eval_set or load_eval_set()
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"{path.name} was saved under schema {saved.get('schema_version')!r}, not {SCHEMA_VERSION!r}: "
            "rescoring it would count fields the model was never asked for. Its own scores stand."
        )
    by_id = {i.id: i for i in eval_set.items}
    results = []
    for old in saved["items"]:
        item = by_id.get(old["id"])
        if item is None:
            continue  # no longer in the set
        res = _new_result(item)
        res.calls, res.output, res.error = old.get("calls", []), old.get("output"), old.get("error")
        if res.output is not None:
            score_output(res, item, eval_set)
        elif res.error is None:
            res.problems = list(old.get("problems", []))
        _finalize(res, item)
        results.append(res)
    keep = ("run_at", "provider", "model", "effort", "fallbacks", "prompt_version", "schema_version")
    return {
        **{k: saved.get(k) for k in keep},
        "rescored_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rescored_from": path.name,
        **_summary(results, eval_set),
    }


def write_results(report: dict[str, Any], out_dir: Path = RESULTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = report["run_at"].replace(":", "").replace("+0000", "Z")
    safe = lambda s: "".join(ch if ch.isalnum() or ch in "-." else "-" for ch in s)  # noqa: E731
    name = f"{stamp}_{safe(report['provider'])}_{safe(report['model'])}_{safe(report['prompt_version'])}"
    if report.get("rescored_at"):
        name += "_rescored-" + report["rescored_at"].replace(":", "").replace("+0000", "Z")
    path = out_dir / f"{name}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def oracle_provider(eval_set: EvalSet | None = None) -> FakeProvider:
    """Answers every complete label perfectly: checks the harness and labels, not a model."""
    eval_set = eval_set or load_eval_set()
    by_text: dict[str, list[EvalItem]] = {}
    for item in eval_set.items:
        by_text.setdefault(item.text, []).append(item)

    def respond(prompt: NLPrompt) -> Any:
        for item in by_text.get(prompt.meta["text"], []):
            if item.context.selected_site_id == prompt.meta["selected_site_id"]:
                out = label_output(item)
                if out is not None:
                    return out
        return "{}"

    return FakeProvider(respond=respond, model="oracle")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m lss.nl.eval", description=__doc__.split("\n\n")[1])
    p.add_argument("--provider", choices=["oracle", "claude"], default="oracle")
    p.add_argument("--model", help="model id for a live provider (required for --provider claude)")
    p.add_argument("--effort", default="low", help="effort for a live provider (default: low)")
    p.add_argument(
        "--live", action="store_true", help="required for providers that call an API (costs money)"
    )
    p.add_argument("--include-blocked", action="store_true", help="also run blocked items (not scored)")
    p.add_argument("--no-write", action="store_true", help="print scores only; don't write a results file")
    p.add_argument(
        "--rescore", type=Path, help="score a saved results file against the current labels (no API)"
    )
    args = p.parse_args(argv)

    if args.rescore is not None:
        try:
            report = rescore(args.rescore)
        except ValueError as e:
            p.error(str(e))
    elif args.provider == "oracle":
        provider: Provider = oracle_provider()
    else:
        if not args.live:
            p.error("--provider claude calls the Anthropic API; pass --live (only with the author's okay)")
        if not args.model:
            p.error("--provider claude needs --model (the project author chooses the model)")
        from lss.nl.claude import ClaudeProvider

        # Refusal fallback off for eval runs, so every score is the chosen model's own answer
        # (project author, 2026-11-15); the deployed demo keeps it on (ClaudeProvider's default).
        provider = ClaudeProvider(model=args.model, effort=args.effort, fallbacks=False)
    if args.rescore is None:
        report = run_eval(provider, include_blocked=args.include_blocked)
    print(
        json.dumps(
            {
                k: report.get(k)
                for k in (
                    "provider",
                    "model",
                    "prompt_version",
                    "rescored_from",
                    "counts",
                    "scores",
                    "scores_by_split",
                    "usage",
                )
            },
            indent=2,
        )
    )
    if not args.no_write:
        print(f"wrote {write_results(report)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
