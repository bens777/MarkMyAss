"""Opt-in integration test: watermark is key-specific.

Enable with: SYNTHID_RUN_MODEL=1 pytest tests/test_replication_smoke.py
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SYNTHID_RUN_MODEL") != "1",
    reason="set SYNTHID_RUN_MODEL=1 to run model-backed integration test",
)


def test_watermark_is_key_specific():
    import replication  # noqa: F401  (bootstraps Study 1/2 packages)
    from replication.experiment import _generate, _score
    from synthid_study.watermark import Engine, GenParams, WatermarkParams
    from transformers import SynthIDTextWatermarkingConfig

    key_a = [654, 400, 836, 123, 340, 443, 597, 160, 57, 29]
    key_b = [11, 929, 215, 703, 88, 451, 660, 17, 540, 382]
    eng = Engine("distilgpt2", WatermarkParams(keys=key_a, ngram_len=5),
                 GenParams(max_new_tokens=96, temperature=1.0, top_k=40),
                 cache_dir="../synthid_text_study/.hf_cache")

    def mk(keys):
        return SynthIDTextWatermarkingConfig(
            ngram_len=5, keys=keys, sampling_table_size=65536,
            sampling_table_seed=0, context_history_size=1024)

    cfg_a, cfg_b = mk(key_a), mk(key_b)
    proc_a = cfg_a.construct_processor(eng.vocab_size, eng.device)
    proc_b = cfg_b.construct_processor(eng.vocab_size, eng.device)

    ids = _generate(eng, "The lighthouse keeper wrote in his journal that", 96, seed=1, wm_config=cfg_a)
    sa, _ = _score(proc_a, 5, eng.eos_token_id, ids)   # scored under the SAME key
    sb, _ = _score(proc_b, 5, eng.eos_token_id, ids)   # scored under a DIFFERENT key

    assert sa > sb                 # watermark shows up only under its own key
    assert abs(sb - 0.5) < 0.12    # wrong key sees ~null
