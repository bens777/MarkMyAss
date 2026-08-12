"""Top-level inspection: dispatches to the right detectors for a text or file input.

This is the single place that decides "what detectors run for this file
type" -- the CLI and the web UI both call into here so their results can
never drift apart.
"""

from __future__ import annotations

from pathlib import Path

from ghostmark.detectors import c2pa, metadata, statistical
from ghostmark.detectors import unicode as unicode_detector
from ghostmark.models import InspectionReport
from ghostmark.security import UnsupportedFileTypeError, check_supported, suffix_of

TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
PDF_EXTENSIONS = {".pdf"}


def inspect_text(text: str, *, target: str = "<text>") -> InspectionReport:
    detections = [unicode_detector.detect_hidden_unicode(text)]
    detections += statistical.detect_all(text)
    return InspectionReport(
        target=target,
        target_type="text",
        detections=detections,
        stats={"characters": len(text)},
    )


def inspect_file(path: Path) -> InspectionReport:
    check_supported(path.name)
    ext = suffix_of(path.name)

    if ext in TEXT_EXTENSIONS:
        text = path.read_text(encoding="utf-8", errors="replace")
        report = inspect_text(text, target=str(path))
        report.target_type = ext.lstrip(".")
        return report

    if ext in PDF_EXTENSIONS:
        detections = metadata.inspect_pdf_metadata(path)
        detections.append(c2pa.detect(path))
        return InspectionReport(
            target=str(path),
            target_type="pdf",
            detections=detections,
            stats={"size_bytes": path.stat().st_size},
            enhanced_metadata_support=metadata.enhanced_metadata_available(),
        )

    if ext in IMAGE_EXTENSIONS:
        detections = metadata.inspect_image_metadata(path)
        detections.append(c2pa.detect(path))
        return InspectionReport(
            target=str(path),
            target_type=ext.lstrip("."),
            detections=detections,
            stats={"size_bytes": path.stat().st_size},
            enhanced_metadata_support=metadata.enhanced_metadata_available(),
        )

    raise UnsupportedFileTypeError(f"No inspector registered for '{ext}'")
