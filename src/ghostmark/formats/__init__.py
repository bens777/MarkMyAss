"""Low-level, dependency-free binary parsers for image container formats.

These parsers operate on raw bytes so metadata can be stripped by deleting
whole segments/chunks instead of decoding and re-encoding pixel data. That
avoids any recompression: the returned bytes are byte-identical to the
input except for the removed segments.
"""
