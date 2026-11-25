"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Loader for the curated site registry (`sites.yaml`).

`load_sites()` returns contract `Site` objects (what /api/sites serves), every category. `site_points()`
returns the engine's provenance (rule, 5 m tile, polar stereographic point) for the PGDA polar sites only, the
entries with a `point`; used by the served-scenario precompute (scripts/precompute_c3.py) and checked by
tests/engine/test_sites.py. Sites elsewhere (e.g. the Apollo sites) have no product 78 tile and no `point`, so
it does not list them.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from lss.contract import Location, Site

SITES_PATH = Path(__file__).with_name("sites.yaml")
RULES = ("largest_roi_centroid", "mazarico_2011")


@dataclass(frozen=True)
class SitePoint:
    site_id: str
    rule: str
    tile: str  # PGDA product 78 tile name, e.g. "Site01"
    ps_m: tuple[float, float]
    roi: int | None = None
    roi_area_m2: float | None = None
    centroid_from: str | None = None


@lru_cache(maxsize=1)
def _raw(path: Path = SITES_PATH) -> tuple[dict, ...]:
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))["sites"]
    ids = [e["id"] for e in entries]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate site ids in registry: {sorted(dupes)}")
    return tuple(entries)


def load_sites() -> tuple[Site, ...]:
    """Every curated site as a contract Site (the location carries the site name)."""
    out = []
    for e in _raw():
        fields = {k: v for k, v in e.items() if k != "point"}
        fields["location"] = Location(**e["location"], name=e["name"])
        out.append(Site.model_validate(fields))
    return tuple(out)


def site_points() -> dict[str, SitePoint]:
    out = {}
    for e in _raw():
        if "point" not in e:  # not a PGDA tile site
            continue
        p = e["point"]
        if p["rule"] not in RULES:
            raise ValueError(f"{e['id']}: unknown point rule {p['rule']!r}")
        out[e["id"]] = SitePoint(
            e["id"],
            p["rule"],
            p["tile"],
            (float(p["ps_m"][0]), float(p["ps_m"][1])),
            p.get("roi"),
            p.get("roi_area_m2"),
            p.get("centroid_from"),
        )
    return out


def get_site(site_id: str) -> Site:
    for s in load_sites():
        if s.id == site_id:
            return s
    raise KeyError(site_id)
