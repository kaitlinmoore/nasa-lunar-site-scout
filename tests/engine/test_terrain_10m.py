# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""The 10 m polar map as an opt-in area near field (lss.registry.terrain.POLAR_10M, LAYERS_10M): which
locations get it, the window it is read through, its fidelity label, and, on the real map (skipped when it
is not downloaded), its header, heights and horizons without missing samples."""

import numpy as np
import pytest

from lss.contract import FidelityTier
from lss.datafiles import get as datafile
from lss.horizon import HorizonParams, compute_horizon
from lss.horizon.cache import key_spec
from lss.horizon.core import segments_for
from lss.registry import terrain as reg
from lss.registry.sites import load_sites
from lss.terrain import MOON_RADIUS_M, latlon_from_ps, ps_from_latlon

HAVE_10M = datafile(reg.POLAR_10M.file_id).path.is_file()
needs_10m = pytest.mark.skipif(not HAVE_10M, reason="10 m polar map not downloaded (fetch_data.py nearfield)")

# Every curated site's stack under the default layers: (near-field file, [(resolution, from km, to km)]).
TILE = [(5.0, 0.0, 5.0), (80.0, 5.0, 100.0), (240.0, 100.0, 400.0)]
POLAR = [(80.0, 0.0, 100.0), (240.0, 100.0, 400.0)]
GLOBAL = [(236.901, 0.0, 400.0)]
SITE_STACKS = {
    "pgda-site01": ("site01_dem", TILE),
    "pgda-site04": ("site04_dem", TILE),
    "pgda-site07": ("site07_dem", TILE),
    "pgda-site11": ("site11_dem", TILE),
    "pgda-site06": ("site06_dem", TILE),
    "pgda-site20": ("site20_dem", TILE),
    "pgda-site23": ("site23_dem", TILE),
    "pgda-site42": ("site42_dem", TILE),
    **{f"apollo-{n}": ("ldem_128_img", GLOBAL) for n in (11, 12, 14, 15, 16, 17)},
    "artemis3-peak-near-cabeus-b": ("ldem_80s_80m", POLAR),
    "artemis3-haworth": ("ldem_80s_80m", POLAR),
    "artemis3-malapert-massif": ("site23_dem", TILE),
    "artemis3-mons-mouton-plateau": ("ldem_80s_80m", POLAR),
    "artemis3-mons-mouton": ("site20_dem", TILE),
    "artemis3-nobile-rim-1": ("site06_dem", TILE),
    "artemis3-nobile-rim-2": ("ldem_80s_80m", POLAR),
    "artemis3-de-gerlache-rim-2": ("ldem_80s_80m", POLAR),
    "artemis3-slater-plain": ("ldem_80s_80m", POLAR),
}


def _summary(stack):
    return (
        stack.layers[0].spec.file_id,
        [(sl.spec.resolution_m, sl.min_range_m / 1000.0, sl.max_range_m / 1000.0) for sl in stack.layers],
    )


def _key(stack, height=1.0):
    loc = stack.location
    return key_spec(loc.lat, loc.lon, height, HorizonParams(), stack)


def test_default_layers_leave_the_10m_map_out_and_keep_every_site_stack():
    """The default layers never include the 10 m map, so all 23 curated sites keep exactly their stacks (and
    so their horizon cache keys)."""
    assert reg.POLAR_10M not in reg.LAYERS and all(
        not isinstance(s, reg.WindowedLayerSpec) for s in reg.LAYERS
    )
    sites = {s.id: s for s in load_sites()}
    assert set(sites) == set(SITE_STACKS)
    for sid, want in SITE_STACKS.items():
        loc = sites[sid].location
        assert _summary(reg.resolve(loc.lat, loc.lon)) == want, sid


def test_10m_list_changes_only_the_sites_without_a_5m_tile():
    """With LAYERS_10M, a site on a 5 m tile keeps its stack and cache key: the tile covers the first 5 km,
    which is as far as the 10 m map is used. The six Artemis III regions off the tiles get the 10 m map
    as near field to 5 km, then the 80 m and 240 m maps as before."""
    for s in load_sites():
        lat, lon = s.location.lat, s.location.lon
        a, b = reg.resolve(lat, lon), reg.resolve(lat, lon, layers=reg.LAYERS_10M)
        if SITE_STACKS[s.id][0] != "ldem_80s_80m":
            assert a == b and _key(a) == _key(b), s.id
            continue
        assert _summary(b) == ("ldem_83s_10m", [(10.0, 0.0, 5.0), (80.0, 5.0, 100.0), (240.0, 100.0, 400.0)])
        assert b.layers[0].spec.centre == (lat, lon) and b.layers[0].spec.window_m == 5_000.0
        assert [sl.spec for sl in b.layers[1:]] == [sl.spec for sl in a.layers]
        assert _key(a) != _key(b)


def _on_axis(dist_from_edge_m, lon=90.0):
    """(lat, lon) on a map axis whose 5 km cap ends `dist_from_edge_m` short of the last pixel's width inside
    the 10 m map's edge. On the map the cap's radius is 5 km x the scale factor k = 1 + (rho / 2R)^2."""
    edge = reg.POLAR_10M.bounds_m[2] - reg.POLAR_10M.resolution_m
    rho = edge - dist_from_edge_m - 5_000.0
    for _ in range(3):
        rho = edge - dist_from_edge_m - 5_000.0 * (1.0 + (rho / (2.0 * MOON_RADIUS_M)) ** 2)
    lat, _ = latlon_from_ps(rho, 0.0, "south")
    return float(lat), lon


@pytest.mark.parametrize(
    "lat, lon, near",
    [
        (-90.0, 0.0, "ldem_83s_10m"),  # the pole
        (-85.0, -110.0, "ldem_83s_10m"),
        (-80.5, 45.0, "ldem_83s_10m"),  # in a corner of the square, beyond the 83 S circle
        (*_on_axis(20.0), "ldem_83s_10m"),  # the 5 km cap ends 20 m inside the margin
        (*_on_axis(-20.0), "ldem_80s_80m"),  # ... 20 m beyond it: rays would leave the map
        (-83.0, 0.0, "ldem_80s_80m"),  # inside the square, but 3.9 km from its edge
        (-81.0, 0.0, "ldem_80s_80m"),  # off the 10 m map
        (-75.0, 0.0, "ldem_60s_240m"),  # off the 80 m map too
        (*reversed((-137.1487, -89.4527)), "site01_dem"),  # a site tile keeps its own near field
    ],
)
def test_10m_list_resolves_inside_at_the_edge_and_outside(lat, lon, near):
    st = reg.resolve(lat, lon, layers=reg.LAYERS_10M)
    assert st.layers[0].spec.file_id == near
    assert st.layers[-1].max_range_m == reg.MAX_RANGE_M
    if near == "ldem_83s_10m":
        assert reg.holds_cap(reg.POLAR_10M, lat, lon, reg.POLAR_10M.use_to_m)
        assert [sl.spec.file_id for sl in st.layers[1:]] == ["ldem_80s_80m", "ldem_60s_240m"]


def _destination(lat, lon, bearing_deg, dist_m):
    p1, l1, b, d = np.radians(lat), np.radians(lon), np.radians(bearing_deg), dist_m / MOON_RADIUS_M
    p2 = np.arcsin(np.sin(p1) * np.cos(d) + np.cos(p1) * np.sin(d) * np.cos(b))
    l2 = l1 + np.arctan2(np.sin(b) * np.sin(d) * np.cos(p1), np.cos(d) - np.sin(p1) * np.sin(p2))
    return np.degrees(p2), np.degrees(l2)


@pytest.mark.parametrize("lat, lon", [(-90.0, 0.0), (-89.99, 30.0), (-86.0, 120.0), (-80.5, 45.0)])
def test_window_holds_every_ray_sample_it_is_used_for(lat, lon):
    """The pixel window (from the cap's circle, no file needed) holds every point within 5 km, with at least a
    pixel to spare for bilinear interpolation: checked on a ring of great-circle destinations."""
    spec = reg.resolve(lat, lon, layers=reg.LAYERS_10M).layers[0].spec
    col0, row0, n_cols, n_rows = spec.pixel_window()
    left, _, _, top = spec.bounds_m
    x, y = ps_from_latlon(*_destination(lat, lon, np.arange(3600) * 0.1, spec.window_m), "south")
    col = (x - left) / spec.resolution_m - 0.5 - col0
    row = (top - y) / spec.resolution_m - 0.5 - row0
    assert col.min() >= 1.0 and row.min() >= 1.0 and col.max() <= n_cols - 2 and row.max() <= n_rows - 2
    assert n_cols * n_rows * 4 < 5e6  # a few MB, not the 7.5 GB map


def test_fidelity_of_a_10m_near_field():
    fid = reg.resolve(-85.0, -110.0, layers=reg.LAYERS_10M).fidelity()
    assert fid.tier == FidelityTier.high
    assert fid.summary == "10 m polar map near field, 80 m polar map / 240 m polar map far field"
    assert fid.near_field_resolution_m == 10.0 and fid.far_field_resolution_m == 240.0
    # The 80 m map as near field stays medium, a 5 m tile high.
    assert reg.resolve(-85.0, -110.0).fidelity().tier == FidelityTier.medium
    assert reg.resolve(-89.4527, -137.1487, layers=reg.LAYERS_10M).fidelity().tier == FidelityTier.high


# ------------------------------------------------------------------------------------- on the real map


@needs_10m
def test_10m_header_matches_the_spec_and_dem_interface():
    """`dem()` keeps the interface of the other layers: `.path`, `.pole` and `.meta` of the whole file (as a
    caller reading its own 3 x 3 window needs), on the listed spec as on the resolved one. Only the resolved
    one has a grid, and that grid is the window."""
    listed = reg.POLAR_10M.dem()
    m = listed.meta
    assert listed.path == datafile("ldem_83s_10m").path and listed.pole == "south"
    assert (m["x0"], m["y0"], m["res"], m["width"], m["height"]) == (
        -216_400.0,
        216_400.0,
        10.0,
        43_280,
        43_280,
    )
    assert np.isnan(m["nodata"]) and (m["scale"], m["offset"]) == (1.0, 0.0)
    assert listed.bounds == pytest.approx(reg.POLAR_10M.bounds_m)
    with pytest.raises(ValueError, match="no window"):
        _ = listed.grid
    spec = reg.resolve(-85.0, -110.0, layers=reg.LAYERS_10M).layers[0].spec
    dem = spec.dem()
    assert dem.meta == m and dem.path == listed.path
    col0, row0, n_cols, n_rows = spec.pixel_window()
    assert dem.grid.array.shape == (n_rows, n_cols)
    assert (dem.grid.x0, dem.grid.y0) == (m["x0"] + 10.0 * col0, m["y0"] - 10.0 * row0)


@needs_10m
def test_window_heights_are_the_file_pixels():
    import rasterio
    from rasterio.windows import Window

    spec = reg.resolve(-86.0, 120.0, layers=reg.LAYERS_10M).layers[0].spec
    g = spec.dem().grid
    col0, row0, _, _ = spec.pixel_window()
    with rasterio.open(spec.dem().path) as d:
        for r, c in [(0, 0), (37, 412), (500, 500)]:
            want = d.read(1, window=Window(col0 + c, row0 + r, 1, 1))[0, 0]
            x = g.x0 + (c + 0.5) * g.res
            y = g.y0 - (r + 0.5) * g.res
            assert g.array[r, c] == want and float(spec.dem().height_at_ps(x, y)[0]) == pytest.approx(want)


@needs_10m
@pytest.mark.parametrize(
    "lat, lon", [(-89.99, 30.0), (-88.0, 45.0), (-85.0, -110.0), (-83.5, 160.0), (-82.5, 45.0)]
)
def test_no_missing_samples_with_the_10m_near_field(lat, lon):
    st = reg.resolve(lat, lon, layers=reg.LAYERS_10M)
    assert st.layers[0].spec.file_id == "ldem_83s_10m"
    h = compute_horizon(lat, lon, 1.0, segments_for(st), HorizonParams())
    assert h.missing_samples == 0 and h.layers[0]["resolution_m"] == 10.0
