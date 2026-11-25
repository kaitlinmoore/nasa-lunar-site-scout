"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Power and DTE comms metrics from a series.

Exports are loaded lazily (PEP 562), so `import lss.metrics.elevation_band` (the Sun-elevation band functions
the API uses on served data) loads only numpy, not SPICE, numba or the terrain code that `lss.metrics.core`
needs. `from lss.metrics import power_metrics` and the like work as before.
"""

from __future__ import annotations

import importlib

_EXPORTS = {
    "azimuth_arc": "core",
    "comms_metrics": "core",
    "longest": "core",
    "metrics_response": "core",
    "overlap_s": "core",
    "power_metrics": "core",
    "stat": "core",
    "time_mean": "core",
    "ElevationHistogram": "elevation_band",
    "band_fraction": "elevation_band",
    "band_seconds": "elevation_band",
    "elevation_histogram": "elevation_band",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module 'lss.metrics' has no attribute {name!r}")
    value = getattr(importlib.import_module(f"lss.metrics.{module}"), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))
