# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""Validation results for the curated sites (docs/methodology.md sections 3.2 and 6.3), as committed by
scripts/validation_c3.py.

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


# ------------------------------------------------------------------ new sites (methodology 6.7)


def test_barker_roi_definition_at_sites_04_07_11():
    """Every sampled RoI pixel should average > 70% at 1 m (2024-2025). Site04 and Site11 pass; at Site07 one
    of 163 sampled pixels is 0.97 pp below 70% (recorded as a miss, methodology 6.7)."""
    b = V["barker_roi_sites"]
    assert b["tolerance_pp"] == 0.5 and b["every"] == 5
    assert b["pgda-site04"]["pass"] and b["pgda-site11"]["pass"]
    s07 = b["pgda-site07"]
    assert not s07["pass"] and 68.9 < s07["min_pct"] < 69.5 and s07["sampled_pixels"] == 163


def test_barker_supplement_figures_agree():
    """Read from figures (S9, S14, S19): per-RoI nominal-DEM averages vs our sampled RoI averages."""
    b = V["barker_roi_sites"]
    rows = [r for sid in ("pgda-site04", "pgda-site07", "pgda-site11")
            for r in b[sid]["barker_supplement_read_from_figure"]["rois"]]  # fmt: skip
    assert len(rows) == 10
    assert all(abs(r["avg_ill_pct"]["diff"]) < 1.5 for r in rows)
    assert all(abs(r["lcsp_d"]["diff"]) < 0.5 for r in rows)
    assert sum(abs(r["lcip_d"]["diff"]) < 4.0 for r in rows) == 9  # Site04 RoI 3: +15.5 d


def test_mazarico_table3_recorded_as_misses_with_the_rank_20_point_off_the_plateau():
    m = V["mazarico_table3"]
    assert m["primary"] == "emulated" and m["variants"]["emulated"] == {
        "min_range_m": 240.0,
        "azimuth_step_deg": 0.5,
    }
    for variant in ("emulated", "engine"):
        for key, r in m[variant].items():
            assert not r["pass"], (variant, key)  # every comparison misses its shift-derived tolerance
            r20 = next(x for x in r["rows"] if x["rank"] == 20)
            assert x_off(r20) > 30.0  # Site20's published point lands on the plateau's flank in our map
    for variant in ("emulated", "engine"):
        for q in ("10m_avg_ill_pct", "10m_visibility_pct"):
            others = [x for x in m[variant][q]["rows"] if x["rank"] != 20]
            assert sum(abs(x["ours"] - x["mazarico"]) for x in others) / len(others) < 1.0  # diagnostic


def x_off(row):
    return row["mazarico"] - row["ours"]


# ---------------------------------- follow-ups to the second correctness review (methodology 6.6.1, 6.7)


def test_accuracy_at_every_pgda_site():
    a = V["accuracy_sites"]
    assert len([k for k in a if k.startswith("pgda-")]) == 8
    for sid in (
        "pgda-site01",
        "pgda-site11",
    ):  # the Earth's horizon is set far away: a near-field shift does nothing
        r = a[sid]
        assert r["near_minus_0.2"]["earth_visibility_fraction"] == r["base"]["earth_visibility_fraction"]
        assert r["earth_partly_hidden"]["lt_1km"] == 0.0
    for sid in ("pgda-site04", "pgda-site06", "pgda-site07", "pgda-site20", "pgda-site23", "pgda-site42"):
        r = a[sid]
        assert r["earth_partly_hidden"]["lt_1km"] == 1.0  # here near terrain sets the Earth's horizon
        assert r["near_minus_0.2"]["earth_visibility_fraction"] > r["base"]["earth_visibility_fraction"]
    for sid, r in a.items():
        if sid.startswith("pgda-"):  # the 600 s baseline is the served value to 0.1 pp
            served = a["served_heights"][sid]["1m"]["illumination_fraction"]
            assert abs(r["base"]["illumination_fraction"] - served) < 1e-3


def test_site20_cluster_disagrees_between_the_maps():
    m = V["maz20"]
    assert m["grid_points"] == 49 and m["grid_above_table3"] == 0
    assert m["grid_nearest_above_65pct_m"] > m["rounding_halfwidth_m"]["latitude"]  # outside the rounding
    r38, t38 = m["rank38_matched"], m["rank38_table3"]
    assert r38["0m"]["avg_ill_pct"] < t38["0m"][0] - 15 and r38["10m"]["avg_ill_pct"] < t38["10m"][0]


def test_site04_roi3_full_run_matches_the_figure():
    f = V["roifull"]
    assert (f["site"], f["roi"], f["pixels"]) == ("pgda-site04", 3, 126)
    d = f["full_minus_figure"]
    assert abs(d["avg_ill_pct"]) < 0.5 and abs(d["lcip_d"]) < 1.0 and abs(d["lcsp_d"]) < 0.2
