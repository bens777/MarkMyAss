"""C2PA / Content Credentials detection.

GhostMark does NOT implement a full C2PA manifest parser or validator (that
is a substantial spec: https://c2pa.org/specifications/). What it does do
is a byte-level scan for the container structures a C2PA manifest is
embedded in:

- JPEG: an APP11 (0xFFEB) marker segment holding a JUMBF box
  (ISO/IEC 19566-5).
- PNG: a ``caBX`` ancillary chunk holding the same JUMBF box.
- PDF: an ``/AF`` (associated file) or a raw ``c2pa`` / ``jumb`` byte
  signature.

Presence of these markers is a strong signal that *something* JUMBF/C2PA
shaped is embedded. It is NOT proof that the manifest is valid, signed, or
still trustworthy after edits elsewhere in the file -- that requires a real
C2PA validator, which is out of scope for V0. Status is reported as
``detected`` / ``not_detected`` rather than a claim about validity, and
confidence is always ``medium`` at best to reflect that this is a
structural heuristic, not a spec-conformant parse.
"""

from __future__ import annotations

from pathlib import Path

from ghostmark.formats import jpeg, png
from ghostmark.models import Category, Confidence, DetectionResult, Status

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png"}

_PDF_MARKERS = (b"c2pa", b"C2PA", b"jumb", b"JUMB")


def detect(path: Path) -> DetectionResult:
    suffix = path.suffix.lower()
    data = path.read_bytes()

    if suffix in (".jpg", ".jpeg"):
        try:
            found = jpeg.has_c2pa_marker(data)
        except jpeg.NotAJpegError:
            return _unknown("Could not parse file as JPEG.")
        return _tristate(found, "APP11/JUMBF marker segment scan (heuristic, not full manifest validation).")

    if suffix == ".png":
        try:
            found = png.has_c2pa_marker(data)
        except png.NotAPngError:
            return _unknown("Could not parse file as PNG.")
        return _tristate(found, "caBX chunk scan (heuristic, not full manifest validation).")

    if suffix == ".pdf":
        found = any(marker in data for marker in _PDF_MARKERS)
        return _tristate(found, "Raw byte-signature scan for C2PA/JUMBF markers (heuristic only).")

    return _unknown(f"C2PA scanning is not implemented for {suffix or 'this file type'}.")


def _tristate(found: bool, note: str) -> DetectionResult:
    return DetectionResult(
        detector="c2pa",
        label="C2PA / provenance",
        status=Status.FOUND if found else Status.NOT_FOUND,
        category=Category.PROVENANCE,
        confidence=Confidence.MEDIUM if found else Confidence.LOW,
        removable=found,
        details={"note": note},
    )


def _unknown(note: str) -> DetectionResult:
    return DetectionResult(
        detector="c2pa",
        label="C2PA / provenance",
        status=Status.UNKNOWN,
        category=Category.PROVENANCE,
        confidence=Confidence.UNKNOWN,
        removable=False,
        details={"note": note},
    )
