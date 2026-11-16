"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Location -> terrain stack resolver (plan section 3.2).

The engine never hard-codes a region: every elevation layer is listed below with its extent, and a
location gets whichever layers actually cover it, finest first. Adding terrain elsewhere (C7: global
coarse layer, north pole) is a data change here, not an engine change.

Extents are static metadata (polar stereographic metres, copied from the files' GeoTIFF headers and
checked against them by tests/engine/test_terrain.py when the files are present), so the resolver
works where the DEM files are absent, e.g. in the deployed API, which serves cached horizons.

Range split (where each layer is used along a ray; docs/methodology.md section 3): the covering
layers are used finest first, each from where the previous one stops out to its own `use_to_m`; the
last one always continues to the maximum ray range. The first layer is the near field.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from lss.contract import FidelityLabel, FidelityTier, Location, TerrainLayer
from lss.datafiles import get as datafile
from lss.terrain.core import DemLayer, ps_from_latlon


@dataclass(frozen=True)
class LayerSpec:
    file_id: str  # lss/datafiles.py id
    dataset_id: str  # lss/registry/datasets.yaml id
    resolution_m: float
    pole: str
    bounds_m: tuple[float, float, float, float]  # left, bottom, right, top (PS metres)
    label: str  # short user-facing name for fidelity summaries
    use_to_m: float | None  # farthest ray distance this layer is used for (None: no limit)
    site_tile: bool = False  # a local site map (product 78), not an area product

    def covers(self, x_m: float, y_m: float, margin_m: float = 0.0) -> bool:
        left, bottom, right, top = self.bounds_m
        return left + margin_m <= x_m <= right - margin_m and bottom + margin_m <= y_m <= top - margin_m

    def dem(self) -> DemLayer:
        """The layer's DEM (one shared instance per file, so its array is loaded once per process)."""
        return _dem(self.file_id, self.dataset_id, self.pole)


@cache
def _dem(file_id: str, dataset_id: str, pole: str) -> DemLayer:
    return DemLayer(dataset_id, datafile(file_id).path, pole)


# Site tiles (PGDA product 78, 5 m) and the polar maps (product 90). Bounds checked against the files by
# tests/engine/test_terrain.py when they are present.
SITE01_TILE = LayerSpec(
    "site01_dem",
    "pgda_78_site_dems",
    5.0,
    "south",
    (-19_000.0, -20_000.0, -3_000.0, -4_000.0),
    "5 m PGDA site map",
    use_to_m=5_000.0,
    site_tile=True,
)
POLAR_80M = LayerSpec(
    "ldem_80s_80m",
    "pgda_90_south_pole_dems",
    80.0,
    "south",
    (-304_000.0, -304_000.0, 304_000.0, 304_000.0),
    "80 m polar map",
    use_to_m=100_000.0,
)
POLAR_240M = LayerSpec(
    "ldem_60s_240m",
    "pgda_90_south_pole_dems",
    240.0,
    "south",
    (-931_200.0, -931_200.0, 931_200.0, 931_200.0),
    "240 m polar map",
    use_to_m=None,
)


def _site_tile(n: str, bounds: tuple[float, float, float, float]) -> LayerSpec:
    return LayerSpec(
        f"site{n}_dem", "pgda_78_site_dems", 5.0, "south", bounds, "5 m PGDA site map", 5_000.0, True
    )


# C3 sites (lss/registry/sites.yaml); bounds from the GeoTIFF headers (2026-11-15).
SITE_TILES_C3 = (
    _site_tile("04", (-9_000.0, -15_000.0, 7_000.0, 1_000.0)),
    _site_tile("07", (22_000.0, -28_000.0, 38_000.0, -12_000.0)),
    _site_tile("11", (-45_000.0, 7_000.0, -29_000.0, 23_000.0)),
)
# The C1 stack (the served Site01 result and its validation).
C1_LAYERS: tuple[LayerSpec, ...] = (SITE01_TILE, POLAR_80M, POLAR_240M)
# Every layer the resolver may choose from. The first three are C1_LAYERS (scripts index them).
LAYERS: tuple[LayerSpec, ...] = (*C1_LAYERS, *SITE_TILES_C3)

# The `use_to_m` defaults follow Barker et al. (2021): 5 m within 5 km, 80 m to 100 km, 240 m beyond.
# Checked, with the maximum ray range, by scripts/horizon_convergence.py (docs/methodology.md section 3.2).
MAX_RANGE_M = 400_000.0


@dataclass(frozen=True)
class StackLayer:
    spec: LayerSpec
    role: str  # "near_field" | "far_field"
    min_range_m: float
    max_range_m: float


@dataclass(frozen=True)
class TerrainStack:
    location: Location
    layers: tuple[StackLayer, ...]

    @property
    def supported(self) -> bool:
        return bool(self.layers)

    def contract_layers(self) -> list[TerrainLayer]:
        return [
            TerrainLayer(
                dataset_id=sl.spec.dataset_id,
                role=sl.role,
                resolution_m=sl.spec.resolution_m,
                max_range_km=sl.max_range_m / 1000.0,
            )
            for sl in self.layers
        ]

    def fidelity(self) -> FidelityLabel | None:
        if not self.layers:
            return None
        near = self.layers[0].spec
        far = [sl.spec for sl in self.layers[1:]]
        coarsest_far = max((s.resolution_m for s in far), default=None)
        if near.resolution_m <= 5 and far:
            tier = FidelityTier.high
        elif near.resolution_m <= 80:
            tier = FidelityTier.medium
        else:
            tier = FidelityTier.low
        far_text = " / ".join(s.label for s in far)
        summary = f"{near.label} near field" + (f", {far_text} far field" if far else "")
        return FidelityLabel(
            tier=tier,
            summary=summary,
            near_field_resolution_m=near.resolution_m,
            far_field_resolution_m=coarsest_far,
        )


def resolve(
    lat: float,
    lon: float,
    max_range_m: float = MAX_RANGE_M,
    layers: tuple[LayerSpec, ...] = LAYERS,
) -> TerrainStack:
    """The layers that cover (lat, lon), finest first, with the ray-distance range each is used over.

    A layer is a candidate only if the point lies inside it. A site tile is used only if it extends at
    least its `use_to_m` from the point in every direction, so rays never leave it early. One layer is
    kept per resolution (the first listed).
    """
    loc = Location(lat=lat, lon=lon)
    chosen: list[LayerSpec] = []
    for spec in sorted(layers, key=lambda s: s.resolution_m):  # stable: listing order breaks ties
        x, y = ps_from_latlon(lat, lon, spec.pole)
        margin = (spec.use_to_m or 0.0) if spec.site_tile else 0.0
        if not spec.covers(float(x), float(y), margin):
            continue
        if chosen and spec.resolution_m <= chosen[-1].resolution_m:
            continue
        chosen.append(spec)

    out: list[StackLayer] = []
    start = 0.0
    for i, spec in enumerate(chosen):
        last = i == len(chosen) - 1
        stop = max_range_m if last or spec.use_to_m is None else min(spec.use_to_m, max_range_m)
        if stop <= start:
            continue
        out.append(StackLayer(spec, "near_field" if not out else "far_field", start, stop))
        start = stop
        if stop >= max_range_m:
            break
    return TerrainStack(loc, tuple(out))
