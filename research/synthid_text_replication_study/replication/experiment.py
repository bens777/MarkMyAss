"""Replication/robustness factorial for Study 2's detection transition.

Factorial: length bucket x human sample x key x seed x AI fraction x geometry.
Each watermarked passage is generated once per (sample, key, seed, length) and
reused across all fractions/geometries. Scored with the tuning-free Weighted-Mean
detector; a 1% FPR threshold is calibrated PER KEY from un-watermarked controls.
Detector methodology is unchanged from Studies 1-2 (not tuned to results).
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import time
from typing import Any

import pandas as pd
import torch
import yaml
from inverse_study import contaminate as C
from synthid_study.watermark import Engine, GenParams, WatermarkParams
from transformers import SynthIDTextWatermarkingConfig

from .corpus_lengths import load_length_corpus

COLUMNS = [
    "experiment_id", "length_bucket", "sample_id", "key_id", "key_index", "seed",
    "geometry", "nominal_fraction", "ai_generated_fraction",
    "detector_score", "threshold", "detected", "n_tokens", "n_scored_positions", "timestamp",
]


def _key_id(keys: list[int]) -> str:
    return hashlib.sha1(",".join(map(str, keys)).encode()).hexdigest()[:8]


@torch.no_grad()
def _generate(eng: Engine, prompt: str, n: int, seed: int, wm_config) -> list[int]:
    torch.manual_seed(seed)
    enc = eng.tokenizer(prompt, return_tensors="pt").to(eng.device)
    kwargs = dict(do_sample=True, temperature=eng.gen.temperature, top_k=eng.gen.top_k,
                  top_p=eng.gen.top_p, max_new_tokens=n, min_new_tokens=n,
                  pad_token_id=eng.tokenizer.pad_token_id)
    if wm_config is not None:
        kwargs["watermarking_config"] = wm_config
    out = eng.model.generate(**enc, **kwargs)
    return out[0, enc["input_ids"].shape[1]:].tolist()


@torch.no_grad()
def _score(proc, ngram_len: int, eos_id: int, ids: list[int]) -> tuple[float, int]:
    if len(ids) <= ngram_len:
        return float("nan"), 0
    t = torch.tensor([ids], dtype=torch.long)
    g = proc.compute_g_values(t)
    crm = proc.compute_context_repetition_mask(t)
    eos = proc.compute_eos_token_mask(t, eos_id)[:, ngram_len - 1:]
    mask = crm & eos
    if int(mask.sum()) == 0:
        return float("nan"), 0
    m = mask.unsqueeze(-1).expand_as(g)
    return g[m].float().sum().item() / int(m.sum()), int(mask.sum())


def run(config_path: str | pathlib.Path, out_dir: str | pathlib.Path) -> pathlib.Path:
    cfg = yaml.safe_load(pathlib.Path(config_path).read_text(encoding="utf-8"))
    base = pathlib.Path.cwd()
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    wcfg, gcfg = cfg["watermark"], cfg["generation"]
    ngram = wcfg["ngram_len"]
    keys_set = [list(k) for k in cfg["keys"]]

    eng = Engine(
        model_name=cfg["model_name"],
        wm=WatermarkParams(keys=keys_set[0], ngram_len=ngram,
                           sampling_table_size=wcfg["sampling_table_size"],
                           sampling_table_seed=wcfg["sampling_table_seed"],
                           context_history_size=wcfg["context_history_size"]),
        gen=GenParams(max_new_tokens=gcfg["max_new_tokens"], temperature=gcfg["temperature"],
                      top_k=gcfg["top_k"], top_p=gcfg["top_p"]),
        cache_dir=str(base / cfg["hf_cache_dir"]),
    )
    eos_id = eng.eos_token_id

    # per-key watermark configs + detector processors
    def make_cfg(keys):
        return SynthIDTextWatermarkingConfig(
            ngram_len=ngram, keys=keys, sampling_table_size=wcfg["sampling_table_size"],
            sampling_table_seed=wcfg["sampling_table_seed"],
            context_history_size=wcfg["context_history_size"])

    key_cfgs = [make_cfg(k) for k in keys_set]
    key_procs = [c.construct_processor(eng.vocab_size, eng.device) for c in key_cfgs]
    key_ids = [_key_id(k) for k in keys_set]

    samples = load_length_corpus(base / cfg["corpus_dir"])

    # --- per-key thresholds from shared un-watermarked controls (methodology reused) ---
    dcfg = cfg["detector"]
    prompts = [s["text"][:120] for s in samples]
    clean_ids = []
    for i in range(dcfg["n_calibration_samples"]):
        clean_ids.append(_generate(eng, prompts[i % len(prompts)], dcfg["calib_len"],
                                   90000 + i, None))
    thresholds = []
    for proc in key_procs:
        sc = sorted(s for s, n in (_score(proc, ngram, eos_id, ids) for ids in clean_ids)
                    if n > 0 and s == s)
        idx = min(len(sc) - 1, round((1 - dcfg["target_false_positive_rate"]) * (len(sc) - 1)))
        thresholds.append(sc[idx])

    rows: list[dict[str, Any]] = []
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    fractions = cfg["fractions"]
    geometries = cfg["geometries"]
    seeds = [gcfg["base_seed"] + i for i in range(cfg["n_seeds"])]
    exp_id = 0

    for s in samples:
        h_ids = eng.tokenizer(s["text"])["input_ids"][: s["n_tokens"]]
        n = len(h_ids)
        prompt = eng.decode(h_ids[:12])
        for ki, (kcfg, proc, kid, thr) in enumerate(
                zip(key_cfgs, key_procs, key_ids, thresholds, strict=True)):
            # baseline (0% AI): seed/geometry-independent
            b_score, b_ns = _score(proc, ngram, eos_id, h_ids)
            rows.append(dict(experiment_id=exp_id, length_bucket=s["length_bucket"],
                             sample_id=s["sample_id"], key_id=kid, key_index=ki, seed=-1,
                             geometry="none", nominal_fraction=0.0, ai_generated_fraction=0.0,
                             detector_score=b_score, threshold=thr,
                             detected=bool(b_score == b_score and b_score > thr),
                             n_tokens=n, n_scored_positions=b_ns, timestamp=ts))
            exp_id += 1
            for seed in seeds:
                a_ids = _generate(eng, prompt, n, seed, kcfg)
                for geom in geometries:
                    for frac in fractions:
                        if frac == 0.0:
                            continue
                        cont = C.contaminate(h_ids, a_ids, frac, geom,
                                             k_scatter=cfg.get("k_scatter", 5))
                        score, ns = _score(proc, ngram, eos_id, cont.token_ids)
                        rows.append(dict(
                            experiment_id=exp_id, length_bucket=s["length_bucket"],
                            sample_id=s["sample_id"], key_id=kid, key_index=ki, seed=seed,
                            geometry=geom, nominal_fraction=frac,
                            ai_generated_fraction=cont.ai_fraction,
                            detector_score=score, threshold=thr,
                            detected=bool(score == score and score > thr),
                            n_tokens=len(cont.token_ids), n_scored_positions=ns, timestamp=ts))
                        exp_id += 1

    df = pd.DataFrame(rows, columns=COLUMNS)
    df.to_csv(out / "summary.csv", index=False)
    (out / "summary.json").write_text(json.dumps({
        "n_rows": len(df), "n_keys": len(keys_set), "n_seeds": cfg["n_seeds"],
        "lengths": sorted({s["length_bucket"] for s in samples}),
        "key_ids": key_ids,
        "thresholds": dict(zip(key_ids, thresholds, strict=True)),
        "model": cfg["model_name"], "generated_at": ts,
    }, indent=2), encoding="utf-8")
    return out / "summary.csv"
