"""Tests for the reprocess colour-space normalisation and image edge cases.

Covers the previously-dead ``normalize_colorspace`` profile option, ICC
handling, decompression-bomb protection, EXIF orientation, and the various
Pillow image modes (RGB, RGBA, grayscale, palette, CMYK).
"""

from __future__ import annotations

import io

import pytest
from PIL import Image, ImageCms

from ghostmark import reprocess
from ghostmark.reprocess import PROFILES, reprocess_image_bytes


def _srgb_icc_bytes() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def _encode(img: Image.Image, fmt: str, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kw)
    return buf.getvalue()


def _out_info(result) -> dict:
    out = Image.open(io.BytesIO(result.output_bytes))
    out.load()
    return dict(out.info)


# --- normalize_colorspace: the documented behaviour -------------------------------------


def test_profiles_declare_expected_normalize_flags():
    assert PROFILES["light"].normalize_colorspace is False
    assert PROFILES["medium"].normalize_colorspace is True
    assert PROFILES["strong"].normalize_colorspace is True


def test_normalize_true_drops_icc_profile_and_records_operation():
    icc = _srgb_icc_bytes()
    data = _encode(Image.new("RGB", (48, 48), (120, 80, 40)), "PNG", icc_profile=icc)
    # sanity: the source really carries an ICC profile
    assert "icc_profile" in Image.open(io.BytesIO(data)).info

    result = reprocess_image_bytes(data, ".png", "medium")  # normalize_colorspace=True

    assert result.normalize_colorspace is True
    assert "icc_profile" not in _out_info(result), "normalized output must carry no ICC profile"
    assert any("normalize-colorspace" in op for op in result.operations)


def test_normalize_false_preserves_icc_profile():
    icc = _srgb_icc_bytes()
    data = _encode(Image.new("RGB", (48, 48), (120, 80, 40)), "PNG", icc_profile=icc)

    result = reprocess_image_bytes(data, ".png", "light")  # normalize_colorspace=False

    assert result.normalize_colorspace is False
    assert "icc_profile" in _out_info(result), "un-normalized output must preserve the source ICC profile"
    assert not any("normalize-colorspace" in op for op in result.operations)


def test_normalize_false_without_profile_emits_no_icc():
    data = _encode(Image.new("RGB", (32, 32), (10, 20, 30)), "PNG")  # no ICC
    result = reprocess_image_bytes(data, ".png", "light")
    assert "icc_profile" not in _out_info(result)


def test_profiles_dict_exposes_normalize_flag():
    flags = {p["name"]: p["normalize_colorspace"] for p in reprocess.profiles_dict()}
    assert flags == {"light": False, "medium": True, "strong": True}


# --- image modes: predictable behaviour across the board --------------------------------


@pytest.mark.parametrize("profile", ["light", "medium", "strong"])
@pytest.mark.parametrize(
    "mode,color",
    [("RGB", (200, 100, 50)), ("RGBA", (200, 100, 50, 128)), ("L", 128), ("P", None), ("CMYK", (0, 100, 100, 0))],
)
def test_every_mode_reprocesses_to_a_valid_image(mode, color, profile):
    if mode == "P":
        img = Image.new("P", (40, 40))
        img.putpalette([i % 256 for i in range(768)])
    else:
        img = Image.new(mode, (40, 40), color)
    # CMYK cannot be stored as PNG; use a mode-appropriate container.
    fmt = "TIFF" if mode == "CMYK" else "PNG"
    suffix = ".png"  # output suffix drives format; input suffix only picks the default
    data = _encode(img, fmt)

    result = reprocess_image_bytes(data, suffix, profile, out_format="png")
    out = Image.open(io.BytesIO(result.output_bytes))
    out.load()
    assert out.size == (40, 40)
    assert out.mode in ("RGB", "RGBA")


def test_cmyk_normalized_output_is_rgb_without_icc():
    img = Image.new("CMYK", (30, 30), (0, 120, 120, 10))
    data = _encode(img, "TIFF")
    result = reprocess_image_bytes(data, ".jpg", "strong", out_format="png")  # normalize=True
    out = Image.open(io.BytesIO(result.output_bytes))
    out.load()
    assert out.mode == "RGB"
    assert "icc_profile" not in out.info


def test_rgba_alpha_preserved_on_png_output():
    img = Image.new("RGBA", (24, 24), (10, 200, 30, 90))
    data = _encode(img, "PNG")
    result = reprocess_image_bytes(data, ".png", "medium", out_format="png")
    out = Image.open(io.BytesIO(result.output_bytes))
    out.load()
    assert out.mode == "RGBA"
    # the alpha channel is still there and non-opaque
    assert out.getchannel("A").getextrema()[0] < 255


# --- decompression-bomb protection ------------------------------------------------------


def test_oversized_dimensions_are_rejected(monkeypatch):
    # A genuinely huge allocation would OOM the test runner, so lower the cap
    # and prove the header-dimension guard fires before any decode.
    monkeypatch.setattr(reprocess, "MAX_DECODE_PIXELS", 100)
    data = _encode(Image.new("RGB", (64, 64), (1, 2, 3)), "PNG")  # 4096 px > 100
    with pytest.raises(ValueError, match="exceed"):
        reprocess_image_bytes(data, ".png", "light")


def test_bomb_warning_is_escalated_to_error(monkeypatch):
    # Force Pillow's own decompression-bomb *warning* threshold low enough
    # that decoding a normal image trips it; reprocess must turn that warning
    # into a hard ValueError rather than proceeding.
    monkeypatch.setattr(reprocess, "MAX_DECODE_PIXELS", 10_000_000)  # keep our own guard high
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)  # Pillow warns above this
    data = _encode(Image.new("RGB", (64, 64), (1, 2, 3)), "PNG")
    with pytest.raises(ValueError):
        reprocess_image_bytes(data, ".png", "light")


# --- EXIF orientation -------------------------------------------------------------------


def test_exif_orientation_is_applied():
    # A 60x30 image tagged orientation=6 (rotate 90 CW on display) should come
    # out as 30x60 after reprocess bakes the orientation in.
    img = Image.new("RGB", (60, 30), (100, 150, 200))
    exif = img.getexif()
    exif[0x0112] = 6
    data = _encode(img, "JPEG", exif=exif.tobytes())

    result = reprocess_image_bytes(data, ".jpg", "light")
    out = Image.open(io.BytesIO(result.output_bytes))
    out.load()
    assert out.size == (30, 60), "EXIF orientation should have been applied to the pixels"
    assert any("orientation" in op for op in result.operations)
