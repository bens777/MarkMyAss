"""Runs GhostMark's public test corpus and produces a benchmark report.

The public ``/benchmarks`` page is generated from this module's actual
output -- real detect/clean/independently-verify results against the
committed corpus (``ghostmark.corpus_data``) -- not hand-typed numbers.
Failures are surfaced, never hidden: a fixture that doesn't behave as
documented shows up as a failure on the page, the same way it would fail
``tests/test_corpus.py``.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ghostmark import __version__
from ghostmark.cleaner import clean_file
from ghostmark.corpus_data import CORPUS_DIR, load_manifest
from ghostmark.independent_verify import ExifToolVerifier
from ghostmark.inspector import inspect_file
from ghostmark.models import Status


@dataclass
class FixtureResult:
    path: str
    kind: str
    detected_ok: bool
    cleaned_ok: bool
    independently_verified_ok: bool | None  # None = ExifTool unavailable/not applicable
    detail: str = ""

    @property
    def overall_ok(self) -> bool:
        return self.detected_ok and self.cleaned_ok and self.independently_verified_ok is not False


@dataclass
class BenchmarkReport:
    ghostmark_version: str
    generated_at: str
    exiftool_available: bool
    exiftool_version: str | None
    results: list[FixtureResult] = field(default_factory=list)

    @property
    def fixture_count(self) -> int:
        return len(self.results)

    @property
    def detection_pass(self) -> int:
        return sum(1 for r in self.results if r.detected_ok)

    @property
    def cleaning_pass(self) -> int:
        return sum(1 for r in self.results if r.cleaned_ok)

    @property
    def verification_applicable(self) -> int:
        return sum(1 for r in self.results if r.independently_verified_ok is not None)

    @property
    def verification_pass(self) -> int:
        return sum(1 for r in self.results if r.independently_verified_ok is True)

    @property
    def failures(self) -> list[FixtureResult]:
        return [r for r in self.results if not r.overall_ok]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ghostmark_version": self.ghostmark_version,
            "generated_at": self.generated_at,
            "exiftool_available": self.exiftool_available,
            "exiftool_version": self.exiftool_version,
            "fixture_count": self.fixture_count,
            "detection_pass": self.detection_pass,
            "cleaning_pass": self.cleaning_pass,
            "verification_pass": self.verification_pass,
            "verification_applicable": self.verification_applicable,
            "results": [
                {
                    "path": r.path,
                    "kind": r.kind,
                    "detected_ok": r.detected_ok,
                    "cleaned_ok": r.cleaned_ok,
                    "independently_verified_ok": r.independently_verified_ok,
                    "overall_ok": r.overall_ok,
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }


def run_benchmarks() -> BenchmarkReport:
    from datetime import UTC, datetime

    verifier = ExifToolVerifier()
    manifest = load_manifest()
    results: list[FixtureResult] = []

    with tempfile.TemporaryDirectory(prefix="ghostmark-benchmark-") as tmp:
        tmp_path = Path(tmp)
        for entry in manifest:
            fixture = CORPUS_DIR / entry["path"]
            working = tmp_path / fixture.name
            shutil.copyfile(fixture, working)

            before = inspect_file(working)
            found_before = {d.detector for d in before.detections if d.status is Status.FOUND}
            detected_ok = found_before == set(entry["expected_before"])

            cleaned_ok = False
            cleaned_path: Path | None = None
            detail = ""
            try:
                clean_result = clean_file(working)
                cleaned_path = Path(clean_result.output)
                after = inspect_file(cleaned_path)
                found_after = {d.detector for d in after.detections if d.status is Status.FOUND}
                cleaned_ok = found_after == set(entry["expected_after"])
                if not cleaned_ok:
                    detail = f"expected {sorted(entry['expected_after'])} after cleaning, got {sorted(found_after)}"
            except Exception as exc:  # noqa: BLE001 - a benchmark run must never crash the page
                detail = f"clean failed: {exc.__class__.__name__}"

            independently_verified_ok: bool | None = None
            if cleaned_path is not None:
                ext = verifier.inspect(cleaned_path)
                if ext.available and ext.applicable:
                    independently_verified_ok = not ext.has_embedded_metadata

            results.append(
                FixtureResult(
                    path=entry["path"],
                    kind=entry["kind"],
                    detected_ok=detected_ok,
                    cleaned_ok=cleaned_ok,
                    independently_verified_ok=independently_verified_ok,
                    detail=detail,
                )
            )

    return BenchmarkReport(
        ghostmark_version=__version__,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        exiftool_available=verifier.available(),
        exiftool_version=verifier.version(),
        results=results,
    )


def to_markdown_table(report: BenchmarkReport) -> str:
    header = "| Fixture | Detected as documented | Cleaned as documented | Independently verified |"
    sep = "| --- | --- | --- | --- |"
    rows = [header, sep]
    for r in report.results:
        detect_word = "✓ Yes" if r.detected_ok else "✗ NO"
        clean_word = "✓ Yes" if r.cleaned_ok else "✗ NO"
        if r.independently_verified_ok is None:
            verify_word = "N/A"
        else:
            verify_word = "✓ Yes" if r.independently_verified_ok else "✗ NO"
        rows.append(f"| `{r.path}` | {detect_word} | {clean_word} | {verify_word} |")
    return "\n".join(rows)


def to_summary_markdown(report: BenchmarkReport) -> str:
    lines = [
        f"**GhostMark {report.ghostmark_version}** &middot; {report.fixture_count} fixtures &middot; "
        f"generated {report.generated_at}",
        "",
        f"- Detection: {report.detection_pass} / {report.fixture_count} matched documented expectations",
        f"- Cleaning: {report.cleaning_pass} / {report.fixture_count} matched documented expectations",
    ]
    if report.exiftool_available:
        version = report.exiftool_version or "unknown version"
        lines.append(
            f"- Independent verification (ExifTool {version}): "
            f"{report.verification_pass} / {report.verification_applicable} applicable fixtures confirmed clean"
        )
    else:
        lines.append("- Independent verification: ExifTool was not installed when this report was generated (N/A for all fixtures)")

    if report.failures:
        lines.append("")
        lines.append(f"**{len(report.failures)} known failure(s) -- not hidden:**")
        for r in report.failures:
            lines.append(f"- `{r.path}`: {r.detail or 'did not match documented expectations'}")
    else:
        lines.append("")
        lines.append("**0 known failures** in the current corpus.")

    return "\n".join(lines)
