"""Summarise benchmark results into report.md.

With real Vertex data this shows verifier-confidence transitions (e.g. HIGH ->
LOW) per transform. In mock/unavailable mode it summarises transform quality
metrics and the verifier status counts (never fabricated detections).
"""

from __future__ import annotations

import json
import pathlib

import pandas as pd


def _f(x, nd=3):
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def build_report(results_dir: pathlib.Path) -> pathlib.Path:
    results_dir = pathlib.Path(results_dir)
    df = pd.read_csv(results_dir / "summary.csv")
    meta = json.loads((results_dir / "summary.json").read_text(encoding="utf-8"))

    L: list[str] = ["# Google SynthID Image Benchmark — Results\n"]
    L.append(f"- detector: **{meta['detector_provider']} / {meta['detector']}**")
    L.append(f"- sources: **{meta['n_sources']}** | rows: **{meta['n_rows']}** | "
             f"price/call: ${meta['price_per_call_usd']} | "
             f"estimated total: **${meta['estimated_total_cost_usd']}**\n")

    statuses = sorted(set(df["verifier_after_status"].dropna()))
    if set(statuses) <= {"MOCK", "DETECTOR_UNAVAILABLE"}:
        L.append("> Verifier is offline (mock / unavailable). Detection columns are placeholders; "
                 "only transform quality metrics below are meaningful until the real Vertex "
                 "verifier is run.\n")

    tf = df[df["transform"] != "__baseline__"].copy()
    agg = (tf.groupby("transform")
           .agg(ssim=("ssim", "mean"), psnr=("psnr", "mean"),
                width=("width", "mean"), size=("file_size_bytes", "mean"),
                runtime=("runtime_ms", "mean"), n=("ssim", "size"))
           .reset_index().sort_values("ssim"))

    L.append("## Transform quality (mean over sources)\n")
    L.append("| transform | SSIM | PSNR | mean width | mean size (B) | runtime (ms) | n |")
    L.append("|---|---|---|---|---|---|---|")
    for _, r in agg.iterrows():
        L.append(f"| {r['transform']} | {_f(r['ssim'])} | {_f(r['psnr'],2)} "
                 f"| {int(r['width'])} | {int(r['size'])} | {_f(r['runtime'],1)} | {int(r['n'])} |")
    L.append("")

    L.append("## Verifier status counts (after transform)\n")
    L.append("| status | count |")
    L.append("|---|---|")
    for st, c in df["verifier_after_status"].value_counts().items():
        L.append(f"| {st} | {int(c)} |")
    L.append("")

    # If a real verifier produced confidence labels, show transitions.
    real = df[~df["verifier_after_status"].isin(["MOCK", "DETECTOR_UNAVAILABLE"])]
    if not real.empty and real["verifier_after_confidence"].notna().any():
        L.append("## Verifier confidence after transform (real detector)\n")
        piv = (real[real["transform"] != "__baseline__"]
               .groupby(["transform", "verifier_after_confidence"]).size().reset_index(name="n"))
        L.append("| transform | confidence | n |")
        L.append("|---|---|---|")
        for _, r in piv.iterrows():
            L.append(f"| {r['transform']} | {r['verifier_after_confidence']} | {int(r['n'])} |")
        L.append("")

    L.append("## Notes\n")
    L.append("- SSIM/PSNR for geometry-changing transforms (resize/crop) are computed after "
             "resizing back to the source dimensions — approximate perceptual similarity.\n"
             "- `estimated_api_cost_usd` is per-row `price_per_call × calls`; 0 under the mock.\n")

    out = results_dir / "report.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out
