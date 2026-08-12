"""Detection of EXIF/XMP/IPTC (images) and document-info/XMP (PDF) metadata."""

from __future__ import annotations

import shutil
from pathlib import Path

import pikepdf

from ghostmark.formats import jpeg, png, webp
from ghostmark.models import Category, Confidence, DetectionResult, Status


def enhanced_metadata_available() -> bool:
    """Whether an optional external tool (ExifTool) is available for deeper inspection.

    GhostMark's core detectors never require ExifTool -- this only reports
    whether the enhanced path *could* be used. Nothing in V0 currently shells
    out to it; the flag exists so the UI/CLI can be honest about it and so a
    future contributor has a place to wire it in.
    """

    return shutil.which("exiftool") is not None


def _result(detector: str, label: str, found: bool, details: dict) -> DetectionResult:
    return DetectionResult(
        detector=detector,
        label=label,
        status=Status.FOUND if found else Status.NOT_FOUND,
        category=Category.METADATA,
        confidence=Confidence.HIGH,
        removable=found,
        details=details,
    )


def inspect_image_metadata(path: Path) -> list[DetectionResult]:
    data = path.read_bytes()
    suffix = path.suffix.lower()

    if suffix in (".jpg", ".jpeg"):
        try:
            segments, _ = jpeg.parse_header_segments(data)
        except jpeg.NotAJpegError as exc:
            return [_result("exif", "EXIF metadata", False, {"error": str(exc)})]
        kinds = [s.kind() for s in segments]
        return [
            _result("exif", "EXIF metadata", "exif" in kinds, {"segments": kinds.count("exif")}),
            _result("xmp", "XMP metadata", "xmp" in kinds, {"segments": kinds.count("xmp")}),
            _result("iptc", "IPTC metadata", "iptc" in kinds, {"segments": kinds.count("iptc")}),
            _result("comment", "Comment metadata", "comment" in kinds, {"segments": kinds.count("comment")}),
        ]

    if suffix == ".png":
        try:
            chunks = png.parse_chunks(data)
        except png.NotAPngError as exc:
            return [_result("exif", "EXIF metadata", False, {"error": str(exc)})]
        types = [c.type for c in chunks]
        text_keywords = []
        has_xmp = False
        for c in chunks:
            if c.type in (b"tEXt", b"iTXt") and b"\x00" in c.data:
                keyword = c.data.split(b"\x00", 1)[0]
                keyword_str = keyword.decode("latin-1", errors="replace")
                if keyword_str == "XML:com.adobe.xmp":
                    has_xmp = True
                else:
                    text_keywords.append(keyword_str)
        return [
            _result("exif", "EXIF metadata", b"eXIf" in types, {}),
            _result("xmp", "XMP metadata", has_xmp, {}),
            _result(
                "png_text",
                "Text metadata",
                bool(text_keywords) or b"tIME" in types,
                {"keywords": text_keywords},
            ),
        ]

    if suffix == ".webp":
        try:
            found = webp.parse_chunks(data)
        except webp.NotAWebpError as exc:
            return [_result("exif", "EXIF metadata", False, {"error": str(exc)})]
        fourccs = [c.fourcc for c in found]
        return [
            _result("exif", "EXIF metadata", b"EXIF" in fourccs, {}),
            _result("xmp", "XMP metadata", b"XMP " in fourccs, {}),
        ]

    return []


def inspect_pdf_metadata(path: Path) -> list[DetectionResult]:
    results: list[DetectionResult] = []
    with pikepdf.open(str(path)) as pdf:
        docinfo = pdf.docinfo
        info_fields = {}
        if docinfo is not None:
            for key in docinfo:
                try:
                    info_fields[str(key)] = str(docinfo[key])
                except Exception:  # noqa: BLE001 - defensive, PDF metadata is untrusted
                    info_fields[str(key)] = "<unreadable>"
        results.append(
            _result("pdf_info", "Document metadata", bool(info_fields), {"fields": info_fields})
        )

        has_xmp = "/Metadata" in pdf.Root
        xmp_preview = ""
        if has_xmp:
            try:
                xmp_bytes = bytes(pdf.Root.Metadata.read_bytes())
                xmp_preview = xmp_bytes[:200].decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                xmp_preview = "<unreadable>"
        results.append(
            _result("pdf_xmp", "XMP metadata", has_xmp, {"preview": xmp_preview})
        )
    return results
