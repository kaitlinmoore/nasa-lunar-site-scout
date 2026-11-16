# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""The Apollo landing sites in the curated registry (lss/registry/sites.yaml; Kaitlin, 2026-11-16).

Coordinates are the Lunar Module descent stage positions of Wagner et al. (2017), Icarus 283, 92-103,
doi:10.1016/j.icarus.2016.05.011, as listed in the LROC PDS archive table (LRO-L-LROC-5-RDR-V1.0,
EXTRAS/SHAPEFILE/ANTHROPOGENIC_OBJECTS, field LONGITUDE in -180..180) and on NASA NSSDCA's Apollo Landing Site
Coordinates page (mean Earth/polar axis, DE421). The table below is copied from that archive table.
"""

import pytest

from lss.contract import SiteCategory, display_name
from lss.registry.sites import load_sites, site_points
from lss.registry.terrain import resolve

# mission -> (Lunar Module name, lat, lon E, uncertainty m), as published
WAGNER_2017_LM = {
    11: ("Eagle", 0.67416, 23.47314, "0.3"),
    12: ("Intrepid", -3.0128, -23.4219, "2.2"),
    14: ("Antares", -3.64589, -17.47194, "0.4"),
    15: ("Falcon", 26.13239, 3.63330, "1.0"),
    16: ("Orion", -8.9734, 15.5011, "3.0"),
    17: ("Challenger", 20.1911, 30.7723, "3.5"),
}


def apollo_sites():
    return {s.id: s for s in load_sites() if s.category == SiteCategory.apollo}


def test_the_six_crewed_landings_are_listed():
    assert sorted(apollo_sites()) == sorted(f"apollo-{n}" for n in WAGNER_2017_LM)


@pytest.mark.parametrize("mission", sorted(WAGNER_2017_LM))
def test_coordinates_are_wagner_2017_as_published(mission):
    lm, lat, lon, unc = WAGNER_2017_LM[mission]
    s = apollo_sites()[f"apollo-{mission}"]
    assert (s.location.lat, s.location.lon) == (lat, lon)  # exact: copied, never recomputed
    assert s.location.name == s.name and display_name(s) == f"Apollo {mission}"
    assert lm in s.name and f'Lunar Module "{lm}"' in s.source
    assert "doi:10.1016/j.icarus.2016.05.011" in s.source and "DE421" in s.source
    assert f"to within {unc} m" in s.description and f"uncertainty {unc} m" in s.source
    assert f"apollo{mission}info.html" in s.source


def test_apollo_sites_are_served_but_not_polar_tile_sites():
    points = site_points()
    for sid, s in apollo_sites().items():
        assert sid not in points
        assert s.dataset_ids == ["lola_ldem_128"] and not s.has_dem_clones and s.regions == []
        # the dataset listed is the one the terrain resolver uses there (the global coarse layer, C7)
        st = resolve(s.location.lat, s.location.lon)
        assert [tl.dataset_id for tl in st.contract_layers()] == s.dataset_ids
    assert sorted(points) == sorted(s.id for s in load_sites() if s.category == SiteCategory.pgda)
    assert len(points) == 8
