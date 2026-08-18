# Deep Reprocess — architecture & future hooks

Pixel-level image **reprocessing** shipped as a production feature alongside
metadata **cleaning**. This note records the design, the premium/billing hook,
and the future ML-reconstruction backend proposal.

## Clean vs Reprocess (two distinct operations)

| | Clean | Reprocess |
|---|---|---|
| What it does | Removes EXIF/XMP/PNG-text/C2PA metadata | Decodes and re-encodes a **new pixel representation** (optional mild resample) |
| Pixels | Byte-identical | Genuinely re-encoded / reconstructed |
| Guarantees | Supported file-level signals removed & independently verifiable | New pixel encoding + quality metrics; **no** guarantee about statistical watermarks (SynthID) |

Reprocess is **not** a SynthID remover and never claims to be. The UI reports
three separate, never-mixed categories: **file-level** (re-inspected),
**pixel-level** (SSIM/PSNR/pixel-change), **statistical** (not locally
verifiable).

## Pipeline

`ghostmark/reprocess.py` — pure Pillow, no ML deps. `reprocess_image_bytes()`:
decode → mode normalize (alpha-safe) → optional down-then-up LANCZOS resample
(dimensions preserved) → re-encode (PNG lossless / JPEG q / WebP q) → metrics
(`ghostmark/imaging_metrics.py`, NumPy). Profiles:

| profile | resample | colour space | quality | est. compute cost | latency |
|---|---|---|---|---|---|
| Light | none | source ICC preserved | JPEG 95 / WebP 95 / PNG lossless | 1.0 | fast |
| Medium | 0.9× round-trip | normalised to sRGB (ICC resolved, then dropped) | JPEG 90 / WebP 90 | 2.0 | moderate |
| Strong | 0.75× round-trip | normalised to sRGB (ICC resolved, then dropped) | JPEG 85 / WebP 85 | 3.0 | heavy |

The pixel path additionally applies EXIF orientation, normalises image mode
(handling RGB/RGBA/grayscale/palette/CMYK, preserving alpha, flattening
transparency onto white for JPEG), and rejects decompression-bomb-sized
inputs (`MAX_DECODE_PIXELS`) before decoding. `normalize_colorspace` is a
real per-profile behaviour (`ghostmark/reprocess.py::_apply_colorspace`),
not a no-op flag.

Parameters are chosen for **visual quality**, never to defeat a detector, and no
loop optimises against any external "detected/not-detected" signal.

Surfaces: CLI `ghostmark reprocess FILE --profile --format [--report]`; web
`POST /api/reprocess/{session_id}?profile&out_format` + `GET
/api/download/{session_id}?variant=reprocess`. The optional `--report`
(CLI) and the `robustness` block (web response) add an **observational,
read-only** before/after provenance comparison (`ghostmark/robustness.py`):
it never feeds back into reprocessing and makes no claim about statistical
watermarks (e.g. SynthID).

## Future billing hook (not integrated)

`ReprocessProfile.estimated_compute_cost` (credits) and `latency_class` already
travel with every profile and into `ReprocessResult`. A future paid tier can
gate or charge per profile by reading these — the intended seam is a single
`authorize_reprocess(profile, user)` check in the web route **before**
`reprocess_image_bytes()` runs, plus a post-run `record_usage(cost)`. No Stripe
or billing abstraction exists in MarkMyAss today, so nothing is wired; this is
purely the interface so it becomes trivial later.

## Future ML-reconstruction backend (proposal, NOT in the image)

Genuine model-based reconstruction (diffusion img2img, super-resolution) is
deliberately **excluded** from the production image to keep it lightweight (no
torch/CUDA). If pursued, it belongs in a **separate optional worker service**:

- A `STRONG+`/`RECONSTRUCT` profile dispatches to an out-of-process worker
  (own container, its own heavy deps) via a queue; the web app stays slim.
- Same `ReprocessResult` contract, so the UI/metrics need no change.
- Runs as a distinct deployable with its own scaling/cost envelope; the current
  Docker image never gains ML dependencies.

## Privacy

Reprocess reuses the existing session model: work happens in a per-session temp
dir, outputs are deleted by the same TTL sweep as cleaned files, originals are
never mutated, and no filenames/metadata values/image contents are logged.
