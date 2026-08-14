"""Native XMP reader: bounded pattern extraction of provenance properties.

Provenance:
- PUBLIC_SPEC: Adobe XMP Specification Part 1 (property model, core
  namespaces: dc, xmp, xmpMM, photoshop, pdf) and the IPTC Extension
  schema (Iptc4xmpExt:DigitalSourceType -- whose
  ``trainedAlgorithmicMedia`` value is the standardized "created by
  generative AI" marker). Property names below are the specs' own names.
- EXIFTOOL_BEHAVIOR: one structural fact -- the same logical property
  appears in the wild either as an XML attribute
  (``ns:Prop="value"``) or as an element (``<ns:Prop>value</ns:Prop>``),
  with multi-valued properties as rdf Seq/Bag/Alt item lists, so an
  extractor must accept all three shapes. No code or tables copied.
- OWN_IMPLEMENTATION: the extraction strategy. This is deliberately NOT
  an XML parser: uploaded files are hostile, and a size-capped
  regex scan over a fixed property whitelist has no entity expansion,
  no parser state, and linear cost. MarkMyAss removes XMP whole-packet
  (container level), so lossless parsing is not required -- only honest
  reporting of what the packet contains.
"""

from __future__ import annotations

import re

from ghostmark.native.signals import MetadataField, SignalCategory, make_preview

# Never scan more than this many bytes of a hostile packet.
_SCAN_CAP = 512 * 1024

# property name (with namespace prefix) -> category. Names per the XMP /
# Dublin Core / IPTC Extension specifications.
_PROPERTIES: dict[str, SignalCategory] = {
    "dc:creator": SignalCategory.AUTHOR,
    "dc:rights": SignalCategory.AUTHOR,
    "dc:description": SignalCategory.DESCRIPTION,
    "dc:title": SignalCategory.DESCRIPTION,
    "dc:subject": SignalCategory.DESCRIPTION,
    "xmp:CreatorTool": SignalCategory.SOFTWARE,
    "xmp:CreateDate": SignalCategory.TIMESTAMP,
    "xmp:ModifyDate": SignalCategory.TIMESTAMP,
    "xmp:MetadataDate": SignalCategory.TIMESTAMP,
    "photoshop:Credit": SignalCategory.CREATOR,
    "photoshop:Source": SignalCategory.CREATOR,
    "pdf:Producer": SignalCategory.PRODUCER,
    "xmpMM:DocumentID": SignalCategory.PROVENANCE,
    "xmpMM:InstanceID": SignalCategory.PROVENANCE,
    "xmpMM:OriginalDocumentID": SignalCategory.PROVENANCE,
    "xmpMM:History": SignalCategory.PROVENANCE,
    "Iptc4xmpExt:DigitalSourceType": SignalCategory.PROVENANCE,
    "exif:GPSLatitude": SignalCategory.GPS,
    "exif:GPSLongitude": SignalCategory.GPS,
}

# One value inside an rdf list item: <rdf:li ...>value</rdf:li>
_LI_RE = re.compile(rb"<rdf:li[^>]*>(.*?)</rdf:li>", re.S)


def _element_re(prop: bytes) -> re.Pattern[bytes]:
    # <ns:Prop possible-attributes> value </ns:Prop> -- the opening tag's
    # own attributes are consumed before the capture starts.
    return re.compile(rb"<" + prop + rb"(?:\s[^>]{0,512})?>(.{0,4096}?)</" + prop + rb">", re.S)


def _attribute_re(prop: bytes) -> re.Pattern[bytes]:
    # ns:Prop="value" or ns:Prop='value'
    return re.compile(prop + rb"\s*=\s*[\"']([^\"']{0,4096})[\"']")


def _strip_markup(fragment: bytes) -> bytes:
    # For element form: prefer rdf:li item values when present, else
    # drop any residual tags for the preview.
    items = _LI_RE.findall(fragment)
    if items:
        fragment = b"; ".join(items[:5])
    return re.sub(rb"<[^>]{0,200}>", b" ", fragment)


def _maybe_transcode_utf16(data: bytes) -> bytes:
    """Normalize UTF-16 XMP packets (allowed by XMP Spec Part 1) to UTF-8.

    Detected via BOM or via NUL-interleaved angle brackets; anything that
    fails to decode is returned unchanged (the ASCII scan then simply
    finds nothing -- never an error path for hostile bytes).
    """

    is_utf16 = data[:2] in (b"\xfe\xff", b"\xff\xfe") or \
        data[:2] == b"<\x00" or data[:2] == b"\x00<"
    if not is_utf16:
        return data
    try:
        return data.decode("utf-16", errors="strict").encode("utf-8")
    except UnicodeDecodeError:
        for enc in ("utf-16-le", "utf-16-be"):
            try:
                return data.decode(enc, errors="strict").encode("utf-8")
            except UnicodeDecodeError:
                continue
    return data


def parse_xmp_fields(packet: bytes, *, container: str = "xmp") -> list[MetadataField]:
    """Extract whitelisted provenance/privacy properties from an XMP packet."""

    data = _maybe_transcode_utf16(packet[:_SCAN_CAP])
    fields: list[MetadataField] = []

    for prop_name, category in _PROPERTIES.items():
        prop = prop_name.encode("ascii")
        value: bytes | None = None

        m = _element_re(prop).search(data)
        if m:
            value = _strip_markup(m.group(1))
        else:
            m = _attribute_re(prop).search(data)
            if m:
                value = m.group(1)

        if value is None:
            continue
        preview = make_preview(value)
        if prop_name == "xmpMM:History" and not preview:
            preview = "(edit history present)"
        fields.append(MetadataField(container, prop_name, category, preview))

    return fields
