"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Location -> terrain stack resolver.

The engine never hard-codes a region: every elevation layer is listed below with its extent, and a
location gets whichever layers actually cover it, finest first. Adding terrain elsewhere (the global
coarse layer, the north pole) is a data change here, not an engine change.

Extents are static metadata (polar stereographic metres, copied from the files' GeoTIFF headers and
checked against them by tests/engine/test_terrain.py when the files are present), so the resolver
works where the DEM files are absent, e.g. in the deployed API, which serves cached horizons.

Range split (where each layer is used along a ray; docs/methodology.md section 3): the covering
layers are used finest first, each from where the previous one stops out to its own `use_to_m`; the
last one always continues to the maximum ray range. The first layer is the near field.

Full ray range: the last map layer must hold every point within the maximum ray range of the location. Where
it does not (rays would leave it, as from the 240 m polar map north of about 73 deg S), the map layers are
used out to the distance their last layer does hold in every direction (`full_reach_m`), and the global
layer from there to the maximum range. Without a global layer such a location is refused (`reason`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from functools import cache

from lss.contract import FidelityLabel, FidelityTier, Location, TerrainLayer
from lss.datafiles import get as datafile
from lss.terrain.core import MOON_RADIUS_M, DemLayer, ps_from_latlon


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


# The other curated PGDA sites (lss/registry/sites.yaml); bounds from the GeoTIFF headers (2026-11-15).
SITE_TILES_C3 = (
    _site_tile("04", (-9_000.0, -15_000.0, 7_000.0, 1_000.0)),
    _site_tile("07", (22_000.0, -28_000.0, 38_000.0, -12_000.0)),
    _site_tile("11", (-45_000.0, 7_000.0, -29_000.0, 23_000.0)),
    _site_tile("06", (74_000.0, 100_000.0, 94_000.0, 120_000.0)),
    _site_tile("20", (65_000.0, 110_000.0, 81_000.0, 126_000.0)),
    _site_tile("23", (-11_000.0, 111_000.0, 10_000.0, 132_000.0)),
    _site_tile("42", (-123_400.0, -66_100.0, -103_400.0, -46_100.0)),
)


@dataclass(frozen=True)
class GlobalLayerSpec(LayerSpec):
    """The global coarse layer (docs/methodology.md section 3.5): LOLA LDEM_128 on a latitude /
    longitude grid, read by window around each point (lss.terrain.global_layer).

    Used only where no other layer covers the point (`resolve`), so every location the polar maps cover keeps
    exactly the stack it had before the global layer was added. `resolve` returns a copy with `centre` and
    `window_m` set; `dem()` then reads that window.
    """

    label_file_id: str = ""
    centre: tuple[float, float] | None = None  # (lat, lon) of the point the window is read around
    window_m: float = 0.0  # arc radius of the window (the maximum ray range)

    def covers(self, x_m: float, y_m: float, margin_m: float = 0.0) -> bool:
        return True

    def dem(self):
        from lss.terrain.global_layer import cached_window

        if self.centre is None:
            raise ValueError("the global layer is read around a point: use the spec returned by resolve()")
        return cached_window(
            datafile(self.file_id).path, datafile(self.label_file_id).path, *self.centre, self.window_m
        )


GLOBAL_128 = GlobalLayerSpec(
    "ldem_128_img",
    "lola_ldem_128",
    236.901,  # MAP_SCALE: pixel size along a meridian (east-west: 236.901 m x cos(latitude))
    "global",
    (-math.inf, -math.inf, math.inf, math.inf),
    "237 m global map (LOLA LDEM_128)",
    use_to_m=None,
    label_file_id="ldem_128_lbl",
)

# Site01's stack (the first served scenario and its validation).
C1_LAYERS: tuple[LayerSpec, ...] = (SITE01_TILE, POLAR_80M, POLAR_240M)
# Every layer the resolver may choose from. The first three are C1_LAYERS (scripts index them). The global
# layer is last and is chosen only where no other layer covers the point.
LAYERS: tuple[LayerSpec, ...] = (*C1_LAYERS, *SITE_TILES_C3, GLOBAL_128)

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
    reason: str | None = None  # why an empty stack is refused, when that is more than "no layer covers it"

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


def holds_cap(spec: LayerSpec, lat: float, lon: float, range_m: float) -> bool:
    """True if every point within ray distance `range_m` of (lat, lon) lies on the map, at least one pixel
    inside its edges (heights are bilinear between pixel centres, which stop half a pixel inside).

    Exact: polar stereographic projection maps the cap of points within angular distance delta of the
    location to a circle. On the location's meridian the cap spans colatitudes c - delta to c + delta (from
    the projection's pole), so the circle's centre and radius follow from rho(t) = 2 R tan(t / 2), signed (a
    cap over the pole has c - delta < 0).
    """
    left, bottom, right, top = spec.bounds_m
    delta = range_m / MOON_RADIUS_M
    colat = math.radians(90.0 + lat) if spec.pole == "south" else math.radians(90.0 - lat)
    if colat + delta >= math.pi:  # the cap reaches the far pole: its image is unbounded
        return False
    rho_far = 2.0 * MOON_RADIUS_M * math.tan((colat + delta) / 2.0)
    rho_near = 2.0 * MOON_RADIUS_M * math.tan((colat - delta) / 2.0)
    x, y = (float(v) for v in ps_from_latlon(lat, lon, spec.pole))
    rho = math.hypot(x, y)
    ux, uy = (x / rho, y / rho) if rho > 0.0 else (0.0, 1.0)  # at the pole the centre is 0: any direction
    mid, rad = 0.5 * (rho_far + rho_near), 0.5 * (rho_far - rho_near)
    cx, cy, m = mid * ux, mid * uy, spec.resolution_m
    return left + m <= cx - rad and cx + rad <= right - m and bottom + m <= cy - rad and cy + rad <= top - m


def full_reach_m(spec: LayerSpec, lat: float, lon: float, max_range_m: float) -> float:
    """The largest ray distance (<= max_range_m, to 1 m, rounded down) that the map holds from (lat, lon) in
    every direction (`holds_cap`); 0 if it does not hold the point itself."""
    if holds_cap(spec, lat, lon, max_range_m):
        return float(max_range_m)
    lo, hi = 0.0, float(max_range_m)
    if not holds_cap(spec, lat, lon, lo):
        return 0.0
    while hi - lo > 1.0:  # caps are nested, so holds_cap is monotone in the range
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if holds_cap(spec, lat, lon, mid) else (lo, mid)
    return float(math.floor(lo))


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

    The last map layer must hold the whole ray range in every direction. Where it does not, the map layers
    stop at the distance it does hold (`full_reach_m`) and the global layer is used from there to the
    maximum range; without a global layer the location is refused (empty stack with a `reason`).
    """
    loc = Location(lat=lat, lon=lon)
    chosen: list[LayerSpec] = []
    for spec in sorted(layers, key=lambda s: s.resolution_m):  # stable: listing order breaks ties
        if isinstance(spec, GlobalLayerSpec):  # considered below, only if nothing else covers the point
            continue
        x, y = ps_from_latlon(lat, lon, spec.pole)
        margin = (spec.use_to_m or 0.0) if spec.site_tile else 0.0
        if not spec.covers(float(x), float(y), margin):
            continue
        if chosen and spec.resolution_m <= chosen[-1].resolution_m:
            continue
        chosen.append(spec)
    fallback = [s for s in layers if isinstance(s, GlobalLayerSpec)]
    around = (
        [replace(fallback[0], centre=(float(lat), float(lon)), window_m=float(max_range_m))]
        if fallback
        else []
    )
    if not chosen:  # off every polar map, the global layer alone, read around this point
        chosen = around
    limit = max_range_m  # how far along a ray the map layers are used
    far: list[GlobalLayerSpec] = []
    if chosen and not isinstance(chosen[-1], GlobalLayerSpec):
        reach = full_reach_m(chosen[-1], lat, lon, max_range_m)
        if reach < max_range_m:
            if not around:
                why = (
                    f"rays from ({lat}, {lon}) leave the {chosen[-1].label} after {reach / 1000.0:.1f} km, "
                    f"short of the {max_range_m / 1000.0:.0f} km ray range, and no global layer is available"
                )
                return TerrainStack(loc, (), reason=why)
            limit, far = reach, around

    out: list[StackLayer] = []
    start = 0.0
    for i, spec in enumerate(chosen):
        last = i == len(chosen) - 1
        stop = limit if last or spec.use_to_m is None else min(spec.use_to_m, limit)
        if stop <= start:
            continue
        out.append(StackLayer(spec, "near_field" if not out else "far_field", start, stop))
        start = stop
        if stop >= limit:
            break
    for spec in far:  # beyond the maps' full reach: the global layer, to the maximum range
        out.append(StackLayer(spec, "near_field" if not out else "far_field", start, max_range_m))
    return TerrainStack(loc, tuple(out))
