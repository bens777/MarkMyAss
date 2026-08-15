# Google SynthID Image Benchmark Harness (isolated R&D)

Characterises how Google's **real production** image watermark behaves under
common transformations, measured by Google's **own** verifier (Vertex AI Imagen
watermark verification). See `docs/google-synthid-research.md` for the sourced
background. **Characterisation only — not a remover/evasion tool.**

Isolated from MarkMyAss production: own directory, own deps, nothing wired in.

## Safety contract

- **The verifier never fabricates a detection.** The real Vertex adapter returns
  `DETECTOR_UNAVAILABLE` whenever the SDK, credentials, or config are missing, or
  when paid calls are not explicitly enabled.
- **No paid API call** happens unless the `pilot` command is run with
  `--enable-paid` **and** live credentials are present. Everything else is free.
- A clearly-labelled **MOCK** detector exists only so the pipeline/tests run
  offline; its results are stamped `mock` and are never real detections.

## Layout

```
synthid_image/
  detector.py    DetectorAdapter + VertexImagenDetector (real, gated) + MockVertexDetector
  transforms.py  screenshot loops, JPEG sweep, resize, crop, format conversions, brightness/contrast
  metrics.py     SSIM + PSNR (numpy only)
  schema.py      experiment row columns
  experiment.py  verify baseline -> transform -> re-verify -> record
  report.py      summary.csv -> report.md
  sample.py      deterministic synthetic images for offline demo/tests
  cli.py         demo | run (mock) | pilot (real, gated) | report
configs/default.yaml
datasets/sources, datasets/pilot_sources   # real images, gitignored
results/                                    # summary/report committed; transformed/ gitignored
tests/
```

## Commands

```bash
# offline, free
python -m synthid_image.cli demo                       # transform quality on a synthetic image
python -m synthid_image.cli run --results results/mock # full pipeline with the MOCK verifier
python -m synthid_image.cli report --results results/mock

# real pilot -- PAID, gated (see below). Does nothing costly without the flags + credentials.
python -m synthid_image.cli pilot --config configs/default.yaml \
    --project MY_GCP_PROJECT --sources datasets/pilot_sources --enable-paid
```

## Running the first real pilot (later)

1. Provision **GCP + Vertex AI** (billing enabled) and authenticate
   (`gcloud auth application-default login`); install `google-cloud-aiplatform`.
2. Generate ~10 genuine images with **Imagen on Vertex** (watermark on by
   default) and drop them in `datasets/pilot_sources/`.
3. Set the real `detector.vertex.price_per_call_usd` in the config.
4. Finalise `VertexImagenDetector._verify_live` against the live watermark
   verification API (endpoint + response schema).
5. Run the `pilot` command above. It is **hard-capped at 10 images** and prints a
   cost projection first.

Until step 4 is done the pilot records `DETECTOR_UNAVAILABLE` rows — safe by
construction, no paid calls, no fabricated results.

## Row schema

`source_image_id, provider, model, transform, parameters, iteration_count,
verifier_before_*, verifier_after_*, verifier_raw_*, ssim, psnr, width, height,
file_size_bytes, runtime_ms, estimated_api_cost_usd, timestamp`.

SSIM/PSNR for geometry-changing transforms (resize/crop) are computed after
resizing back to source dimensions — approximate perceptual similarity.
