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

import json
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

    Implements the official current SDK contract
    (``vertexai.preview.vision_models.WatermarkVerificationModel``):

        vertexai.init(project=..., location=...)
        model = WatermarkVerificationModel.from_pretrained("imageverification@001")
        image = Image.load_from_file(path)
        response = model.verify_image(image)     # -> WatermarkVerificationResponse
        response.watermark_verification_result   # <- documented field (a string)

    Documented (implemented here): model id ``imageverification@001`` (configurable),
    the call flow, and the ``watermark_verification_result`` field.

    NOT documented (the one live-confirmable unknown): the *string values* that
    ``watermark_verification_result`` (the prediction ``decision`` key) can take.
    We therefore carry the raw decision string through as ``confidence`` and only
    map it to a boolean ``detected`` when it matches an explicitly-configured
    ``positive_labels`` / ``negative_labels`` set. An unrecognised decision maps
    to ``UNCERTAIN`` (never fabricated). Populate the label sets after one live
    call confirms the exact strings.

    Makes a PAID call ONLY when ``enable_paid=True`` AND the SDK + credentials are
    present; otherwise returns DETECTOR_UNAVAILABLE.
    """

    provider = "google-vertex"
    detector = "imagen-watermark-verification"

    def __init__(self, project: str | None = None, location: str = "us-central1",
                 enable_paid: bool = False, price_per_call_usd: float = 0.0,
                 verifier_model: str = "imageverification@001",
                 positive_labels: list[str] | None = None,
                 negative_labels: list[str] | None = None):
        self.project = project
        self.location = location
        self.enable_paid = enable_paid
        self.price_per_call_usd = price_per_call_usd
        self.verifier_model = verifier_model  # documented default; configurable
        self.positive_labels = {s.strip().upper() for s in (positive_labels or [])}
        self.negative_labels = {s.strip().upper() for s in (negative_labels or [])}

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
            import vertexai  # noqa: F401
        except Exception as e:  # ImportError or partial install
            return self._unavailable(f"vertex sdk unavailable: {e.__class__.__name__}")
        try:
            response = self._run_sdk(image_path)
        except Exception as e:  # auth error, quota, network -- never fabricate
            return self._unavailable(f"live verification failed: {e.__class__.__name__}: {e}")
        return self._build_result(response)

    def _run_sdk(self, image_path: str):  # pragma: no cover - needs GCP + network
        """The only part that touches the live SDK/network (not covered offline)."""
        import vertexai
        from vertexai.preview.vision_models import WatermarkVerificationModel
        try:
            from vertexai.preview.vision_models import Image as VertexImage
        except ImportError:
            from vertexai.vision_models import Image as VertexImage
        vertexai.init(project=self.project, location=self.location)
        model = WatermarkVerificationModel.from_pretrained(self.verifier_model)
        image = VertexImage.load_from_file(image_path)
        return model.verify_image(image)

    def _map_decision(self, decision: Any) -> tuple[Status, bool | None]:
        """Map the (undocumented-valued) decision string to our schema. Safe: an
        unrecognised value is UNCERTAIN, never a fabricated True/False."""
        if decision is None:
            return Status.UNCERTAIN, None
        norm = str(decision).strip().upper()
        if norm in self.positive_labels:
            return Status.DETECTED, True
        if norm in self.negative_labels:
            return Status.NOT_DETECTED, False
        return Status.UNCERTAIN, None

    def _build_result(self, response: Any) -> DetectorResult:
        """Parse a WatermarkVerificationResponse into a DetectorResult, preserving
        the raw response for research logging."""
        decision = getattr(response, "watermark_verification_result", None)
        raw: dict[str, Any] = {"watermark_verification_result": decision}
        pr = getattr(response, "_prediction_response", None)
        if pr is not None:
            try:
                json.dumps(pr)
                raw["prediction_response"] = pr
            except (TypeError, ValueError):
                raw["prediction_response"] = repr(pr)  # keep it, even if not JSON-safe
        status, detected = self._map_decision(decision)
        return DetectorResult(
            provider=self.provider, detector=self.detector, status=status,
            detected=detected,
            confidence=(str(decision) if decision is not None else None),
            raw_result=raw, estimated_cost_usd=self.price_per_call_usd)
