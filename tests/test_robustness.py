"""Tests for the observational before/after robustness report."""

from __future__ import annotations

import io

from PIL import Image, PngImagePlugin

from ghostmark.inspector import inspect_file
from ghostmark.reprocess import reprocess_image_bytes
from ghostmark.robustness import build_robustness_report, snapshot


def _photo(size=(60, 40)) -> Image.Image:
    return Image.new("RGB", size, (123, 77, 44))


def test_report_structure_and_observational_flag(tmp_path):
    data = io.BytesIO()
    _photo().save(data, format="PNG")
    src = tmp_path / "in.png"
    src.write_bytes(data.getvalue())

    result = reprocess_image_bytes(data.getvalue(), ".png", "medium")
    out = tmp_path / "out.png"
    out.write_bytes(result.output_bytes)

    report = build_robustness_report(
        input_report=inspect_file(src),
        output_report=inspect_file(out),
        reprocess_result=result,
    )

    assert report["observational"] is True
    for section in ("input", "processing", "output", "image_similarity", "statistical_watermark"):
        assert section in report
    assert report["statistical_watermark"]["locally_verifiable"] is False
    assert report["processing"]["profile"] == "medium"
    sim = report["image_similarity"]
    assert sim["input_dimensions"] == [60, 40]
    assert 0.0 <= sim["ssim"] <= 1.0


def test_metadata_present_before_absent_after(tmp_path):
    info = PngImagePlugin.PngInfo()
    info.add_text("Software", "test-suite")
    info.add_text("Comment", "hidden")
    buf = io.BytesIO()
    _photo().save(buf, format="PNG", pnginfo=info)
    src = tmp_path / "in.png"
    src.write_bytes(buf.getvalue())

    before = snapshot(inspect_file(src))
    assert before.metadata_signals, "the input snapshot should observe embedded metadata"

    result = reprocess_image_bytes(buf.getvalue(), ".png", "light")
    out = tmp_path / "out.png"
    out.write_bytes(result.output_bytes)

    report = build_robustness_report(
        input_report=inspect_file(src),
        output_report=inspect_file(out),
        reprocess_result=result,
    )
    # Reprocess re-encodes pixels only, dropping the ancillary text chunks --
    # observed, not claimed as a guarantee.
    assert report["output"]["metadata_signals"] == []
