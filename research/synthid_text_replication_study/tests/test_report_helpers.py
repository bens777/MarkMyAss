"""Tests for the replication report statistics (no ML stack required)."""

from replication.report import _crossings, _wilson


def test_wilson_bounds():
    p, lo, hi = _wilson(5, 10)
    assert p == 0.5
    assert 0.0 <= lo < p < hi <= 1.0
    # zero and full detection stay in [0, 1]
    _, lo0, hi0 = _wilson(0, 20)
    assert lo0 == 0.0 and hi0 < 0.5
    _, lo1, hi1 = _wilson(20, 20)
    assert hi1 == 1.0 and lo1 > 0.5
    assert _wilson(0, 0) == (0.0, 0.0, 0.0)


def test_wilson_ci_narrows_with_n():
    _, lo_small, hi_small = _wilson(5, 10)
    _, lo_big, hi_big = _wilson(50, 100)
    assert (hi_big - lo_big) < (hi_small - lo_small)


def test_crossings_interpolation():
    fr = [0.0, 0.1, 0.2, 0.3, 0.4]
    rate = [0.0, 0.1, 0.4, 0.8, 1.0]
    cr = _crossings(fr, rate, [0.25, 0.5, 0.75, 0.9])
    # 0.5 lies between 0.2 (0.4) and 0.3 (0.8): 0.2 + (0.5-0.4)/(0.8-0.4)*0.1 = 0.225
    assert abs(cr[0.5] - 0.225) < 1e-9
    assert cr[0.25] is not None and 0.1 < cr[0.25] < 0.2
    assert cr[0.9] is not None and 0.3 < cr[0.9] < 0.4


def test_crossings_never_reached():
    cr = _crossings([0.0, 0.1, 0.2], [0.0, 0.1, 0.2], [0.5])
    assert cr[0.5] is None
