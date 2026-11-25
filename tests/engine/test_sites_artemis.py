# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""The Artemis III candidate regions in the curated registry (lss/registry/sites.yaml; the project author,
2026-11-16).

Region names: NASA release 24-136 (28 October 2024), in its order. Each point is the centre of the region's
1 km grid box in McClernan (2024), U.S. Geological Survey data release doi:10.5066/P1MEQ6UK. The table below
is copied from that release: the box is the header of each zip's <stem>_PolarLGRS_ACC_1km_S_Grid.shp (lunar
polar stereographic metres: false easting/northing 500 km, scale factor 0.994, 1737.4 km sphere, from its
.prj), and the bounds are westbc, eastbc, northbc, southbc of the region's <stem>_1km.xml, as written there.
"""

import math

import pytest

from lss.contract import SiteCategory, display_name
from lss.registry import terrain as reg
from lss.registry.sites import load_sites, site_points
from lss.terrain.core import latlon_from_ps

K0, FALSE_ORIGIN_M = 0.994, 500_000.0

# id slug -> (NASA name, USGS zip stem, 1 km box (xmin, ymin, xmax, ymax) m, XML bounds (W, E, N, S) deg)
USGS_2024 = {
    "peak-near-cabeus-b": (
        "Peak near Cabeus B",
        "Peak_Near_Cabeus_B",
        (311000, 559000, 332000, 580000),
        ("-72.6632", "-64.5367", "-83.4383", "-83.8326"),
    ),
    "haworth": (
        "Haworth",
        "Haworth",
        (447000, 575000, 478000, 605000),
        ("-35.2476", "-11.8336", "-86.4419", "-86.9539"),
    ),
    "malapert-massif": (
        "Malapert Massif",
        "Malapert_Massif",
        (489000, 610000, 510000, 632000),
        ("-5.7106", "4.3323", "-85.6102", "-86.3336"),
    ),
    "mons-mouton-plateau": (
        "Mons Mouton Plateau",
        "Mons_Mouton_Plateau",
        (548000, 618000, 626000, 676000),
        ("22.1355", "35.5992", "-82.8281", "-85.7755"),
    ),
    "mons-mouton": (
        "Mons Mouton",
        "Mons_Mouton",
        (564000, 609000, 581000, 626000),
        ("30.4196", "32.7352", "-85.0335", "-85.8083"),
    ),
    "nobile-rim-1": (
        "Nobile Rim 1",
        "Nobile_Rim_1",
        (573000, 599000, 594000, 620000),
        ("36.4041", "38.0728", "-84.9460", "-85.9208"),
    ),
    "nobile-rim-2": (
        "Nobile Rim 2",
        "Nobile_Rim_2",
        (646000, 584000, 666000, 605000),
        ("57.6854", "60.0864", "-83.4904", "-84.4161"),
    ),
    "de-gerlache-rim-2": (
        "de Gerlache Rim 2",
        "de_Gerlache_Rim_2",
        (441000, 512000, 462000, 533000),
        ("-78.5034", "-49.0283", "-88.0027", "-88.3304"),
    ),
    "slater-plain": (
        "Slater Plain",
        "Slater_Plain",
        (559000, 440000, 580000, 461000),
        ("115.9892", "135.4815", "-87.0479", "-87.2088"),
    ),
}
# Regions whose box contains a curated site: the site's short name, as the description names it.
NEAR_SITE = {
    "malapert-massif": "Malapert Massif",
    "mons-mouton": "Leibnitz Beta Plateau",
    "nobile-rim-1": "Nobile Rim",
}


def lps_to_latlon(x_m, y_m):
    """USGS lunar polar stereographic (south) -> lat, lon, via the engine's k = 1 projection."""
    lat, lon = latlon_from_ps((x_m - FALSE_ORIGIN_M) / K0, (y_m - FALSE_ORIGIN_M) / K0, "south")
    return float(lat), float(lon)


def lps_to_latlon_direct(x_m, y_m):
    """The same, written out from the .prj parameters (independent of lss.terrain.core)."""
    x, y = x_m - FALSE_ORIGIN_M, y_m - FALSE_ORIGIN_M
    rho = math.hypot(x, y)
    lat = 2.0 * math.degrees(math.atan(rho / (2.0 * 1_737_400.0 * K0))) - 90.0
    return lat, math.degrees(math.atan2(x, y))


def arc_km(a, b):
    (p1, l1), (p2, l2) = [(math.radians(u), math.radians(v)) for u, v in (a, b)]
    c = math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(l1 - l2)
    return 1737.4 * math.acos(min(1.0, c))


def artemis_sites():
    return {s.id: s for s in load_sites() if s.category == SiteCategory.artemis_iii}


def test_the_nine_regions_in_nasa_order():
    assert list(artemis_sites()) == [f"artemis3-{k}" for k in USGS_2024]


@pytest.mark.parametrize("slug", list(USGS_2024))
def test_projection_matches_the_bounds_usgs_published(slug):
    """Every published lat/lon bound is a box corner's latitude or longitude (to its 4 decimals)."""
    _, _, (x0, y0, x1, y1), bounds = USGS_2024[slug]
    corners = [lps_to_latlon(x, y) for x in (x0, x1) for y in (y0, y1)]
    for v in map(float, bounds):
        assert min(min(abs(v - lat), abs(v - lon)) for lat, lon in corners) <= 0.5e-4 + 1e-9


@pytest.mark.parametrize("slug", list(USGS_2024))
def test_point_is_the_box_centre(slug):
    nasa, stem, (x0, y0, x1, y1), _ = USGS_2024[slug]
    s = artemis_sites()[f"artemis3-{slug}"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    lat, lon = lps_to_latlon(cx, cy)
    assert lps_to_latlon_direct(cx, cy) == pytest.approx((lat, lon), abs=1e-10)
    assert (s.location.lat, s.location.lon) == (round(lat, 6), round(lon, 6))
    # Visitor text states the box size and the distance from the pole as computed here.
    size = f"about {(x1 - x0) // 1000} by {(y1 - y0) // 1000} km"
    pole_km = round(1737.4 * math.radians(90.0 + s.location.lat))
    assert size in s.description and f"about {pole_km} km from the pole" in s.description
    assert "this project's calculation from the USGS grid" in s.description
    assert "geometric centre, not a landing site" in s.description
    # Source: the region, the grid file and box, the mission change.
    assert "release 24-136, 28 October 2024" in s.source and "release 26-022, 27 February 2026" in s.source
    assert "doi:10.5066/P1MEQ6UK" in s.source and f"{stem}.zip, {stem}_PolarLGRS_ACC_1km_S_Grid" in s.source
    assert f"easting {x0 // 1000}-{x1 // 1000} km, northing {y0 // 1000}-{y1 // 1000} km" in s.source
    assert "not yet checked" in s.source  # the grids' frame
    # Names: NASA's, and distinct from the curated sites' short names.
    assert s.name == f"{nasa} (Artemis III candidate region, NASA 2024)"
    assert display_name(s) == f"{nasa} region"
    assert s.subtitle == "Artemis III candidate region · NASA, Oct 2024"


def test_short_names_are_unique():
    names = [display_name(s) for s in load_sites()]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("slug", list(USGS_2024))
def test_distance_to_curated_site_as_stated(slug):
    s = artemis_sites()[f"artemis3-{slug}"]
    if slug not in NEAR_SITE:
        assert " km from the " not in s.description.replace("km from the pole", "")
        return
    pgda = [t for t in load_sites() if t.category == SiteCategory.pgda]
    site = next(t for t in pgda if t.short_name == NEAR_SITE[slug])
    d = arc_km((s.location.lat, s.location.lon), (site.location.lat, site.location.lon))
    assert f"The point is {d:.1f} km from the {NEAR_SITE[slug]} site." in s.description


def test_mons_mouton_plateau_caveat_and_mons_mouton_name():
    sites = artemis_sites()
    assert "only loosely" in sites["artemis3-mons-mouton-plateau"].description
    mm = sites["artemis3-mons-mouton"]
    assert "Leibnitz Beta" in mm.description
    assert "Feature/16070" in mm.source and "svs.gsfc.nasa.gov/5074" in mm.source


@pytest.mark.parametrize("slug", list(USGS_2024))
def test_terrain_and_datasets(slug):
    """Inside the PGDA polar maps; the 5 m site dataset is listed where a 5 m tile covers the point."""
    s = artemis_sites()[f"artemis3-{slug}"]
    st = reg.resolve(s.location.lat, s.location.lon)
    assert all(not isinstance(sl.spec, reg.GlobalLayerSpec) for sl in st.layers)
    on_5m = st.layers[0].spec.resolution_m == 5.0
    assert ("pgda_78_site_dems" in s.dataset_ids) == on_5m and "pgda_90_south_pole_dems" in s.dataset_ids
    assert on_5m == (slug in NEAR_SITE)


def test_regions_are_served_but_not_polar_tile_sites():
    points = site_points()
    for sid, s in artemis_sites().items():
        assert sid not in points and s.regions == [] and not s.has_dem_clones
    assert len(points) == 8
