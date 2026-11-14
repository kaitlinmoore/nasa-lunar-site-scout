"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Export the contract to `fixtures/`: `openapi.json` plus every example response.

    uv run python -m lss.contract.export           # write fixtures/
    uv run python -m lss.contract.export --check   # exit 1 if fixtures/ is stale

`openapi.json` = the FastAPI app's OpenAPI document, with every contract model added to
`components.schemas` (including models whose endpoints don't exist yet), so the web can
generate TypeScript types for the whole contract.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from lss.config import FIXTURES_DIR
from lss.contract import models
from lss.contract.examples import EXAMPLES, dump


def contract_models() -> list[type[BaseModel]]:
    return [
        obj
        for _, obj in inspect.getmembers(models, inspect.isclass)
        if issubclass(obj, BaseModel)
        and obj.__module__ == models.__name__
        and obj not in (models.Model, models.Response)
    ]


def build_openapi() -> dict:
    from lss.api.app import create_app

    doc = create_app().openapi()
    _, defs = models_json_schema(
        [(m, "validation") for m in contract_models()],
        ref_template="#/components/schemas/{model}",
    )
    schemas = doc.setdefault("components", {}).setdefault("schemas", {})
    for name, schema in defs.get("$defs", {}).items():
        schemas.setdefault(name, schema)
    doc["components"]["schemas"] = dict(sorted(schemas.items()))
    doc["info"]["x-contract-version"] = models.CONTRACT_VERSION
    return doc


def render(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def outputs() -> dict[str, str]:
    files = {name: render(dump(build())) for name, (build, _) in EXAMPLES.items()}
    files["openapi.json"] = render(build_openapi())
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    parser.add_argument("--check", action="store_true", help="fail if fixtures/ is out of date")
    args = parser.parse_args(argv)

    FIXTURES_DIR.mkdir(exist_ok=True)
    stale = []
    for name, text in outputs().items():
        path = FIXTURES_DIR / name
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        stale.append(name)
        if not args.check:
            path.write_text(text, encoding="utf-8", newline="\n")
    if args.check and stale:
        print(f"fixtures out of date: {stale}. Run: uv run python -m lss.contract.export")
        return 1
    print(f"{'stale' if args.check else 'wrote'}: {stale or 'nothing (up to date)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
