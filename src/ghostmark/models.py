"""Shared data model for GhostMark.

Every detector, cleaner, the CLI, and the web UI speak this vocabulary so
there is exactly one definition of what "found", "removed", or "unknown"
means anywhere in the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    """Tri-state outcome of a single detection check."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class Category(StrEnum):
    """The distinct families of "AI watermark" GhostMark treats separately."""

    UNICODE = "unicode"
    METADATA = "metadata"
    PROVENANCE = "provenance"
    STATISTICAL = "statistical"


class UnicodeClassification(StrEnum):
    """How safe a detected Unicode signal is to touch automatically."""

    SAFE_TO_REMOVE = "safe_to_remove"
    SAFE_TO_NORMALIZE = "safe_to_normalize"
    POTENTIALLY_SEMANTIC = "potentially_semantic"
    INFORMATIONAL = "informational"


@dataclass
class DetectionResult:
    """The outcome of one detector running against one input."""

    detector: str
    label: str
    status: Status
    category: Category
    confidence: Confidence
    removable: bool
    experimental: bool = False
    classification: UnicodeClassification | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def detected(self) -> bool:
        return self.status is Status.FOUND

    def to_dict(self) -> dict[str, Any]:
        return {
            "detector": self.detector,
            "label": self.label,
            "status": self.status.value,
            "category": self.category.value,
            "confidence": self.confidence.value,
            "removable": self.removable,
            "experimental": self.experimental,
            "classification": self.classification.value if self.classification else None,
            "details": self.details,
        }


@dataclass
class InspectionReport:
    """Everything GhostMark learned about one input (text or file)."""

    target: str
    target_type: str
    detections: list[DetectionResult] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    enhanced_metadata_support: bool = False

    def signals_found(self) -> list[DetectionResult]:
        return [d for d in self.detections if d.status is Status.FOUND]

    def signal_count(self) -> int:
        return len(self.signals_found())

    def get(self, detector: str) -> DetectionResult | None:
        for d in self.detections:
            if d.detector == detector:
                return d
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "target_type": self.target_type,
            "detections": [d.to_dict() for d in self.detections],
            "stats": self.stats,
            "warnings": self.warnings,
            "enhanced_metadata_support": self.enhanced_metadata_support,
            "signal_count": self.signal_count(),
        }


@dataclass
class CleanAction:
    """What happened to one detected signal during cleaning."""

    detector: str
    label: str
    attempted: bool
    removed: bool
    preserved: bool
    failed: bool
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "detector": self.detector,
            "label": self.label,
            "attempted": self.attempted,
            "removed": self.removed,
            "preserved": self.preserved,
            "failed": self.failed,
            "note": self.note,
        }


@dataclass
class CleanResult:
    """The outcome of running the cleaner pipeline on one input."""

    source: str
    output: str
    actions: list[CleanAction] = field(default_factory=list)
    before_hash: str = ""
    after_hash: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "output": self.output,
            "actions": [a.to_dict() for a in self.actions],
            "before_hash": self.before_hash,
            "after_hash": self.after_hash,
            "warnings": self.warnings,
        }


class MetadataOrigin(StrEnum):
    """How an independent tool's reported property relates to GhostMark's cleaning claims.

    Only ``EMBEDDED_METADATA`` is counted when deciding whether a cleaned
    file independently verifies as clean -- the rest (file size, computed
    composite values, structural facts a file needs to render/open) are
    not privacy/provenance signals GhostMark claims to remove.
    """

    EMBEDDED_METADATA = "embedded_metadata"
    STRUCTURAL = "structural"
    FILESYSTEM = "filesystem"
    COMPUTED = "computed"
    UNKNOWN = "unknown"


class VerificationVerdict(StrEnum):
    VERIFIED_CLEAN = "verified_clean"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"


@dataclass
class ExternalVerificationResult:
    """Result of an independent, third-party cross-check (currently: ExifTool).

    GhostMark's own detectors are pure Python and always run. This is a
    *second opinion* from a separate, independently-trusted tool, so a
    user doesn't have to take GhostMark's word for it.
    """

    tool: str
    available: bool
    applicable: bool = True
    version: str | None = None
    tags_by_origin: dict[str, dict[str, str]] = field(default_factory=dict)
    note: str = ""

    @property
    def embedded_metadata_tags(self) -> dict[str, str]:
        return self.tags_by_origin.get(MetadataOrigin.EMBEDDED_METADATA.value, {})

    @property
    def has_embedded_metadata(self) -> bool:
        return bool(self.embedded_metadata_tags)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "available": self.available,
            "applicable": self.applicable,
            "version": self.version,
            "tags_by_origin": self.tags_by_origin,
            "has_embedded_metadata": self.has_embedded_metadata,
            "note": self.note,
        }


@dataclass
class VerificationSummary:
    """The headline verdict for a clean: PASS only when GhostMark's own
    re-inspection AND an independent tool both agree nothing supported
    remains. This is NOT a claim that the file contains no possible
    identifying signal whatsoever -- only that the specific, supported
    metadata categories GhostMark targets are independently confirmed gone.
    """

    ghostmark_pass: bool
    exiftool_pass: bool | None  # None = not run / not applicable / unavailable
    statistical_watermark_verified: bool = False
    c2pa_status: str = "partial"
    exiftool_available: bool = False
    exiftool_applicable: bool = True
    exiftool_version: str | None = None
    note: str = ""

    @property
    def supported_metadata_clean(self) -> bool:
        return self.ghostmark_pass and self.exiftool_pass is not False

    @property
    def verdict(self) -> VerificationVerdict:
        if self.exiftool_pass is None:
            return VerificationVerdict.PARTIAL if self.ghostmark_pass else VerificationVerdict.UNVERIFIED
        if self.ghostmark_pass and self.exiftool_pass:
            return VerificationVerdict.VERIFIED_CLEAN
        if self.ghostmark_pass or self.exiftool_pass:
            return VerificationVerdict.PARTIAL
        return VerificationVerdict.UNVERIFIED

    def to_dict(self) -> dict[str, Any]:
        return {
            "ghostmark_pass": self.ghostmark_pass,
            "exiftool_pass": self.exiftool_pass,
            "supported_metadata_clean": self.supported_metadata_clean,
            "statistical_watermark_verified": self.statistical_watermark_verified,
            "c2pa_status": self.c2pa_status,
            "exiftool_available": self.exiftool_available,
            "exiftool_applicable": self.exiftool_applicable,
            "exiftool_version": self.exiftool_version,
            "verdict": self.verdict.value,
            "note": self.note,
        }


@dataclass
class VerifyResult:
    """Comparison between a pre-clean and post-clean inspection."""

    before: InspectionReport
    after: InspectionReport
    resolved: list[str] = field(default_factory=list)
    remaining: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    external_before: ExternalVerificationResult | None = None
    external_after: ExternalVerificationResult | None = None
    summary_v2: VerificationSummary | None = None

    @property
    def supported_found_before(self) -> int:
        return len([d for d in self.before.signals_found() if d.category != Category.STATISTICAL])

    @property
    def supported_resolved(self) -> int:
        return len(self.resolved)

    def summary(self) -> str:
        total = self.supported_found_before
        return (
            f"GhostMark successfully removed {self.supported_resolved}/{total} "
            "supported detected signals."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "resolved": self.resolved,
            "remaining": self.remaining,
            "unknown": self.unknown,
            "summary": self.summary(),
            "external_before": self.external_before.to_dict() if self.external_before else None,
            "external_after": self.external_after.to_dict() if self.external_after else None,
            "verification_summary": self.summary_v2.to_dict() if self.summary_v2 else None,
        }
