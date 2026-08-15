"""Tests for pixel-level image reprocessing."""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image, PngImagePlugin

from ghostmark.inspector import inspect_file
from ghostmark.models import Category, Status
from ghostmark.reprocess import PROFILES, reprocess_image_bytes

PROFILE_NAMES = list(PROFILES)


def _photo(size=(160, 120)) -> Image.Image:
    # A textured gradient (not a flat colour) so resampling produces a real,
    # measurable pixel change at the higher profiles.
    w, h = size
    xs = np.tile(np.linspace(0, 255, w), (h, 1))
    ys = np.tile(np.linspace(0, 255, h), (w, 1)).T
    noise = (np.indices((h, w)).sum(axis=0) * 37 % 64).astype(np.float64)
    arr = np.dstack([xs, ys, (xs + ys + noise) / 3]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _encode(img: Image.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.parametrize("suffix,fmt", [(".png", "PNG"), (".jpg", "JPEG"), (".webp", "WEBP")])
@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_reprocess_each_format_and_profile(suffix, fmt, profile):
    data = _encode(_photo(), fmt)
    result = reprocess_image_bytes(data, suffix, profile)

    # output is a valid, openable image of the SAME dimensions
    out = Image.open(io.BytesIO(result.output_bytes))
    out.load()
    assert (out.width, out.height) == (160, 120)
    assert result.output_width == 160 and result.output_height == 120

    # metrics are present and in-range
    assert 0.0 <= result.ssim <= 1.0
    assert result.psnr > 0.0
    assert 0.0 <= result.pixel_changed_pct <= 100.0
    assert result.output_size_bytes == len(result.output_bytes)
    assert result.estimated_compute_cost == PROFILES[profile].estimated_compute_cost
    assert result.operations and result.operations[0] == "decode"


def test_original_bytes_not_mutated():
    data = _encode(_photo(), "PNG")
    snapshot = bytes(data)
    reprocess_image_bytes(data, ".png", "strong")
    assert data == snapshot  # input buffer is never modified in place


def test_output_format_override_and_alpha_flatten():
    rgba = Image.new("RGBA", (40, 40), (255, 0, 0, 100))
    data = _encode(rgba, "PNG")
    result = reprocess_image_bytes(data, ".png", "light", out_format="jpeg")
    assert result.output_format == "JPEG"
    assert result.output_suffix == ".jpg"
    assert any("transparency flattened" in w for w in result.warnings)


def test_metadata_is_absent_after_reprocess(tmp_path):
    # PNG carrying text metadata -> reprocess -> re-inspect: no metadata signals.
    info = PngImagePlugin.PngInfo()
    info.add_text("Software", "ghostmark-test-suite")
    info.add_text("Comment", "should-not-survive")
    buf = io.BytesIO()
    _photo().save(buf, format="PNG", pnginfo=info)

    result = reprocess_image_bytes(buf.getvalue(), ".png", "light")
    out_path = tmp_path / "out.png"
    out_path.write_bytes(result.output_bytes)

    report = inspect_file(out_path)
    meta_or_prov = [
        d for d in report.signals_found()
        if d.category in (Category.METADATA, Category.PROVENANCE)
    ]
    assert meta_or_prov == [], f"reprocessed image still has: {[d.detector for d in meta_or_prov]}"


def test_jpeg_exif_absent_after_reprocess(tmp_path):
    exif = Image.Exif()
    exif[0x0131] = "ghostmark-test-software"  # Software tag
    buf = io.BytesIO()
    _photo().save(buf, format="JPEG", exif=exif.tobytes())

    result = reprocess_image_bytes(buf.getvalue(), ".jpg", "medium")
    out_path = tmp_path / "out.jpg"
    out_path.write_bytes(result.output_bytes)

    report = inspect_file(out_path)
    assert all(d.status is not Status.FOUND or d.category == Category.STATISTICAL
               for d in report.detections)


def test_malformed_input_raises():
    with pytest.raises(ValueError):
        reprocess_image_bytes(b"definitely not an image", ".png", "light")


def test_unknown_profile_and_format_raise():
    data = _encode(_photo(), "PNG")
    with pytest.raises(ValueError):
        reprocess_image_bytes(data, ".png", "nope")
    with pytest.raises(ValueError):
        reprocess_image_bytes(data, ".png", "light", out_format="gif")


def test_strong_changes_more_pixels_than_light_on_a_photo():
    data = _encode(_photo(), "JPEG")
    light = reprocess_image_bytes(data, ".jpg", "light")
    strong = reprocess_image_bytes(data, ".jpg", "strong")
    # A textured photo through a bigger resample round-trip changes at least as
    # many pixels as a conservative re-encode.
    assert strong.pixel_changed_pct >= light.pixel_changed_pct
