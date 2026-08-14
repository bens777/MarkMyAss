"""Native IPTC IIM reader: Photoshop 8BIM resources -> IIM datasets.

Provenance:
- PUBLIC_SPEC: Adobe Photoshop File Formats specification (image
  resource blocks: ``8BIM`` signature, 16-bit resource ID -- 0x0404
  carries IPTC -- Pascal-string name padded to even length, 32-bit data
  size, data padded to even length) and the IPTC-NAA Information
  Interchange Model v4 (dataset wire format and the record 2 dataset
  numbers/names used below).
- EXIFTOOL_SOURCE_RESEARCH: real-world tolerances only, learned by
  studying how a mature reader hardens this format: writers null-pad
  IPTC blocks (trailing zeros are not an error); the 16-bit dataset
  length's high bit flags an "extended" length whose low 15 bits give
  the byte-count (sanity-capped) of a following big-endian length
  integer; records may arrive out of order. These behaviors are
  implemented here independently -- no code, comments, or tables copied.
- OWN_IMPLEMENTATION: everything else.
"""

from __future__ import annotations

from ghostmark.native.signals import MetadataField, SignalCategory, make_preview

PHOTOSHOP_PREFIX = b"Photoshop 3.0\x00"
_8BIM = b"8BIM"
_IPTC_RESOURCE_ID = 0x0404
_DATASET_MARKER = 0x1C
_MAX_DATASETS = 512
_MAX_EXTENDED_LEN_BYTES = 8

# IIM record 2 (application record) datasets relevant to MarkMyAss.
# Names per the IIM v4 specification.
_RECORD2_TAGS: dict[int, tuple[str, SignalCategory]] = {
    25: ("Keywords", SignalCategory.DESCRIPTION),
    55: ("DateCreated", SignalCategory.TIMESTAMP),
    60: ("TimeCreated", SignalCategory.TIMESTAMP),
    65: ("OriginatingProgram", SignalCategory.SOFTWARE),
    70: ("ProgramVersion", SignalCategory.SOFTWARE),
    80: ("By-line", SignalCategory.AUTHOR),
    85: ("By-lineTitle", SignalCategory.AUTHOR),
    105: ("Headline", SignalCategory.DESCRIPTION),
    110: ("Credit", SignalCategory.CREATOR),
    115: ("Source", SignalCategory.CREATOR),
    116: ("CopyrightNotice", SignalCategory.AUTHOR),
    120: ("Caption-Abstract", SignalCategory.DESCRIPTION),
    122: ("Writer-Editor", SignalCategory.AUTHOR),
}


def _iter_8bim_resources(data: bytes):
    """Yield (resource_id, payload) for each Photoshop image resource block."""

    pos = 0
    n = len(data)
    while pos + 12 <= n:
        if data[pos:pos + 4] != _8BIM:
            break
        res_id = int.from_bytes(data[pos + 4:pos + 6], "big")
        pos += 6
        # Pascal name: length byte + bytes, padded so (1 + len) is even.
        name_len = data[pos]
        pos += 1 + name_len
        if (1 + name_len) % 2:
            pos += 1
        if pos + 4 > n:
            break
        size = int.from_bytes(data[pos:pos + 4], "big")
        pos += 4
        if pos + size > n:
            break
        yield res_id, data[pos:pos + size]
        pos += size + (size % 2)


def _iter_iim_datasets(block: bytes):
    """Yield (record, dataset, value) for each IIM dataset in a block."""

    pos = 0
    n = len(block)
    emitted = 0
    while pos + 5 <= n and emitted < _MAX_DATASETS:
        marker = block[pos]
        if marker != _DATASET_MARKER:
            # Tolerate trailing null padding; stop on anything else.
            if marker == 0 and not any(block[pos:]):
                break
            break
        record = block[pos + 1]
        dataset = block[pos + 2]
        length = int.from_bytes(block[pos + 3:pos + 5], "big")
        pos += 5
        if length & 0x8000:
            len_bytes = length & 0x7FFF
            if len_bytes > _MAX_EXTENDED_LEN_BYTES or pos + len_bytes > n:
                break
            length = int.from_bytes(block[pos:pos + len_bytes], "big")
            pos += len_bytes
        if pos + length > n:
            break
        yield record, dataset, block[pos:pos + length]
        pos += length
        emitted += 1


def parse_iptc_fields(payload: bytes, *, container: str = "iptc") -> list[MetadataField]:
    """Extract IIM record-2 identity/provenance datasets from an APP13 payload.

    ``payload`` is the APP13 segment body, with or without the
    ``Photoshop 3.0\\0`` prefix.
    """

    if payload.startswith(PHOTOSHOP_PREFIX):
        payload = payload[len(PHOTOSHOP_PREFIX):]

    fields: list[MetadataField] = []
    other_count = 0

    for res_id, block in _iter_8bim_resources(payload):
        if res_id != _IPTC_RESOURCE_ID:
            continue
        for record, dataset, value in _iter_iim_datasets(block):
            if record != 2:
                other_count += 1
                continue
            known = _RECORD2_TAGS.get(dataset)
            if known is None:
                other_count += 1
                continue
            name, category = known
            fields.append(MetadataField(container, name, category, make_preview(value)))

    if other_count:
        fields.append(MetadataField(
            container, "OtherDatasets", SignalCategory.UNKNOWN_METADATA,
            f"{other_count} additional IPTC dataset(s) not individually decoded",
        ))
    return fields
