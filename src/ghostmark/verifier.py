"""Verification: re-inspect a cleaned output and compare it against the original.

This is the module that turns "we ran some cleaners" into an evidence-based
claim: exactly which detected signals are gone, which remain, and which
mechanisms GhostMark simply cannot evaluate (e.g. statistical watermarks).
"""

from __future__ import annotations

from pathlib import Path

from ghostmark.independent_verify import exiftool_check
from ghostmark.inspector import inspect_file, inspect_text
from ghostmark.models import InspectionReport, Status, VerifyResult


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


def verify_file(original: Path, cleaned: Path) -> VerifyResult:
    """Re-inspect the cleaned file with GhostMark's own detectors, then cross-check
    it independently with ExifTool (if installed) as a second opinion GhostMark
    doesn't control the outcome of.
    """

    before = inspect_file(original)
    after = inspect_file(cleaned)

    before.detections.append(exiftool_check(original))
    after.detections.append(exiftool_check(cleaned))

    return _compare(before, after)


def verify_text(original_text: str, cleaned_text: str) -> VerifyResult:
    return _compare(
        inspect_text(original_text, target="<original text>"),
        inspect_text(cleaned_text, target="<cleaned text>"),
    )


def verify_output_only(cleaned: Path) -> InspectionReport:
    """Inspect just the cleaned file, for when no original inspection is available."""

    return inspect_file(cleaned)
