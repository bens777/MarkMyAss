"""Tests for the contamination splicing logic (no ML stack required)."""

import pytest
from inverse_study import contaminate as C


def _h():
    return list(range(1000, 1100))  # 100 human tokens


def _a():
    return list(range(2000, 2100))  # 100 aligned AI tokens


def test_contiguous_positions():
    pos = C.contiguous_positions(100, 20)
    assert len(pos) == 20
    assert pos == set(range(15, 35))  # starts at round(0.15*100)=15
    assert C.contiguous_positions(100, 0) == set()
    assert len(C.contiguous_positions(100, 100)) == 100


def test_scattered_positions_count_and_spread():
    pos = C.scattered_positions(100, 20, k=5)
    assert len(pos) == 20
    # spread across the document, not one contiguous run
    assert max(pos) - min(pos) > 20
    assert C.scattered_positions(100, 0) == set()


def test_unit_positions_takes_whole_units():
    spans = [(0, 10), (10, 25), (25, 40), (40, 100)]
    pos = C.unit_positions(spans, 100, 12)
    # accumulate whole units until >= 12 tokens -> first two units (0..25)
    assert pos == set(range(0, 25))


def test_contaminate_fraction_and_mask():
    full = C.contaminate(_h(), _a(), 1.0, "contiguous")
    assert full.n_ai == 100
    assert full.ai_fraction == 1.0
    assert full.token_ids == _a()

    none = C.contaminate(_h(), _a(), 0.0, "contiguous")
    assert none.n_ai == 0
    assert none.token_ids == _h()

    half = C.contaminate(_h(), _a(), 0.2, "scattered")
    assert half.n_ai == 20
    assert abs(half.ai_fraction - 0.2) < 1e-9
    # AI tokens must come from _a, human from _h
    for i, is_ai in enumerate(half.ai_mask):
        assert half.token_ids[i] == (_a()[i] if is_ai else _h()[i])


def test_append_prepend_wrap():
    ap = C.append_ai(_h(), _a(), 10)
    assert len(ap.token_ids) == 110 and ap.n_ai == 10
    assert ap.ai_mask[:100] == [False] * 100 and ap.ai_mask[100:] == [True] * 10

    pp = C.prepend_ai(_h(), _a(), 8)
    assert len(pp.token_ids) == 108 and pp.n_ai == 8
    assert pp.ai_mask[:8] == [True] * 8

    wr = C.wrap_ai(_h(), _a(), _a(), 5, 7)
    assert len(wr.token_ids) == 112 and wr.n_ai == 12


def test_unknown_geometry_and_missing_spans():
    with pytest.raises(ValueError):
        C.contaminate(_h(), _a(), 0.2, "bogus")
    with pytest.raises(ValueError):
        C.contaminate(_h(), _a(), 0.2, "sentence", unit_spans=None)
