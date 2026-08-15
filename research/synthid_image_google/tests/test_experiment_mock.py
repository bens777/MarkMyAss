"""End-to-end pipeline with the mock detector (offline, no API)."""

import pandas as pd
from synthid_image.detector import MockVertexDetector
from synthid_image.experiment import run
from synthid_image.report import build_report
from synthid_image.sample import synthetic_image
from synthid_image.schema import COLUMNS


def test_run_produces_rows_and_report(tmp_path):
    sources = [("s0", synthetic_image(seed=0, size=96))]
    out = tmp_path / "res"
    csv = run(sources, MockVertexDetector(), out, price_per_call_usd=0.0)
    df = pd.read_csv(csv)

    assert list(df.columns) == COLUMNS
    assert (df["transform"] == "__baseline__").sum() == 1
    assert len(df) > 10  # baseline + full transform set

    # mock verifier: after-status is MOCK, and NEVER a fabricated detection
    assert set(df["verifier_after_status"]) == {"MOCK"}
    assert df["verifier_after_detected"].isna().all()

    # quality metrics populated; identity baseline is ~perfect
    base = df[df["transform"] == "__baseline__"].iloc[0]
    assert base["ssim"] == 1.0
    assert df["estimated_api_cost_usd"].sum() == 0.0

    rep = build_report(out)
    assert rep.exists()
    assert "Google SynthID Image Benchmark" in rep.read_text(encoding="utf-8")


def test_cost_projection_scales_with_price(tmp_path):
    sources = [("s0", synthetic_image(seed=0, size=64))]
    out = tmp_path / "res2"
    run(sources, MockVertexDetector(), out, price_per_call_usd=0.01)
    df = pd.read_csv(out / "summary.csv")
    # every row books one call at the configured price
    assert (df["estimated_api_cost_usd"] == 0.01).all()
