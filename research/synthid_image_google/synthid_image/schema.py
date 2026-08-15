"""Experiment row schema for the Google SynthID image benchmark."""

from __future__ import annotations

COLUMNS: list[str] = [
    "experiment_id",
    "source_image_id",
    "provider",            # source image provider (imagen / gemini / synthetic-mock)
    "model",               # source model/version
    "transform",           # transform name ("__baseline__" for the untouched check)
    "parameters",          # JSON string of transform params
    "iteration_count",
    "verifier_before_status",
    "verifier_before_detected",
    "verifier_before_confidence",
    "verifier_after_status",
    "verifier_after_detected",
    "verifier_after_confidence",
    "verifier_raw_before",   # JSON
    "verifier_raw_after",    # JSON
    "ssim",
    "psnr",
    "width",
    "height",
    "file_size_bytes",
    "runtime_ms",
    "estimated_api_cost_usd",
    "timestamp",
]
