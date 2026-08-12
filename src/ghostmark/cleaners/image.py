"""Image metadata cleaning: strip EXIF/XMP/IPTC/comments without recompressing.

Every format is handled by deleting whole segments/chunks from the raw file
bytes (see ``ghostmark.formats``). Pixel data, ICC color profiles, and
(for animated PNG/WebP) animation chunks are never touched, so the visible
image is byte-identical to the source.
"""

from __future__ import annotations

from pathlib import Path

from ghostmark.formats import jpeg, png, webp
from ghostmark.models import CleanAction

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def clean_image_bytes(data: bytes, suffix: str) -> tuple[bytes, list[CleanAction]]:
    suffix = suffix.lower()

    if suffix in (".jpg", ".jpeg"):
        cleaned, found = jpeg.strip_metadata(data)
        return cleaned, [
            CleanAction("exif", "EXIF metadata", True, found["exif"], not found["exif"], False,
                        "Removed." if found["exif"] else "Not present."),
            CleanAction("xmp", "XMP metadata", True, found["xmp"], not found["xmp"], False,
                        "Removed." if found["xmp"] else "Not present."),
            CleanAction("iptc", "IPTC metadata", True, found["iptc"], not found["iptc"], False,
                        "Removed." if found["iptc"] else "Not present."),
            CleanAction("comment", "Comment metadata", True, found["comment"], not found["comment"], False,
                        "Removed." if found["comment"] else "Not present."),
            CleanAction("icc", "ICC color profile", False, False, True, False, "Preserved (untouched)."),
        ]

    if suffix == ".png":
        cleaned, found = png.strip_metadata(data)
        return cleaned, [
            CleanAction("exif", "EXIF metadata", True, found["exif"], not found["exif"], False,
                        "Removed." if found["exif"] else "Not present."),
            CleanAction("xmp", "XMP metadata", True, found["xmp"], not found["xmp"], False,
                        "Removed." if found["xmp"] else "Not present."),
            CleanAction("png_text", "Text metadata", True, found["text"], not found["text"], False,
                        "Removed." if found["text"] else "Not present."),
            CleanAction("icc", "ICC color profile", False, False, True, False, "Preserved (untouched)."),
        ]

    if suffix == ".webp":
        cleaned, found = webp.strip_metadata(data)
        return cleaned, [
            CleanAction("exif", "EXIF metadata", True, found["exif"], not found["exif"], False,
                        "Removed." if found["exif"] else "Not present."),
            CleanAction("xmp", "XMP metadata", True, found["xmp"], not found["xmp"], False,
                        "Removed." if found["xmp"] else "Not present."),
            CleanAction("icc", "ICC color profile", False, False, True, False, "Preserved (untouched)."),
        ]

    raise ValueError(f"Unsupported image format: {suffix}")


def clean_image_file(path: Path) -> tuple[bytes, list[CleanAction]]:
    return clean_image_bytes(path.read_bytes(), path.suffix)
