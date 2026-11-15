# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""scripts/series_checks.py resumes after an interruption, and its flat-cut switch is undone afterwards."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from test_series import brute  # pytest puts tests/engine on sys.path

import lss.series.disc as disc
from lss.contract import PowerMetrics
from lss.series import body_visibility

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "series_checks.py"


@pytest.fixture()
def checks(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("series_checks", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls = {"n": 0, "fail_after": None}

    def fake_sun(start, end, limb, params):
        if calls["fail_after"] is not None and calls["n"] >= calls["fail_after"]:
            raise KeyboardInterrupt  # e.g. the computer going to sleep mid-run
        calls["n"] += 1

        def sample(t):
            t = np.asarray(t, dtype=float)
            return (t / 360.0) % 360.0, np.zeros_like(t), np.full(t.shape, 0.27)

        return body_visibility(sample, lambda az: np.where(np.asarray(az) < 90, 1.0, -1.0), 86400.0, limb)

    monkeypatch.setattr(mod, "sun_over", fake_sun)
    monkeypatch.setattr(mod, "compute_series", lambda *a, **k: None)
    monkeypatch.setattr(mod, "power_metrics", lambda res: PowerMetrics())
    monkeypatch.setattr(mod, "out_path", lambda: tmp_path / "out.json")
    return mod, calls, tmp_path / "out.json"


def test_interrupted_checks_resume_without_redoing(checks):
    mod, calls, out = checks
    calls["fail_after"] = 2
    with pytest.raises(KeyboardInterrupt):
        mod.main([])
    assert len(json.loads(out.read_text(encoding="utf-8"))["checks"]) == 2
    assert disc._horizon_at_columns.__name__ == "_horizon_at_columns"  # flat cut undone after the interrupt

    calls["fail_after"] = None
    assert mod.main([]) == 0 and calls["n"] == 3  # the third Sun run only
    assert len(json.loads(out.read_text(encoding="utf-8"))["checks"]) == 4
    assert mod.main([]) == 0 and calls["n"] == 3  # nothing recomputed
    assert mod.main(["--fresh"]) == 0 and calls["n"] == 6


def test_flat_cut_uses_the_centre_azimuth_only():
    def horizon(az):  # +2 deg left of 100 deg, -2 deg right of it, as a ramp over one 0.1 deg interval
        return np.clip((100.0 - np.asarray(az)) / 0.1, -0.5, 0.5) * 4.0

    r = 0.27
    got = disc.visible_fraction(horizon, 100.1, 0.0, r, False)[0]
    assert got == pytest.approx(brute(horizon, 100.1, 0.0, r, False), abs=5e-4)
    assert 0.6 < got < 0.8  # the left part of the disc is behind the high horizon
    spec = importlib.util.spec_from_file_location("series_checks", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with mod.flat_cut():
        assert disc.visible_fraction(horizon, 100.1, 0.0, r, False)[0] == 1.0  # the centre sees -2 deg
    assert disc.visible_fraction(horizon, 100.1, 0.0, r, False)[0] == got
