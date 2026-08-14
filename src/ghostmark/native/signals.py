"""Normalized signal model for the native metadata engine.

Provenance: OWN_IMPLEMENTATION (plain data model; no external source).

Every native parser (EXIF/TIFF, XMP, IPTC, PNG text, PDF DocInfo)
normalizes what it finds into :class:`MetadataField` records so the
inspector, verifier, receipts and UI all speak one vocabulary regardless
of which container a value came from. Raw tag names are preserved
alongside the normalized category.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

# Value previews are for humans (UI, receipts, logs) -- they are never
# used for round-tripping, so truncation is safe and keeps hostile
# multi-megabyte values from ballooning reports.
PREVIEW_MAX_CHARS = 120


class SignalCategory(StrEnum):
    """What kind of privacy/provenance signal a metadata field represents."""

    AUTHOR = "author"
    CREATOR = "creator"
    PRODUCER = "producer"
    SOFTWARE = "software"
    COMMENTS = "comments"
    DESCRIPTION = "description"
    GPS = "gps"
    TIMESTAMP = "timestamp"
    EXIF = "exif"
    XMP = "xmp"
    IPTC = "iptc"
    PNG_TEXT = "png_text"
    PDF_DOCINFO = "pdf_docinfo"
    PROVENANCE = "provenance"
    C2PA = "c2pa"
    HIDDEN_UNICODE = "hidden_unicode"
    UNKNOWN_METADATA = "unknown_metadata"


@dataclass(frozen=True)
class MetadataField:
    """One normalized metadata field found inside a container payload.

    ``container`` says where it physically lives (``exif``, ``xmp``,
    ``iptc``, ``png_text``, ``pdf_docinfo``, ``webp_exif``, ...);
    ``tag`` preserves the raw/spec tag name (``Artist``, ``dc:creator``,
    ``By-line``, ``parameters``, ``/Author``); ``category`` is the
    normalized meaning used for reporting and differential testing.
    """

    container: str
    tag: str
    category: SignalCategory
    preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "container": self.container,
            "tag": self.tag,
            "category": self.category.value,
            "preview": self.preview,
        }


def make_preview(raw: bytes | str) -> str:
    """Render an untrusted value as a short, printable, single-line preview."""

    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    text = "".join(ch if ch.isprintable() else " " for ch in text)
    text = " ".join(text.split())
    if len(text) > PREVIEW_MAX_CHARS:
        text = text[: PREVIEW_MAX_CHARS - 1] + "…"
    return text


def fields_to_details(fields: list[MetadataField]) -> list[dict[str, Any]]:
    """Serialize fields for a DetectionResult's free-form ``details`` dict."""

    return [f.to_dict() for f in fields]


def categories_present(fields: list[MetadataField]) -> list[str]:
    """Sorted unique category values -- the unit of differential testing."""

    return sorted({f.category.value for f in fields})
