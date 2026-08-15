"""Build/load a reproducible corpus of genuinely human, public-domain prose.

Source: Project Gutenberg plain-text editions of works long in the US public
domain (all first published before 1929). We download each work once, strip the
Gutenberg header/footer, keep qualifying prose paragraphs, skip front matter,
and slice fixed-size consecutive-paragraph samples. The derived samples and a
manifest are committed; raw downloads are cached and gitignored.

IMPORTANT: the "human original" is real human writing. No LLM text is used as
the human baseline.
"""

from __future__ import annotations

import json
import pathlib
import re
import urllib.request

# Pinned public-domain works (Gutenberg ebook id -> metadata). Pre-1929.
WORKS: list[dict] = [
    {"id": 1342, "title": "Pride and Prejudice", "author": "Jane Austen", "year": 1813},
    {"id": 1661, "title": "The Adventures of Sherlock Holmes", "author": "Arthur Conan Doyle",
     "year": 1892},
    {"id": 84, "title": "Frankenstein", "author": "Mary Wollstonecraft Shelley", "year": 1818},
    {"id": 345, "title": "Dracula", "author": "Bram Stoker", "year": 1897},
    {"id": 98, "title": "A Tale of Two Cities", "author": "Charles Dickens", "year": 1859},
]

URL_TMPL = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"

_SKIP_MARKERS = ("gutenberg", "illustration", "chapter", "contents", "http",
                 "produced by", "transcriber")


def _download(work_id: int, raw_dir: pathlib.Path) -> str:
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache = raw_dir / f"pg{work_id}.txt"
    # Binary I/O + explicit normalisation: text-mode write/read on Windows
    # translates newlines and corrupts paragraph structure on round-trip.
    if cache.exists():
        data = cache.read_bytes().decode("utf-8", "replace")
    else:
        req = urllib.request.Request(URL_TMPL.format(id=work_id),
                                     headers={"User-Agent": "Mozilla/5.0 research"})
        data = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
        cache.write_bytes(data.encode("utf-8"))
    return data.replace("\r\n", "\n").replace("\r", "\n")


def _strip_gutenberg(text: str) -> str:
    start = text.find("*** START OF")
    start = text.find("\n", start) + 1 if start != -1 else 0
    end = text.find("*** END OF")
    if end == -1:
        end = len(text)
    return text[start:end]


def _paragraphs(body: str) -> list[str]:
    raw = re.split(r"\n\s*\n", body)
    out: list[str] = []
    for p in raw:
        para = re.sub(r"\s+", " ", p).strip()
        low = para.lower()
        words = para.split()
        if len(words) < 45:
            continue
        letters = sum(c.isalpha() for c in para)
        nonspace = sum(not c.isspace() for c in para) or 1
        if letters / nonspace < 0.75:
            continue
        if any(m in low for m in _SKIP_MARKERS):
            continue
        upper_words = sum(1 for w in words if w.isupper())
        if upper_words / len(words) > 0.4:
            continue
        out.append(para)
    return out


def _trim_to_sentence(text: str, max_words: int) -> str:
    """Trim to at most max_words, ending at the last sentence boundary if possible."""
    words = text.split()
    if len(words) <= max_words:
        return text
    clipped = " ".join(words[:max_words])
    m = list(re.finditer(r"[.!?][\"')\]]?\s", clipped))
    if m and m[-1].end() > len(clipped) * 0.5:
        return clipped[: m[-1].end()].strip()
    return clipped.strip()


def build_corpus(
    out_dir: pathlib.Path,
    samples_per_work: int = 4,
    target_words: int = 180,
    max_words: int = 230,
    skip_front: int = 25,
) -> pathlib.Path:
    """Download works, slice samples, write samples/ + manifest.json. Returns manifest path."""
    out_dir = pathlib.Path(out_dir)
    samples_dir = out_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"

    manifest: list[dict] = []
    for work in WORKS:
        body = _strip_gutenberg(_download(work["id"], raw_dir))
        paras = _paragraphs(body)[skip_front:]
        if not paras:
            continue
        # Evenly-spaced start indices; each sample = consecutive paragraphs
        # accumulated to >= target_words.
        span = max(1, len(paras) // samples_per_work)
        made = 0
        for s in range(samples_per_work):
            start = min(s * span, len(paras) - 1)
            acc: list[str] = []
            wc = 0
            i = start
            while i < len(paras) and wc < target_words:
                acc.append(paras[i])
                wc += len(paras[i].split())
                i += 1
            if wc < target_words * 0.6:
                continue
            text = _trim_to_sentence("\n\n".join(acc), max_words)
            sid = f"{work['id']}_{s}"
            (samples_dir / f"{sid}.txt").write_text(text, encoding="utf-8")
            manifest.append({
                "sample_id": sid,
                "work_id": work["id"],
                "title": work["title"],
                "author": work["author"],
                "year": work["year"],
                "source_url": URL_TMPL.format(id=work["id"]),
                "license": "Public domain (Project Gutenberg; first published pre-1929)",
                "n_words": len(text.split()),
                "n_paragraphs": len(acc),
            })
            made += 1
        if made == 0:
            continue
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def load_corpus(out_dir: pathlib.Path) -> list[dict]:
    out_dir = pathlib.Path(out_dir)
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    samples = []
    for m in manifest:
        text = (out_dir / "samples" / f"{m['sample_id']}.txt").read_text(encoding="utf-8")
        samples.append({**m, "text": text})
    return samples
