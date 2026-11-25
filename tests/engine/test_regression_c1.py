# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Regression fixture: the validated first served result (Site01 RoI 4, 1 m, 2028-05-15 to 06-14, PT1H).

tests/engine/fixtures/site01_roi4_c1.json is written by scripts/precompute_c1.py after the
validation (docs/methodology.md section 6). A fresh computation must reproduce it; any change to the
engine that moves these numbers must be deliberate (regenerate the fixture and say why in the commit).
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from lss.contract import HorizonProfile, MetricsResponse, SeriesResponse
from lss.contract.examples import SCENARIO
from lss.registry.terrain import C1_LAYERS

FIXTURE = Path(__file__).parent / "fixtures" / "site01_roi4_c1.json"
REF = json.loads(FIXTURE.read_text(encoding="utf-8"))

FRACTION_TOL = 1e-6
HOURS_TOL = 1e-3  # 3.6 s; events are refined to 0.5 s
DEG_TOL = 1e-6

try:
    from lss.ephem import load_kernels

    load_kernels()
    HAVE_KERNELS = True
except Exception:  # noqa: BLE001 - any missing-kernel error means: skip
    HAVE_KERNELS = False
HAVE_DATA = HAVE_KERNELS and all(spec.dem().path.is_file() for spec in C1_LAYERS)
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="kernels/DEMs not downloaded (scripts/fetch_data.py)")


def test_fixture_is_the_served_scenario_and_valid():
    assert REF["scenario_key"] == SCENARIO.key() == "00010cfa5fef681c"
    m = MetricsResponse.model_validate(REF["metrics"])
    s = SeriesResponse.model_validate(REF["series"])
    assert m.scenario == SCENARIO and s.scenario == SCENARIO
    assert m.placeholder is False and s.placeholder is False
    assert len(s.time) == 121 and s.downsampled  # 721 hourly samples, every 6th kept
    h = HorizonProfile.model_validate(REF["horizon"])
    assert h.location == SCENARIO.location and h.unit_height_m == SCENARIO.unit_height_m
    assert (
        len(h.azimuth_deg) == 360 and REF["horizon_every"] == 10
    )  # 3600 azimuths at 0.1 deg, every 10th kept
    assert h.placeholder is False and h.max_range_km == 400.0
    assert [t.role for t in h.terrain_stack] == ["near_field", "far_field", "far_field"]
    assert h.fidelity is not None and h.fidelity.near_field_resolution_m == 5.0


def _compare(got, want, path=""):
    if isinstance(want, dict):
        assert set(got) == set(want), path
        for k in want:
            _compare(got[k], want[k], f"{path}.{k}")
    elif isinstance(want, list):
        assert len(got) == len(want), path
        for i, (g, w) in enumerate(zip(got, want, strict=True)):
            _compare(g, w, f"{path}[{i}]")
    elif isinstance(want, bool) or want is None or isinstance(want, str) and not path.endswith("time"):
        assert got == want, path
    elif isinstance(want, str):  # event times
        dt = datetime.fromisoformat(got) - datetime.fromisoformat(want)
        assert abs(dt.total_seconds()) <= 1.0, path
    else:
        tol = HOURS_TOL if path.endswith("_h") else FRACTION_TOL if "fraction" in path else DEG_TOL
        assert got == pytest.approx(want, abs=tol), path


@pytest.fixture(scope="module")
def fresh():
    from lss.metrics import metrics_response
    from lss.series import compute_series, horizon_response, series_response

    res = compute_series(SCENARIO)
    return (
        metrics_response(res).model_dump(mode="json", by_alias=True),
        series_response(res).model_dump(mode="json", by_alias=True),
        horizon_response(res).model_dump(mode="json", by_alias=True),
    )


@needs_data
def test_metrics_reproduce_the_fixture(fresh):
    got = {k: v for k, v in fresh[0].items() if k != "contract_version"}  # not stored in the fixture
    _compare(got, REF["metrics"])


@needs_data
def test_series_reproduce_the_fixture(fresh):
    s, every = fresh[1], REF["series_every"]
    ref = REF["series"]
    assert s["time"][::every] == ref["time"]
    for body in ("sun", "earth"):
        for k, v in ref[body].items():
            assert np.allclose(s[body][k][::every], v, atol=DEG_TOL, rtol=0), (body, k)
    _compare(s["events"], ref["events"], "events")


@needs_data
def test_horizon_reproduces_the_fixture(fresh):
    h, every, ref = fresh[2], REF["horizon_every"], REF["horizon"]
    assert len(h["azimuth_deg"]) == 3600  # served at full resolution
    for k in ("azimuth_deg", "elevation_deg"):
        assert np.allclose(h[k][::every], ref[k], atol=DEG_TOL, rtol=0), k
    _compare(
        {k: v for k, v in h.items() if k not in ("contract_version", "azimuth_deg", "elevation_deg")},
        {k: v for k, v in ref.items() if k not in ("azimuth_deg", "elevation_deg")},
    )


@needs_data
def test_served_file_with_horizon_loads(fresh, tmp_path):
    """A format 2 file as precompute_c1.py writes it is accepted by the API's loader (lss/api/served.py)."""
    from lss.api.served import horizon_key, load_file

    m, s, h = fresh
    path = tmp_path / "c1.json"
    body = {
        "format": 2,
        "scenario_key": SCENARIO.key(),
        "metrics": m,
        "series": s,
        "horizon": h,
        "provenance": {},
    }
    path.write_text(json.dumps(body), encoding="utf-8")
    sv = load_file(path)
    assert sv.horizon is not None and len(sv.horizon.azimuth_deg) == 3600
    loc = SCENARIO.location
    assert sv.horizon_key == horizon_key(loc.lat, loc.lon, SCENARIO.unit_height_m)  # /api/horizon key
