"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

NL eval harness (step 4.5; plan section 4.5).

    uv run python -m lss.nl.eval                   # oracle provider: label self-check, no network
    uv run python -m lss.nl.eval --provider claude --live --model <id>   # needs the author's okay

Scores (plan section 4.5, the project author's two measures), over `ready` items only:
  (a) structured-query correctness, for items expecting a query (answer / partial):
      output is valid, outcome matches, operation matches, params match (exact, or the
      label's keys for `subset`), and height_source / window_source match when the label
      gives them.
  (b) refusal/partial-reason correctness, for items expecting limitations (partial / unsupported):
      output is valid, outcome matches, and the cited registry entries include every required
      citation and nothing outside required + optional.
Blocked items are skipped unless `--include-blocked` (then run and recorded, never scored).
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
from lss.nl.evalset import EvalItem, EvalSet, ItemStatus, label_output, load_eval_set
from lss.nl.prompt import PROMPT_VERSION, build_prompt
from lss.nl.provider import FakeProvider, NLPrompt, Provider
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


@dataclass
class ItemResult:
    id: str
    source: str
    status: str
    blocked_reasons: list[str]
    scored: bool
    expected_outcome: str | None
    outcome: str | None = None
    valid: bool = False
    problems: list[str] = field(default_factory=list)
    query_correct: bool | None = None  # (a); None = not applicable
    reason_correct: bool | None = None  # (b); None = not applicable
    error: str | None = None
    raw_output: str | None = None
    provider_meta: dict[str, Any] | None = None  # e.g. served_by, token counts, request id


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
    if exp.window_source is not None and v.output.window_source != exp.window_source:
        notes.append(f"window_source {v.output.window_source.value} != expected {exp.window_source.value}")
    if exp.height_source is not None and v.output.height_source != exp.height_source:
        notes.append(f"height_source {v.output.height_source.value} != expected {exp.height_source.value}")
    return not notes, notes


def _score_reason(item: EvalItem, v: ValidatedOutput) -> tuple[bool, list[str]]:
    exp = item.expected
    cited = {(c.dataset_id, c.cannot_answer) for lim in v.output.limitations for c in lim.citations}
    required = {(c.dataset_id, c.cannot_answer) for c in exp.citations}
    allowed = required | {(c.dataset_id, c.cannot_answer) for c in exp.citations_optional}
    notes = [f"missing citation {c}" for c in sorted(required - cited)]
    notes += [f"unexpected citation {c}" for c in sorted(cited - allowed)]
    return not notes, notes


def run_item(item: EvalItem, provider: Provider, eval_set: EvalSet) -> ItemResult:
    exp = item.expected
    res = ItemResult(
        id=item.id,
        source=item.source.value,
        status=item.status.value,
        blocked_reasons=item.blocked_reasons,
        scored=item.status == ItemStatus.ready,
        expected_outcome=exp.outcome.value if exp else None,
    )
    ctx = default_context(selected_site_id=item.context.selected_site_id, today=eval_set.reference_date)
    prompt = build_prompt(item.text, ctx, eval_set.reference_date)
    try:
        res.raw_output = provider.complete(prompt)
        meta = getattr(provider, "last_meta", None)
        res.provider_meta = dict(meta) if meta else None
    except Exception as e:  # provider failures are recorded, not fatal
        res.error = f"{type(e).__name__}: {e}"
    else:
        try:
            v = validate_output(res.raw_output, ctx)
        except NLValidationError as e:
            res.problems = e.problems
        else:
            res.valid = True
            res.outcome = v.output.outcome.value
            if exp is not None:
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
    if res.valid is False and exp is not None:
        res.query_correct = False if exp.outcome != Outcome.unsupported else None
        res.reason_correct = False if exp.outcome != Outcome.answer else None
    return res


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
    scored = [r for r in results if r.scored]
    return {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "provider": provider.name,
        "model": provider.model,
        "effort": getattr(provider, "effort", None),
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "eval_set_version": eval_set.version,
        "reference_date": eval_set.reference_date.isoformat(),
        "counts": {
            "items_in_set": len(eval_set.items),
            "run": len(results),
            "scored": len(scored),
            "blocked": sum(i.status == ItemStatus.blocked for i in eval_set.items),
        },
        "scores": {
            "a_structured_query": _score(results, "query_correct"),
            "b_refusal_reason": _score(results, "reason_correct"),
            "valid_output": {
                "correct": sum(r.valid for r in scored),
                "total": len(scored),
                "score": sum(r.valid for r in scored) / len(scored) if scored else None,
            },
        },
        "items": [asdict(r) for r in results],
    }


def write_results(report: dict[str, Any], out_dir: Path = RESULTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = report["run_at"].replace(":", "").replace("+0000", "Z")
    safe = lambda s: "".join(ch if ch.isalnum() or ch in "-." else "-" for ch in s)  # noqa: E731
    name = f"{stamp}_{safe(report['provider'])}_{safe(report['model'])}_{safe(report['prompt_version'])}.json"
    path = out_dir / name
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
    args = p.parse_args(argv)

    if args.provider == "oracle":
        provider: Provider = oracle_provider()
    else:
        if not args.live:
            p.error("--provider claude calls the Anthropic API; pass --live (only with the author's okay)")
        if not args.model:
            p.error("--provider claude needs --model (the project author chooses the model)")
        from lss.nl.claude import ClaudeProvider

        provider = ClaudeProvider(model=args.model, effort=args.effort)

    report = run_eval(provider, include_blocked=args.include_blocked)
    print(
        json.dumps(
            {k: report[k] for k in ("provider", "model", "prompt_version", "counts", "scores")}, indent=2
        )
    )
    if not args.no_write:
        print(f"wrote {write_results(report)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
