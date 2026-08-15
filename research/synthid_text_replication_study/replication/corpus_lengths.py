"""Build length-bucketed human public-domain samples (~250/500/900 tokens).

Reuses Study 2's Gutenberg download/clean/paragraph helpers, then accumulates
consecutive qualifying paragraphs until a target *token* length (measured with
the model tokenizer) is reached, and trims to that length at a sentence
boundary. No LLM text is used as the human baseline.
"""

from __future__ import annotations

import json
import pathlib

from inverse_study import corpus as base

# Two distinct works per bucket (rotated) so samples are not all one author.
BUCKET_WORKS = {
    250: [(1342, 30), (1661, 30)],   # (gutenberg id, skip_front)
    500: [(84, 30), (345, 30)],
    900: [(98, 30), (1342, 120)],
}


def _sentence_trim_tokens(tok, ids: list[int], target: int) -> list[int]:
    if len(ids) <= target:
        return ids
    text = tok.decode(ids[:target])
    # cut back to the last sentence terminator for a clean sample
    for end in (". ", "! ", "? "):
        p = text.rfind(end)
        if p > len(text) * 0.5:
            text = text[: p + 1]
            break
    return tok(text)["input_ids"]


def build_length_corpus(out_dir: pathlib.Path, tokenizer, samples_per_bucket: int = 2) -> pathlib.Path:
    out_dir = pathlib.Path(out_dir)
    samples_dir = out_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"

    manifest: list[dict] = []
    for target, works in BUCKET_WORKS.items():
        for idx in range(samples_per_bucket):
            work_id, skip = works[idx % len(works)]
            meta = next(w for w in base.WORKS if w["id"] == work_id)
            body = base._strip_gutenberg(base._download(work_id, raw_dir))
            paras = base._paragraphs(body)[skip:]
            acc: list[str] = []
            ids: list[int] = []
            for p in paras:
                acc.append(p)
                ids = tokenizer("\n\n".join(acc))["input_ids"]
                if len(ids) >= target:
                    break
            ids = _sentence_trim_tokens(tokenizer, ids, target)
            text = tokenizer.decode(ids)
            sid = f"{target}_{idx}"
            (samples_dir / f"{sid}.txt").write_text(text, encoding="utf-8")
            manifest.append({
                "sample_id": sid, "length_bucket": target, "work_id": work_id,
                "title": meta["title"], "author": meta["author"], "year": meta["year"],
                "source_url": base.URL_TMPL.format(id=work_id),
                "license": "Public domain (Project Gutenberg; first published pre-1929)",
                "n_tokens": len(ids),
            })
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out_dir / "manifest.json"


def load_length_corpus(out_dir: pathlib.Path) -> list[dict]:
    out_dir = pathlib.Path(out_dir)
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    for m in manifest:
        m["text"] = (out_dir / "samples" / f"{m['sample_id']}.txt").read_text(encoding="utf-8")
    return manifest
