"""Run the full SynthID-Text behaviour grid and write results.

Produces one row per (prompt, condition) across two axes:
  * mixture -- retained watermarked-token fraction x geometry
  * edit    -- realistic edit-category perturbations

Every row is scored with the tuning-free Weighted-Mean detector using our own
local key. A decision threshold is calibrated from un-watermarked control
samples to a target false-positive rate.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import time
from dataclasses import dataclass
from typing import Any

import pandas as pd
import yaml

from . import edits, metrics
from .mixtures import make_mixture
from .schema import COLUMNS
from .watermark import Engine, GenParams, WatermarkParams


@dataclass
class StudyConfig:
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: str | pathlib.Path) -> StudyConfig:
        with open(path, encoding="utf-8") as fh:
            return cls(raw=yaml.safe_load(fh))


def _key_id(keys: list[int]) -> str:
    return hashlib.sha1(",".join(map(str, keys)).encode()).hexdigest()[:8]


def _read_prompts(path: pathlib.Path, n: int) -> list[str]:
    lines = [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    return lines[:n]


def _calibrate_threshold(eng: Engine, prompts: list[str], n_samples: int, fpr: float) -> float:
    """Threshold = (1 - fpr) quantile of un-watermarked control scores."""
    scores: list[float] = []
    i = 0
    while len(scores) < n_samples:
        prompt = prompts[i % len(prompts)]
        ids = eng.generate(prompt, watermarked=False, seed=90000 + i)
        s, n = eng.weighted_mean_score(ids)
        if n > 0 and s == s:  # not NaN
            scores.append(s)
        i += 1
    scores.sort()
    idx = min(len(scores) - 1, int(round((1.0 - fpr) * (len(scores) - 1))))
    return scores[idx]


def _candidate_metrics(
    eng: Engine,
    cand_ids: list[int],
    wm_ids: list[int],
    ref_ids: list[int],
    emb_wm: list[float],
    emb_ref: list[float],
    threshold: float,
) -> dict[str, Any]:
    score, n_scored = eng.weighted_mean_score(cand_ids)
    emb_c = eng.embed(cand_ids)
    text = eng.decode(cand_ids)
    return {
        "detector_score": score,
        "threshold": threshold,
        "detected": bool(score == score and score > threshold),
        "n_scored_positions": n_scored,
        "token_overlap_original": metrics.retained_fraction(ref_ids, cand_ids),
        "edit_distance_vs_watermarked": metrics.token_edit_distance(cand_ids, wm_ids),
        "edit_distance_vs_original": metrics.token_edit_distance(cand_ids, ref_ids),
        "semantic_sim_vs_watermarked": metrics.cosine(emb_c, emb_wm),
        "semantic_sim_vs_original": metrics.cosine(emb_c, emb_ref),
        "n_tokens": len(cand_ids),
        "n_chars": len(text),
    }


def run(config_path: str | pathlib.Path, out_dir: str | pathlib.Path) -> pathlib.Path:
    cfg = StudyConfig.load(config_path).raw
    # prompts_file / hf_cache_dir are relative to the study root (the CWD the
    # CLI is run from), not the config file's own directory.
    base = pathlib.Path.cwd()
    out = pathlib.Path(out_dir)
    (out / "texts").mkdir(parents=True, exist_ok=True)

    wcfg = cfg["watermark"]
    gcfg = cfg["generation"]
    keys = list(wcfg["keys"])
    key_id = _key_id(keys)
    language = cfg.get("language", "en")

    eng = Engine(
        model_name=cfg["model_name"],
        wm=WatermarkParams(
            keys=keys,
            ngram_len=wcfg["ngram_len"],
            sampling_table_size=wcfg["sampling_table_size"],
            sampling_table_seed=wcfg["sampling_table_seed"],
            context_history_size=wcfg["context_history_size"],
        ),
        gen=GenParams(
            max_new_tokens=gcfg["max_new_tokens"],
            temperature=gcfg["temperature"],
            top_k=gcfg["top_k"],
            top_p=gcfg["top_p"],
        ),
        cache_dir=str(base / cfg.get("hf_cache_dir", ".hf_cache")),
    )

    prompts = _read_prompts(base / cfg["prompts_file"], cfg["n_prompts"])
    dcfg = cfg["detector"]
    threshold = _calibrate_threshold(
        eng, prompts, dcfg["n_calibration_samples"], dcfg["target_false_positive_rate"]
    )

    rows: list[dict[str, Any]] = []
    texts: list[dict[str, Any]] = []
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    replicates = cfg.get("replicates", 1)
    exp_id = 0

    def add_row(axis: str, condition: str, param_value: float, pid: int, rep: int,
                seed: int, m: dict[str, Any], n_wm_retained: int) -> None:
        nonlocal exp_id
        row = {c: None for c in COLUMNS}
        row.update(m)
        row.update(
            experiment_id=exp_id,
            axis=axis,
            condition=condition,
            param_value=param_value,
            prompt_id=pid,
            replicate=rep,
            seed=seed,
            key_id=key_id,
            language=language,
            watermarked_tokens_retained=n_wm_retained,
            watermarked_fraction_retained=(n_wm_retained / m["n_tokens"] if m["n_tokens"] else 0.0),
            timestamp=ts,
        )
        rows.append(row)
        exp_id += 1

    for pid, prompt in enumerate(prompts):
        for rep in range(replicates):
            seed = gcfg["seed"] + 1000 * pid + rep
            wm_ids = eng.generate(prompt, watermarked=True, seed=seed)
            ref_ids = eng.generate(prompt, watermarked=False, seed=seed)
            n = min(len(wm_ids), len(ref_ids))
            wm_ids, ref_ids = wm_ids[:n], ref_ids[:n]
            emb_wm = eng.embed(wm_ids)
            emb_ref = eng.embed(ref_ids)

            texts.append({"prompt_id": pid, "prompt": prompt,
                          "watermarked": eng.decode(wm_ids), "original": eng.decode(ref_ids)})

            # baselines
            m_wm = _candidate_metrics(eng, wm_ids, wm_ids, ref_ids, emb_wm, emb_ref, threshold)
            add_row("baseline", "watermarked", 1.0, pid, rep, seed, m_wm, n)
            m_ref = _candidate_metrics(eng, ref_ids, wm_ids, ref_ids, emb_wm, emb_ref, threshold)
            add_row("baseline", "reference", 0.0, pid, rep, seed, m_ref, 0)

            # Axis 1 -- mixtures
            for geom in cfg["mixture"]["geometries"]:
                for frac in cfg["mixture"]["retained_fractions"]:
                    mix = make_mixture(wm_ids, ref_ids, frac, geometry=geom, seed=seed)
                    m = _candidate_metrics(
                        eng, mix.token_ids, wm_ids, ref_ids, emb_wm, emb_ref, threshold
                    )
                    add_row("mixture", geom, frac, pid, rep, seed, m, mix.n_watermarked)

            # Axis 2 -- edit categories
            for cat in cfg["edits"]["categories"]:
                res = edits.apply_edit(wm_ids, ref_ids, cat, eng.vocab_size, seed=seed)
                m = _candidate_metrics(
                    eng, res.token_ids, wm_ids, ref_ids, emb_wm, emb_ref, threshold
                )
                retained = n - res.n_changed
                add_row("edit", cat, res.n_changed / n if n else 0.0,
                        pid, rep, seed, m, retained)

    df = pd.DataFrame(rows, columns=COLUMNS)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "summary.csv", index=False)
    (out / "summary.json").write_text(
        json.dumps({"threshold": threshold, "key_id": key_id, "n_rows": len(df),
                    "model": cfg["model_name"], "generated_at": ts}, indent=2),
        encoding="utf-8",
    )
    (out / "texts" / "generations.jsonl").write_text(
        "\n".join(json.dumps(t) for t in texts), encoding="utf-8"
    )
    return out / "summary.csv"
