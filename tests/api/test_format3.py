# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Served-file format 3: the Sun-elevation histogram and compare's Sun elevation band."""

import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

import lss.api.app as app_module
from lss.api.served import ServedFileError, band_fraction, load_all
from lss.config import get_settings
from lss.contract import CompareResponse
from tests.api.test_thin_slice import WEB_SCENARIO, write_served

WINDOW_S = 30 * 86400.0  # the first served scenario's window


def histogram(seconds_by_bin, first_edge=-2.0, total=WINDOW_S):
    return {
        "quantity": "Sun disc-centre apparent elevation above the local horizontal, deg (no refraction)",
        "bin_deg": 0.1,
        "first_edge_deg": first_edge,
        "seconds": seconds_by_bin,
        "total_seconds": total,
    }


def make_format3(directory, hist):
    path = write_served(directory)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["format"] = 3
    data["sun_elevation_histogram"] = hist
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path))
    for f in (get_settings, app_module._served, app_module._terrain):
        f.cache_clear()
    yield tmp_path
    for f in (get_settings, app_module._served, app_module._terrain):
        f.cache_clear()


def test_histogram_is_read_and_band_fraction_uses_streams_a_function(tmp_path):
    # 40 bins of 0.1 deg from -2.0: the first 20 bins (-2.0..0.0) hold three quarters of the time
    secs = [WINDOW_S * 0.75 / 20] * 20 + [WINDOW_S * 0.25 / 20] * 20
    path = make_format3(tmp_path / "served", histogram(secs))
    (sv,) = load_all(path.parent).values()
    assert sv.sun_elevation_histogram["bin_deg"] == 0.1
    assert band_fraction(sv, -2.0, 0.0) == pytest.approx(0.75)
    assert band_fraction(sv, 0.0, 2.0) == pytest.approx(0.25)
    assert band_fraction(sv, 10.0, 25.0) == pytest.approx(0.0)


def test_files_without_a_histogram_give_no_band(tmp_path):
    path = write_served(tmp_path / "served")
    (sv,) = load_all(path.parent).values()
    assert sv.sun_elevation_histogram is None and band_fraction(sv, 0, 1) is None


@pytest.mark.parametrize(
    "hist, why",
    [
        (histogram([WINDOW_S / 2]), "doesn't cover"),  # seconds sum to half the window
        (histogram([WINDOW_S], total=WINDOW_S / 2), "doesn't cover"),  # total isn't the window
        (histogram([-1.0, WINDOW_S + 1.0]), "doesn't cover"),  # negative seconds
        ({"bin_deg": 0.1}, "malformed"),
    ],
)
def test_malformed_histograms_are_refused(tmp_path, hist, why):
    path = make_format3(tmp_path / "served", hist)
    with pytest.raises(ServedFileError, match=why):
        load_all(path.parent)


def test_compare_ranks_and_filters_by_the_band(data_dir):
    secs = [WINDOW_S * 0.75 / 20] * 20 + [WINDOW_S * 0.25 / 20] * 20
    make_format3(data_dir / "cache" / "served", histogram(secs))
    band = {"min_deg": 0.0, "max_deg": 2.0}
    req = {
        "scenarios": [WEB_SCENARIO],
        "filters": [{"metric": band, "op": "gt", "value": 0}],
        "rank": {"metric": band},
    }
    body = CompareResponse.model_validate(
        TestClient(app_module.create_app()).post("/api/compare", json=req).json()
    )
    assert len(body.items) == 1 and body.filtered_out == []
    assert body.evaluated[0].metric == "sun_elevation_band_fraction[0,2]"
    assert body.evaluated[0].value == pytest.approx(0.25)


def test_band_compare_imports_no_engine(data_dir):
    secs = [WINDOW_S / 40] * 40
    make_format3(data_dir / "cache" / "served", histogram(secs))
    code = (
        "import json, sys\n"
        "from fastapi.testclient import TestClient\n"
        "from lss.api.app import app\n"
        f"sc = json.loads({json.dumps(json.dumps(WEB_SCENARIO))})\n"
        "band = {'min_deg': 10, 'max_deg': 25}\n"
        "r = TestClient(app).post('/api/compare', json={'scenarios': [sc], 'rank': {'metric': band}})\n"
        "assert r.status_code == 200 and r.json()['evaluated'][0]['value'] == 0.0, r.text\n"
        "print(sorted(m for m in ('spiceypy', 'rasterio', 'numba') if m in sys.modules))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "LSS_DATA_DIR": str(data_dir)},
        check=True,
    )
    assert out.stdout.strip() == "[]"
