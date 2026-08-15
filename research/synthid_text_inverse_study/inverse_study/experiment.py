"""Run the inverse study grid: human prose -> progressively AI-contaminated.

Reuses Study 1's Engine, Weighted-Mean detector, metrics, and threshold
calibration (imported via the sys.path bootstrap in __init__). Nothing in
Study 1 is modified.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import time
from typing import Any

import torch
import yaml

# Study 1 (reused, unmodified) -- available via the package bootstrap.
from synthid_study import metrics  # noqa: E402
from synthid_study.experiment import _calibrate_threshold  # noqa: E402
from synthid_study.watermark import Engine, GenParams, WatermarkParams  # noqa: E402

from . import contaminate as C
from .corpus import load_corpus

COLUMNS: list[str] = [
    "experiment_id", "axis", "condition", "nominal_fraction",
    "sample_id", "work_id", "seed", "key_id", "language",
    "n_tokens", "n_chars", "ai_generated_tokens", "ai_generated_fraction",
    "retained_human_fraction", "detector_score", "threshold", "detected",
    "n_scored_positions", "semantic_sim_vs_original", "edit_distance_vs_original",
    "timestamp",
]


def _key_id(keys: list[int]) -> str:
    return hashlib.sha1(",".join(map(str, keys)).encode()).hexdigest()[:8]


@torch.no_grad()
def _gen_watermarked(eng: Engine, prompt: str, n_tokens: int, seed: int) -> list[int]:
    """Generate exactly n_tokens SynthID-watermarked tokens conditioned on prompt."""
    torch.manual_seed(seed)
    enc = eng.tokenizer(prompt, return_tensors="pt").to(eng.device)
    out = eng.model.generate(
        **enc, do_sample=True, temperature=eng.gen.temperature, top_k=eng.gen.top_k,
        top_p=eng.gen.top_p, max_new_tokens=n_tokens, min_new_tokens=n_tokens,
        pad_token_id=eng.tokenizer.pad_token_id, watermarking_config=eng.wm_config,
    )
    return out[0, enc["input_ids"].shape[1]:].tolist()


def _char_to_token(starts: list[int], char_pos: int, n: int) -> int:
    for i, s in enumerate(starts):
        if s >= char_pos:
            return i
    return n


def _unit_spans(text: str, offsets: list[tuple[int, int]], kind: str) -> list[tuple[int, int]]:
    """Sentence or paragraph token-index spans covering [0, n)."""
    n = len(offsets)
    starts = [o[0] for o in offsets]
    if kind == "sentence":
        bounds = [m.end() for m in re.finditer(r"[.!?][\"')\]]?\s", text)]
    else:  # paragraph
        bounds = [m.end() for m in re.finditer(r"\n\s*\n", text)]
    toks = sorted({_char_to_token(starts, b, n) for b in bounds if 0 < b < len(text)})
    toks = [t for t in toks if 0 < t < n]
    edges = [0, *toks, n]
    return [(edges[i], edges[i + 1]) for i in range(len(edges) - 1) if edges[i + 1] > edges[i]]


def run(config_path: str | pathlib.Path, out_dir: str | pathlib.Path) -> pathlib.Path:
    cfg = yaml.safe_load(pathlib.Path(config_path).read_text(encoding="utf-8"))
    base = pathlib.Path.cwd()
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    wcfg, gcfg = cfg["watermark"], cfg["generation"]
    keys = list(wcfg["keys"])
    key_id = _key_id(keys)
    language = cfg.get("language", "en")
    max_ctx = cfg.get("max_human_tokens", 256)

    eng = Engine(
        model_name=cfg["model_name"],
        wm=WatermarkParams(keys=keys, ngram_len=wcfg["ngram_len"],
                           sampling_table_size=wcfg["sampling_table_size"],
                           sampling_table_seed=wcfg["sampling_table_seed"],
                           context_history_size=wcfg["context_history_size"]),
        gen=GenParams(max_new_tokens=gcfg["max_new_tokens"], temperature=gcfg["temperature"],
                      top_k=gcfg["top_k"], top_p=gcfg["top_p"]),
        cache_dir=str(base / cfg.get("hf_cache_dir", ".hf_cache")),
    )

    samples = load_corpus(base / cfg["corpus_dir"])
    if cfg.get("n_samples"):
        samples = samples[: cfg["n_samples"]]

    dcfg = cfg["detector"]
    prompts = [s["text"][:120] for s in samples]
    threshold = _calibrate_threshold(
        eng, prompts, dcfg["n_calibration_samples"], dcfg["target_false_positive_rate"]
    )

    rows: list[dict[str, Any]] = []
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    fractions = cfg["fractions"]
    geometries = cfg["geometries"]
    exp_id = 0

    def metric_row(axis: str, cond: str, nominal: float, s: dict, seed: int,
                   cont: C.Contaminated, h_ids: list[int], emb_h: list[float]) -> None:
        nonlocal exp_id
        ids = cont.token_ids
        score, n_scored = eng.weighted_mean_score(ids)
        emb = eng.embed(ids)
        rows.append({
            "experiment_id": exp_id, "axis": axis, "condition": cond,
            "nominal_fraction": nominal, "sample_id": s["sample_id"],
            "work_id": s["work_id"], "seed": seed, "key_id": key_id, "language": language,
            "n_tokens": len(ids), "n_chars": len(eng.decode(ids)),
            "ai_generated_tokens": cont.n_ai, "ai_generated_fraction": cont.ai_fraction,
            "retained_human_fraction": 1.0 - cont.ai_fraction,
            "detector_score": score, "threshold": threshold,
            "detected": bool(score == score and score > threshold),
            "n_scored_positions": n_scored,
            "semantic_sim_vs_original": metrics.cosine(emb, emb_h),
            "edit_distance_vs_original": metrics.token_edit_distance(ids, h_ids),
            "timestamp": ts,
        })
        exp_id += 1

    for pid, s in enumerate(samples):
        enc = eng.tokenizer(s["text"], return_offsets_mapping=True)
        h_ids = enc["input_ids"][:max_ctx]
        offsets = enc["offset_mapping"][:max_ctx]
        n = len(h_ids)
        seed = gcfg["seed"] + 1000 * pid
        emb_h = eng.embed(h_ids)

        a_ids = _gen_watermarked(eng, eng.decode(h_ids[:12]), n, seed)
        b_ids = _gen_watermarked(eng, eng.decode(h_ids[-60:]), 64, seed + 7)
        sent_spans = _unit_spans(s["text"], offsets, "sentence")
        para_spans = _unit_spans(s["text"], offsets, "paragraph")

        # baseline: pure human text
        metric_row("baseline", "human", 0.0, s, seed,
                   C.Contaminated(list(h_ids), [False] * n), h_ids, emb_h)

        # Axis 1 x 2: fraction x geometry
        for geom in geometries:
            spans = sent_spans if geom == "sentence" else para_spans if geom == "paragraph" else None
            for frac in fractions:
                if frac == 0.0:
                    continue
                cont = C.contaminate(h_ids, a_ids, frac, geom, unit_spans=spans,
                                     k_scatter=cfg.get("k_scatter", 5))
                metric_row("fraction_geometry", geom, frac, s, seed, cont, h_ids, emb_h)

        # Axis 3: realistic editing modes (genuine generated spans)
        mid_sent = sent_spans[len(sent_spans) // 2] if sent_spans else (0, min(12, n))
        mid_para = para_spans[len(para_spans) // 2] if para_spans else (0, n)
        modes = [
            ("spelling", C.contaminate(h_ids, a_ids, 0.02, "scattered", k_scatter=8)),
            ("grammar", C.contaminate(h_ids, a_ids, 0.04, "scattered", k_scatter=6)),
            ("punctuation", C.contaminate(h_ids, a_ids, 0.02, "scattered", k_scatter=8)),
            ("light_copyedit", C.contaminate(h_ids, a_ids, 0.08, "scattered", k_scatter=6)),
            ("sentence_rewrite", C._fill(h_ids, a_ids, set(range(*mid_sent)))),
            ("paragraph_rewrite", C._fill(h_ids, a_ids, set(range(*mid_para)))),
            ("added_paragraph", C.append_ai(h_ids, b_ids, 50)),
            ("ai_intro_conclusion", C.wrap_ai(h_ids, a_ids, b_ids, 30, 30)),
        ]
        for name, cont in modes:
            metric_row("edit_mode", name, cont.ai_fraction, s, seed, cont, h_ids, emb_h)

    import pandas as pd
    df = pd.DataFrame(rows, columns=COLUMNS)
    df.to_csv(out / "summary.csv", index=False)
    (out / "summary.json").write_text(json.dumps({
        "threshold": threshold, "key_id": key_id, "n_rows": len(df),
        "model": cfg["model_name"], "n_samples": len(samples), "generated_at": ts,
    }, indent=2), encoding="utf-8")
    return out / "summary.csv"
