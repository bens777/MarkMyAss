"""Chunk-level PNG parsing so metadata can be stripped without recompression."""

from __future__ import annotations

import zlib
from dataclasses import dataclass

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

_METADATA_CHUNK_TYPES = {b"tEXt", b"zTXt", b"iTXt", b"tIME", b"eXIf"}
_C2PA_CHUNK_TYPE = b"caBX"


class NotAPngError(ValueError):
    pass


@dataclass
class Chunk:
    type: bytes
    data: bytes


def parse_chunks(data: bytes) -> list[Chunk]:
    if not data.startswith(PNG_SIGNATURE):
        raise NotAPngError("Not a PNG file (bad signature)")
    chunks: list[Chunk] = []
    pos = len(PNG_SIGNATURE)
    n = len(data)
    while pos < n:
        if pos + 8 > n:
            raise NotAPngError("Truncated chunk header")
        length = int.from_bytes(data[pos : pos + 4], "big")
        ctype = data[pos + 4 : pos + 8]
        start = pos + 8
        end = start + length
        if end + 4 > n:
            raise NotAPngError("Truncated chunk data")
        chunks.append(Chunk(type=ctype, data=data[start:end]))
        pos = end + 4  # skip CRC
        if ctype == b"IEND":
            break
    return chunks


def rebuild(chunks: list[Chunk]) -> bytes:
    out = bytearray(PNG_SIGNATURE)
    for chunk in chunks:
        out += len(chunk.data).to_bytes(4, "big")
        out += chunk.type
        out += chunk.data
        crc = zlib.crc32(chunk.type + chunk.data) & 0xFFFFFFFF
        out += crc.to_bytes(4, "big")
    return bytes(out)


_XMP_KEYWORD = b"XML:com.adobe.xmp\x00"


def strip_metadata(data: bytes) -> tuple[bytes, dict[str, bool]]:
    chunks = parse_chunks(data)
    found = {"text": False, "xmp": False, "time": False, "exif": False}
    kept: list[Chunk] = []
    for chunk in chunks:
        if chunk.type in (b"tEXt", b"iTXt") and chunk.data.startswith(_XMP_KEYWORD):
            found["xmp"] = True
            continue
        if chunk.type in (b"tEXt", b"zTXt", b"iTXt"):
            found["text"] = True
            continue
        if chunk.type == b"tIME":
            found["time"] = True
            continue
        if chunk.type == b"eXIf":
            found["exif"] = True
            continue
        kept.append(chunk)
    return rebuild(kept), found


def has_c2pa_marker(data: bytes) -> bool:
    try:
        chunks = parse_chunks(data)
    except NotAPngError:
        return False
    return any(c.type == _C2PA_CHUNK_TYPE for c in chunks)


def strip_c2pa(data: bytes) -> tuple[bytes, bool]:
    chunks = parse_chunks(data)
    removed = False
    kept: list[Chunk] = []
    for chunk in chunks:
        if chunk.type == _C2PA_CHUNK_TYPE:
            removed = True
            continue
        kept.append(chunk)
    return rebuild(kept), removed
