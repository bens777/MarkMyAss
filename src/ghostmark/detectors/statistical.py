"""Statistical / model-level text watermark detection.

Some LLM providers embed a statistical bias into token sampling (e.g. a
green/red token-list scheme) that a matching detector with the provider's
secret key/seed can, in principle, detect with some confidence. GhostMark
has no access to any provider's detection key or model, and does not
implement a detector for any of them in V0.

This module exists so the *architecture* is in place: a
``StatisticalWatermarkDetector`` can be registered for a given provider and
plugged in later without touching the rest of the app. Until then, every
provider reports ``unknown`` -- never a fabricated confidence score.
"""

from __future__ import annotations

from typing import Protocol

from ghostmark.models import Category, Confidence, DetectionResult, Status

KNOWN_PROVIDERS = ("claude", "gemini", "gpt", "other")


class StatisticalWatermarkDetector(Protocol):
    """Interface a future provider-specific detector must implement."""

    provider: str

    def detect(self, text: str) -> DetectionResult: ...


def _unverified(provider: str) -> DetectionResult:
    label = {
        "claude": "Claude statistical watermark",
        "gemini": "Gemini statistical watermark",
        "gpt": "GPT statistical watermark",
    }.get(provider, "Statistical watermark")
    return DetectionResult(
        detector=f"statistical_{provider}",
        label=label,
        status=Status.UNKNOWN,
        category=Category.STATISTICAL,
        confidence=Confidence.UNKNOWN,
        removable=False,
        experimental=False,
        details={
            "note": (
                "GhostMark does not implement a statistical watermark detector for this "
                "provider. No provider has published a public, independently reproducible "
                "detector, so any claimed result would be a guess. This is reported honestly "
                "as unverified rather than faked."
            ),
        },
    )


def detect_all(text: str) -> list[DetectionResult]:
    """Return the (currently all-unverified) statistical watermark report for ``text``."""

    return [_unverified(provider) for provider in ("claude", "gemini", "gpt")]
