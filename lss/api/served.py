"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Precomputed results: the API serves only results computed ahead of time.

The precompute scripts (scripts/precompute_c1.py, scripts/precompute_c3.py) write one file per served scenario
to `LSS_DATA_DIR/cache/served/`; this module loads them, keyed by `Scenario.key()` (location, unit height,
window and step all count). Nothing here touches DEMs or SPICE kernels, so the deployed API needs only these
files.

File format (JSON object; owned here, written by the precompute scripts):
- `format`: 1 or 2; `scenario_key`; `provenance` (free-form, not served);
- `metrics`: a MetricsResponse body; `series`: a SeriesResponse body;
- format 2 adds `horizon`: the HorizonProfile body for the scenario's location and unit height (optional;
  without it, /api/horizon has no profile for that location and height);
- format 3 adds `sun_elevation_histogram` (methodology 5.3): `{quantity, bin_deg, first_edge_deg, seconds:
  [...], total_seconds}`, the seconds the Sun's disc-centre apparent elevation spends in each bin over the
  window (they sum to the window). Optional: without it, a compare on a Sun elevation band has no value (not
  computed) for that scenario. Read with `band_fraction` below (lss.metrics.elevation_band).
All bodies must be made with the same contract version.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from lss.config import get_settings
from lss.contract import (
    CONTRACT_VERSION,
    HorizonProfile,
    HorizonRequest,
    MetricsResponse,
    Scenario,
    ScenarioField,
    SeriesResponse,
    TerrainRequest,
    TerrainResponse,
)

# The engine's band arithmetic; this module imports only numpy (lss.metrics exports are lazy).
from lss.metrics.elevation_band import band_fraction as elevation_band_fraction

# Older contract versions whose served bodies (MetricsResponse, SeriesResponse, HorizonProfile,
# TerrainResponse) are unchanged in the current contract. Files made with them are still served, stamped with
# the current version; any other version is refused (503) until the file is regenerated. Maintained by
# the contract owner (the project author, 2026-11-15):
# - list a version only if its result format equals the current one: tests/api/test_served_format.py checks
#   each against a snapshot in tests/api/served_formats/ (how to make one: lss/api/served_format.py);
# - drop a version, and its snapshot, once the served files have been regenerated at a newer version.
#   0.5.0 and 0.6.0 dropped 2026-11-16: every served file regenerated (format 2, with horizons) at 0.7.0.
#   0.7.0 and 0.8.0 dropped 2026-11-16: every served and terrain file regenerated at 0.9.0.
#   0.10.0 and 0.11.0 dropped 2026-11-16: every served file regenerated at 0.12.0 (format 3).
#   0.9.0 dropped 2026-11-16: the 16 terrain statistics regenerated at 0.12.0.
#   0.12.0: the installed served files and most cached NL answers (contract 0.13.0 only added the terrain
#   views, CompareResponse.compared_keys and StaticIndex.terrain_views); drop once regenerated.
#   0.13.0: the installed terrain statistics and two cached answers (contract 0.14.0 only added the feature
#   labels and StaticIndex.feature_labels).
COMPATIBLE_VERSIONS = frozenset({"0.12.0", "0.13.0"})


class ServedFileError(ValueError):
    """A served-result file that is inconsistent or made with an incompatible contract version."""


@dataclass(frozen=True)
class Served:
    scenario: Scenario
    metrics: MetricsResponse
    series: SeriesResponse
    path: Path
    made_with: str  # the contract version the file was written with
    horizon: HorizonProfile | None = None
    sun_elevation_histogram: dict | None = None  # format 3

    @property
    def horizon_key(self) -> str:
        """HorizonRequest.key() of this scenario's location and unit height."""
        return horizon_key(
            self.scenario.location.lat, self.scenario.location.lon, self.scenario.unit_height_m
        )


def horizon_key(lat: float, lon: float, unit_height_m: float) -> str:
    return HorizonRequest(location={"lat": lat, "lon": lon}, unit_height_m=unit_height_m).key()


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
    h = HorizonProfile.model_validate(data["horizon"]) if data.get("horizon") is not None else None
    if h is not None:
        same_point = (h.location.lat, h.location.lon) == (m.scenario.location.lat, m.scenario.location.lon)
        if not same_point or h.unit_height_m != m.scenario.unit_height_m:
            raise ServedFileError(f"{path.name}: the horizon is for another location or unit height")
        if h.placeholder:
            raise ServedFileError(f"{path.name}: placeholder horizon")
    versions = {r.contract_version for r in (m, s, h) if r is not None}
    if len(versions) != 1:
        raise ServedFileError(f"{path.name}: its parts were made with different contract versions")
    made_with = m.contract_version
    if made_with != CONTRACT_VERSION and made_with not in COMPATIBLE_VERSIONS:
        raise ServedFileError(
            f"{path.name}: made with contract {made_with}, the API is {CONTRACT_VERSION}; "
            "regenerate it with scripts/precompute_c1.py"
        )
    hist = data.get("sun_elevation_histogram")
    if hist is not None:
        _check_histogram(path, hist, s)
    stamp = {"contract_version": CONTRACT_VERSION}
    return Served(
        m.scenario,
        m.model_copy(update=stamp),
        s.model_copy(update=stamp),
        path,
        made_with,
        h.model_copy(update=stamp) if h is not None else None,
        hist,
    )


def _check_histogram(path: Path, hist: dict, series: SeriesResponse) -> None:
    """Shape checks for a format-3 histogram: positive bin, non-negative seconds that sum to the window."""
    try:
        seconds = [float(x) for x in hist["seconds"]]
        bin_deg, total = float(hist["bin_deg"]), float(hist["total_seconds"])
        float(hist["first_edge_deg"])
    except (KeyError, TypeError, ValueError) as e:
        raise ServedFileError(f"{path.name}: malformed sun_elevation_histogram ({e})") from e
    window = (series.scenario.window_end - series.scenario.window_start).total_seconds()
    if (
        bin_deg <= 0
        or any(x < 0 for x in seconds)
        or abs(total - window) > 1.0
        or abs(sum(seconds) - total) > 1.0
    ):
        raise ServedFileError(f"{path.name}: sun_elevation_histogram doesn't cover the window")


def band_fraction(sv: Served, min_deg: float, max_deg: float) -> float | None:
    """Fraction of the window with the Sun's elevation in [min_deg, max_deg] (lss.metrics `band_fraction`), or
    None when the served file has no histogram (format < 3)."""
    if sv.sun_elevation_histogram is None:
        return None
    return float(elevation_band_fraction(sv.sun_elevation_histogram, min_deg, max_deg))


def load_all(directory: Path | None = None) -> dict[str, Served]:
    """Every served result in the directory, by scenario key (empty if the directory is missing)."""
    d = directory or served_dir()
    out: dict[str, Served] = {}
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        sv = load_file(p)
        key = sv.scenario.key()
        if key in out:
            raise ServedFileError(f"{p.name} and {out[key].path.name} serve the same scenario ({key})")
        out[key] = sv
    return out


def horizons(served: dict[str, Served]) -> dict[str, Served]:
    """One served scenario per horizon key, among those whose file has a horizon (first by scenario key)."""
    out: dict[str, Served] = {}
    for sv in served.values():
        if sv.horizon is not None:
            out.setdefault(sv.horizon_key, sv)
    return out


def differences(asked: Scenario | HorizonRequest, served: Scenario) -> list[ScenarioField]:
    """Which parts of the scenario key differ (for the 422 body); a HorizonRequest has no window or step."""
    out = []
    if (asked.location.lat, asked.location.lon) != (served.location.lat, served.location.lon):
        out.append(ScenarioField.location)
    if asked.unit_height_m != served.unit_height_m:
        out.append(ScenarioField.unit_height_m)
    if isinstance(asked, HorizonRequest):
        return out
    if asked.window_start != served.window_start:
        out.append(ScenarioField.window_start)
    if asked.window_end != served.window_end:
        out.append(ScenarioField.window_end)
    if asked.step != served.step:
        out.append(ScenarioField.step)
    return out


# ----------------------------------------------------------- slope statistics (cache/terrain/)
# Written by scripts/precompute_terrain.py: one file per site, `{"format": 1, "site_id",
# "terrain": [TerrainResponse, ...], "provenance"}` (1 km on the 5 m site map, 10 km on the 10 m map).
# Same rules as served files: current or compatible contract version, not placeholder, no duplicates.


@dataclass(frozen=True)
class ServedTerrain:
    body: TerrainResponse
    path: Path
    made_with: str

    @property
    def key(self) -> str:
        return terrain_key(self.body.location.lat, self.body.location.lon, self.body.radius_m)


def terrain_key(lat: float, lon: float, radius_m: float) -> str:
    return TerrainRequest(location={"lat": lat, "lon": lon}, radius_m=radius_m).key()


def terrain_dir() -> Path:
    return get_settings().cache_dir / "terrain"


def load_terrain(directory: Path | None = None) -> dict[str, ServedTerrain]:
    """Every precomputed slope statistic in the directory, by TerrainRequest.key() (empty if missing)."""
    d = directory or terrain_dir()
    out: dict[str, ServedTerrain] = {}
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        data = json.loads(p.read_text(encoding="utf-8"))
        for raw in data["terrain"]:
            body = TerrainResponse.model_validate(raw)
            if body.placeholder:
                raise ServedFileError(f"{p.name}: placeholder data")
            made_with = body.contract_version
            if made_with != CONTRACT_VERSION and made_with not in COMPATIBLE_VERSIONS:
                raise ServedFileError(
                    f"{p.name}: made with contract {made_with}, the API is {CONTRACT_VERSION}; "
                    "regenerate it with scripts/precompute_terrain.py"
                )
            st = ServedTerrain(body.model_copy(update={"contract_version": CONTRACT_VERSION}), p, made_with)
            if st.key in out:
                raise ServedFileError(f"{p.name} and {out[st.key].path.name}: the same location and radius")
            out[st.key] = st
    return out
