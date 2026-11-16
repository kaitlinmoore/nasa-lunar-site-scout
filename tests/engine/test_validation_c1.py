# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Step 4.7 validation results (docs/methodology.md section 6), as committed by scripts/validation_c1.py.

tests/engine/fixtures/validation_c1.json is the script's summary output: the Barker et al. (2021) RoI 4 bound,
the internal PGDA product 69 pass and the ridge-top check. The runs take about an hour (532 horizons), so
they are not repeated here. These tests check that the committed results meet the stated tolerances and
belong to the served scenario. The RoI outline reading is checked on the real file when it is present.
"""

import importlib.util
import json
from pathlib import Path

import pytest

from lss.contract.examples import SCENARIO
from lss.datafiles import get as datafile

ROOT = Path(__file__).resolve().parents[2]
V = json.loads((Path(__file__).parent / "fixtures" / "validation_c1.json").read_text(encoding="utf-8"))
REG = json.loads((Path(__file__).parent / "fixtures" / "site01_roi4_c1.json").read_text(encoding="utf-8"))


def script():
    spec = importlib.util.spec_from_file_location("validation_c1", ROOT / "scripts" / "validation_c1.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_results_belong_to_the_served_scenario():
    assert V["scenario_key"] == SCENARIO.key() == REG["scenario_key"]
    r = V["ridge_top"]
    assert r["scenario_key"] == SCENARIO.key()
    served = REG["metrics"]["power"]["illumination_fraction"]
    assert r["illumination_fraction"] == pytest.approx(served, abs=1e-9)


# ------------------------------------------------------------------ Barker et al. (2021), RoI 4


def test_barker_inputs_are_table_2():
    b = V["barker_roi4"]
    assert b["pixels"] == 532 and b["area_m2"] == 13_300.0  # Table 2: RoI 4 area 13,300 m2
    assert b["unit_height_m"] == 1.0 and b["period"] == ["2024-01-01T00:00:00Z", "2026-01-01T00:00:00Z"]
    assert b["barker_table2_A"] == {"avg_ill_pct_p1": 69.61, "lcip_d_p1": 136.49, "lcsp_d_p99": 13.27}
    assert b["tolerance"] == {"avg_ill_pct": 1.0, "lcip_d": 2.0, "lcsp_d": 1.0}


def test_barker_bound_holds_within_tolerance():
    b = V["barker_roi4"]
    a, ref, tol = b["roi_average_hourly"], b["barker_table2_A"], b["tolerance"]
    assert a["avg_ill_pct"] >= ref["avg_ill_pct_p1"] - tol["avg_ill_pct"]
    assert a["lcip_d"] >= ref["lcip_d_p1"] - tol["lcip_d"]
    assert a["lcsp_d"] <= ref["lcsp_d_p99"] + tol["lcsp_d"]
    assert all(b["pass"].values())


def test_barker_area_grid_matches_the_default_grid():
    """The area run uses a 600 s internal grid; a subset was repeated at the served 60 s grid."""
    g = V["barker_roi4"]["grid_check_60s_minus_600s"]
    assert len(g) >= 10
    for row in g:
        assert abs(row["d_avg_ill_pct"]) < 0.01
        assert abs(row["d_illumination_fraction"]) < 1e-4
        assert abs(row["d_lcip_d"]) < 0.01 and abs(row["d_lcsp_d"]) < 0.01


@pytest.mark.skipif(not datafile("site01_rois").path.is_file(), reason="Site01_ROIs.tgz not downloaded")
def test_roi4_outline_gives_barkers_area_and_centroid():
    px = script().roi_pixels(4)
    assert len(px) == 532
    assert px.mean(axis=0) == pytest.approx([-11287.5, -12167.5], abs=3.0)  # Table 2 centroid (PS m)


# ------------------------------------------------------------------ ridge-top check


def test_sun_is_seen_only_below_the_local_horizontal():
    r = V["ridge_top"]
    w = r["while_visible"]
    assert w["share_with_upper_limb_below_horizontal"] == 1.0
    assert w["sun_upper_limb_el"][1] < 0.0
    assert r["flat_horizontal_horizon"]["served_window_time_any_part"] == 0.0
    assert w["horizon_el"][1] < w["sun_upper_limb_el"][1]  # the horizon is lower still
    assert r["sphere_dip_deg"] == pytest.approx(-2.718, abs=1e-3)  # 1957.4 m above the 1737.4 km sphere
    assert r["horizon_range_deg"][0] > r["sphere_dip_deg"]  # terrain only raises the horizon


def test_independent_ray_scan_confirms_the_horizon_along_the_suns_path():
    r = V["ridge_top"]
    assert len(r["independent_scan"]) >= 30
    assert r["independent_scan_max_abs_diff_deg"] < 0.05


def test_barkers_bound_itself_needs_a_horizon_below_the_horizontal():
    r, b = V["ridge_top"], V["barker_roi4"]
    flat = r["flat_horizontal_horizon"]["barker_period_avg_ill_pct"]
    assert flat < b["barker_table2_A"]["avg_ill_pct_p1"] - 10.0  # 51.4% vs 69.61%


def test_barker_fig15_horizon_agrees_under_the_map_angle():
    f = V["ridge_top"]["barker_fig15_roi4"]
    assert len(f["rows"]) == 16
    assert f["median_abs_diff_deg"] < 0.3  # figure read by eye (about +-0.3 deg)


def test_barker_fig19_and_c_rows_agree():
    """Qualitative: Fig. 19's nominal-DEM points (read by eye); Table 2's C rows (most illuminated pixel)."""
    b = V["barker_roi4"]
    a, fig = b["roi_average_hourly"], b["fig19_read_nominal"]
    assert abs(a["avg_ill_pct"] - fig["avg_ill_pct"]) < 2.0
    assert abs(a["lcip_d"] - fig["lcip_d"]) < 10.0 and abs(a["lcsp_d"] - fig["lcsp_d"]) < 1.0
    c, ref = b["most_illuminated_pixel_hourly"], b["barker_table2_C"]
    assert c["avg_ill_pct"] >= ref["avg_ill_pct_p1"] - 1.0 and c["lcip_d"] >= ref["lcip_d_p1"] - 2.0
    assert c["lcsp_d"] <= ref["lcsp_d_p99"] + 1.0


# ------------------------------------------------------------------ PGDA product 69 (internal pass)


def test_product69_earth_within_tolerance():
    e = V["product69"]["EARTH"]
    assert e["pass"] and e["mean_abs_diff_pp"] <= V["product69"]["tolerance_mean_abs_pp"] == 5.0


def test_product69_sun_result_is_recorded_as_a_miss():
    """The Sun comparison misses the stated 5 pp tolerance (methodology section 6.3 says so and why). These
    assertions pin what the methodology claims, so a rerun that changes it is noticed."""
    p = V["product69"]
    s = p["SUN"]
    assert not s["pass"] and s["mean_abs_diff_pp"] > p["tolerance_mean_abs_pp"]
    assert abs(s["mean_diff_pp"]) < 3.0  # no overall bias
    assert abs(s["centre_pixel"]["ours_pct"] - s["centre_pixel"]["product69_pct"]) < 3.0
    assert s["start_date_spread_pp_max"] < 1.5
    d = p["diagnostic_half_pixel_shift"]
    assert d["median_max_change_pp"] > s["mean_abs_diff_pp"]  # a half-pixel move changes more than the miss
    z = s["diagnostic_zero_pixel_excluded"]  # product 69's zero-valued pixel left out: still a miss
    assert z["pixels_excluded"] == 1
    assert p["tolerance_mean_abs_pp"] < z["mean_abs_diff_pp"] < s["mean_abs_diff_pp"]


def test_product69_supports_the_ridge_top_result():
    """Product 69's RoI 4 pixel sees the Sun more often than a horizon at the local horizontal would allow."""
    flat = 100.0 * V["ridge_top"]["flat_horizontal_horizon"]["years_18_6_from_2024_time_any_part"]
    s = V["product69"]["SUN"]
    assert s["centre_pixel"]["product69_pct"] > flat + 10.0
    assert s["centre_pixel"]["ours_pct"] > flat + 10.0


# ------------------------------------------------------------------ G1 review follow-ups


def test_barker_70pct_contour_is_reproduced_on_both_sides():
    """Barker drew RoI 4 as the connected pixels above 70% (1 m, 2024-2025): pixels inside must be above it
    and edge neighbours outside must be at or below it. Two-sided, unlike the Table 2 bound (methodology
    6.2)."""
    c = V["barker_roi4"]["contour_70pct"]
    assert c["contour_pct"] == 70.0 and c["tolerance_pp"] == 0.5  # fixed before the ring run
    assert c["inside"]["pixels"] == 532
    assert c["outside_edge"]["pixels"] + c["outside_corner_only"]["pixels"] == 172
    assert c["inside"]["min"] >= c["contour_pct"] - c["tolerance_pp"]
    assert c["outside_edge"]["max"] <= c["contour_pct"] + c["tolerance_pp"]
    assert all(c["pass"].values())


def test_served_accuracy_cases():
    """Methodology 6.6: the served scenario with its horizon shifted (figures quoted there)."""
    a = V["served_accuracy"]
    cases = {c["case"]: c for c in a["cases"]}
    served, m = cases["served"], REG["metrics"]["power"]
    assert served["illumination_fraction"] == pytest.approx(m["illumination_fraction"], abs=1e-9)
    assert served["shadow_count"] == m["shadow_count"]
    assert served["longest_shadow_h"] == pytest.approx(m["longest_shadow_h"], abs=1e-6)
    for k in ("whole -0.01", "whole +0.01"):  # the numerical horizon error (section 3.2)
        c = cases[k]
        assert abs(c["illumination_fraction"] - served["illumination_fraction"]) < 0.004
        assert abs(c["longest_shadow_h"] - served["longest_shadow_h"]) < 0.6
        assert c["shadow_count"] == served["shadow_count"]
    lo, hi = cases["near -0.20"], cases["near +0.20"]
    assert 0.64 < hi["illumination_fraction"] < 0.65 and 0.74 < lo["illumination_fraction"] < 0.75
    assert (lo["shadow_count"], hi["shadow_count"]) == (6, 4)
    for c in (lo, hi):  # the Earth's horizon is set far away: a near-field error leaves it alone
        assert c["earth_visibility_fraction"] == served["earth_visibility_fraction"]
    assert cases["whole -0.05"]["longest_sunlit_period_h"] > 220.0  # two sunlit periods merge
    assert a["horizon_distance_share"]["lt_100m"] == pytest.approx(0.36, abs=0.01)
    assert a["EARTH"]["partly_visible_horizon_lt_1km"] == 0.0


def test_barker_fig15_reread_near_the_outliers():
    d = V["ridge_top"]["barker_fig15_roi4"]["digitised_near_outliers"]
    assert len(d["rows"]) == 9 and d["max_abs_diff_deg"] < 0.1


def test_product69_c3_tolerance_is_derived_from_the_half_pixel_shift():
    s = script()
    d = V["product69"]["diagnostic_half_pixel_shift"]
    assert round(d["mean_abs_change_pp"], 1) == s.P69_C3_TOL_PP == 9.6
    assert s.P69_C3_HEIGHTS_M == (0.0, 2.0)
