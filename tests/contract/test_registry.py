# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
from lss.registry.loader import get_dataset, load_datasets

REQUIRED = {
    "pgda_78_site_dems",
    "pgda_81_mosaic_5m",
    "pgda_90_south_pole_dems",
    "pgda_69_polar_illumination",
    "pgda_98_polar_roughness",
    "lola_ldem_128",
    "sldem2015",
    "diviner_polar_temperature",
    "robbins_craters",
    "m3_surface_ice",
    "aussel_2025_boulders",
    "spice_de421",
}


def test_registry_loads_and_has_required_entries():
    ids = {d.id for d in load_datasets()}
    assert REQUIRED <= ids


def test_every_entry_has_citation_license_and_limits():
    for d in load_datasets():
        assert d.citation and d.license and d.cannot_answer, d.id


def test_get_dataset():
    assert get_dataset("spice_de421").kind == "ephemeris"
