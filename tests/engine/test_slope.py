# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""lss.terrain.slope: central-difference slope (Barker et al. 2021's definition), statistics in a radius."""

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from lss.datafiles import get as datafile
from lss.terrain.slope import scale_factor, slope_deg, slope_stats


def test_tilted_plane_has_its_slope():
    step = 5.0
    yy, xx = np.mgrid[0:50, 0:60] * step
    z = np.tan(np.radians(12.0)) * xx + 0.0 * yy  # rises to the east by tan(12 deg)
    assert np.allclose(slope_deg(z, step), 12.0, atol=1e-9)
    z2 = np.tan(np.radians(7.0)) * (xx * np.cos(0.6) + yy * np.sin(0.6))  # any direction
    assert np.allclose(slope_deg(z2, step), 7.0, atol=1e-9)


def test_scale_factor_steepens_map_slopes_slightly():
    assert scale_factor(0.0, 0.0) == 1.0
    k83 = float(scale_factor(212_000.0, 0.0))  # ~83 S
    assert 1.0036 < k83 < 1.0039
    z = np.tan(np.radians(10.0)) * np.mgrid[0:5, 0:5][1] * 10.0
    assert slope_deg(z, 10.0, k83)[0, 0] > slope_deg(z, 10.0)[0, 0]


def test_stats_within_a_radius(tmp_path):
    """A cone of known slope (20 deg) around the centre, flat beyond 500 m: stats count the right pixels."""
    step, n = 10.0, 301
    x0, y0 = -100_000.0, 50_000.0  # map centre (PS m); scale factor ~1.0009 here
    left, top = x0 - n * step / 2, y0 + n * step / 2
    cols, rows = np.meshgrid(np.arange(n), np.arange(n))
    X, Y = left + (cols + 0.5) * step, top - (rows + 0.5) * step
    r = np.hypot(X - x0, Y - y0)
    z = (np.tan(np.radians(20.0)) * np.minimum(r, 500.0)).astype(np.float32)
    path = tmp_path / "cone.tif"
    with rasterio.open(
        path, "w", driver="GTiff", width=n, height=n, count=1, dtype="float32",
        transform=from_origin(left, top, step, step), nodata=np.nan,
    ) as d:  # fmt: skip
        d.write(z, 1)
    s = slope_stats(path, x0, y0, 300.0)
    assert s.max_deg == pytest.approx(20.0 + 0.05, abs=0.1)  # map slopes x scale factor
    assert s.pixels == pytest.approx(np.pi * (300.0 / step) ** 2, rel=0.03)
    with pytest.raises(ValueError, match="leaves the map"):
        slope_stats(path, x0, y0, 2000.0)


@pytest.mark.skipif(
    not (datafile("site01_dem").path.is_file() and datafile("site01_slope").path.is_file()),
    reason="Site01 DEM / Barker slope map not downloaded",
)
def test_reproduces_barkers_site01_slope_map():
    with rasterio.open(datafile("site01_dem").path) as d, rasterio.open(datafile("site01_slope").path) as b:
        assert d.transform == b.transform
        z, ref = d.read(1).astype(float), b.read(1).astype(float)[1:-1, 1:-1]
        step = d.transform.a
    diff = np.abs(slope_deg(z, step) - ref)
    assert np.nanmedian(diff) < 0.001 and np.nanpercentile(diff, 99) < 0.01


def _terrain_script():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "precompute_terrain.py"
    spec = importlib.util.spec_from_file_location("precompute_terrain", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_terrain_radii_use_the_decided_layers():
    """1 km on the 5 m site tile, 10 km on the 10 m polar map (the project author, 2026-11-15)."""
    m = _terrain_script()
    assert m.RADII_M == (1_000.0, 10_000.0)
    for tile in ("Site01", "Site04"):
        f = m.layer_files(tile)
        assert f[1_000.0][1:] == ("pgda_78_site_dems", 5.0) and f[10_000.0][1:] == (
            "pgda_90_south_pole_dems",
            10.0,
        )


@pytest.mark.skipif(not datafile("site01_dem").path.is_file(), reason="Site01 DEM not downloaded")
def test_site01_slope_at_the_served_point():
    from lss.registry.sites import site_points

    s = slope_stats(datafile("site01_dem").path, *site_points()["pgda-site01"].ps_m, 1_000.0)
    assert s.at_point_deg == pytest.approx(1.17, abs=0.01)
    assert s.pixels == pytest.approx(np.pi * (1_000.0 / 5.0) ** 2, rel=0.01)
    assert s.max_deg > 30.0 and 5.0 < s.mean_deg < 15.0


def test_artemis_regions_use_the_5m_map_only_where_their_point_lies_on_one():
    """Sites without a PGDA site point (precompute_terrain.other_site_files): 1 km on the 5 m site map if the
    point lies on one, else on the 10 m map; 10 km always on the 10 m map."""
    from lss.registry.sites import get_site

    m = _terrain_script()
    _, on_tile = m.other_site_files(get_site("artemis3-malapert-massif"))
    _, off_tile = m.other_site_files(get_site("artemis3-haworth"))
    assert on_tile[1_000.0][1:] == ("pgda_78_site_dems", 5.0)
    assert off_tile[1_000.0] == ("ldem_83s_10m_artemis3_haworth_clip", "pgda_90_south_pole_dems", 10.0)
    assert on_tile[10_000.0][2] == off_tile[10_000.0][2] == 10.0


def test_apollo_sites_use_the_global_map_with_the_approved_limitation():
    from lss.registry.sites import get_site

    m = _terrain_script()
    assert m.on_global_map(get_site("apollo-11")) and not m.on_global_map(get_site("artemis3-haworth"))
    assert (m.GLOBAL_DATASET, m.GLOBAL_RES_M) == ("lola_ldem_128", 236.901)
    assert m.LIMIT_GLOBAL == (  # approved by the project author (2026-11-16)
        "Measured on the 237 m global map (LOLA LDEM_128): regional slopes over about 500 m; smaller "
        "features are not resolved, and values are not comparable with the 5 m and 10 m maps at the polar "
        "sites."
    )
