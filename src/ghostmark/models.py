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


@dataclass
class VerifyResult:
    """Comparison between a pre-clean and post-clean inspection."""

    before: InspectionReport
    after: InspectionReport
    resolved: list[str] = field(default_factory=list)
    remaining: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

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
        }
