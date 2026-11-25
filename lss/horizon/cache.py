"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Horizon cache in `LSS_DATA_DIR/cache/horizon/` (horizons depend only on location and unit height, so they are
computed once and reused for any date window).

The cache key is a SHA-256 of everything that changes the result: algorithm version, location, unit
height, numerical settings, and the terrain stack (file ids, source URLs, ray-distance ranges). The key
needs no DEM files, so a deployment can serve cached horizons without them. Each file also records the
DEMs' SHA-256 from `MANIFEST.json` (when present) for provenance; that is not part of the key.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from lss.config import get_settings
from lss.datafiles import get as datafile
from lss.horizon.core import (
    HORIZON_VERSION,
    Horizon,
    HorizonParams,
    HorizonUnavailable,
    compute_horizon,
    segments_for,
)
from lss.registry.terrain import LAYERS, LayerSpec, TerrainStack, resolve


def cache_dir() -> Path:
    return get_settings().cache_dir / "horizon"


def key_spec(
    lat: float, lon: float, unit_height_m: float, params: HorizonParams, stack: TerrainStack
) -> dict:
    return {
        "version": HORIZON_VERSION,
        "lat": float(lat),
        "lon": float(lon),
        "unit_height_m": float(unit_height_m),
        "params": asdict(params),
        "layers": [
            {
                "file_id": sl.spec.file_id,
                "url": datafile(sl.spec.file_id).url,
                "min_range_m": sl.min_range_m,
                "max_range_m": sl.max_range_m,
            }
            for sl in stack.layers
        ],
    }


def cache_key(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def cache_path(spec: dict, directory: Path | None = None) -> Path:
    s = spec
    name = f"h_{s['lat']:+.5f}_{s['lon']:+.5f}_{s['unit_height_m']:g}m_{cache_key(s)[:16]}.npz"
    return (directory or cache_dir()) / name


def _provenance(spec: dict) -> dict:
    manifest = get_settings().data_dir / "MANIFEST.json"
    entries = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
    return {layer["file_id"]: entries.get(layer["file_id"], {}).get("sha256") for layer in spec["layers"]}


def save(h: Horizon, spec: dict, path: Path) -> None:
    meta = {
        "key": spec,
        "surface_height_m": h.surface_height_m,
        "missing_samples": h.missing_samples,
        "total_samples": h.total_samples,
        "layers": list(h.layers),
        "dem_sha256": _provenance(spec),
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    buf = io.BytesIO()
    np.savez_compressed(
        buf,
        azimuth_deg=h.azimuth_deg,
        elevation_deg=h.elevation_deg,
        distance_m=h.distance_m,
        meta=np.array(json.dumps(meta, sort_keys=True)),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_bytes(buf.getvalue())
    part.replace(path)


def load(path: Path, spec: dict) -> Horizon | None:
    """The cached horizon, or None if absent or written for a different key."""
    if not path.is_file():
        return None
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(str(z["meta"]))
        if meta.get("key") != spec:
            return None
        az, el, dist = z["azimuth_deg"], z["elevation_deg"], z["distance_m"]
    return Horizon(
        lat=spec["lat"],
        lon=spec["lon"],
        unit_height_m=spec["unit_height_m"],
        surface_height_m=meta["surface_height_m"],
        azimuth_deg=az,
        elevation_deg=el,
        distance_m=dist,
        missing_samples=meta["missing_samples"],
        total_samples=meta["total_samples"],
        params=HorizonParams(**spec["params"]),
        layers=tuple(meta["layers"]),
    )


def cached_horizon(
    lat: float,
    lon: float,
    unit_height_m: float,
    params: HorizonParams | None = None,
    layers: tuple[LayerSpec, ...] = LAYERS,
    recompute: bool = False,
    directory: Path | None = None,
) -> Horizon:
    """The horizon for (location, unit height): from the cache if present, else computed and stored."""
    params = params or HorizonParams()
    stack = resolve(lat, lon, params.max_range_m, layers)
    if not stack.supported:
        raise HorizonUnavailable(stack.reason or f"no terrain layer covers ({lat}, {lon})")
    spec = key_spec(lat, lon, unit_height_m, params, stack)
    path = cache_path(spec, directory)
    if not recompute and (h := load(path, spec)) is not None:
        return h
    h = compute_horizon(lat, lon, unit_height_m, segments_for(stack), params)
    save(h, spec, path)
    return h
