"""Canonical result-row schema shared by experiment.py and report.py."""

from __future__ import annotations

COLUMNS: list[str] = [
    "experiment_id",
    "axis",  # "baseline" | "mixture" | "edit"
    "condition",  # geometry name, edit category, or "reference"/"watermarked"
    "param_value",  # retained_fraction (mixture) or changed_fraction (edit)
    "prompt_id",
    "replicate",
    "seed",
    "key_id",
    "language",
    "n_tokens",
    "n_chars",
    # detection
    "detector_score",
    "threshold",
    "detected",
    "n_scored_positions",
    # watermark retention
    "watermarked_tokens_retained",
    "watermarked_fraction_retained",
    # similarity to original human tokens / to watermarked tokens
    "token_overlap_original",
    "edit_distance_vs_watermarked",
    "edit_distance_vs_original",
    "semantic_sim_vs_watermarked",
    "semantic_sim_vs_original",
    "timestamp",
]
