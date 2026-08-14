"""Segment-level JPEG parsing so metadata can be stripped without recompression.

JPEG structure: SOI, then a sequence of marker segments, then a Start Of
Scan (SOS) segment followed by entropy-coded scan data that runs until EOI.
We only need to parse segments *before* SOS -- once SOS is reached the rest
of the file (scan data + EOI, and any trailing scans for progressive JPEGs)
is copied through verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass

SOI = 0xD8
EOI = 0xD9
SOS = 0xDA
APP0 = 0xE0
APP1 = 0xE1
APP2 = 0xE2
APP11 = 0xEB
APP13 = 0xED
APP14 = 0xEE
COM = 0xFE

# Markers with no length field / no payload.
_NO_PAYLOAD = {0x01, EOI, SOI} | set(range(0xD0, 0xD8))

EXIF_PREFIX = b"Exif\x00\x00"
XMP_PREFIX = b"http://ns.adobe.com/xap/1.0/\x00"
# Multi-segment "Extended XMP" (XMP Spec Part 3): additional APP1
# segments carrying overflow XMP data under their own namespace URI,
# followed by a 32-byte GUID, 4-byte total length and 4-byte offset.
EXTENDED_XMP_PREFIX = b"http://ns.adobe.com/xmp/extension/\x00"
PHOTOSHOP_PREFIX = b"Photoshop 3.0\x00"
ICC_PREFIX = b"ICC_PROFILE\x00"
JUMBF_PREFIX = b"JP"  # ISO/IEC 19566-5 APP11 payload starts with a JPEG-XT box marker


class NotAJpegError(ValueError):
    pass


@dataclass
class Segment:
    marker: int
    payload: bytes  # excludes the 2-byte length field itself

    def kind(self) -> str:
        if self.marker == APP1 and self.payload.startswith(EXIF_PREFIX):
            return "exif"
        if self.marker == APP1 and (self.payload.startswith(XMP_PREFIX)
                                    or self.payload.startswith(EXTENDED_XMP_PREFIX)):
            # Extended XMP overflow segments are XMP too: they must be
            # detected AND removed together with the main packet, or a
            # "cleaned" file would still carry most of its XMP data.
            return "xmp"
        if self.marker == APP13 and self.payload.startswith(PHOTOSHOP_PREFIX):
            return "iptc"
        if self.marker == APP11:
            return "c2pa"
        if self.marker == COM:
            return "comment"
        if self.marker == APP2 and self.payload.startswith(ICC_PREFIX):
            return "icc"
        return "other"


def parse_header_segments(data: bytes) -> tuple[list[Segment], bytes]:
    """Parse segments up to (and including) SOS.

    Returns ``(segments, rest)`` where ``rest`` is everything in the file
    starting at the SOS segment's scan data (i.e. after the SOS segment's own
    header+payload) through EOI, copied verbatim.
    """

    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        raise NotAJpegError("Not a JPEG file (missing SOI marker)")

    segments: list[Segment] = []
    pos = 2  # past SOI
    n = len(data)
    while pos < n:
        if data[pos] != 0xFF:
            raise NotAJpegError(f"Expected marker at offset {pos}")
        # Skip fill bytes (0xFF padding before a marker).
        marker_pos = pos
        while marker_pos < n and data[marker_pos] == 0xFF:
            marker_pos += 1
        if marker_pos >= n:
            raise NotAJpegError("Truncated JPEG")
        marker = data[marker_pos]
        pos = marker_pos + 1

        if marker in _NO_PAYLOAD:
            continue
        if marker == SOS:
            if pos + 2 > n:
                raise NotAJpegError("Truncated SOS segment")
            length = int.from_bytes(data[pos : pos + 2], "big")
            # payload holds the marker bytes + length field + payload verbatim,
            # since SOS is reproduced as-is in rebuild() rather than re-framed.
            segments.append(Segment(marker=SOS, payload=data[pos - 2 : pos + length]))
            rest = data[pos + length :]
            return segments, rest
        if pos + 2 > n:
            raise NotAJpegError("Truncated segment length")
        length = int.from_bytes(data[pos : pos + 2], "big")
        if length < 2 or pos + length > n:
            raise NotAJpegError("Invalid segment length")
        payload = data[pos + 2 : pos + length]
        segments.append(Segment(marker=marker, payload=payload))
        pos += length

    raise NotAJpegError("Reached end of file before SOS/EOI")


def rebuild(segments: list[Segment], rest: bytes) -> bytes:
    out = bytearray(b"\xff\xd8")
    for seg in segments:
        if seg.marker == SOS:
            out += seg.payload  # already includes its own FFDA + length
            continue
        out += bytes([0xFF, seg.marker])
        length = len(seg.payload) + 2
        out += length.to_bytes(2, "big")
        out += seg.payload
    out += rest
    return bytes(out)


def strip_metadata(data: bytes) -> tuple[bytes, dict[str, bool]]:
    """Remove EXIF, XMP, IPTC (Photoshop IRB) and comment segments.

    ICC profile (APP2), JFIF (APP0), Adobe (APP14) and C2PA (APP11)
    segments are left untouched -- ICC/JFIF/Adobe affect rendering, and
    C2PA is handled by the dedicated c2pa cleaner.
    """

    segments, rest = parse_header_segments(data)
    found = {"exif": False, "xmp": False, "iptc": False, "comment": False}
    kept: list[Segment] = []
    for seg in segments:
        kind = seg.kind()
        if kind in found:
            found[kind] = True
            continue
        kept.append(seg)
    return rebuild(kept, rest), found


def has_c2pa_marker(data: bytes) -> bool:
    try:
        segments, _ = parse_header_segments(data)
    except NotAJpegError:
        return False
    return any(seg.marker == APP11 for seg in segments)


def strip_c2pa(data: bytes) -> tuple[bytes, bool]:
    segments, rest = parse_header_segments(data)
    removed = False
    kept: list[Segment] = []
    for seg in segments:
        if seg.marker == APP11:
            removed = True
            continue
        kept.append(seg)
    return rebuild(kept, rest), removed
