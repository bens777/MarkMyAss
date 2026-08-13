"""Verification: re-inspect a cleaned output and compare it against the original.

This is the module that turns "we ran some cleaners" into an evidence-based
claim: exactly which detected signals are gone, which remain, which
mechanisms GhostMark simply cannot evaluate (e.g. statistical watermarks),
and -- for files ExifTool/c2patool can read -- whether an independent
third-party tool agrees nothing supported remains.

The headline verdict (:class:`~ghostmark.models.VerificationSummary`) is
only ever VERIFIED CLEAN when something supported was actually found
before cleaning, GhostMark's own re-inspection agrees it's gone, AND
every independent verifier that could run agrees too. If a verifier isn't
installed or isn't applicable, that is stated explicitly rather than
silently dropped or counted as a pass -- see
:class:`~ghostmark.models.VerificationVerdict` for the full decision
rules.
"""

from __future__ import annotations

from pathlib import Path

from ghostmark.independent_verify import C2paToolVerifier, ExifToolVerifier
from ghostmark.inspector import inspect_file, inspect_text
from ghostmark.models import (
    C2paVerificationResult,
    Category,
    ExternalVerificationResult,
    ExternalVerifierOutcome,
    InspectionReport,
    Status,
    VerificationSummary,
    VerifyResult,
)

_exiftool = ExifToolVerifier()
_c2patool = C2paToolVerifier()


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


def _exiftool_outcome(external_after: ExternalVerificationResult) -> ExternalVerifierOutcome:
    passed = None
    if external_after.available and external_after.applicable:
        passed = not external_after.has_embedded_metadata
    return ExternalVerifierOutcome(
        name="exiftool",
        label="ExifTool",
        available=external_after.available,
        applicable=external_after.applicable,
        passed=passed,
        version=external_after.version,
        note=external_after.note,
    )


def _c2patool_outcome(c2pa_after: C2paVerificationResult) -> ExternalVerifierOutcome:
    passed = None
    if c2pa_after.available and c2pa_after.applicable:
        passed = not c2pa_after.found
    return ExternalVerifierOutcome(
        name="c2patool",
        label="c2patool",
        available=c2pa_after.available,
        applicable=c2pa_after.applicable,
        passed=passed,
        version=c2pa_after.version,
        note=c2pa_after.note,
    )


def _build_summary(
    result: VerifyResult,
    *,
    external_after: ExternalVerificationResult,
    c2pa_after: C2paVerificationResult,
    c2pa_status: str,
) -> VerificationSummary:
    supported_found_before = len(
        [d for d in result.before.signals_found() if d.category != Category.STATISTICAL]
    )
    notes = [n for n in (external_after.note, c2pa_after.note) if n]

    return VerificationSummary(
        ghostmark_pass=not result.remaining,
        supported_found_before=supported_found_before,
        external_verifiers=[_exiftool_outcome(external_after), _c2patool_outcome(c2pa_after)],
        statistical_watermark_verified=False,
        c2pa_status=c2pa_status,
        note=" ".join(notes),
    )


def verify_file(original: Path, cleaned: Path) -> VerifyResult:
    """Re-inspect the cleaned file with GhostMark's own detectors, then cross-check
    it independently with ExifTool and c2patool (whichever are installed and
    applicable) as second opinions GhostMark doesn't control the outcome of.
    """

    before = inspect_file(original)
    after = inspect_file(cleaned)
    result = _compare(before, after)

    result.external_before = _exiftool.inspect(original)
    result.external_after = _exiftool.inspect(cleaned)
    result.c2pa_before = _c2patool.inspect(original)
    result.c2pa_after = _c2patool.inspect(cleaned)

    # GhostMark's C2PA support is a structural heuristic, not a manifest
    # validator -- its capability level is fixed, not something a single
    # verification outcome can upgrade to "verified".
    c2pa_status = "partial" if before.get("c2pa") is not None else "not_applicable"

    result.summary_v2 = _build_summary(
        result, external_after=result.external_after, c2pa_after=result.c2pa_after, c2pa_status=c2pa_status
    )
    return result


def verify_text(original_text: str, cleaned_text: str) -> VerifyResult:
    before = inspect_text(original_text, target="<original text>")
    after = inspect_text(cleaned_text, target="<cleaned text>")
    result = _compare(before, after)

    result.external_before = None
    result.external_after = ExternalVerificationResult(
        tool="exiftool",
        available=_exiftool.available(),
        applicable=False,
        version=_exiftool.version(),
        note="ExifTool does not apply to plain text.",
    )
    result.c2pa_before = None
    result.c2pa_after = C2paVerificationResult(
        tool="c2patool",
        available=_c2patool.available(),
        applicable=False,
        version=_c2patool.version(),
        note="c2patool does not apply to plain text.",
    )
    result.summary_v2 = _build_summary(
        result, external_after=result.external_after, c2pa_after=result.c2pa_after, c2pa_status="not_applicable"
    )
    return result


def verify_output_only(cleaned: Path) -> InspectionReport:
    """Inspect just the cleaned file, for when no original inspection is available."""

    return inspect_file(cleaned)
