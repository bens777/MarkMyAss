# SynthID-Text Detection Transition — Replication / Robustness (isolated R&D)

Study 2 found that a mostly-human document becomes commonly detectable once
roughly **20–30%** of its tokens are AI-generated (contiguous). This study asks
whether that transition is **robust** or an artifact of one key, one seed, one
model run, or one document length.

It reuses Studies 1–2 unchanged and **does not touch the detector methodology**
(tuning-free Weighted-Mean, per-key 1% FPR threshold) — deliberately not tuned
to improve the result. Uses **our own local keys**; says nothing about Google's
production secret key.

## Design (reduced factorial)

A full factorial would be many CPU-hours and partly impossible (`distilgpt2`'s
1024-token context rules out a 2000-token bucket). The reduced factorial keeps
statistical power where the questions live:

| factor | levels |
|---|---|
| independent local keys | 5 (key 0 = Study 1/2 anchor) |
| generation seeds / (sample, key) | 5 |
| document length | 250, 500, 900 tokens |
| human samples / length | 2 (public-domain prose) |
| AI fraction | 0/5/10/15/20/25/30/40/50 % |
| geometry | contiguous, scattered (no degenerate paragraph) |

Each watermarked passage is generated **once** per (sample, key, seed, length)
and reused across all fractions/geometries. **Trials per (length, fraction,
geometry) cell = 2×5×5 = 50**, giving usable binomial (Wilson) confidence
intervals, plus per-key / per-length / per-seed decompositions.

To keep runtime tractable the replication records **detection only** (score +
detected); it drops the edit-distance/embedding metrics, which do not bear on the
robustness questions.

## Running

```bash
# reuses Study 1's venv (C:\synthid_venv) and cached model
C:\synthid_venv\Scripts\python -m replication.cli build-corpus --out datasets --config configs/default.yaml
C:\synthid_venv\Scripts\python -m replication.cli run    --config configs/default.yaml
C:\synthid_venv\Scripts\python -m replication.cli report --results results

C:\synthid_venv\Scripts\python -m pytest tests -q                              # fast
SYNTHID_RUN_MODEL=1 C:\synthid_venv\Scripts\python -m pytest tests/test_replication_smoke.py -q
```

## Results

See [`results/report.md`](results/report.md): pooled transition with 95% CIs,
detection crossings at 25/50/75/90%, and the spread of the 50% crossing across
keys, lengths, and seeds — with direct answers to the seven robustness
questions. Limitations (local key, `distilgpt2` vehicle / 1024-token context,
tuning-free detector, 2 samples/bucket) apply to every number.
