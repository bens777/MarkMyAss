"""Chunk-level RIFF/WebP parsing so metadata can be stripped without recompression."""

from __future__ import annotations

from dataclasses import dataclass

RIFF_MAGIC = b"RIFF"
WEBP_MAGIC = b"WEBP"


class NotAWebpError(ValueError):
    pass


@dataclass
class Chunk:
    fourcc: bytes
    data: bytes


def parse_chunks(data: bytes) -> list[Chunk]:
    if len(data) < 12 or data[0:4] != RIFF_MAGIC or data[8:12] != WEBP_MAGIC:
        raise NotAWebpError("Not a WebP file")
    chunks: list[Chunk] = []
    pos = 12
    n = len(data)
    while pos + 8 <= n:
        fourcc = data[pos : pos + 4]
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        start = pos + 8
        end = start + size
        if end > n:
            raise NotAWebpError("Truncated RIFF chunk")
        chunks.append(Chunk(fourcc=fourcc, data=data[start:end]))
        pos = end + (size % 2)  # chunks are padded to even length
    return chunks


def rebuild(chunks: list[Chunk]) -> bytes:
    body = bytearray()
    for chunk in chunks:
        body += chunk.fourcc
        body += len(chunk.data).to_bytes(4, "little")
        body += chunk.data
        if len(chunk.data) % 2:
            body += b"\x00"
    out = bytearray(RIFF_MAGIC)
    out += (len(body) + 4).to_bytes(4, "little")  # +4 for the "WEBP" fourcc
    out += WEBP_MAGIC
    out += body
    return bytes(out)


def strip_metadata(data: bytes) -> tuple[bytes, dict[str, bool]]:
    chunks = parse_chunks(data)
    found = {"exif": False, "xmp": False}
    kept: list[Chunk] = []
    for chunk in chunks:
        if chunk.fourcc == b"EXIF":
            found["exif"] = True
            continue
        if chunk.fourcc == b"XMP ":
            found["xmp"] = True
            continue
        kept.append(chunk)
    return rebuild(kept), found
