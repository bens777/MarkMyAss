"""Pixel-level image reprocessing.

Distinct from cleaning:

* **Clean**   -- remove metadata/provenance, pixels byte-identical (see
  ``ghostmark.cleaners.image``).
* **Reprocess** -- decode and re-encode a *new* pixel representation of the
  image, optionally with mild resampling. Parameters are chosen for visual
  quality, NOT to defeat any detector.

Three user-selectable profiles trade fidelity for how much the pixels are
reconstructed. Pure Pillow -- no ML/torch dependency in the production image.
Genuine model-based reconstruction (diffusion, etc.) is deliberately NOT here;
it belongs in a future optional worker backend (see docs).
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from ghostmark import imaging_metrics

# Formats we accept as input and can emit.
SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_FORMAT_BY_SUFFIX = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
_SUFFIX_BY_FORMAT = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}


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
    normalize_colorspace: bool
    # Future billing hook: a small abstract cost unit ("credits") and a rough
    # latency class, so LIGHT/MEDIUM/STRONG can later be gated or charged
    # without touching the pipeline. See docs/ for the billing-hook note.
    estimated_compute_cost: float
    latency_class: str  # "fast" | "moderate" | "heavy"


PROFILES: dict[str, ReprocessProfile] = {
    "light": ReprocessProfile(
        name="light", label="Light",
        description="High-fidelity re-encode. No resampling; visually indistinguishable.",
        resample_factor=None, jpeg_quality=95, webp_quality=95,
        normalize_colorspace=False, estimated_compute_cost=1.0, latency_class="fast"),
    "medium": ReprocessProfile(
        name="medium", label="Medium",
        description="Moderate reprocessing: a mild resample round-trip, still visually very close.",
        resample_factor=0.9, jpeg_quality=90, webp_quality=90,
        normalize_colorspace=True, estimated_compute_cost=2.0, latency_class="moderate"),
    "strong": ReprocessProfile(
        name="strong", label="Strong",
        description="Stronger reconstruction: a larger resample round-trip and colour normalisation, "
                    "while keeping the image visually usable.",
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
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "output_format": self.output_format,
            "output_suffix": self.output_suffix,
            "operations": self.operations,
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


def _normalize_mode(img: Image.Image, out_format: str, warnings: list[str]) -> Image.Image:
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
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


def _encode(img: Image.Image, out_format: str, profile: ReprocessProfile) -> bytes:
    buf = io.BytesIO()
    if out_format == "JPEG":
        img.save(buf, format="JPEG", quality=profile.jpeg_quality)
    elif out_format == "WEBP":
        img.save(buf, format="WEBP", quality=profile.webp_quality)
    else:  # PNG (lossless)
        img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def reprocess_image_bytes(
    data: bytes, source_suffix: str, profile_name: str = DEFAULT_PROFILE,
    out_format: str | None = None,
) -> ReprocessResult:
    """Reprocess raw image bytes and return the new representation + metrics.

    Raises ``ValueError`` on an unknown profile/format or undecodable image.
    """
    if profile_name not in PROFILES:
        raise ValueError(f"Unknown profile: {profile_name!r}")
    profile = PROFILES[profile_name]
    t0 = time.perf_counter()

    try:
        original = Image.open(io.BytesIO(data))
        original.load()
    except Exception as exc:  # undecodable / malformed
        raise ValueError(f"Could not decode image: {exc.__class__.__name__}") from exc

    fmt = _resolve_out_format(source_suffix, out_format)
    warnings: list[str] = []
    operations = ["decode"]

    work = _normalize_mode(original, fmt, warnings)
    operations.append(f"normalize→{work.mode}")

    if profile.resample_factor is not None:
        w, h = work.size
        small = (max(1, round(w * profile.resample_factor)), max(1, round(h * profile.resample_factor)))
        work = work.resize(small, Image.LANCZOS).resize((w, h), Image.LANCZOS)
        operations.append(f"resample {profile.resample_factor:g}×→1× (LANCZOS)")

    output_bytes = _encode(work, fmt, profile)
    operations.append(
        f"re-encode {fmt}"
        + (f" q{profile.jpeg_quality}" if fmt == "JPEG"
           else f" q{profile.webp_quality}" if fmt == "WEBP" else " (lossless)")
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
        warnings=warnings,
    )
    return result


def profiles_dict() -> list[dict[str, Any]]:
    """Serializable profile catalogue for the API/UI."""
    return [
        {"name": p.name, "label": p.label, "description": p.description,
         "estimated_compute_cost": p.estimated_compute_cost, "latency_class": p.latency_class}
        for p in PROFILES.values()
    ]
