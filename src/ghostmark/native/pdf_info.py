"""Native PDF DocInfo classifier (pikepdf resolves the object graph).

Provenance:
- PUBLIC_SPEC: ISO 32000-1 section 14.3.3 (document information
  dictionary keys and meanings).
- THIRD_PARTY_LIBRARY: pikepdf (MPL-2.0, existing dependency) parses the
  PDF object graph and resolves incremental updates, so the DocInfo we
  classify is the effective "latest wins" view; string decoding
  (PDFDocEncoding / UTF-16) is pikepdf's.
- OWN_IMPLEMENTATION: classification.
"""

from __future__ import annotations

from ghostmark.native.signals import MetadataField, SignalCategory, make_preview

# Standard DocInfo keys (ISO 32000-1 Table 317) -> category.
_DOCINFO_KEYS: dict[str, SignalCategory] = {
    "/Title": SignalCategory.DESCRIPTION,
    "/Author": SignalCategory.AUTHOR,
    "/Subject": SignalCategory.DESCRIPTION,
    "/Keywords": SignalCategory.DESCRIPTION,
    "/Creator": SignalCategory.CREATOR,
    "/Producer": SignalCategory.PRODUCER,
    "/CreationDate": SignalCategory.TIMESTAMP,
    "/ModDate": SignalCategory.TIMESTAMP,
}


def classify_docinfo_fields(info_fields: dict[str, str],
                            *, container: str = "pdf_docinfo") -> list[MetadataField]:
    """Normalize an already-extracted DocInfo key->string mapping."""

    fields: list[MetadataField] = []
    for key, value in info_fields.items():
        category = _DOCINFO_KEYS.get(key, SignalCategory.PDF_DOCINFO)
        fields.append(MetadataField(container, key, category, make_preview(value)))
    return fields
