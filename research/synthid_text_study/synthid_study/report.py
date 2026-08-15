"""Aggregate study results (summary.csv) into report.md + charts.

Pure post-processing: reads the CSV produced by experiment.py, writes tables,
a headline "where detection degrades" finding, and PNG charts. Uses pandas +
matplotlib (Agg backend, no display required).
"""

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


def _fmt(x: float, nd: int = 3) -> str:
    return f"{x:.{nd}f}"


def _degradation_point(curve: pd.DataFrame) -> float | None:
    """Largest retained_fraction at which detection rate first falls below 0.5.

    `curve` has columns retained_fraction (desc) and detection_rate. Returns the
    retained fraction where the watermark stops being reliably detectable, or
    None if it is detected across the whole range.
    """
    ordered = curve.sort_values("param_value", ascending=False)
    below = ordered[ordered["detection_rate"] < 0.5]
    if below.empty:
        return None
    return float(below.iloc[0]["param_value"])


def build_report(results_dir: pathlib.Path) -> pathlib.Path:
    csv_path = results_dir / "summary.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"missing {csv_path}; run the study first")
    df = pd.read_csv(csv_path)

    lines: list[str] = []
    lines.append("# SynthID-Text Behaviour Study — Results\n")
    lines.append(
        "> Produced with **our own local watermark key** on a small open model "
        "(`distilgpt2`). These numbers characterise the SynthID-Text *mechanism* "
        "and say **nothing** about Google's production detector, whose key we do "
        "not hold.\n"
    )

    meta = df.iloc[0]
    lines.append("## Run configuration\n")
    lines.append(f"- rows: **{len(df)}**")
    lines.append(f"- language: {meta['language']}")
    lines.append(f"- decision threshold (calibrated): {_fmt(float(meta['threshold']))}")
    lines.append(
        f"- prompts × replicates: "
        f"{df['prompt_id'].nunique()} × {df['replicate'].nunique()}\n"
    )

    # ---- Baselines ----
    base = df[df["axis"] == "baseline"]
    if not base.empty:
        lines.append("## Baselines\n")
        lines.append("| condition | mean score | detected rate | n |")
        lines.append("|---|---|---|---|")
        for cond, g in base.groupby("condition"):
            lines.append(
                f"| {cond} | {_fmt(g['detector_score'].mean())} "
                f"| {_fmt(g['detected'].mean())} | {len(g)} |"
            )
        lines.append("")

    # ---- Axis 1: mixture retention curves ----
    mix = df[df["axis"] == "mixture"].copy()
    headline = None
    if not mix.empty:
        lines.append("## Axis 1 — Watermarked-token retention vs detection\n")
        agg = (
            mix.groupby(["condition", "param_value"])
            .agg(
                mean_score=("detector_score", "mean"),
                detection_rate=("detected", "mean"),
                sem_sim_original=("semantic_sim_vs_original", "mean"),
                n=("detector_score", "size"),
            )
            .reset_index()
        )

        for geom, g in agg.groupby("condition"):
            lines.append(f"### geometry: `{geom}`\n")
            lines.append(
                "| retained watermarked frac | mean score | detection rate "
                "| mean sem-sim vs original | n |"
            )
            lines.append("|---|---|---|---|---|")
            for _, r in g.sort_values("param_value", ascending=False).iterrows():
                lines.append(
                    f"| {_fmt(r['param_value'], 2)} | {_fmt(r['mean_score'])} "
                    f"| {_fmt(r['detection_rate'])} | {_fmt(r['sem_sim_original'])} "
                    f"| {int(r['n'])} |"
                )
            dp = _degradation_point(g)
            if dp is not None:
                lines.append(
                    f"\n**Detection degrades** (rate < 0.5) at retained "
                    f"watermarked fraction ≈ **{_fmt(dp, 2)}** for `{geom}`.\n"
                )
                if headline is None or dp > headline[1]:
                    headline = (geom, dp)
            else:
                lines.append("\nDetected across the full retained range.\n")

        _plot_mixture(agg, results_dir / "mixture_curves.png")
        lines.append("![Mixture retention curves](mixture_curves.png)\n")

    # ---- Axis 2: edit categories ----
    ed = df[df["axis"] == "edit"].copy()
    if not ed.empty:
        lines.append("## Axis 2 — Detection by edit category\n")
        agg2 = (
            ed.groupby("condition")
            .agg(
                mean_changed=("param_value", "mean"),
                mean_score=("detector_score", "mean"),
                detection_rate=("detected", "mean"),
                sem_sim_original=("semantic_sim_vs_original", "mean"),
                n=("detector_score", "size"),
            )
            .reset_index()
            .sort_values("mean_changed")
        )
        lines.append(
            "| edit category | mean tokens changed frac | mean score "
            "| detection rate | mean sem-sim vs original | n |"
        )
        lines.append("|---|---|---|---|---|---|")
        for _, r in agg2.iterrows():
            lines.append(
                f"| {r['condition']} | {_fmt(r['mean_changed'])} "
                f"| {_fmt(r['mean_score'])} | {_fmt(r['detection_rate'])} "
                f"| {_fmt(r['sem_sim_original'])} | {int(r['n'])} |"
            )
        lines.append("")
        _plot_edits(agg2, results_dir / "edit_categories.png")
        lines.append("![Edit-category detection](edit_categories.png)\n")

    # ---- Headline ----
    if headline is not None:
        lines.insert(
            2,
            f"\n**Headline (local implementation):** under the tuning-free "
            f"Weighted-Mean detector, watermark detection becomes unreliable "
            f"(<50%) once the retained watermarked-token fraction drops to about "
            f"**{_fmt(headline[1], 2)}** (worst-case geometry `{headline[0]}`).\n",
        )

    lines.append("## Limitations\n")
    lines.append(
        "- `distilgpt2` is a *vehicle* for the watermark mechanism, not Gemini; "
        "absolute scores are implementation-specific.\n"
        "- Weighted-Mean (tuning-free) detector, not the trained Bayesian one.\n"
        "- Our own local key; **not** Google's production key.\n"
        "- Edit categories are perturbation *profiles*, not real linguistic edits "
        "(see README / edits.py).\n"
        "- English-only; single small model; modest prompt count.\n"
    )

    out = results_dir / "report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _plot_mixture(agg: pd.DataFrame, path: pathlib.Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    for geom, g in agg.groupby("condition"):
        g = g.sort_values("param_value")
        ax1.plot(g["param_value"], g["mean_score"], marker="o", label=geom)
        ax2.plot(g["param_value"], g["detection_rate"], marker="o", label=geom)
    ax1.set_xlabel("retained watermarked-token fraction")
    ax1.set_ylabel("mean detector score")
    ax1.set_title("Watermark score vs retention")
    ax1.legend()
    ax2.set_xlabel("retained watermarked-token fraction")
    ax2.set_ylabel("detection rate")
    ax2.set_title("Detection rate vs retention")
    ax2.set_ylim(-0.05, 1.05)
    ax2.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_edits(agg2: pd.DataFrame, path: pathlib.Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(agg2["condition"], agg2["detection_rate"], color="#4C72B0")
    ax.set_ylabel("detection rate")
    ax.set_title("Detection rate by edit category")
    ax.set_ylim(0, 1.05)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
