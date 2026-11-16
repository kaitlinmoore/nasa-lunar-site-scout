# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Per-site regression fixtures (plan section 5.4): each C3 site's served 1 m result over the C1 window.

tests/engine/fixtures/c3/<site id>.json is written by scripts/regression_c3.py from the served files. A fresh
computation must reproduce it, with the same tolerances as the Site01 fixture (test_regression_c1.py). An
engine change that moves these numbers must be deliberate: regenerate the served files and the fixtures,
and say why in the commit.
"""

import json
from pathlib import Path

import numpy as np
import pytest
from test_regression_c1 import DEG_TOL, HAVE_KERNELS, _compare

from lss.contract import HorizonProfile, MetricsResponse, Scenario, SeriesResponse
from lss.datafiles import BY_ID
from lss.registry.sites import load_sites, site_points

FIXTURES = Path(__file__).parent / "fixtures" / "c3"
REFS = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(FIXTURES.glob("*.json"))}
SITES = {s.id: s for s in load_sites()}


def test_every_c3_site_has_a_fixture():
    assert set(REFS) == set(SITES) - {"pgda-site01"}  # Site01: test_regression_c1.py


def _have_data(site_id: str) -> bool:
    from lss.registry.terrain import POLAR_80M, POLAR_240M

    tile = BY_ID[f"site{site_points()[site_id].tile[4:].lower()}_dem"]
    return HAVE_KERNELS and all(
        f.path.is_file() for f in (tile, BY_ID[POLAR_80M.file_id], BY_ID[POLAR_240M.file_id])
    )


@pytest.mark.parametrize("site_id", sorted(REFS))
def test_fixture_is_the_sites_1m_scenario(site_id):
    ref = REFS[site_id]
    m = MetricsResponse.model_validate(ref["metrics"])
    s = SeriesResponse.model_validate(ref["series"])
    h = HorizonProfile.model_validate(ref["horizon"])
    loc = SITES[site_id].location
    assert m.scenario.key() == s.scenario.key() == ref["scenario_key"]
    assert (m.scenario.location.lat, m.scenario.location.lon) == (loc.lat, loc.lon)
    assert m.scenario.unit_height_m == 1.0 and not m.placeholder and not s.placeholder
    assert (h.location.lat, h.location.lon) == (loc.lat, loc.lon) and len(h.azimuth_deg) == 360


@pytest.mark.parametrize("site_id", sorted(REFS))
def test_fresh_computation_reproduces_the_fixture(site_id):
    if not _have_data(site_id):
        pytest.skip("kernels/DEMs not downloaded (scripts/fetch_data.py)")
    from lss.metrics import metrics_response
    from lss.series import compute_series, horizon_response, series_response

    ref = REFS[site_id]
    sc = Scenario.model_validate(ref["metrics"]["scenario"])
    res = compute_series(sc)
    m = metrics_response(res).model_dump(mode="json", by_alias=True)
    _compare({k: v for k, v in m.items() if k != "contract_version"}, ref["metrics"])
    s, every = series_response(res).model_dump(mode="json", by_alias=True), ref["series_every"]
    assert s["time"][::every] == ref["series"]["time"]
    for body in ("sun", "earth"):
        for k, v in ref["series"][body].items():
            assert np.allclose(s[body][k][::every], v, atol=DEG_TOL, rtol=0), (body, k)
    _compare(s["events"], ref["series"]["events"], "events")
    h, hevery = horizon_response(res).model_dump(mode="json", by_alias=True), ref["horizon_every"]
    for k in ("azimuth_deg", "elevation_deg"):
        assert np.allclose(h[k][::hevery], ref["horizon"][k], atol=DEG_TOL, rtol=0), k
