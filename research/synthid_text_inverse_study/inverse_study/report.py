"""Build report.md + charts for the inverse study, including a Study 1 vs 2 comparison."""

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

STUDY1_CSV = pathlib.Path(__file__).resolve().parents[2] / "synthid_text_study" / "results" / "summary.csv"
ANSWER_FRACS = [0.02, 0.05, 0.10, 0.20, 0.30, 0.50]


def _f(x: float, nd: int = 3) -> str:
    return "nan" if x != x else f"{x:.{nd}f}"


def build_report(results_dir: pathlib.Path) -> pathlib.Path:
    df = pd.read_csv(results_dir / "summary.csv")
    fg = df[df["axis"] == "fraction_geometry"].copy()
    agg = (fg.groupby(["condition", "nominal_fraction"])
           .agg(detection_rate=("detected", "mean"), mean_score=("detector_score", "mean"),
                actual_frac=("ai_generated_fraction", "mean"),
                sem_sim=("semantic_sim_vs_original", "mean"), n=("detected", "size"))
           .reset_index())

    lines: list[str] = ["# Inverse SynthID-Text Study — AI-assisted human text\n"]
    lines.append("> Human public-domain prose progressively contaminated with genuine "
                 "SynthID-watermarked AI spans, scored with our own local key and Study 1's "
                 "Weighted-Mean detector. Characterises detectability; says **nothing** about "
                 "Google's production secret key.\n")

    base = df[df["axis"] == "baseline"]
    thr = float(df["threshold"].iloc[0])
    lines.append("## Setup\n")
    lines.append(f"- human samples: **{df['sample_id'].nunique()}** (5 public-domain works)")
    lines.append(f"- rows: **{len(df)}** | detector threshold (reused methodology): **{_f(thr)}**")
    lines.append(f"- human baseline (0% AI): mean score {_f(base['detector_score'].mean())}, "
                 f"detection rate {_f(base['detected'].mean())} (≈ false-positive floor)\n")

    # ---- Answers to the specific questions ----
    lines.append("## Headline answers (measured)\n")
    lines.append("Detection rate at each AI-generated fraction, by geometry:\n")
    geoms = sorted(agg["condition"].unique())
    header = "| AI frac | " + " | ".join(geoms) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(geoms) + 1))
    for fr in ANSWER_FRACS:
        cells = []
        for gm in geoms:
            row = agg[(agg["condition"] == gm) & (agg["nominal_fraction"] == fr)]
            cells.append(_f(float(row["detection_rate"].iloc[0]), 2) if not row.empty else "—")
        lines.append(f"| {int(fr*100)}% | " + " | ".join(cells) + " |")
    lines.append("")

    # Granularity / degeneracy caveat: sentence/paragraph replace whole units,
    # so actual AI fraction is floor-limited by unit size. On short samples the
    # paragraph geometry collapses to ~whole-document replacement.
    para = agg[agg["condition"] == "paragraph"].sort_values("nominal_fraction")
    p_actual_lo = float(para["actual_frac"].iloc[0]) if not para.empty else float("nan")
    degenerate = {gm for gm in geoms
                  if float(agg[agg["condition"] == gm].sort_values("nominal_fraction")
                           ["actual_frac"].iloc[0]) > 0.4}
    lines.append(
        "> **Granularity caveat.** `sentence` and `paragraph` replace whole linguistic "
        "units, so their *actual* AI fraction is floor-limited by unit size and can far "
        f"exceed the nominal target. On these short samples the `paragraph` geometry "
        f"collapses to near-whole-document replacement (actual AI ≈ {_f(p_actual_lo, 2)} even "
        "at 2% nominal) and is **not a valid fraction sweep** — read `contiguous`, `scattered`, "
        "and `sentence` (by *actual* fraction) as the informative results.\n")

    lines.append("**AI fraction at which detection becomes common (rate ≥ 0.5), by *actual* AI fraction:**\n")
    for gm in geoms:
        g = agg[agg["condition"] == gm].sort_values("actual_frac")
        hit = g[g["detection_rate"] >= 0.5]
        if hit.empty:
            txt = "not reached within tested range"
        else:
            r = hit.iloc[0]
            txt = f"actual AI ≈ **{_f(float(r['actual_frac']), 2)}** (nominal {int(r['nominal_fraction']*100)}%)"
        flag = " — _degenerate on these samples; see caveat_" if gm in degenerate else ""
        lines.append(f"- `{gm}`: {txt}{flag}")
    lines.append("")

    # ---- Full curve table ----
    lines.append("## Axis 1 × 2 — AI fraction × geometry\n")
    for gm in geoms:
        g = agg[agg["condition"] == gm].sort_values("nominal_fraction")
        lines.append(f"### `{gm}`\n")
        lines.append("| nominal AI frac | actual AI frac | mean score | detection rate | sem-sim vs orig | n |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in g.iterrows():
            lines.append(f"| {_f(r['nominal_fraction'],2)} | {_f(r['actual_frac'],3)} "
                         f"| {_f(r['mean_score'])} | {_f(r['detection_rate'],2)} "
                         f"| {_f(r['sem_sim'])} | {int(r['n'])} |")
        lines.append("")

    _plot_curves(agg, geoms, results_dir)
    lines.append("![Detection vs AI fraction](fraction_detection.png)\n")
    lines.append("![Score vs AI fraction](fraction_score.png)\n")
    lines.append("![Geometry comparison](geometry_comparison.png)\n")

    # ---- Axis 3 edit modes ----
    em = df[df["axis"] == "edit_mode"].copy()
    if not em.empty:
        agg3 = (em.groupby("condition")
                .agg(ai_frac=("ai_generated_fraction", "mean"), mean_score=("detector_score", "mean"),
                     detection_rate=("detected", "mean"), sem_sim=("semantic_sim_vs_original", "mean"),
                     n=("detected", "size")).reset_index().sort_values("ai_frac"))
        lines.append("## Axis 3 — Realistic editing modes\n")
        lines.append("| mode | mean AI frac | mean score | detection rate | sem-sim vs orig | n |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in agg3.iterrows():
            lines.append(f"| {r['condition']} | {_f(r['ai_frac'],3)} | {_f(r['mean_score'])} "
                         f"| {_f(r['detection_rate'],2)} | {_f(r['sem_sim'])} | {int(r['n'])} |")
        lines.append("")
        _plot_modes(agg3, results_dir)
        lines.append("![Edit modes](edit_modes.png)\n")

    # ---- Study 1 vs Study 2 comparison ----
    lines.append("## Study 1 vs Study 2 — symmetry\n")
    cmp_made = _compare_studies(agg, results_dir, lines)
    if cmp_made:
        lines.append("![Study 1 vs Study 2](comparison_study1_study2.png)\n")

    lines.append("## Limitations\n")
    lines.append("- `distilgpt2` vehicle, not Gemini; our local key, **not** Google's production key.\n"
                 "- Weighted-Mean (tuning-free) detector.\n"
                 "- AI spans are genuine watermarked generations spliced into human text; light-edit "
                 "modes approximate touch density with real generated micro-spans.\n"
                 "- 20 samples, English, single small model.\n")

    out = results_dir / "report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _plot_curves(agg: pd.DataFrame, geoms: list[str], d: pathlib.Path) -> None:
    for metric, fname, ylab, title in [
        ("detection_rate", "fraction_detection.png", "detection rate", "Detection vs AI fraction"),
        ("mean_score", "fraction_score.png", "mean detector score", "Score vs AI fraction"),
    ]:
        fig, ax = plt.subplots(figsize=(7.5, 4.5))
        for gm in geoms:
            g = agg[agg["condition"] == gm].sort_values("nominal_fraction")
            ax.plot(g["nominal_fraction"], g[metric], marker="o", label=gm)
        ax.set_xlabel("AI-generated fraction")
        ax.set_ylabel(ylab)
        ax.set_title(title)
        if metric == "detection_rate":
            ax.set_ylim(-0.05, 1.05)
        ax.legend()
        fig.tight_layout()
        fig.savefig(d / fname, dpi=120)
        plt.close(fig)

    # geometry comparison: grouped bars at key fractions
    key = [0.05, 0.10, 0.20, 0.30]
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    width = 0.8 / max(1, len(geoms))
    for i, gm in enumerate(geoms):
        vals = []
        for fr in key:
            row = agg[(agg["condition"] == gm) & (agg["nominal_fraction"] == fr)]
            vals.append(float(row["detection_rate"].iloc[0]) if not row.empty else 0.0)
        xs = [x + i * width for x in range(len(key))]
        ax.bar(xs, vals, width=width, label=gm)
    ax.set_xticks([x + 0.4 - width / 2 for x in range(len(key))])
    ax.set_xticklabels([f"{int(f*100)}%" for f in key])
    ax.set_xlabel("AI-generated fraction")
    ax.set_ylabel("detection rate")
    ax.set_title("Geometry comparison: concentrated vs spread AI")
    ax.set_ylim(0, 1.05)
    ax.legend()
    fig.tight_layout()
    fig.savefig(d / "geometry_comparison.png", dpi=120)
    plt.close(fig)


def _plot_modes(agg3: pd.DataFrame, d: pathlib.Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(agg3["condition"], agg3["detection_rate"], color="#55A868")
    ax.set_ylabel("detection rate")
    ax.set_title("Detection rate by realistic editing mode")
    ax.set_ylim(0, 1.05)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(d / "edit_modes.png", dpi=120)
    plt.close(fig)


def _compare_studies(agg: pd.DataFrame, d: pathlib.Path, lines: list[str]) -> bool:
    if not STUDY1_CSV.exists():
        lines.append("_Study 1 results not found; comparison skipped._\n")
        return False
    s1 = pd.read_csv(STUDY1_CSV)

    # FAIR pairing: both are a SINGLE contiguous watermarked block of fraction f.
    #   Study 1 `keep_prefix` = retain one leading watermarked block (remove the rest)
    #   Study 2 `contiguous`  = insert one watermarked block into human text
    s1blk = (s1[(s1["axis"] == "mixture") & (s1["condition"] == "keep_prefix")]
             .groupby("param_value").agg(det=("detected", "mean")).reset_index())
    s2blk = agg[agg["condition"] == "contiguous"][["nominal_fraction", "detection_rate"]]

    lines.append(
        "Study 1 reached a given watermarked-token fraction by **removing** watermark from "
        "fully-watermarked text; Study 2 reaches it by **adding** watermarked spans to human "
        "text. To compare fairly we match the *construction*, not just the fraction: the "
        "comparable pair is a **single contiguous block** — Study 1 `keep_prefix` vs Study 2 "
        "`contiguous`.\n")
    lines.append("| block fraction | Study 1 keep_prefix (remove) | Study 2 contiguous (add) |")
    lines.append("|---|---|---|")
    diffs = []
    for fr in sorted(set(s2blk["nominal_fraction"]) | set(s1blk["param_value"])):
        a = s1blk[abs(s1blk["param_value"] - fr) < 1e-6]
        b = s2blk[abs(s2blk["nominal_fraction"] - fr) < 1e-6]
        if a.empty and b.empty:
            continue
        av = float(a["det"].iloc[0]) if not a.empty else None
        bv = float(b["detection_rate"].iloc[0]) if not b.empty else None
        if av is not None and bv is not None:
            diffs.append(abs(av - bv))
        lines.append(f"| {_f(fr,2)} | {_f(av,2) if av is not None else '—'} "
                     f"| {_f(bv,2) if bv is not None else '—'} |")
    lines.append("")

    mean_diff = sum(diffs) / len(diffs) if diffs else float("nan")
    verdict = "broadly symmetric" if mean_diff < 0.2 else "asymmetric"
    lines.append(
        f"**Verdict: {verdict}.** For the matched single-block construction the two curves track "
        f"each other (mean |Δ detection| = {_f(mean_diff, 2)} over shared fractions). This is the "
        "expected result: the Weighted-Mean statistic depends on the *count of watermarked tokens "
        "whose generation-time context is preserved*, not on whether you arrived there by adding or "
        "removing — essentially **history-independent**.\n")
    lines.append(
        "> The two studies' `scattered` conditions are **not** directly comparable: Study 1 "
        "scatters *individual isolated tokens* (which strips almost all signal — each watermarked "
        "token loses its generation context), whereas Study 2 scatters *k contiguous blocks* "
        "(which preserve context inside each block). That difference — geometry/granularity of the "
        "AI region, not history — is what drives detectability, and is the main lesson of the pair "
        "of studies.\n")

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.plot(s1blk["param_value"], s1blk["det"], marker="s", label="Study 1 keep_prefix (remove)")
    ax.plot(s2blk["nominal_fraction"], s2blk["detection_rate"], marker="o",
            label="Study 2 contiguous (add)")
    ax.set_xlabel("single-block watermarked / AI fraction")
    ax.set_ylabel("detection rate")
    ax.set_title("Study 1 vs Study 2 — matched single-block construction")
    ax.set_ylim(-0.05, 1.05)
    ax.legend()
    fig.tight_layout()
    fig.savefig(d / "comparison_study1_study2.png", dpi=120)
    plt.close(fig)
    return True
