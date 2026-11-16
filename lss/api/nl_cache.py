"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Cached showcase NL answers (C8, plan section 4.6): the questions the project author chooses are answered once
and stored in LSS_DATA_DIR/cache/nl/, so the deployed POST /api/nl returns them instantly, at no cost, without
rate limits, and even when the daily cap is reached or the model can't be reached. `deploy-api.sh` stages them
into the image and `deploy-web.sh` publishes them in the static copy.

    uv run python -m lss.api.nl_cache add-from-run RESULTS_FILE ITEM_ID [--replace]
        replays a saved eval run's model output for one eval item (its question and selected site) through
        today's validation and API: no LLM call, no cost
    uv run python -m lss.api.nl_cache add "QUESTION" [--site SITE_ID] [--scenario-key KEY] --live [--replace]
        one live call through the demo's own pipeline (refusal fallback on): needs the project author's okay
    uv run python -m lss.api.nl_cache list
    uv run python -m lss.api.nl_cache remove NAME

An entry answers exactly one request: the question text (case, spacing and final punctuation ignored), the
selected site and the selected scenario. Its default windows are fixed at the date it was recorded on
(stated in the entry's disclosures). "Couldn't understand" answers and errors are refused, never cached.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from lss.api import app as api
from lss.api import nl
from lss.contract import CONTRACT_VERSION, NLRequest, NLUnsupported, Scenario
from lss.nl.prompt import PROMPT_VERSION
from lss.nl.provider import FakeProvider
from lss.nl.schema import SCHEMA_VERSION


class CacheWriteError(RuntimeError):
    pass


def entry_name(req: NLRequest) -> str:
    """File stem: a readable slug of the question plus a hash of the whole cache key."""
    text, site, scenario = nl.cache_key(req)
    slug = re.sub(r"[^a-z0-9]+", "-", text)[:48].strip("-") or "question"
    digest = hashlib.sha256(json.dumps([text, site, scenario]).encode()).hexdigest()[:8]
    return f"{slug}-{digest}"


def _scenario(key: str | None) -> Scenario | None:
    if key is None:
        return None
    served = api.served_results()
    if key not in served:
        raise CacheWriteError(f"no served scenario with key {key}")
    return served[key].scenario


def _answer(service: nl.NLService, req: NLRequest) -> nl.NLResult:
    try:
        resp = service.answer(req, "nl-cache-writer")
    except HTTPException as e:
        raise CacheWriteError(f"the API answered {e.status_code}: {e.detail}") from e
    if isinstance(resp, NLUnsupported) and resp.unsupported.reason == nl.NOT_UNDERSTOOD_REASON:
        raise CacheWriteError(
            "the model's output didn't validate ('couldn't be turned into a query'): not cached"
        )
    return resp


def write_entry(
    req: NLRequest,
    resp: nl.NLResult,
    provenance: dict[str, Any],
    directory: Path | None = None,
    replace: bool = False,
) -> Path:
    d = directory or nl.cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    existing = nl.load_cache_entries(d).get(nl.cache_key(req))
    if existing is not None and not replace:
        raise CacheWriteError(f"{existing.path.name} already answers this request (use --replace)")
    if existing is not None:
        existing.path.unlink()
    path = d / f"{entry_name(req)}.json"
    data = {
        "format": 1,
        "request": req.model_dump(mode="json", exclude_none=True),
        "response": resp.model_dump(mode="json", by_alias=True),
        "provenance": provenance,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    nl.load_cache_entries(d)  # the new entry loads exactly as the API will load it
    return path


def add_from_run(results: Path, item_id: str, directory: Path | None = None, replace: bool = False) -> Path:
    """Replay one eval item's saved model output (no LLM call)."""
    from lss.nl.evalset import load_eval_set

    run = json.loads(results.read_text(encoding="utf-8"))
    item = next((i for i in load_eval_set().items if i.id == item_id), None)
    saved = next((r for r in run["items"] if r["id"] == item_id), None)
    if item is None or saved is None or saved.get("output") is None:
        raise CacheWriteError(f"{item_id}: not in the eval set, or no saved output in {results.name}")
    recorded_for = date.fromisoformat(run["reference_date"])
    req = NLRequest(text=item.text, selected_site_id=item.context.selected_site_id)
    service = nl.NLService(
        executors=api.NL_EXECUTORS,
        provider_factory=lambda: FakeProvider({item.text: saved["output"]}),
        list_free_reasons=api.LIST_FREE_REASONS,
        today=lambda: recorded_for,
    )
    resp = _answer(service, req)
    provenance = {
        "source": f"replay of {results.name}, item {item_id}",
        "model": run.get("model"),
        "prompt_version": run.get("prompt_version"),
        "schema_version": run.get("schema_version"),
        "recorded_for_date": recorded_for.isoformat(),
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "contract_version": CONTRACT_VERSION,
        "est_cost_usd": 0.0,
    }
    return write_entry(req, resp, provenance, directory, replace)


def add_live(
    text: str,
    site_id: str | None = None,
    scenario_key: str | None = None,
    directory: Path | None = None,
    replace: bool = False,
    provider_factory=None,
) -> Path:
    """One live call through the demo's own pipeline (the project author's okay first)."""
    today = datetime.now(UTC).date()
    req = NLRequest(text=text, selected_site_id=site_id, selected_scenario=_scenario(scenario_key))
    service = nl.NLService(
        executors=api.NL_EXECUTORS,
        provider_factory=provider_factory or nl.default_provider,
        list_free_reasons=api.LIST_FREE_REASONS,
        today=lambda: today,
    )
    resp = _answer(service, req)
    provider = service.provider()
    provenance = {
        "source": "live",
        "model": getattr(provider, "model", None),
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "recorded_for_date": today.isoformat(),
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "contract_version": CONTRACT_VERSION,
        "est_cost_usd": round(service.meter.spent, 4),
    }
    return write_entry(req, resp, provenance, directory, replace)


def list_entries(directory: Path | None = None) -> list[str]:
    rows = []
    for entry in nl.load_cache_entries(directory or nl.cache_dir()).values():
        r = entry.request
        where = f" [site {r.selected_site_id}]" if r.selected_site_id else ""
        if r.selected_scenario:
            where += f" [scenario {r.selected_scenario.key()}]"
        rows.append(f"{entry.path.stem}: {r.text}{where} -> {type(entry.response).__name__}")
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cached showcase NL answers (C8).")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add-from-run", help="replay a saved eval run's output for one item (no LLM call)")
    a.add_argument("results", type=Path)
    a.add_argument("item_id")
    a.add_argument("--replace", action="store_true")
    b = sub.add_parser("add", help="one live call (needs the project author's okay)")
    b.add_argument("question")
    b.add_argument("--site", default=None)
    b.add_argument("--scenario-key", default=None)
    b.add_argument("--live", action="store_true", help="required: this calls the Anthropic API (costs money)")
    b.add_argument("--replace", action="store_true")
    sub.add_parser("list")
    r = sub.add_parser("remove")
    r.add_argument("name", help="file stem, as `list` prints it")
    args = p.parse_args(argv)
    try:
        if args.cmd == "add-from-run":
            print(f"wrote {add_from_run(args.results, args.item_id, replace=args.replace)}")
        elif args.cmd == "add":
            if not args.live:
                p.error("add calls the Anthropic API; pass --live (only with the project author's okay)")
            print(f"wrote {add_live(args.question, args.site, args.scenario_key, replace=args.replace)}")
        elif args.cmd == "list":
            print("\n".join(list_entries()) or "no cached answers")
        else:
            path = nl.cache_dir() / f"{args.name}.json"
            if not path.is_file():
                raise CacheWriteError(f"no cached answer {args.name}")
            path.unlink()
            print(f"removed {path}")
    except CacheWriteError as e:
        print(f"nl cache: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
