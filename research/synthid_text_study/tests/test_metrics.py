"""Tests for pure-python metrics (no ML stack required)."""

from synthid_study import metrics


def test_edit_distance_basic():
    assert metrics.token_edit_distance([1, 2, 3], [1, 2, 3]) == 0
    assert metrics.token_edit_distance([1, 2, 3], [1, 9, 3]) == 1
    assert metrics.token_edit_distance([], [1, 2]) == 2
    assert metrics.token_edit_distance([1, 2], []) == 2
    # one substitution + one deletion
    assert metrics.token_edit_distance([1, 2, 3, 4], [1, 9, 4]) == 2


def test_lcs_and_retained_fraction():
    assert metrics.lcs_length([1, 2, 3, 4], [1, 3, 4]) == 3
    assert metrics.retained_fraction([1, 2, 3, 4], [1, 3, 4]) == 0.75
    assert metrics.retained_fraction([], [1]) == 0.0
    # identical -> full retention
    assert metrics.retained_fraction([5, 6, 7], [5, 6, 7]) == 1.0
    # nothing in common -> zero retention
    assert metrics.retained_fraction([1, 2, 3], [9, 8, 7]) == 0.0


def test_token_jaccard():
    assert metrics.token_jaccard([1, 2, 3], [1, 2, 3]) == 1.0
    assert metrics.token_jaccard([1, 2], [3, 4]) == 0.0
    assert metrics.token_jaccard([], []) == 1.0
    assert metrics.token_jaccard([1, 2, 3, 4], [3, 4, 5, 6]) == 2 / 6


def test_cosine():
    assert metrics.cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert metrics.cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert metrics.cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    approx = metrics.cosine([1.0, 1.0], [1.0, 0.0])
    assert abs(approx - (1 / 2**0.5)) < 1e-9
