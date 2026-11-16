# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""lss.terrain.views: hillshade, slope classes and elevation encoding for the 2D site view."""

import numpy as np
import pytest

from lss.terrain import views as tv


def plane(rows, cols, step, dzdx, dzdy_up):
    yy, xx = np.mgrid[0:rows, 0:cols] * step
    return dzdx * xx - dzdy_up * yy  # rows run down the map


def test_flat_ground_is_lit_by_the_light_altitude():
    hs = tv.hillshade(np.zeros((10, 10)), 5.0)
    assert hs.shape == (8, 8) and np.all(hs == round(255 * np.sin(np.radians(tv.HILLSHADE_ALTITUDE_DEG))))


def test_slope_facing_the_light_is_brighter_than_one_facing_away():
    t = np.tan(np.radians(20.0))
    up_left = plane(
        10, 10, 5.0, -t / np.sqrt(2), t / np.sqrt(2)
    )  # rises towards the upper left (azimuth 315)
    down_left = plane(10, 10, 5.0, t / np.sqrt(2), -t / np.sqrt(2))
    assert tv.hillshade(down_left, 5.0).mean() > tv.hillshade(up_left, 5.0).mean() + 50


@pytest.mark.parametrize("deg, cls", [(2.0, 0), (7.0, 1), (12.0, 2), (17.0, 3), (35.0, 4)])
def test_slope_classes(deg, cls):
    z = plane(6, 6, 5.0, np.tan(np.radians(deg)), 0.0)
    assert np.all(tv.slope_classes(z, 5.0) == cls)


def test_nodata_and_elevation_round_trip():
    z = np.full((5, 5), 1956.37)
    z[2, 2] = np.nan
    assert tv.slope_classes(z, 5.0)[1, 1] == tv.NODATA_CLASS  # the no-data pixel itself
    cross = np.array(
        [[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool
    )  # and its four edge neighbours (central differences)
    assert np.array_equal(tv.slope_classes(z, 5.0) == tv.NODATA_CLASS, cross)
    assert tv.hillshade(z, 5.0)[1, 1] == 0
    v, off = tv.elevation_u16(z)
    assert v[2, 2] == 0 and v[0, 0] > 0
    assert off + tv.ELEVATION_SCALE_M * v[0, 0] == pytest.approx(1956.37, abs=0.05)


def test_palettes_have_one_colour_per_class():
    assert len(tv.SLOPE_CLASS_LABELS) == len(tv.SLOPE_CLASS_EDGES_DEG) + 1
    assert all(len(p) == len(tv.SLOPE_CLASS_LABELS) for p in tv.SLOPE_PALETTE.values())
