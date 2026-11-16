# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""IAU feature names for the globe labels (contract 0.14.0).

Stream E's `scripts/fetch_iau_names.py` writes `LSS_DATA_DIR/cache/features/iau_names.json` (format 1): the
Gazetteer of Planetary Nomenclature's adopted Moon names as compact rows `[id, name, type, lat, lon,
diameter_km]`. This module checks that file once and filters it per request; no engine imports.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from lss.config import get_settings
from lss.contract import (
    FEATURE_LABEL_FIELDS,
    SATELLITE_TYPE,
    BBox,
    FeatureLabelsQuery,
    FeatureLabelsResponse,
)

LABELS_FORMAT = 1
LABELS_FILE = "iau_names.json"
DATASET_ID = "iau_gazetteer_moon"
APPROVAL = "Adopted by IAU"

Row = tuple[int, str, str, float, float, float]


class FeatureLabelsError(ValueError):
    """The names file is missing a part the contract needs, or holds a value it can't serve."""


@dataclass(frozen=True)
class Labels:
    types: dict[str, str]
    rows: tuple[Row, ...]  # largest diameter first, ties by name


def features_dir() -> Path:
    return get_settings().data_dir / "cache" / "features"


def _row(raw: object, types: dict[str, str]) -> Row:
    if not isinstance(raw, list) or len(raw) != len(FEATURE_LABEL_FIELDS):
        raise FeatureLabelsError(f"a row isn't {len(FEATURE_LABEL_FIELDS)} values: {raw!r}")
    fid, name, kind, lat, lon, diam = raw
    if not isinstance(fid, int) or isinstance(fid, bool):
        raise FeatureLabelsError(f"id isn't an integer: {raw!r}")
    if not isinstance(name, str) or not name.strip():
        raise FeatureLabelsError(f"empty name: {raw!r}")
    if kind not in types:
        raise FeatureLabelsError(f"type {kind!r} isn't in the file's type list: {raw!r}")
    nums = (lat, lon, diam)
    if not all(isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v) for v in nums):
        raise FeatureLabelsError(f"lat, lon or diameter isn't a finite number: {raw!r}")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180 and diam >= 0):
        raise FeatureLabelsError(f"lat, lon or diameter out of range: {raw!r}")
    return (fid, name, kind, float(lat), float(lon), float(diam))


def load_labels(directory: Path | None = None) -> Labels | None:
    """The checked names, or None if no file is installed (the route then returns no rows)."""
    path = (directory or features_dir()) / LABELS_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise FeatureLabelsError(f"{path.name} can't be read: {e}") from e
    if data.get("format") != LABELS_FORMAT:
        raise FeatureLabelsError(f"{path.name} is format {data.get('format')!r}, not {LABELS_FORMAT}")
    if tuple(data.get("fields") or ()) != FEATURE_LABEL_FIELDS:
        raise FeatureLabelsError(f"{path.name} fields are {data.get('fields')!r}, not {FEATURE_LABEL_FIELDS}")
    if data.get("approval") != APPROVAL:
        raise FeatureLabelsError(f"{path.name} isn't limited to names {APPROVAL!r}")
    types = data.get("types")
    if not isinstance(types, dict) or not all(isinstance(v, str) for v in types.values()):
        raise FeatureLabelsError(f"{path.name} has no type list")
    rows = [_row(r, types) for r in data.get("features") or []]
    if not rows:
        raise FeatureLabelsError(f"{path.name} has no features")
    if len({r[0] for r in rows}) != len(rows):
        raise FeatureLabelsError(f"{path.name} repeats a feature id")
    rows.sort(key=lambda r: (-r[5], r[1], r[0]))
    return Labels(types=dict(sorted(types.items())), rows=tuple(rows))


def _in_bbox(row: Row, box: BBox) -> bool:
    lat, lon = row[3], row[4]
    if not box.lat_min <= lat <= box.lat_max:
        return False
    if box.lon_min <= box.lon_max:
        return box.lon_min <= lon <= box.lon_max
    return lon >= box.lon_min or lon <= box.lon_max  # the box crosses ±180°


def select(labels: Labels | None, query: FeatureLabelsQuery) -> FeatureLabelsResponse:
    rows: list[Row] = []
    if labels is not None:
        wanted = set(query.types)
        for r in labels.rows:  # largest first, so `limit` keeps the largest
            if wanted and r[2] not in wanted:
                continue
            if r[2] == SATELLITE_TYPE and not query.include_satellite and SATELLITE_TYPE not in wanted:
                continue
            if query.min_diameter_km is not None and r[5] < query.min_diameter_km:
                continue
            if query.bbox is not None and not _in_bbox(r, query.bbox):
                continue
            rows.append(r)
            if query.limit is not None and len(rows) >= query.limit:
                break
    return FeatureLabelsResponse(
        dataset_id=DATASET_ID,
        fields=list(FEATURE_LABEL_FIELDS),
        types=labels.types if labels else {},
        total=len(labels.rows) if labels else 0,
        rows=rows,
    )
