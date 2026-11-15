# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""scripts/horizon_convergence.py resumes cleanly after an interruption (no DEMs needed)."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from lss.horizon import Horizon, HorizonParams

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "horizon_convergence.py"


@pytest.fixture()
def conv(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("horizon_convergence", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def fake_horizon(*a, **k):
        az = np.arange(0, 360, 1.0)
        return Horizon(0, 0, 1, 0, az, np.sin(np.radians(az)), az * 0, 0, 1, HorizonParams(1.0))

    calls = {"run": 0, "fail_after": None}

    def fake_run(lat, lon, height, s):
        if calls["fail_after"] is not None and calls["run"] >= calls["fail_after"]:
            raise KeyboardInterrupt  # e.g. the computer going to sleep mid-run
        calls["run"] += 1
        return fake_horizon(), 0.5

    monkeypatch.setattr(mod, "run", fake_run)
    monkeypatch.setattr(mod, "cached_horizon", fake_horizon)
    monkeypatch.setattr(mod, "resolve", lambda *a, **k: None)
    monkeypatch.setattr(mod, "key_spec", lambda *a, **k: {})
    monkeypatch.setattr(mod, "cache_path", lambda *a, **k: tmp_path / "ref.npz")
    monkeypatch.setattr(mod, "out_path", lambda *a: tmp_path / "out.json")
    return mod, calls, tmp_path / "out.json"


def test_interrupted_study_resumes_without_redoing_variants(conv):
    mod, calls, out = conv
    n_variants = 1 + len(mod.DEFAULT) + len(mod.COARSER)

    calls["fail_after"] = 4
    with pytest.raises(KeyboardInterrupt):
        mod.main([])
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert len(saved["rows"]) == 4 and not list(out.parent.glob("*.part"))

    calls["fail_after"] = None
    assert mod.main([]) == 0
    assert calls["run"] == n_variants  # 4 before the interruption + the rest after; none twice
    assert len(json.loads(out.read_text(encoding="utf-8"))["rows"]) == n_variants

    assert mod.main([]) == 0 and calls["run"] == n_variants  # a complete study is not recomputed
    assert mod.main(["--fresh"]) == 0 and calls["run"] == 2 * n_variants


def test_results_from_other_settings_are_not_reused(conv):
    mod, calls, out = conv
    out.write_text(
        json.dumps({"format": 2, "reference": {"az": 9}, "rows": [{"variant": "x"}]}), encoding="utf-8"
    )
    assert mod.main([]) == 0
    assert calls["run"] == 1 + len(mod.DEFAULT) + len(mod.COARSER)
