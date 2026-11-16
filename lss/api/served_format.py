"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

The "result format" of a contract version: the JSON Schemas of the bodies a served file holds
(MetricsResponse, SeriesResponse, HorizonProfile) and every schema they reference, taken from that version's
`fixtures/openapi.json`, normalized so that only the format is compared:
- `description` and `title` are removed (wording);
- `"default": null` is removed (an annotation; FastAPI's and pydantic's exports differ on writing it);
- the default of `contract_version` is removed (it is the version itself).
Everything else counts: types, required fields, enums, value limits, `additionalProperties`, non-null
defaults (e.g. a Scenario `step` default).

An older version may be listed in `lss.api.served.COMPATIBLE_VERSIONS` only if its result format equals the
current one. `tests/api/test_served_format.py` checks this against a snapshot per listed version, made from
that version's committed OpenAPI document:

    git show <commit at that version>:fixtures/openapi.json > old_openapi.json
    uv run python -m lss.api.served_format old_openapi.json tests/api/served_formats/<version>.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SERVED_MODELS = ("MetricsResponse", "SeriesResponse", "HorizonProfile")
REF_PREFIX = "#/components/schemas/"
WORDING_KEYS = frozenset({"description", "title"})


def _strip(node):
    if isinstance(node, dict):
        out = {
            k: _strip(v)
            for k, v in node.items()
            if k not in WORDING_KEYS and not (k == "default" and v is None)
        }
        version = out.get("properties", {}).get("contract_version")
        if isinstance(version, dict):
            version.pop("default", None)
        return out
    if isinstance(node, list):
        return [_strip(v) for v in node]
    return node


def _refs(node, found: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith(REF_PREFIX):
            found.add(ref.removeprefix(REF_PREFIX))
        for v in node.values():
            _refs(v, found)
    elif isinstance(node, list):
        for v in node:
            _refs(v, found)


def result_format(openapi: dict) -> dict:
    """The served bodies' schemas and their transitive references, wording removed, plus the version."""
    schemas = openapi["components"]["schemas"]
    todo, seen = list(SERVED_MODELS), set()
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        found: set[str] = set()
        _refs(schemas[name], found)
        todo.extend(found - seen)
    return {
        "contract_version": openapi["info"]["x-contract-version"],
        "schemas": {name: _strip(schemas[name]) for name in sorted(seen)},
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: python -m lss.api.served_format OPENAPI_JSON OUT_JSON", file=sys.stderr)
        return 2
    doc = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    out = Path(args[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result_format(doc), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {out} (contract {doc['info']['x-contract-version']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
