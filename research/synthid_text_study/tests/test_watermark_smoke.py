"""Opt-in integration test for the SynthID-Text engine.

Skipped by default because it downloads a model and runs generation. Enable
with:  SYNTHID_RUN_MODEL=1 pytest tests/test_watermark_smoke.py

It asserts the *instrument* is valid: watermarked text must score above
un-watermarked text under the Weighted-Mean detector with our own key.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SYNTHID_RUN_MODEL") != "1",
    reason="set SYNTHID_RUN_MODEL=1 to run model-backed integration test",
)


def test_watermarked_scores_above_clean():
    from synthid_study.watermark import Engine, GenParams, WatermarkParams

    eng = Engine(
        "distilgpt2",
        WatermarkParams(keys=[654, 400, 836, 123, 340, 443, 597, 160, 57, 29], ngram_len=5),
        GenParams(max_new_tokens=96, temperature=1.0, top_k=40),
        cache_dir=".hf_cache",
    )
    prompt = "The history of the coffee trade began when"
    wm = eng.generate(prompt, watermarked=True, seed=12345)
    clean = eng.generate(prompt, watermarked=False, seed=12345)
    s_wm, n_wm = eng.weighted_mean_score(wm)
    s_clean, n_clean = eng.weighted_mean_score(clean)
    assert n_wm > 0 and n_clean > 0
    assert s_wm > s_clean
    # clean text should sit near the 0.5 coin-flip null
    assert abs(s_clean - 0.5) < 0.12
