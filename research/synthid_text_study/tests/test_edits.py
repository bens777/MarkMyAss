"""Tests for edit-category transforms (no ML stack required)."""

import pytest
from synthid_study.edits import CATEGORIES, apply_edit


def _wm():
    return list(range(100, 200))  # 100 watermarked tokens


def _ref():
    return list(range(300, 400))  # 100 aligned original tokens


def test_all_categories_run_and_report_changes():
    for name, spec in CATEGORIES.items():
        res = apply_edit(_wm(), _ref(), name, vocab_size=5000, seed=1)
        assert len(res.token_ids) == 100
        expected = round(spec.density * 100)
        # changed count is at most the targeted positions
        assert res.n_changed <= expected
        # for "alt" edits on a large vocab almost all targets actually change
        if spec.replacement == "alt" and expected > 0:
            assert res.n_changed >= expected - 1


def test_restoration_reverts_to_reference():
    res = apply_edit(_wm(), _ref(), "restoration", vocab_size=5000, seed=1)
    assert res.token_ids == _ref()
    assert res.n_changed == 100


def test_scattered_vs_contiguous_positions():
    scattered = apply_edit(_wm(), _ref(), "word_substitution", vocab_size=5000, seed=2)
    contiguous = apply_edit(_wm(), _ref(), "sentence_rewrite", vocab_size=5000, seed=2)
    # contiguous positions form a single run
    cp = contiguous.changed_positions
    assert cp == list(range(cp[0], cp[0] + len(cp)))
    # scattered positions generally do not
    sp = scattered.changed_positions
    assert sp != list(range(sp[0], sp[0] + len(sp)))


def test_determinism():
    a = apply_edit(_wm(), _ref(), "grammar", vocab_size=5000, seed=3)
    b = apply_edit(_wm(), _ref(), "grammar", vocab_size=5000, seed=3)
    assert a.token_ids == b.token_ids


def test_unknown_category():
    with pytest.raises(ValueError):
        apply_edit(_wm(), _ref(), "does_not_exist", vocab_size=5000)
