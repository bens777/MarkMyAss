"""Native EXIF/TIFF reader: a bounded IFD walker for privacy/provenance tags.

Provenance:
- PUBLIC_SPEC: TIFF 6.0 (byte order marks, IFD layout, the twelve field
  types and their sizes) and Exif 2.32 / CIPA DC-008 (the tag IDs below,
  the 0x8769 Exif-IFD and 0x8825 GPS-IFD pointer tags, and UserComment's
  8-byte character-code header). All structure and all tag names come
  from those specifications.
- EXIFTOOL_BEHAVIOR: two things only -- (1) real files contain broken
  offsets/cyclic IFD pointers, so a robust reader needs hard bounds and
  a visited-set rather than trusting the structure; (2) some writers
  fill UserComment's charset header with nonstandard casing, so charset
  sniffing should be tolerant and fall back to a lossy decode. No
  ExifTool code, tables, or structure were copied.
- OWN_IMPLEMENTATION: everything else.

Scope control: this is NOT a general TIFF reader. It surfaces a small
whitelist of identity/provenance/privacy tags plus the *presence* of GPS
data, and counts everything else without decoding it. MakerNotes,
thumbnails, interop IFDs and vendor tags are deliberately out of scope.
"""

from __future__ import annotations

from ghostmark.native.signals import MetadataField, SignalCategory, make_preview

# Hard safety bounds for hostile input (all own choices, not spec values).
_MAX_IFDS = 8               # IFD0 + Exif + GPS + IFD1 chain, with headroom
_MAX_ENTRIES_PER_IFD = 256
_MAX_INLINE_VALUE_BYTES = 4096

# TIFF field type -> byte size (TIFF 6.0 section 2).
_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}
_ASCII = 2
_UNDEFINED = 7

# Exif/TIFF tag IDs (Exif 2.32 tables) -> (spec tag name, category).
_IFD0_TAGS = {
    0x010E: ("ImageDescription", SignalCategory.DESCRIPTION),
    0x010F: ("Make", SignalCategory.EXIF),
    0x0110: ("Model", SignalCategory.EXIF),
    0x0131: ("Software", SignalCategory.SOFTWARE),
    0x0132: ("ModifyDate", SignalCategory.TIMESTAMP),
    0x013B: ("Artist", SignalCategory.AUTHOR),
    0x8298: ("Copyright", SignalCategory.AUTHOR),
}
_EXIF_IFD_TAGS = {
    0x9003: ("DateTimeOriginal", SignalCategory.TIMESTAMP),
    0x9004: ("CreateDate", SignalCategory.TIMESTAMP),
    0x9286: ("UserComment", SignalCategory.COMMENTS),
    0xA430: ("OwnerName", SignalCategory.AUTHOR),
    0xA433: ("LensMake", SignalCategory.EXIF),
}
_POINTER_EXIF_IFD = 0x8769
_POINTER_GPS_IFD = 0x8825

# GPS IFD tag names we name explicitly (Exif 2.32 GPS attribute table);
# any other tag in the GPS IFD still counts as a GPS signal.
_GPS_TAG_NAMES = {
    0x0001: "GPSLatitudeRef",
    0x0002: "GPSLatitude",
    0x0003: "GPSLongitudeRef",
    0x0004: "GPSLongitude",
    0x0006: "GPSAltitude",
    0x0007: "GPSTimeStamp",
    0x001D: "GPSDateStamp",
}

EXIF_PREFIX = b"Exif\x00\x00"


class ExifParseError(ValueError):
    pass


def _decode_user_comment(raw: bytes) -> str:
    """Exif 2.32: UserComment = 8-byte character-code header + payload."""

    if len(raw) < 8:
        return make_preview(raw)
    code, payload = raw[:8], raw[8:]
    code_upper = code.upper()
    if code_upper.startswith(b"ASCII"):
        return make_preview(payload.decode("ascii", errors="replace"))
    if code_upper.startswith(b"UNICODE"):
        # Exif says UCS-2; byte order follows the TIFF header in theory,
        # but real files vary -- try both and keep the cleaner result.
        be = payload.decode("utf-16-be", errors="replace")
        le = payload.decode("utf-16-le", errors="replace")
        return make_preview(min((be, le), key=lambda s: s.count("�")))
    return make_preview(payload)


def parse_exif_fields(payload: bytes, *, container: str = "exif") -> list[MetadataField]:
    """Walk a TIFF structure and return the whitelisted metadata fields.

    ``payload`` may start with the Exif APP1 prefix (``Exif\\0\\0``) or be
    raw TIFF (PNG eXIf; WebP EXIF chunks exist in both forms). Never
    raises on malformed input past the header -- it reports what it
    could read safely and stops.
    """

    if payload.startswith(EXIF_PREFIX):
        payload = payload[len(EXIF_PREFIX):]

    n = len(payload)
    if n < 8:
        raise ExifParseError("EXIF payload too short for a TIFF header")
    if payload[0:2] == b"II":
        order = "little"
    elif payload[0:2] == b"MM":
        order = "big"
    else:
        raise ExifParseError("EXIF payload missing TIFF byte-order mark")

    def u16(off: int) -> int:
        return int.from_bytes(payload[off:off + 2], order)

    def u32(off: int) -> int:
        return int.from_bytes(payload[off:off + 4], order)

    if u16(2) != 42:
        raise ExifParseError("EXIF payload missing TIFF magic 42")

    fields: list[MetadataField] = []
    other_tag_count = 0
    visited: set[int] = set()
    # (offset, table, is_gps) work queue seeded with IFD0.
    queue: list[tuple[int, dict, bool]] = [(u32(4), _IFD0_TAGS, False)]
    ifds_walked = 0

    def read_value(vtype: int, count: int, value_field_off: int) -> bytes | None:
        size = _TYPE_SIZES.get(vtype)
        if size is None:
            return None
        total = size * count
        if total > _MAX_INLINE_VALUE_BYTES:
            return None
        if total <= 4:
            return payload[value_field_off:value_field_off + total]
        data_off = u32(value_field_off)
        if data_off + total > n:
            return None
        return payload[data_off:data_off + total]

    while queue and ifds_walked < _MAX_IFDS:
        ifd_off, table, is_gps = queue.pop(0)
        if ifd_off in visited or ifd_off == 0 or ifd_off + 2 > n:
            continue
        visited.add(ifd_off)
        ifds_walked += 1

        count = u16(ifd_off)
        if count > _MAX_ENTRIES_PER_IFD:
            count = _MAX_ENTRIES_PER_IFD
        entries_end = ifd_off + 2 + count * 12
        if entries_end > n:
            count = max(0, (n - ifd_off - 2) // 12)
            entries_end = ifd_off + 2 + count * 12

        for i in range(count):
            e = ifd_off + 2 + i * 12
            tag_id = u16(e)
            vtype = u16(e + 2)
            vcount = u32(e + 4)

            if tag_id == _POINTER_EXIF_IFD and not is_gps:
                queue.append((u32(e + 8), _EXIF_IFD_TAGS, False))
                continue
            if tag_id == _POINTER_GPS_IFD and not is_gps:
                queue.append((u32(e + 8), {}, True))
                continue

            if is_gps:
                name = _GPS_TAG_NAMES.get(tag_id, f"GPSTag{tag_id:#06x}")
                fields.append(MetadataField(container, name, SignalCategory.GPS,
                                            "(location data present)"))
                continue

            known = table.get(tag_id)
            if known is None:
                other_tag_count += 1
                continue
            name, category = known
            raw = read_value(vtype, vcount, e + 8)
            if raw is None:
                preview = "(unreadable value)"
            elif tag_id == 0x9286:
                preview = _decode_user_comment(raw)
            elif vtype == _ASCII:
                preview = make_preview(raw.split(b"\x00", 1)[0])
            elif vtype == _UNDEFINED:
                preview = make_preview(raw)
            else:
                preview = "(binary value)"
            fields.append(MetadataField(container, name, category, preview))

        # We do not follow the next-IFD chain (IFD1 = thumbnail; out of scope).

    if other_tag_count:
        fields.append(MetadataField(
            container, "OtherTags", SignalCategory.UNKNOWN_METADATA,
            f"{other_tag_count} additional EXIF tag(s) not individually decoded",
        ))
    return fields
