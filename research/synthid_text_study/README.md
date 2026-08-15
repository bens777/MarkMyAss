# SynthID-Text Behaviour Study (isolated R&D)

Characterise **how the SynthID-Text watermark statistic behaves when
watermarked (AI-generated) tokens are progressively replaced by
un-watermarked ("human original") tokens**, and under a range of realistic
edit categories.

This is **feasibility research only**. It is not a product, not a "remover",
and not wired into anything.

---

## What this is — and is not

**Is:** a reproducible local experiment that measures the relationship

```
   proportion of watermarked (AI-generated) tokens  ->  detector score
```

using the **official DeepMind SynthID-Text implementation** shipped in
Hugging Face `transformers` (`SynthIDTextWatermarkingConfig` +
`SynthIDTextWatermarkLogitsProcessor` / g-value computation), driven with
**our own local watermark keys**.

**Is NOT:**

- It does **not** use, query, or approximate **Google's production watermark
  key**. Google holds that key; there is no public detector API. Every number
  here is produced with *our own* key on *our own* generations, and says
  **nothing** about whether text would trip Google's production detector.
- It does **not** optimise anything against a detector. The detector is only a
  *measurement instrument*. There is no transform here tuned to suppress a
  watermark, and none will be added.
- It is **fully isolated** from MarkMyAss production (`src/ghostmark`): its own
  directory, its own venv, its own dependencies (torch/transformers, which
  production never uses). Nothing here touches the cleaner, API, CLI, Docker
  image, billing, or deployment.

### Why this is legitimate research

SynthID-Text watermarks *generated tokens* by biasing the model's sampling at
generation time. The detectable signal lives only in tokens the watermarked
model actually produced. So the question "what happens to the signal when a
human's original wording is restored?" is a question about a **mechanism**,
answered honestly by measuring it. The finding we expect — and want to
quantify — is that restoring the human's own tokens removes the signal
*because the text becomes the human's text*, not because of any attack.

---

## Method

Two independent axes, both scored with the same detector and our own key.

### Axis 1 — Mixture / retention curve (the core quantitative result)

For each prompt we generate a **watermarked** continuation `W` and an
**un-watermarked** continuation `H` (same model, watermark off) of equal
length — `H` stands in for "human original" tokens. We then build mixtures that
retain a chosen fraction of `W`'s tokens and take the rest from `H`, at
retained fractions `{1.0, 0.9, 0.75, 0.5, 0.25, 0.1, 0.0}`.

Because each SynthID g-value depends on a sliding window of *preceding* tokens,
a replaced token disturbs not only its own scored position but nearby ones (a
**blast radius**). We therefore test three replacement geometries —
`keep_prefix`, `keep_suffix`, `scattered` — to expose that effect.

### Axis 2 — Edit-category degradation

Starting from `W`, we apply token-level perturbations that model realistic edit
categories (`spelling`, `grammar`, `punctuation`, `light_copyedit`,
`word_substitution`, `sentence_rewrite`, `paragraph_rewrite`, `restoration`)
and re-score.

> **Modelling honesty:** the SynthID statistic does not depend on the
> *linguistic* nature of an edit — only on how many scored positions change and
> how the context window is disturbed. So each category is a perturbation
> profile `(density, locality, replacement source)`, not a real linguistic
> edit. Category labels are shorthand; read `configs/` and `edits.py` for the
> exact profiles. `restoration` is the special case: full revert to `H`.

### Detector / scoring method

The tuning-free **Weighted-Mean** detector: compute official SynthID g-values
for the scored positions of a token sequence under our key(s), take their mean.
Un-watermarked text sits near the null mean; watermarked text is elevated. The
**decision threshold** is *calibrated from un-watermarked control samples* to a
target false-positive rate (default 1%), not hard-coded. `detected = score >
threshold`.

### Metrics recorded per condition

detector score · detected (bool) · threshold · scored positions · watermarked
tokens retained (count & %) · token overlap with original (LCS-based) · token
edit distance (vs `W` and vs `H`) · semantic similarity (mean-pooled model
embedding cosine, vs `W` and vs `H`) · token & char length · language.

---

## Layout

```
synthid_study/
  metrics.py     pure-python token/text metrics (no ML deps)
  mixtures.py    watermarked/original token splicing (Axis 1)
  edits.py       edit-category perturbations (Axis 2)
  watermark.py   official SynthID-Text generation + Weighted-Mean detector
  experiment.py  runs the full grid -> result rows
  report.py      aggregate CSV/JSON -> report.md + charts
  cli.py         entry point
configs/default.yaml
datasets/prompts.txt
tests/           metrics/mixtures/edits unit tests (run without the ML stack)
results/         summary.csv, summary.json, report.md, *.png (committed)
                 raw/ and texts/ (gitignored)
```

## Running it

```bash
# 1. Isolated venv at a SHORT path (Windows MAX_PATH; see requirements.txt)
py -3.12 -m venv C:\synthid_venv
C:\synthid_venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
C:\synthid_venv\Scripts\python -m pip install -r requirements.txt

# 2. Unit tests (no model download needed)
C:\synthid_venv\Scripts\python -m pytest research/synthid_text_study/tests -q

# 3. Full study (downloads distilgpt2 ~350 MB on first run; CPU-only, free)
C:\synthid_venv\Scripts\python -m synthid_study.cli run --config configs/default.yaml
C:\synthid_venv\Scripts\python -m synthid_study.cli report
```

Everything is CPU-only and uses no paid API. First run downloads a small
open model into `.hf_cache/` (gitignored).

## Results & limitations

See [`results/report.md`](results/report.md) once generated. Key standing
limitations (also restated in the report): distilgpt2 is a *vehicle* for the
watermark mechanism, not Gemini; the Weighted-Mean detector is the tuning-free
detector, not the trained Bayesian one; English-only; our key ≠ Google's key.
