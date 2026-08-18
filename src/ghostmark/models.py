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


class VerifierStatus(StrEnum):
    """Explicit outcome of a single independent verifier run.

    The whole point of this enum is that ``UNAVAILABLE``/``UNSUPPORTED``/
    ``ERROR`` are never collapsed into ``NOT_DETECTED``. "The detector could
    not run" and "the detector ran and found nothing" are different facts,
    and conflating them would let a missing tool masquerade as a clean pass.

    Framed from the perspective of the *signal being looked for* (embedded
    metadata, a C2PA manifest): ``DETECTED`` means the signal is still
    present in the checked file; ``NOT_DETECTED`` means the verifier ran and
    confirmed it is gone.
    """

    DETECTED = "detected"           # verifier ran; the signal is still present
    NOT_DETECTED = "not_detected"   # verifier ran; the signal is gone
    UNAVAILABLE = "unavailable"     # the verifier binary/tool is not installed
    UNSUPPORTED = "unsupported"     # verifier installed but not applicable to this input
    ERROR = "error"                 # verifier tried to run but crashed/timed out/unparseable


def _derive_verifier_status(available: bool, applicable: bool, passed: bool | None) -> VerifierStatus:
    """Map a verifier's (available, applicable, passed) triple to an explicit status.

    ``passed`` is only ever a concrete bool when the verifier actually ran to
    completion (see ``ExternalVerificationResult.ran_successfully``); an
    available+applicable verifier with ``passed is None`` therefore means it
    tried but could not produce a result -> ``ERROR``, never ``NOT_DETECTED``.
    """

    if not available:
        return VerifierStatus.UNAVAILABLE
    if not applicable:
        return VerifierStatus.UNSUPPORTED
    if passed is None:
        return VerifierStatus.ERROR
    return VerifierStatus.NOT_DETECTED if passed else VerifierStatus.DETECTED


class VerificationVerdict(StrEnum):
    """The headline result of a clean, in order of strength.

    - ``VERIFIED_CLEAN``: something supported WAS found before cleaning,
      GhostMark's own re-inspection finds it gone, AND every independent
      verifier that could check agrees. The strongest claim GhostMark
      ever makes -- never awarded on GhostMark's own say-so alone.
    - ``PARTIAL``: GhostMark's own re-inspection says clean, but an
      independent verifier that DID run disagrees (still finds
      something). GhostMark's internal claim is not corroborated.
    - ``UNVERIFIED``: GhostMark's own re-inspection says clean, but no
      independent verifier was available/applicable to check at all.
    - ``NOT_APPLICABLE``: no supported signal was detected before
      cleaning in the first place -- there was nothing to verify removal
      of, so "clean" would be a claim about nothing.
    - ``FAILED``: GhostMark's own re-inspection still finds a signal it
      flagged before cleaning. GhostMark's own core promise did not hold
      for this input.
    """

    VERIFIED_CLEAN = "verified_clean"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    NOT_APPLICABLE = "not_applicable"
    FAILED = "failed"


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
    # True only when the tool actually ran to completion and its output was
    # parsed -- NOT when it's merely installed/applicable. A timeout, crash,
    # or unparseable output leaves this False, which the empty
    # ``tags_by_origin`` default alone can't distinguish from "genuinely
    # clean file with zero tags." Without this flag, a verifier that failed
    # to run would be indistinguishable from one that ran and passed --
    # see ``ghostmark.verifier._exiftool_outcome``.
    ran_successfully: bool = False
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
            "ran_successfully": self.ran_successfully,
            "note": self.note,
        }


@dataclass
class C2paVerificationResult:
    """Result of an independent C2PA manifest check using ``c2patool``.

    c2patool is the official Content Authenticity Initiative CLI -- it can
    read a C2PA manifest, but this is still NOT a claim of cryptographic
    validation (signature/trust-chain checking) unless ``trust_checked`` is
    True; GhostMark only uses it to confirm presence/absence of a
    manifest, matching GhostMark's own heuristic C2PA detector's scope.
    """

    tool: str
    available: bool
    applicable: bool = True
    version: str | None = None
    found: bool = False
    # True only when c2patool actually ran to completion (either a
    # successful parse, or a non-zero exit whose message was confidently
    # recognized as "no manifest") -- NOT when it's merely installed. See
    # ExternalVerificationResult.ran_successfully for why this matters: a
    # crash or timeout must never be indistinguishable from "checked, no
    # manifest found" via the ``found=False`` default alone.
    ran_successfully: bool = False
    trust_checked: bool = False
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "available": self.available,
            "applicable": self.applicable,
            "version": self.version,
            "found": self.found,
            "ran_successfully": self.ran_successfully,
            "trust_checked": self.trust_checked,
            "note": self.note,
        }


@dataclass
class ExternalVerifierOutcome:
    """A simple pass/fail/n-a summary from one independent verifier, used to
    build the overall verdict and the verification receipt. Distinct from
    :class:`ExternalVerificationResult`, which carries ExifTool's full
    per-tag breakdown -- this is the condensed "did it agree" signal.
    """

    name: str
    label: str
    available: bool
    applicable: bool
    passed: bool | None  # None = not available/applicable/errored
    version: str | None = None
    note: str = ""
    # Both currently-shipped verifiers (ExifTool, c2patool) run as local
    # subprocesses; the field exists so a future remote/API verifier can be
    # distinguished in the receipt without a schema change.
    is_remote: bool = False
    provider: str | None = None

    @property
    def status(self) -> VerifierStatus:
        """Explicit, never-collapsed outcome (see :class:`VerifierStatus`)."""
        return _derive_verifier_status(self.available, self.applicable, self.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "available": self.available,
            "applicable": self.applicable,
            "passed": self.passed,
            "status": self.status.value,
            "version": self.version,
            "provider": self.provider,
            "is_remote": self.is_remote,
            "note": self.note,
        }


@dataclass
class VerificationSummary:
    """The headline verdict for a clean: VERIFIED CLEAN only when something
    supported was actually found before cleaning, GhostMark's own
    re-inspection finds it gone, AND every independent verifier that could
    run agrees. This is NOT a claim that the file contains no possible
    identifying signal whatsoever -- only that the specific, supported
    metadata categories GhostMark targets are independently confirmed gone.
    """

    ghostmark_pass: bool
    supported_found_before: int = 0
    external_verifiers: list[ExternalVerifierOutcome] = field(default_factory=list)
    statistical_watermark_verified: bool = False
    c2pa_status: str = "partial"
    note: str = ""

    # --- backward/forward-compatible convenience accessors -------------------------

    def _verifier(self, name: str) -> ExternalVerifierOutcome | None:
        return next((v for v in self.external_verifiers if v.name == name), None)

    @property
    def exiftool_pass(self) -> bool | None:
        v = self._verifier("exiftool")
        return v.passed if v else None

    @property
    def exiftool_available(self) -> bool:
        v = self._verifier("exiftool")
        return v.available if v else False

    @property
    def exiftool_applicable(self) -> bool:
        v = self._verifier("exiftool")
        return v.applicable if v else True

    @property
    def exiftool_version(self) -> str | None:
        v = self._verifier("exiftool")
        return v.version if v else None

    @property
    def supported_metadata_clean(self) -> bool:
        return self.ghostmark_pass and all(v.passed is not False for v in self.external_verifiers)

    @property
    def verdict(self) -> VerificationVerdict:
        if self.supported_found_before == 0:
            return VerificationVerdict.NOT_APPLICABLE
        if not self.ghostmark_pass:
            return VerificationVerdict.FAILED

        relevant = [v for v in self.external_verifiers if v.available and v.applicable]
        if not relevant:
            return VerificationVerdict.UNVERIFIED
        if all(v.passed for v in relevant):
            return VerificationVerdict.VERIFIED_CLEAN
        return VerificationVerdict.PARTIAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "ghostmark_pass": self.ghostmark_pass,
            "supported_found_before": self.supported_found_before,
            "external_verifiers": [v.to_dict() for v in self.external_verifiers],
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
    c2pa_before: C2paVerificationResult | None = None
    c2pa_after: C2paVerificationResult | None = None
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
            "c2pa_before": self.c2pa_before.to_dict() if self.c2pa_before else None,
            "c2pa_after": self.c2pa_after.to_dict() if self.c2pa_after else None,
            "verification_summary": self.summary_v2.to_dict() if self.summary_v2 else None,
        }
