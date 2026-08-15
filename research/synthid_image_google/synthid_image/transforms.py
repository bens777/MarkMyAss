"""Image transform pipeline for SynthID robustness characterisation.

Each transform maps a PIL image to a transformed PIL image. Transforms are
deterministic. The experiment layer saves outputs and (later) re-verifies them
with Google's real verifier; the transforms themselves make no API calls.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageEnhance


def _to_rgb(img: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        base = Image.new("RGB", img.size, bg)
        rgba = img.convert("RGBA")
        base.paste(rgba, mask=rgba.split()[-1])
        return base
    return img.convert("RGB")


def _roundtrip(img: Image.Image, fmt: str, **save_kw) -> Image.Image:
    buf = io.BytesIO()
    src = img if fmt.upper() == "PNG" else _to_rgb(img)
    src.save(buf, format=fmt, **save_kw)
    buf.seek(0)
    return Image.open(buf).copy()


# ---- individual transforms ------------------------------------------------

def screenshot_rerender(img: Image.Image, scale: float = 1.0) -> Image.Image:
    """Approximate a screenshot: flatten to opaque RGB, optional display rescale,
    re-encode losslessly (PNG). One iteration ~ one screen capture."""
    out = _to_rgb(img)
    if scale != 1.0:
        w, h = out.size
        disp = out.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
        out = disp.resize((w, h), Image.LANCZOS)
    return _roundtrip(out, "PNG")


def repeated_rerender(img: Image.Image, iterations: int, scale: float = 1.0) -> Image.Image:
    out = img
    for _ in range(max(0, iterations)):
        out = screenshot_rerender(out, scale=scale)
    return out


def jpeg_quality(img: Image.Image, quality: int) -> Image.Image:
    return _roundtrip(img, "JPEG", quality=int(quality))


def resize_scale(img: Image.Image, scale: float) -> Image.Image:
    w, h = img.size
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)


def center_crop(img: Image.Image, frac_removed: float) -> Image.Image:
    """Remove `frac_removed` of each linear dimension symmetrically (keep centre)."""
    frac_removed = max(0.0, min(0.95, frac_removed))
    w, h = img.size
    keep_w, keep_h = round(w * (1 - frac_removed)), round(h * (1 - frac_removed))
    left, top = (w - keep_w) // 2, (h - keep_h) // 2
    return img.crop((left, top, left + keep_w, top + keep_h))


def convert_format(img: Image.Image, fmt: str) -> Image.Image:
    return _roundtrip(img, fmt.upper())


def format_chain(img: Image.Image, chain: list[str]) -> Image.Image:
    out = img
    for fmt in chain:
        out = _roundtrip(out, fmt.upper())
    return out


def brightness_contrast(img: Image.Image, brightness: float = 1.0,
                        contrast: float = 1.0) -> Image.Image:
    out = ImageEnhance.Brightness(_to_rgb(img)).enhance(brightness)
    out = ImageEnhance.Contrast(out).enhance(contrast)
    return out


# ---- registry -------------------------------------------------------------

@dataclass
class Transform:
    name: str
    params: dict[str, Any]
    apply: Callable[[Image.Image], Image.Image]
    out_format: str = "PNG"  # how the transformed image is stored for verification
    iterations: int = 1
    geometry_changing: bool = False
    tags: list[str] = field(default_factory=list)


def build_transform_set() -> list[Transform]:
    """The first transform set (screenshot loops, JPEG sweep, resize, crop,
    format conversions, mild brightness/contrast)."""
    ts: list[Transform] = []

    for it in (1, 2, 5, 10):
        ts.append(Transform(f"screenshot_x{it}", {"iterations": it},
                            (lambda it_: (lambda im: repeated_rerender(im, it_)))(it),
                            out_format="PNG", iterations=it, tags=["screenshot"]))

    for q in (95, 85, 75, 50):
        ts.append(Transform(f"jpeg_q{q}", {"quality": q},
                            (lambda q_: (lambda im: jpeg_quality(im, q_)))(q),
                            out_format="JPEG", tags=["recompress"]))

    for sc in (0.75, 0.5, 1.5):
        ts.append(Transform(f"resize_{sc}", {"scale": sc},
                            (lambda s_: (lambda im: resize_scale(im, s_)))(sc),
                            out_format="PNG", geometry_changing=True, tags=["geometric"]))

    for fr in (0.1, 0.25, 0.5):
        ts.append(Transform(f"crop_{fr}", {"frac_removed": fr},
                            (lambda f_: (lambda im: center_crop(im, f_)))(fr),
                            out_format="PNG", geometry_changing=True, tags=["geometric"]))

    for fmt in ("PNG", "JPEG", "WEBP"):
        ts.append(Transform(f"convert_{fmt.lower()}", {"format": fmt},
                            (lambda fm: (lambda im: convert_format(im, fm)))(fmt),
                            out_format=fmt, tags=["format"]))
    ts.append(Transform("chain_png_jpeg_webp", {"chain": ["PNG", "JPEG", "WEBP"]},
                        lambda im: format_chain(im, ["PNG", "JPEG", "WEBP"]),
                        out_format="WEBP", tags=["format"]))

    for b, c in ((1.1, 1.0), (1.0, 1.1), (0.9, 1.1)):
        ts.append(Transform(f"bc_b{b}_c{c}", {"brightness": b, "contrast": c},
                            (lambda b_, c_: (lambda im: brightness_contrast(im, b_, c_)))(b, c),
                            out_format="PNG", tags=["color"]))

    return ts
