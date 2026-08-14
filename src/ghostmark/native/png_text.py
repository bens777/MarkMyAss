"""Native PNG text-chunk reader: tEXt / zTXt / iTXt keyword-value fields.

Provenance:
- PUBLIC_SPEC: PNG specification (Third Edition, W3C) -- the exact field
  layouts of tEXt (keyword NUL text, Latin-1), zTXt (keyword NUL
  compression-method NUL-less zlib stream) and iTXt (keyword NUL
  compression-flag compression-method language-tag NUL translated-keyword
  NUL text, UTF-8), and the registered keywords (Author, Description,
  Software, Comment, ...). XMP-in-PNG placement per Adobe XMP Spec Part 3
  (iTXt with keyword ``XML:com.adobe.xmp``).
- EXIFTOOL_BEHAVIOR: one ecosystem fact -- AI image generators commonly
  store their generation settings in text chunks under de-facto keywords
  (Stable Diffusion family: ``parameters``; others: ``prompt``,
  ``workflow``, ``invokeai_metadata``, ...), which is exactly the
  provenance MarkMyAss exists to surface. No code or tables copied.
- OWN_IMPLEMENTATION: bounded decompression (zip-bomb defense) and
  classification.
"""

from __future__ import annotations

import zlib

from ghostmark.native.signals import MetadataField, SignalCategory, make_preview

# Registered PNG textual keywords (PNG spec) -> category.
_KEYWORD_CATEGORIES: dict[str, tuple[str, SignalCategory]] = {
    "author": ("Author", SignalCategory.AUTHOR),
    "artist": ("Artist", SignalCategory.AUTHOR),
    "copyright": ("Copyright", SignalCategory.AUTHOR),
    "description": ("Description", SignalCategory.DESCRIPTION),
    "title": ("Title", SignalCategory.DESCRIPTION),
    "comment": ("Comment", SignalCategory.COMMENTS),
    "software": ("Software", SignalCategory.SOFTWARE),
    "source": ("Source", SignalCategory.CREATOR),
    "creation time": ("CreationTime", SignalCategory.TIMESTAMP),
}

# De-facto AI-generator keys observed in the ecosystem: their presence is
# a provenance signal (generation prompts/settings embedded in the file).
_AI_PROVENANCE_KEYWORDS = {
    "parameters", "prompt", "negative_prompt", "workflow", "generation_data",
    "sd-metadata", "invokeai_metadata", "dream", "chara", "comfy",
}

_XMP_KEYWORD = "xml:com.adobe.xmp"

# Hard cap on decompressed text (zTXt / compressed iTXt): a hostile
# 100-byte chunk must not inflate into hundreds of megabytes.
_MAX_INFLATED = 64 * 1024


def _bounded_inflate(data: bytes) -> bytes | None:
    try:
        d = zlib.decompressobj()
        out = d.decompress(data, _MAX_INFLATED)
        if d.unconsumed_tail:
            return out + b"\xe2\x80\xa6"  # truncated marker (ellipsis)
        return out
    except zlib.error:
        return None


def parse_text_chunk_field(chunk_type: bytes, data: bytes,
                           *, container: str = "png_text") -> MetadataField | None:
    """Parse one tEXt/zTXt/iTXt chunk into a normalized field.

    Returns None for structurally unusable chunks and for the XMP iTXt
    (which is handled by the XMP extractor instead).
    """

    if chunk_type == b"tEXt":
        if b"\x00" not in data:
            return None
        keyword, text = data.split(b"\x00", 1)
        value: bytes | None = text
    elif chunk_type == b"zTXt":
        if b"\x00" not in data:
            return None
        keyword, rest = data.split(b"\x00", 1)
        if len(rest) < 1:
            return None
        # rest[0] = compression method (0 = zlib per spec)
        value = _bounded_inflate(rest[1:]) if rest[0] == 0 else None
    elif chunk_type == b"iTXt":
        # iTXt layout (PNG spec 11.3.4.5): keyword NUL, compression flag
        # byte, compression method byte, language tag NUL, translated
        # keyword NUL, text. The two single bytes are raw values (often
        # 0x00), so this must be parsed positionally -- splitting on NUL
        # would swallow a zero flag byte.
        kw_end = data.find(b"\x00")
        if kw_end < 0 or kw_end + 3 > len(data):
            return None
        keyword = data[:kw_end]
        comp_flag = data[kw_end + 1]
        comp_method = data[kw_end + 2]
        lang_end = data.find(b"\x00", kw_end + 3)
        if lang_end < 0:
            return None
        trans_end = data.find(b"\x00", lang_end + 1)
        if trans_end < 0:
            return None
        text = data[trans_end + 1:]
        if comp_flag == 0:
            value = text
        elif comp_method == 0:
            value = _bounded_inflate(text)
        else:
            value = None
    else:
        return None

    keyword_str = keyword.decode("latin-1", errors="replace").strip()
    key_lower = keyword_str.lower()
    if key_lower == _XMP_KEYWORD:
        return None  # routed through the XMP extractor by the caller

    preview = make_preview(value) if value is not None else "(compressed value not decoded)"

    if key_lower in _AI_PROVENANCE_KEYWORDS:
        return MetadataField(container, keyword_str, SignalCategory.PROVENANCE, preview)
    known = _KEYWORD_CATEGORIES.get(key_lower)
    if known:
        name, category = known
        return MetadataField(container, name, category, preview)
    return MetadataField(container, keyword_str, SignalCategory.PNG_TEXT, preview)
