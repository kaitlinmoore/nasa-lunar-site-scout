# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Regression fixture: the validated served C1 result (Site01 RoI 4, 1 m, 2028-05-15 to 06-14, PT1H).

tests/engine/fixtures/site01_roi4_c1.json is written by scripts/precompute_c1.py after the step 4.7
validation (docs/methodology.md section 6). A fresh computation must reproduce it; any change to the
engine that moves these numbers must be deliberate (regenerate the fixture and say why in the commit).
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from lss.contract import MetricsResponse, SeriesResponse
from lss.contract.examples import SCENARIO
from lss.registry.terrain import LAYERS

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
HAVE_DATA = HAVE_KERNELS and all(spec.dem().path.is_file() for spec in LAYERS)
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="kernels/DEMs not downloaded (scripts/fetch_data.py)")


def test_fixture_is_the_served_scenario_and_valid():
    assert REF["scenario_key"] == SCENARIO.key() == "00010cfa5fef681c"
    m = MetricsResponse.model_validate(REF["metrics"])
    s = SeriesResponse.model_validate(REF["series"])
    assert m.scenario == SCENARIO and s.scenario == SCENARIO
    assert m.placeholder is False and s.placeholder is False
    assert len(s.time) == 121 and s.downsampled  # 721 hourly samples, every 6th kept


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
    from lss.series import compute_series, series_response

    res = compute_series(SCENARIO)
    return (
        metrics_response(res).model_dump(mode="json", by_alias=True),
        series_response(res).model_dump(mode="json", by_alias=True),
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
