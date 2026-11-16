# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""lss.metrics.elevation_band: Sun-elevation time histogram and band fractions (RA7; methodology 5.3)."""

import numpy as np
import pytest

from lss.metrics import band_fraction, band_seconds, elevation_histogram


def test_linear_ramp_spends_equal_time_per_bin():
    t = np.linspace(0.0, 1000.0, 101)
    el = np.linspace(-1.0, 1.0, 101)  # 0.1 deg bins: 20 bins of 50 s
    h = elevation_histogram(t, el)
    assert h.seconds.sum() == pytest.approx(1000.0)
    assert np.allclose(h.seconds[:20], 50.0)
    assert band_fraction(h, -0.5, 0.5) == pytest.approx(0.5)
    assert band_seconds(h, -0.05, 0.05) == pytest.approx(50.0)  # half of two bins each


def test_matches_brute_force_on_a_wiggly_track():
    t = np.arange(0.0, 30 * 86400.0 + 1, 60.0)
    el = 1.2 * np.sin(2 * np.pi * t / (29.5 * 86400)) + 0.4 * np.sin(2 * np.pi * t / 86400.0)
    h = elevation_histogram(t, el)
    assert h.seconds.sum() == pytest.approx(t[-1])
    fine = np.linspace(0.0, t[-1], 2_000_001)
    elf = np.interp(fine, t, el)  # the same piecewise-linear track, densely sampled
    for a, b in ((-0.3, 0.7), (0.0, 1.0), (-2.0, -1.0)):
        want = np.mean((elf >= a) & (elf <= b))
        assert band_fraction(h, a, b) == pytest.approx(want, abs=2e-5)


def test_flat_segments_and_json_round_trip():
    t = np.array([0.0, 10.0, 20.0, 30.0])
    el = np.array([0.25, 0.25, 0.35, 0.35])
    h = elevation_histogram(t, el)
    assert h.seconds.sum() == pytest.approx(30.0)
    j = h.to_json()
    assert band_seconds(j, 0.2, 0.3) == pytest.approx(10.0 + 5.0)
    with pytest.raises(ValueError):
        band_fraction(j, 1.0, 0.0)


def test_site01_histogram_matches_its_elevation_statistics():
    """On the served scenario: the histogram covers [min, max] and its time mean is the served mean."""
    from test_regression_c1 import HAVE_DATA

    if not HAVE_DATA:
        pytest.skip("kernels/DEMs not downloaded")
    from lss.contract.examples import SCENARIO
    from lss.metrics import power_metrics
    from lss.series import compute_series

    res = compute_series(SCENARIO)
    g = res.sun.grid
    h = elevation_histogram(g.t_s, g.elevation_deg)
    e = power_metrics(res).sun_elevation_deg
    assert h.seconds.sum() == pytest.approx(res.duration_s)
    lo, hi = np.floor(e.min / h.bin_deg) * h.bin_deg, np.ceil(e.max / h.bin_deg) * h.bin_deg
    assert band_fraction(h, lo, hi) == pytest.approx(1.0, abs=1e-9)  # bin edges: exact
    centres = h.first_edge_deg + h.bin_deg * (np.arange(h.seconds.size) + 0.5)
    assert (centres * h.seconds).sum() / h.seconds.sum() == pytest.approx(
        e.mean, abs=0.01
    )  # within a bin's width
    assert band_fraction(h, 10.0, 25.0) == 0.0  # k7's band: the Sun never reaches 10 deg here


def test_band_functions_import_without_spice_or_numba():
    """C api's request RA10: the API reads histograms from served files and must not load the engine."""
    import subprocess
    import sys

    code = (
        "import sys\n"
        "from lss.metrics.elevation_band import band_fraction, band_seconds\n"
        "heavy = [m for m in ('spiceypy', 'numba', 'rasterio', 'lss.series', 'lss.ephem', 'lss.horizon',"
        " 'lss.metrics.core') if m in sys.modules]\n"
        "print(','.join(heavy))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ""


def test_package_exports_still_work():
    import lss.metrics as m

    assert m.band_fraction is band_fraction and callable(m.power_metrics) and "time_mean" in dir(m)
