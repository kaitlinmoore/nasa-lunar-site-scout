"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Precomputed results for the C1 thin slice (plan section 4.6: cached results are allowed).

`scripts/precompute_c1.py` writes one file per served scenario to `LSS_DATA_DIR/cache/served/`; this module
loads them, keyed by `Scenario.key()` (location, unit height, window and step all count). Nothing here
touches DEMs or SPICE kernels, so the deployed API needs only these files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from lss.config import get_settings
from lss.contract import CONTRACT_VERSION, MetricsResponse, Scenario, SeriesResponse


class ServedFileError(ValueError):
    """A served-result file that is inconsistent or made with another contract version."""


@dataclass(frozen=True)
class Served:
    scenario: Scenario
    metrics: MetricsResponse
    series: SeriesResponse
    path: Path


def served_dir() -> Path:
    return get_settings().cache_dir / "served"


def load_file(path: Path) -> Served:
    data = json.loads(path.read_text(encoding="utf-8"))
    m = MetricsResponse.model_validate(data["metrics"])
    s = SeriesResponse.model_validate(data["series"])
    key = m.scenario.key()
    if not (key == data["scenario_key"] == m.scenario_key == s.scenario_key == s.scenario.key()):
        raise ServedFileError(f"{path.name}: scenario keys disagree")
    if m.placeholder or s.placeholder:
        raise ServedFileError(f"{path.name}: placeholder data")
    for r in (m, s):
        if r.contract_version != CONTRACT_VERSION:
            raise ServedFileError(
                f"{path.name}: made with contract {r.contract_version}, the API is {CONTRACT_VERSION}; "
                "regenerate it with scripts/precompute_c1.py"
            )
    return Served(m.scenario, m, s, path)


def load_all(directory: Path | None = None) -> dict[str, Served]:
    """Every served result in the directory, by scenario key (empty if the directory is missing)."""
    d = directory or served_dir()
    out: dict[str, Served] = {}
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        sv = load_file(p)
        out[sv.scenario.key()] = sv
    return out


def differences(asked: Scenario, served: Scenario) -> list[str]:
    """Which parts of the scenario key differ, in words (for the 4xx reason)."""
    out = []
    if (asked.location.lat, asked.location.lon) != (served.location.lat, served.location.lon):
        out.append("location")
    if asked.unit_height_m != served.unit_height_m:
        out.append("unit_height_m")
    if asked.window_start != served.window_start:
        out.append("window_start")
    if asked.window_end != served.window_end:
        out.append("window_end")
    if asked.step != served.step:
        out.append("step")
    return out
