"""Verification: re-inspect a cleaned output and compare it against the original.

This is the module that turns "we ran some cleaners" into an evidence-based
claim: exactly which detected signals are gone, which remain, which
mechanisms GhostMark simply cannot evaluate (e.g. statistical watermarks),
and -- for files ExifTool can read -- whether an independent third-party
tool agrees nothing supported remains embedded.

The headline verdict (:class:`~ghostmark.models.VerificationSummary`) is
only ever "verified clean" when BOTH GhostMark's own re-inspection AND
ExifTool's independent check agree. If ExifTool isn't installed or isn't
applicable (plain text), that is stated explicitly rather than silently
dropped or counted as a pass.
"""

from __future__ import annotations

from pathlib import Path

from ghostmark.independent_verify import ExifToolVerifier
from ghostmark.inspector import inspect_file, inspect_text
from ghostmark.models import (
    ExternalVerificationResult,
    InspectionReport,
    Status,
    VerificationSummary,
    VerifyResult,
)

_verifier = ExifToolVerifier()


def _compare(before: InspectionReport, after: InspectionReport) -> VerifyResult:
    resolved: list[str] = []
    remaining: list[str] = []
    unknown: list[str] = []

    for b in before.detections:
        a = after.get(b.detector)
        if a is None:
            continue
        if b.status is Status.UNKNOWN or a.status is Status.UNKNOWN:
            unknown.append(b.detector)
        elif b.status is Status.FOUND and a.status is Status.NOT_FOUND:
            resolved.append(b.detector)
        elif b.status is Status.FOUND and a.status is Status.FOUND:
            remaining.append(b.detector)

    return VerifyResult(before=before, after=after, resolved=resolved, remaining=remaining, unknown=unknown)


def _build_summary(ghostmark_pass: bool, external_after: ExternalVerificationResult, *, c2pa_status: str) -> VerificationSummary:
    if not external_after.applicable or not external_after.available:
        exiftool_pass = None
    else:
        exiftool_pass = not external_after.has_embedded_metadata

    return VerificationSummary(
        ghostmark_pass=ghostmark_pass,
        exiftool_pass=exiftool_pass,
        statistical_watermark_verified=False,
        c2pa_status=c2pa_status,
        exiftool_available=external_after.available,
        exiftool_applicable=external_after.applicable,
        exiftool_version=external_after.version,
        note=external_after.note,
    )


def verify_file(original: Path, cleaned: Path) -> VerifyResult:
    """Re-inspect the cleaned file with GhostMark's own detectors, then cross-check
    it independently with ExifTool (if installed) as a second opinion GhostMark
    doesn't control the outcome of.
    """

    before = inspect_file(original)
    after = inspect_file(cleaned)
    result = _compare(before, after)

    result.external_before = _verifier.inspect(original)
    result.external_after = _verifier.inspect(cleaned)

    # GhostMark's C2PA support is a structural heuristic, not a manifest
    # validator -- its capability level is fixed, not something a single
    # verification outcome can upgrade to "verified".
    c2pa_status = "partial" if before.get("c2pa") is not None else "not_applicable"

    result.summary_v2 = _build_summary(ghostmark_pass=not result.remaining, external_after=result.external_after, c2pa_status=c2pa_status)
    return result


def verify_text(original_text: str, cleaned_text: str) -> VerifyResult:
    before = inspect_text(original_text, target="<original text>")
    after = inspect_text(cleaned_text, target="<cleaned text>")
    result = _compare(before, after)

    result.external_before = None
    result.external_after = ExternalVerificationResult(
        tool="exiftool",
        available=_verifier.available(),
        applicable=False,
        version=_verifier.version(),
        note="ExifTool does not apply to plain text.",
    )
    result.summary_v2 = _build_summary(
        ghostmark_pass=not result.remaining, external_after=result.external_after, c2pa_status="not_applicable"
    )
    return result


def verify_output_only(cleaned: Path) -> InspectionReport:
    """Inspect just the cleaned file, for when no original inspection is available."""

    return inspect_file(cleaned)
