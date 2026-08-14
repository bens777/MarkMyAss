"""Detection of EXIF/XMP/IPTC (images) and document-info/XMP (PDF) metadata.

Detection is container-level (which metadata blocks exist), enriched by
MarkMyAss's native tag-level engine (``ghostmark.native``) so every
result also reports WHAT is inside: author/creator/software/GPS/
timestamps/AI-provenance markers, normalized into
:class:`~ghostmark.native.signals.MetadataField` records under
``details["fields"]``. All of it is pure Python -- no ExifTool required.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pikepdf

from ghostmark.formats import jpeg, png, webp
from ghostmark.models import Category, Confidence, DetectionResult, Status
from ghostmark.native import exif_tiff, iptc, pdf_info, png_text, xmp
from ghostmark.native.signals import MetadataField, fields_to_details

_XMP_ITXT_KEYWORD = b"XML:com.adobe.xmp\x00"


def enhanced_metadata_available() -> bool:
    """Whether the optional external cross-checker (ExifTool) is installed.

    MarkMyAss's own inspect/clean/verify pipeline never requires
    ExifTool -- this flag only tells the UI/CLI whether the *independent*
    second opinion can run on this machine.
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


def _safe_fields(parser, payload: bytes, **kwargs) -> tuple[list[MetadataField], str | None]:
    """Run a native parser on hostile bytes; never let it break inspection."""

    try:
        return parser(payload, **kwargs), None
    except Exception as exc:  # noqa: BLE001 - uploaded data is untrusted
        return [], f"{type(exc).__name__}: {exc}"


def _details(fields: list[MetadataField], error: str | None, **extra) -> dict:
    out: dict = {**extra}
    if fields:
        out["fields"] = fields_to_details(fields)
    if error:
        out["parse_error"] = error
    return out


def inspect_image_metadata(path: Path) -> list[DetectionResult]:
    data = path.read_bytes()
    suffix = path.suffix.lower()

    if suffix in (".jpg", ".jpeg"):
        try:
            segments, _ = jpeg.parse_header_segments(data)
        except jpeg.NotAJpegError as exc:
            return [_result("exif", "EXIF metadata", False, {"error": str(exc)})]

        exif_fields: list[MetadataField] = []
        xmp_fields: list[MetadataField] = []
        iptc_fields: list[MetadataField] = []
        errors: dict[str, str | None] = {"exif": None, "xmp": None, "iptc": None}
        kinds = []
        comment_previews: list[str] = []

        for seg in segments:
            kind = seg.kind()
            kinds.append(kind)
            if kind == "exif":
                f, errors["exif"] = _safe_fields(exif_tiff.parse_exif_fields, seg.payload)
                exif_fields.extend(f)
            elif kind == "xmp":
                if seg.payload.startswith(jpeg.EXTENDED_XMP_PREFIX):
                    # Extended XMP overflow (XMP Spec Part 3): prefix,
                    # 32-byte GUID, 4-byte total length, 4-byte offset,
                    # then the serialized XMP data portion.
                    packet = seg.payload[len(jpeg.EXTENDED_XMP_PREFIX) + 40:]
                else:
                    packet = seg.payload[len(jpeg.XMP_PREFIX):]
                f, errors["xmp"] = _safe_fields(xmp.parse_xmp_fields, packet)
                xmp_fields.extend(f)
            elif kind == "iptc":
                f, errors["iptc"] = _safe_fields(iptc.parse_iptc_fields, seg.payload)
                iptc_fields.extend(f)
            elif kind == "comment":
                from ghostmark.native.signals import make_preview
                comment_previews.append(make_preview(seg.payload))

        return [
            _result("exif", "EXIF metadata", "exif" in kinds,
                    _details(exif_fields, errors["exif"], segments=kinds.count("exif"))),
            _result("xmp", "XMP metadata", "xmp" in kinds,
                    _details(xmp_fields, errors["xmp"], segments=kinds.count("xmp"))),
            _result("iptc", "IPTC metadata", "iptc" in kinds,
                    _details(iptc_fields, errors["iptc"], segments=kinds.count("iptc"))),
            _result("comment", "Comment metadata", "comment" in kinds,
                    {"segments": kinds.count("comment"), "previews": comment_previews[:5]}),
        ]

    if suffix == ".png":
        try:
            chunks = png.parse_chunks(data)
        except png.NotAPngError as exc:
            return [_result("exif", "EXIF metadata", False, {"error": str(exc)})]

        types = [c.type for c in chunks]
        text_fields: list[MetadataField] = []
        exif_fields = []
        xmp_fields = []
        errors = {"exif": None, "xmp": None}
        text_keywords: list[str] = []
        has_xmp = False

        for c in chunks:
            if c.type in (b"tEXt", b"iTXt") and c.data.startswith(_XMP_ITXT_KEYWORD):
                has_xmp = True
                packet = c.data[len(_XMP_ITXT_KEYWORD):]
                if c.type == b"iTXt":
                    # skip compression flag/method + language + translated kw
                    parts = packet.split(b"\x00", 2)
                    packet = parts[2] if len(parts) == 3 else packet
                f, errors["xmp"] = _safe_fields(xmp.parse_xmp_fields, packet)
                xmp_fields.extend(f)
                continue
            if c.type in (b"tEXt", b"zTXt", b"iTXt"):
                field = png_text.parse_text_chunk_field(c.type, c.data)
                if field is not None:
                    text_fields.append(field)
                    text_keywords.append(field.tag)
                continue
            if c.type == b"eXIf":
                f, errors["exif"] = _safe_fields(
                    exif_tiff.parse_exif_fields, c.data, container="png_exif")
                exif_fields.extend(f)

        return [
            _result("exif", "EXIF metadata", b"eXIf" in types,
                    _details(exif_fields, errors["exif"])),
            _result("xmp", "XMP metadata", has_xmp, _details(xmp_fields, errors["xmp"])),
            _result(
                "png_text",
                "Text metadata",
                bool(text_fields) or b"tIME" in types,
                _details(text_fields, None, keywords=text_keywords),
            ),
        ]

    if suffix == ".webp":
        try:
            found = webp.parse_chunks(data)
        except webp.NotAWebpError as exc:
            return [_result("exif", "EXIF metadata", False, {"error": str(exc)})]

        fourccs = [c.fourcc for c in found]
        exif_fields = []
        xmp_fields = []
        errors = {"exif": None, "xmp": None}
        for c in found:
            if c.fourcc == b"EXIF":
                # WebP spec says raw TIFF; files with an Exif\0\0 prefix
                # also exist in the wild -- parse_exif_fields sniffs both.
                f, errors["exif"] = _safe_fields(
                    exif_tiff.parse_exif_fields, c.data, container="webp_exif")
                exif_fields.extend(f)
            elif c.fourcc == b"XMP ":
                f, errors["xmp"] = _safe_fields(
                    xmp.parse_xmp_fields, c.data, container="webp_xmp")
                xmp_fields.extend(f)

        return [
            _result("exif", "EXIF metadata", b"EXIF" in fourccs,
                    _details(exif_fields, errors["exif"])),
            _result("xmp", "XMP metadata", b"XMP " in fourccs,
                    _details(xmp_fields, errors["xmp"])),
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
        docinfo_fields = pdf_info.classify_docinfo_fields(info_fields)
        results.append(
            _result("pdf_info", "Document metadata", bool(info_fields),
                    _details(docinfo_fields, None, fields_raw=info_fields))
        )

        has_xmp = "/Metadata" in pdf.Root
        xmp_fields: list[MetadataField] = []
        xmp_error: str | None = None
        xmp_preview = ""
        if has_xmp:
            try:
                xmp_bytes = bytes(pdf.Root.Metadata.read_bytes())
                xmp_preview = xmp_bytes[:200].decode("utf-8", errors="replace")
                xmp_fields, xmp_error = _safe_fields(
                    xmp.parse_xmp_fields, xmp_bytes, container="pdf_xmp")
            except Exception:  # noqa: BLE001
                xmp_preview = "<unreadable>"
        results.append(
            _result("pdf_xmp", "XMP metadata", has_xmp,
                    _details(xmp_fields, xmp_error, preview=xmp_preview))
        )
    return results
