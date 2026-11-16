# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""The curated site registry (lss/registry/sites.yaml): contract-valid, consistent with its own provenance,
and Site01 unchanged from what the API serves today."""

import pytest

from lss.contract.examples import SCENARIO
from lss.contract.examples import sites as fixture_sites
from lss.datafiles import BY_ID
from lss.registry.rois import largest, read_rois
from lss.registry.sites import load_sites, site_points
from lss.terrain.core import latlon_from_ps


def test_sites_load_as_contract_sites():
    sites = load_sites()
    assert len({s.id for s in sites}) == len(sites)
    for s in sites:
        assert s.location.name == s.name and s.description and s.source
        assert s.id in site_points()


def test_site01_is_what_the_api_serves_today():
    """C api will generate /api/sites from the registry; Site01 must not change when it does."""
    reg = {s.id: s for s in load_sites()}["pgda-site01"]
    assert reg == fixture_sites().sites[0]
    assert (reg.location.lat, reg.location.lon) == (SCENARIO.location.lat, SCENARIO.location.lon)


@pytest.mark.parametrize("site_id", sorted(site_points()))
def test_coordinates_are_the_stored_polar_stereographic_point(site_id):
    loc = {s.id: s for s in load_sites()}[site_id].location
    p = site_points()[site_id]
    lat, lon = latlon_from_ps(*p.ps_m, "south")
    assert loc.lat == pytest.approx(float(lat), abs=1e-6) and loc.lon == pytest.approx(float(lon), abs=1e-6)
    assert f"site{p.tile[4:].lower()}_dem" in BY_ID  # its 5 m tile is in the data catalog


@pytest.mark.parametrize(
    "site_id", sorted(k for k, p in site_points().items() if p.rule == "largest_roi_centroid")
)
def test_roi_point_is_the_largest_rois_centroid(site_id):
    p = site_points()[site_id]
    f = BY_ID[f"site{p.tile[4:].lower()}_rois"]
    if not f.path.is_file():
        pytest.skip(f"{f.relpath} not downloaded (scripts/fetch_data.py)")
    r = largest(read_rois(f.path))
    assert (r.number, r.area_m2) == (p.roi, p.roi_area_m2)
    assert r.centroid_ps == p.ps_m  # Site01: exactly Barker's Table 2 centroid
