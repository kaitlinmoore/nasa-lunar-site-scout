# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""C3 validation results (docs/methodology.md sections 3.2 and 6.3), as committed by scripts/validation_c3.py.

The runs take about 45 minutes, so they are not repeated here; these tests check the committed results
against the tolerances fixed before the runs.
"""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V = json.loads((Path(__file__).parent / "fixtures" / "validation_c3.json").read_text(encoding="utf-8"))


def c1_script():
    spec = importlib.util.spec_from_file_location("validation_c1", ROOT / "scripts" / "validation_c1.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_product69_standin_tolerances_are_the_ones_fixed_before_the_run():
    p = V["product69_standin"]
    c1 = c1_script()
    assert (
        p["tolerance_mean_abs_pp"]
        == {"SUN": c1.P69_C3_TOL_PP, "EARTH": c1.P69_TOL_PP}
        == {"SUN": 9.6, "EARTH": 5.0}
    )
    assert p["heights_m"] == [0.0, 2.0] and "LDEM_75S_60M" in p["terrain"]


def test_product69_standin_sun_passes_at_surface_level_only():
    s = V["product69_standin"]["SUN"]
    assert s["0m"]["pass"] and s["0m"]["mean_abs_diff_pp"] < s["c1_adj_map"]["mean_abs_diff_pp"]
    assert not s["2m"]["pass"] and s["2m"]["mean_diff_pp"] > 10.0  # 2 m sees far more Sun: product 69 is ~0 m
    assert s["pass_at_either_height"]
    assert s["0m"]["start_date_spread_pp_max"] < 1.5


def test_product69_standin_earth_passes_at_both_heights():
    e = V["product69_standin"]["EARTH"]
    assert e["0m"]["pass"] and e["2m"]["pass"]


def test_standin_terrain_is_close_to_the_adjusted_60m_map():
    d = V["product69_standin"]["surface_diff_m"]
    assert abs(d["mean"]) < 1.0 and d["max_abs"] < 3.0


def test_10m_near_field_at_site01():
    """Methodology 3.2: what a 10 m near field loses against the 5 m site map at the served point."""
    n = V["nearfield_10m_site01"]
    assert n["horizon_diff_deg"]["median_abs"] < 0.02 and n["horizon_diff_deg"]["max_abs"] < 1.0
    m5, m10 = n["metrics_5m"], n["metrics_10m"]
    assert abs(m10["illumination_fraction"] - m5["illumination_fraction"]) < 0.02
    assert m10["shadow_count"] == m5["shadow_count"]
    assert abs(m10["earth_visibility_fraction"] - m5["earth_visibility_fraction"]) < 1e-5
    assert max(n["horizon_seconds"][1:]) < 10.0
