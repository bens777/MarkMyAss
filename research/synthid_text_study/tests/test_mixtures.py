"""Tests for controlled watermark/original mixtures (no ML stack required)."""

import pytest
from synthid_study.mixtures import make_mixture


def _wm():
    return list(range(100, 120))  # 20 "watermarked" token ids


def _ref():
    return list(range(200, 220))  # 20 aligned "original" token ids


def test_boundaries_full_and_none():
    full = make_mixture(_wm(), _ref(), 1.0)
    assert full.token_ids == _wm()
    assert full.n_watermarked == 20
    assert full.retained_fraction == 1.0

    none = make_mixture(_wm(), _ref(), 0.0)
    assert none.token_ids == _ref()
    assert none.n_watermarked == 0
    assert none.retained_fraction == 0.0


def test_keep_prefix_geometry():
    mix = make_mixture(_wm(), _ref(), 0.25, geometry="keep_prefix")
    # first 5 watermarked, remaining 15 from reference
    assert mix.watermarked_mask[:5] == [True] * 5
    assert mix.watermarked_mask[5:] == [False] * 15
    assert mix.token_ids[:5] == list(range(100, 105))
    assert mix.token_ids[5:] == list(range(205, 220))


def test_keep_suffix_geometry():
    mix = make_mixture(_wm(), _ref(), 0.25, geometry="keep_suffix")
    assert mix.watermarked_mask[:15] == [False] * 15
    assert mix.watermarked_mask[15:] == [True] * 5


def test_scattered_is_seeded_and_counts_match():
    a = make_mixture(_wm(), _ref(), 0.5, geometry="scattered", seed=7)
    b = make_mixture(_wm(), _ref(), 0.5, geometry="scattered", seed=7)
    c = make_mixture(_wm(), _ref(), 0.5, geometry="scattered", seed=8)
    assert a.token_ids == b.token_ids  # deterministic for a fixed seed
    assert a.n_watermarked == 10
    assert c.n_watermarked == 10
    assert a.token_ids != c.token_ids  # different seed -> different placement


def test_validation():
    with pytest.raises(ValueError):
        make_mixture([1, 2], [1], 0.5)
    with pytest.raises(ValueError):
        make_mixture([1, 2], [3, 4], 1.5)
    with pytest.raises(ValueError):
        make_mixture([1, 2], [3, 4], 0.5, geometry="nonsense")
