# Inverse SynthID-Text Study — AI-assisted human text (isolated R&D)

The companion to Study 1 (`research/synthid_text_study`). Study 1 started from
**100% watermarked** text and progressively **restored** it toward the
original. This study measures the **inverse**:

```
   genuinely human prose  ->  progressively add SynthID-watermarked AI spans
```

The research question: **at what fraction and geometry of AI-generated content
does a mostly-human document become detectable under our local reference
SynthID setup?**

This is **contamination/detectability characterisation**, not detector-evasion
optimisation. It uses **our own local key** and says **nothing** about Google's
production secret key (which we do not hold; there is no public detector API).

---

## Reuse, not duplication

This package imports Study 1's validated components unchanged — the SynthID-Text
`Engine`, the Weighted-Mean detector, the metrics, and the threshold-calibration
methodology — via a `sys.path` bootstrap in `inverse_study/__init__.py`. Study 1
is not modified. The watermark key and generation parameters are identical to
Study 1 so the two are directly comparable.

## Dataset — genuinely human, public domain

`inverse_study/corpus.py` downloads five Project Gutenberg works (all first
published before 1929, long in the US public domain), strips the Gutenberg
header/footer, keeps qualifying prose paragraphs, and slices 20 fixed-size
samples (4 per work):

| work | author | Gutenberg id |
|---|---|---|
| Pride and Prejudice | Jane Austen | 1342 |
| The Adventures of Sherlock Holmes | Arthur Conan Doyle | 1661 |
| Frankenstein | Mary W. Shelley | 84 |
| Dracula | Bram Stoker | 345 |
| A Tale of Two Cities | Charles Dickens | 98 |

**No LLM-generated text is used as the human baseline.** The derived samples and
`datasets/manifest.json` (source URLs + public-domain statement) are committed;
raw downloads under `datasets/raw/` are gitignored.

## Construction

For each human sample `H` (token ids `h`), a genuine SynthID-watermarked passage
`a` (same length, conditioned on `H`'s opening) and an appended passage `b` are
generated with our key. A condition splices `a` into `h` at chosen positions —
filling from `a` at the **same indices** so a contiguous block keeps its
generation-time context (the watermark survives inside the block; only block
edges sit in human context — the same "blast radius" Study 1 measured).

- **Axis 1 × 2 — fraction × geometry:** AI fraction ∈
  {0, 2, 5, 10, 15, 20, 25, 30, 50, 75, 100}% × geometry ∈
  {contiguous, scattered, sentence, paragraph}.
- **Axis 3 — realistic editing modes:** spelling / grammar / punctuation /
  light copy-edit (small scattered generated micro-spans), sentence rewrite,
  paragraph rewrite, added AI paragraph, AI intro+conclusion.

Per condition we record: actual AI-generated fraction, Weighted-Mean detector
score, detected (score > calibrated threshold), retained-human fraction,
semantic similarity to the original, token edit distance, and length.

## Running

```bash
# reuses Study 1's venv (C:\synthid_venv) and cached model
C:\synthid_venv\Scripts\python -m inverse_study.cli build-corpus --out datasets
C:\synthid_venv\Scripts\python -m inverse_study.cli run    --config configs/default.yaml
C:\synthid_venv\Scripts\python -m inverse_study.cli report --results results

# tests (fast, offline)
C:\synthid_venv\Scripts\python -m pytest tests -q
# opt-in model-backed smoke test
SYNTHID_RUN_MODEL=1 C:\synthid_venv\Scripts\python -m pytest tests/test_inverse_smoke.py -q
```

## Results

See [`results/report.md`](results/report.md): headline answers at 2/5/10/20/30/50%
AI, per-geometry curves, the concentrated-vs-spread comparison, the editing-mode
table, and the Study 1 vs Study 2 symmetry analysis. Limitations (local key,
`distilgpt2` vehicle, tuning-free detector, 20 samples, English) are restated in
the report and apply to every number.
