"""Opt-in integration test: watermarked contamination raises the detector score.

Enable with:  SYNTHID_RUN_MODEL=1 pytest tests/test_inverse_smoke.py
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SYNTHID_RUN_MODEL") != "1",
    reason="set SYNTHID_RUN_MODEL=1 to run model-backed integration test",
)


def test_full_contamination_scores_above_human():
    import inverse_study  # noqa: F401  (triggers sys.path bootstrap to Study 1)
    from inverse_study import contaminate as C
    from inverse_study.experiment import _gen_watermarked
    from synthid_study.watermark import Engine, GenParams, WatermarkParams

    eng = Engine(
        "distilgpt2",
        WatermarkParams(keys=[654, 400, 836, 123, 340, 443, 597, 160, 57, 29], ngram_len=5),
        GenParams(max_new_tokens=96, temperature=1.0, top_k=40),
        cache_dir="../synthid_text_study/.hf_cache",  # reuse Study 1's cached model
    )
    human_text = ("It is a truth universally acknowledged, that a single man in possession of a "
                  "good fortune, must be in want of a wife. However little known the feelings of "
                  "such a man may be on his first entering a neighbourhood.")
    h_ids = eng.tokenizer(human_text)["input_ids"]
    n = len(h_ids)
    a_ids = _gen_watermarked(eng, eng.decode(h_ids[:12]), n, seed=1)

    human_score, _ = eng.weighted_mean_score(h_ids)
    full = C.contaminate(h_ids, a_ids, 1.0, "contiguous")
    ai_score, _ = eng.weighted_mean_score(full.token_ids)

    assert abs(human_score - 0.5) < 0.12   # real human prose sits near the null
    assert ai_score > human_score          # full AI raises the score
