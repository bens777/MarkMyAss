"""Pixel-level image reprocessing.

Distinct from cleaning:

* **Clean**   -- remove metadata/provenance, pixels byte-identical (see
  ``ghostmark.cleaners.image``).
* **Reprocess** -- decode and re-encode a *new* pixel representation of the
  image, optionally with mild resampling and colour-space normalisation.
  Parameters are chosen for visual quality, NOT to defeat any detector.

Three user-selectable profiles trade fidelity for how much the pixels are
reconstructed. Pure Pillow -- no ML/torch dependency in the production image.
Genuine model-based reconstruction (diffusion, etc.) is deliberately NOT here;
it belongs in a future optional worker backend (see docs).

Reprocess is the only place GhostMark *decodes* pixels (cleaning is
byte/segment level), so it is also the only place a decompression-bomb
upload could force a huge allocation -- ``MAX_DECODE_PIXELS`` below bounds
that explicitly.
"""

from __future__ import annotations

import io
import time
import warnings as _warnings
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageCms, ImageOps

from ghostmark import imaging_metrics

# Formats we accept as input and can emit.
SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_FORMAT_BY_SUFFIX = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
_SUFFIX_BY_FORMAT = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}

# Hard ceiling on the number of pixels Reprocess will decode. A malicious
# upload can declare enormous dimensions to force a multi-gigabyte
# allocation ("decompression bomb"); the check runs on the header
# dimensions (available without decoding) BEFORE any pixel buffer is
# allocated, and any Pillow DecompressionBombWarning during the actual
# decode is additionally escalated to a hard error below. 64 MP comfortably
# covers real photography (e.g. 9504x6336 from a 60 MP camera) while
# staying well under a memory-exhaustion threshold.
MAX_DECODE_PIXELS = 64_000_000

_ALPHA_MODES = ("RGBA", "LA", "PA")


@dataclass(frozen=True)
class ReprocessProfile:
    """A named reprocessing recipe. Parameters reflect a quality/fidelity
    trade-off, and carry premium-gating metadata for a future paid tier."""

    name: str
    label: str
    description: str
    # down-then-up resample factor (None = no geometric resampling; output keeps
    # the original dimensions either way)
    resample_factor: float | None
    jpeg_quality: int
    webp_quality: int
    # When True, the image is converted into a canonical sRGB representation:
    # any embedded ICC profile is resolved (ICC-aware transform to sRGB when
    # possible) and the output carries NO ICC profile. When False, the source
    # colour space is preserved -- the original ICC profile is carried through
    # to the output unchanged (for RGB/RGBA sources) so a colour-managed
    # viewer renders identical colours. See ``_apply_colorspace``.
    normalize_colorspace: bool
    # Future billing hook: a small abstract cost unit ("credits") and a rough
    # latency class, so LIGHT/MEDIUM/STRONG can later be gated or charged
    # without touching the pipeline. See docs/ for the billing-hook note.
    estimated_compute_cost: float
    latency_class: str  # "fast" | "moderate" | "heavy"


PROFILES: dict[str, ReprocessProfile] = {
    "light": ReprocessProfile(
        name="light", label="Light",
        description="High-fidelity re-encode. No resampling; source colour space preserved.",
        resample_factor=None, jpeg_quality=95, webp_quality=95,
        normalize_colorspace=False, estimated_compute_cost=1.0, latency_class="fast"),
    "medium": ReprocessProfile(
        name="medium", label="Medium",
        description="Moderate reprocessing: a mild resample round-trip plus sRGB colour "
                    "normalisation, still visually very close.",
        resample_factor=0.9, jpeg_quality=90, webp_quality=90,
        normalize_colorspace=True, estimated_compute_cost=2.0, latency_class="moderate"),
    "strong": ReprocessProfile(
        name="strong", label="Strong",
        description="Stronger reconstruction: a larger resample round-trip and sRGB colour "
                    "normalisation, while keeping the image visually usable.",
        resample_factor=0.75, jpeg_quality=85, webp_quality=85,
        normalize_colorspace=True, estimated_compute_cost=3.0, latency_class="heavy"),
}

DEFAULT_PROFILE = "medium"


@dataclass
class ReprocessResult:
    profile: str
    output_format: str
    output_suffix: str
    output_bytes: bytes
    operations: list[str]
    original_width: int
    original_height: int
    output_width: int
    output_height: int
    original_size_bytes: int
    output_size_bytes: int
    ssim: float
    psnr: float
    pixel_changed_pct: float
    processing_time_ms: float
    estimated_compute_cost: float
    normalize_colorspace: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "output_format": self.output_format,
            "output_suffix": self.output_suffix,
            "operations": self.operations,
            "normalize_colorspace": self.normalize_colorspace,
            "metrics": {
                "original_dimensions": [self.original_width, self.original_height],
                "output_dimensions": [self.output_width, self.output_height],
                "original_size_bytes": self.original_size_bytes,
                "output_size_bytes": self.output_size_bytes,
                "ssim": round(self.ssim, 4),
                "psnr": round(self.psnr, 2),
                "pixel_changed_pct": round(self.pixel_changed_pct, 2),
            },
            "processing_time_ms": round(self.processing_time_ms, 1),
            "estimated_compute_cost": self.estimated_compute_cost,
            "warnings": self.warnings,
        }


def _resolve_out_format(source_suffix: str, out_format: str | None) -> str:
    if out_format:
        fmt = out_format.strip().upper()
        fmt = "JPEG" if fmt in ("JPG", "JPEG") else fmt
        if fmt not in _SUFFIX_BY_FORMAT:
            raise ValueError(f"Unsupported output format: {out_format}")
        return fmt
    return _FORMAT_BY_SUFFIX.get(source_suffix.lower(), "PNG")


def _has_alpha(img: Image.Image) -> bool:
    return img.mode in _ALPHA_MODES or (img.mode == "P" and "transparency" in img.info)


def _ensure_rgb(img: Image.Image) -> Image.Image:
    """Convert to RGB/RGBA, preserving any alpha channel."""
    if img.mode in ("RGB", "RGBA"):
        return img
    return img.convert("RGBA") if _has_alpha(img) else img.convert("RGB")


def _to_srgb(img: Image.Image, warnings: list[str]) -> tuple[Image.Image, str]:
    """Return an sRGB copy of ``img`` with no ICC profile, plus an operation label.

    Uses an ICC-aware transform (via littleCMS through Pillow) when the image
    carries an embedded profile; otherwise the pixels are assumed already
    sRGB and simply normalised to RGB/RGBA. Any CMS failure (mismatched
    profile/mode, unusual colour space) falls back to a plain mode
    conversion so this can never raise. Alpha is always preserved.
    """

    icc = img.info.get("icc_profile")
    if not icc:
        out = _ensure_rgb(img).copy()
        out.info.pop("icc_profile", None)
        return out, "normalize-colorspace->sRGB (assumed; no ICC profile)"

    try:
        src_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        dst_profile = ImageCms.createProfile("sRGB")
        if _has_alpha(img):
            rgba = img.convert("RGBA")
            alpha = rgba.getchannel("A")
            rgb = ImageCms.profileToProfile(rgba.convert("RGB"), src_profile, dst_profile, outputMode="RGB")
            if rgb is None:
                raise ImageCms.PyCMSError("profileToProfile returned None")
            rgb.putalpha(alpha)
            out = rgb
        else:
            # Feed the CMS transform an input mode compatible with common
            # source profiles (RGB / CMYK / grayscale); anything else is
            # coerced to RGB first.
            in_img = img if img.mode in ("RGB", "CMYK", "L") else img.convert("RGB")
            out = ImageCms.profileToProfile(in_img, src_profile, dst_profile, outputMode="RGB")
            if out is None:
                raise ImageCms.PyCMSError("profileToProfile returned None")
        out.info.pop("icc_profile", None)
        return out, "normalize-colorspace->sRGB (ICC-aware)"
    except Exception:  # noqa: BLE001 - never let colour management crash reprocessing
        warnings.append(
            "Colour normalisation could not use the embedded ICC profile; "
            "converted to sRGB without it."
        )
        out = _ensure_rgb(img).copy()
        out.info.pop("icc_profile", None)
        return out, "normalize-colorspace->sRGB (fallback, ICC ignored)"


def _apply_colorspace(
    img: Image.Image, profile: ReprocessProfile, warnings: list[str]
) -> tuple[Image.Image, str | None, bytes | None]:
    """Resolve the working image's colour space per the profile.

    Returns ``(image, operation_or_None, icc_to_embed_or_None)``.

    * ``normalize_colorspace=True``  -> transform to sRGB, emit no ICC profile.
    * ``normalize_colorspace=False`` -> keep the pixels as-is and preserve the
      source ICC profile in the output (only when the source is already
      RGB/RGBA, where the profile still describes the pixels; a grayscale/
      CMYK/palette profile can't survive the later RGB normalisation and is
      dropped with a warning).
    """

    source_icc = img.info.get("icc_profile")
    if profile.normalize_colorspace:
        work, op = _to_srgb(img, warnings)
        return work, op, None

    if source_icc and img.mode not in ("RGB", "RGBA"):
        warnings.append(
            "Source ICC colour profile could not be preserved through the "
            "mode conversion and was dropped."
        )
        return img, None, None
    return img, None, source_icc


def _normalize_mode(img: Image.Image, out_format: str, warnings: list[str]) -> Image.Image:
    has_alpha = _has_alpha(img)
    if out_format == "JPEG":
        if has_alpha:
            warnings.append("JPEG output: transparency flattened onto white.")
        base = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        base.paste(rgba, mask=rgba.split()[-1])
        return base
    if has_alpha:
        return img.convert("RGBA")
    return img.convert("RGB")


def _encode(
    img: Image.Image, out_format: str, profile: ReprocessProfile, icc_profile: bytes | None
) -> bytes:
    buf = io.BytesIO()
    save_kwargs: dict[str, Any] = {}
    # Only re-embed an ICC profile for a mode it actually describes (RGB/RGBA
    # here) -- guarded by the caller, which never passes an incompatible one.
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile
    if out_format == "JPEG":
        img.save(buf, format="JPEG", quality=profile.jpeg_quality, **save_kwargs)
    elif out_format == "WEBP":
        img.save(buf, format="WEBP", quality=profile.webp_quality, **save_kwargs)
    else:  # PNG (lossless)
        img.save(buf, format="PNG", optimize=True, **save_kwargs)
    return buf.getvalue()


def reprocess_image_bytes(
    data: bytes, source_suffix: str, profile_name: str = DEFAULT_PROFILE,
    out_format: str | None = None,
) -> ReprocessResult:
    """Reprocess raw image bytes and return the new representation + metrics.

    Raises ``ValueError`` on an unknown profile/format, an undecodable image,
    or an image whose dimensions exceed ``MAX_DECODE_PIXELS``.
    """
    if profile_name not in PROFILES:
        raise ValueError(f"Unknown profile: {profile_name!r}")
    profile = PROFILES[profile_name]
    t0 = time.perf_counter()

    try:
        opened = Image.open(io.BytesIO(data))
    except Exception as exc:  # undecodable / malformed / unidentified
        raise ValueError(f"Could not decode image: {exc.__class__.__name__}") from exc

    # Decompression-bomb guard on header dimensions, before any decode/alloc.
    decl_w, decl_h = opened.size
    if decl_w * decl_h > MAX_DECODE_PIXELS:
        raise ValueError(
            f"Image dimensions {decl_w}x{decl_h} exceed the "
            f"{MAX_DECODE_PIXELS:,}-pixel reprocess limit."
        )

    # Read the EXIF orientation before decoding, so we can note it as an
    # explicit operation, then materialise the pixels with the Pillow
    # decompression-bomb *warning* escalated to a hard error.
    try:
        orientation = opened.getexif().get(0x0112)
    except Exception:  # noqa: BLE001 - a broken EXIF block must not abort reprocessing
        orientation = None

    try:
        with _warnings.catch_warnings():
            _warnings.simplefilter("error", Image.DecompressionBombWarning)
            opened.load()
    except Exception as exc:  # decode failure or decompression bomb
        raise ValueError(f"Could not decode image: {exc.__class__.__name__}") from exc

    source_icc = opened.info.get("icc_profile")
    # Apply EXIF orientation so the re-encoded (EXIF-stripped) image looks
    # right; exif_transpose carries the ICC profile over but we re-attach the
    # captured one below to be safe.
    original = ImageOps.exif_transpose(opened) or opened
    if source_icc and "icc_profile" not in original.info:
        original.info["icc_profile"] = source_icc

    fmt = _resolve_out_format(source_suffix, out_format)
    warnings: list[str] = []
    operations = ["decode"]
    if orientation not in (None, 1):
        operations.append(f"apply-exif-orientation ({orientation})")

    # 1. Colour space (per profile), 2. output mode, 3. resample, 4. encode.
    work, cs_op, icc_to_embed = _apply_colorspace(original, profile, warnings)
    if cs_op:
        operations.append(cs_op)

    work = _normalize_mode(work, fmt, warnings)
    operations.append(f"normalize->{work.mode}")
    # An ICC profile only survives if the pixels stayed RGB/RGBA.
    if icc_to_embed and work.mode not in ("RGB", "RGBA"):
        icc_to_embed = None

    if profile.resample_factor is not None:
        w, h = work.size
        small = (max(1, round(w * profile.resample_factor)), max(1, round(h * profile.resample_factor)))
        work = work.resize(small, Image.LANCZOS).resize((w, h), Image.LANCZOS)
        operations.append(f"resample {profile.resample_factor:g}x->1x (LANCZOS)")

    output_bytes = _encode(work, fmt, profile, icc_to_embed)
    operations.append(
        f"re-encode {fmt}"
        + (f" q{profile.jpeg_quality}" if fmt == "JPEG"
           else f" q{profile.webp_quality}" if fmt == "WEBP" else " (lossless)")
        + (" +ICC" if icc_to_embed else "")
    )

    out_img = Image.open(io.BytesIO(output_bytes))
    out_img.load()

    result = ReprocessResult(
        profile=profile.name,
        output_format=fmt,
        output_suffix=_SUFFIX_BY_FORMAT[fmt],
        output_bytes=output_bytes,
        operations=operations,
        original_width=original.width, original_height=original.height,
        output_width=out_img.width, output_height=out_img.height,
        original_size_bytes=len(data), output_size_bytes=len(output_bytes),
        ssim=imaging_metrics.ssim(original, out_img),
        psnr=imaging_metrics.psnr(original, out_img),
        pixel_changed_pct=imaging_metrics.pixel_changed_pct(original, out_img),
        processing_time_ms=(time.perf_counter() - t0) * 1000.0,
        estimated_compute_cost=profile.estimated_compute_cost,
        normalize_colorspace=profile.normalize_colorspace,
        warnings=warnings,
    )
    return result


def profiles_dict() -> list[dict[str, Any]]:
    """Serializable profile catalogue for the API/UI."""
    return [
        {"name": p.name, "label": p.label, "description": p.description,
         "normalize_colorspace": p.normalize_colorspace,
         "estimated_compute_cost": p.estimated_compute_cost, "latency_class": p.latency_class}
        for p in PROFILES.values()
    ]
