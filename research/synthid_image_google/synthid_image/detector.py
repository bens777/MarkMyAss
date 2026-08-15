"""Detector adapter interface + Vertex Imagen verifier + offline mock.

CRITICAL SAFETY CONTRACT
------------------------
* A detector must NEVER invent a detection. The real Vertex adapter returns
  status ``DETECTOR_UNAVAILABLE`` whenever the SDK, credentials, or config are
  missing, or whenever paid calls are not explicitly enabled.
* The mock adapter is for offline pipeline/testing only. Every result it returns
  is stamped ``status=MOCK`` and ``raw_result={"mock": true, ...}`` so it can
  never be mistaken for a genuine Google verification.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    DETECTED = "DETECTED"
    NOT_DETECTED = "NOT_DETECTED"
    UNCERTAIN = "UNCERTAIN"
    DETECTOR_UNAVAILABLE = "DETECTOR_UNAVAILABLE"
    MOCK = "MOCK"  # offline stand-in only; never a real Google result


@dataclass
class DetectorResult:
    provider: str
    detector: str
    status: Status
    detected: bool | None  # None unless a real/mocked decision exists
    confidence: str | None  # e.g. HIGH/MEDIUM/LOW when the API returns it
    raw_result: dict[str, Any] = field(default_factory=dict)
    estimated_cost_usd: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")


class DetectorAdapter:
    """Interface: verify an image and return a DetectorResult. Never fabricate."""

    provider = "abstract"
    detector = "abstract"

    def verify(self, image_path: str) -> DetectorResult:  # pragma: no cover - abstract
        raise NotImplementedError


class MockVertexDetector(DetectorAdapter):
    """Offline stand-in. Returns clearly-labelled MOCK results (never real).

    A deterministic pseudo-confidence is derived from the file path so the
    pipeline produces stable rows in tests — but it is explicitly ``MOCK`` and
    must not be read as a Google detection.
    """

    provider = "mock"
    detector = "mock-vertex-imagen"

    def verify(self, image_path: str) -> DetectorResult:
        # Deterministic, obviously-synthetic label. NOT a detection.
        label = "MOCK_HIGH"
        return DetectorResult(
            provider=self.provider,
            detector=self.detector,
            status=Status.MOCK,
            detected=None,
            confidence=label,
            raw_result={"mock": True, "note": "offline placeholder, not a real verification",
                        "image_path": image_path},
            estimated_cost_usd=0.0,
        )


class VertexImagenDetector(DetectorAdapter):
    """Real Google Vertex AI Imagen watermark verifier.

    Makes a PAID API call ONLY when ``enable_paid=True`` AND the Vertex SDK and
    credentials are available. Otherwise returns DETECTOR_UNAVAILABLE. It never
    returns a detection without a genuine API response.
    """

    provider = "google-vertex"
    detector = "imagen-watermark-verification"

    def __init__(self, project: str | None = None, location: str = "us-central1",
                 enable_paid: bool = False, price_per_call_usd: float = 0.0):
        self.project = project
        self.location = location
        self.enable_paid = enable_paid
        self.price_per_call_usd = price_per_call_usd

    def _unavailable(self, reason: str) -> DetectorResult:
        return DetectorResult(
            provider=self.provider, detector=self.detector,
            status=Status.DETECTOR_UNAVAILABLE, detected=None, confidence=None,
            raw_result={"reason": reason}, estimated_cost_usd=0.0)

    def verify(self, image_path: str) -> DetectorResult:
        # Hard gate: no paid call unless explicitly enabled.
        if not self.enable_paid:
            return self._unavailable("paid calls not enabled (enable_paid=False)")
        if not self.project:
            return self._unavailable("no GCP project configured")
        # Lazy import so the harness/tests never require the SDK to be installed.
        try:
            from google.cloud import aiplatform  # noqa: F401
        except Exception as e:  # ImportError or partial install
            return self._unavailable(f"vertex sdk unavailable: {e.__class__.__name__}")
        try:
            return self._verify_live(image_path)
        except Exception as e:  # auth error, quota, network -- never fabricate
            return self._unavailable(f"live verification failed: {e.__class__.__name__}: {e}")

    def _verify_live(self, image_path: str) -> DetectorResult:  # pragma: no cover - needs GCP
        """Call the real Vertex watermark verifier.

        NOTE: this is the integration point to finalise against the live API
        (endpoint/model name + response schema) once GCP access exists. It is
        never exercised without credentials + enable_paid, so it is not covered
        by offline tests. It must map the API response to a real DETECTED/
        NOT_DETECTED/UNCERTAIN status and confidence -- and must raise (caught
        above) rather than guess if the response is unexpected.
        """
        raise NotImplementedError(
            "finalise Vertex watermark-verification request/response against the "
            "live API before running the paid pilot")
