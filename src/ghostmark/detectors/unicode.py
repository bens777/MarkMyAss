"""Detection of invisible / suspicious Unicode characters in text.

This module never mutates text -- it only classifies characters that are
already present. Classification drives what ``ghostmark.cleaners.text`` is
allowed to touch automatically:

- ``safe_to_remove``: characters with no legitimate typographic role in
  ordinary text (e.g. zero-width space, Unicode "tag" steganography
  characters). Removing them cannot change how the text reads.
- ``safe_to_normalize``: characters that can be replaced with a plain-text
  equivalent (e.g. an unusual space character becomes U+0020) without
  changing meaning.
- ``potentially_semantic``: characters that ARE sometimes load-bearing
  (bidi control marks, ZWJ/ZWNJ in Arabic/Indic scripts and emoji
  sequences, emoji variation selectors). GhostMark reports these but does
  not remove them by default.
- ``informational``: characters that are expected and benign in the
  position they were found (e.g. a BOM at byte offset 0).

Codepoints are written as explicit ``0x....`` integers rather than literal
invisible characters embedded in source, so the table stays reviewable and
diff-able.
"""

from __future__ import annotations

from dataclasses import dataclass

from ghostmark.models import (
    Category,
    Confidence,
    DetectionResult,
    Status,
    UnicodeClassification,
)

SAFE_REMOVE = UnicodeClassification.SAFE_TO_REMOVE
SAFE_NORMALIZE = UnicodeClassification.SAFE_TO_NORMALIZE
SEMANTIC = UnicodeClassification.POTENTIALLY_SEMANTIC
INFO = UnicodeClassification.INFORMATIONAL

# Single codepoints with no legitimate role in ordinary running text.
SAFE_TO_REMOVE: dict[int, str] = {
    0x200B: "ZERO WIDTH SPACE",
    0x2060: "WORD JOINER",
    0x00AD: "SOFT HYPHEN",
    0x180E: "MONGOLIAN VOWEL SEPARATOR",
    0xFEFF: "ZERO WIDTH NO-BREAK SPACE (BOM)",
}

# Unicode "Tags" block (U+E0000-U+E007F): fully invisible in every mainstream
# renderer and has no legitimate use in ordinary text. This is the block used
# by the well-documented "ASCII smuggling" hidden-instruction technique, so it
# is always treated as safe to remove.
UNICODE_TAGS_RANGE = (0xE0000, 0xE007F)

# Unusual space characters that can be safely collapsed to a normal space
# without changing the meaning of the text.
SAFE_TO_NORMALIZE_SPACES: dict[int, str] = {
    0x2000: "EN QUAD",
    0x2001: "EM QUAD",
    0x2002: "EN SPACE",
    0x2003: "EM SPACE",
    0x2004: "THREE-PER-EM SPACE",
    0x2005: "FOUR-PER-EM SPACE",
    0x2006: "SIX-PER-EM SPACE",
    0x2007: "FIGURE SPACE",
    0x2008: "PUNCTUATION SPACE",
    0x2009: "THIN SPACE",
    0x200A: "HAIR SPACE",
    0x205F: "MEDIUM MATHEMATICAL SPACE",
    0x3000: "IDEOGRAPHIC SPACE",
}

# Characters that DO have legitimate typographic/linguistic uses and are
# never touched automatically, but are still worth reporting.
POTENTIALLY_SEMANTIC: dict[int, str] = {
    0x200C: "ZERO WIDTH NON-JOINER",
    0x200D: "ZERO WIDTH JOINER",
    0x200E: "LEFT-TO-RIGHT MARK",
    0x200F: "RIGHT-TO-LEFT MARK",
    0x061C: "ARABIC LETTER MARK",
    0x202A: "LEFT-TO-RIGHT EMBEDDING",
    0x202B: "RIGHT-TO-LEFT EMBEDDING",
    0x202C: "POP DIRECTIONAL FORMATTING",
    0x202D: "LEFT-TO-RIGHT OVERRIDE",
    0x202E: "RIGHT-TO-LEFT OVERRIDE",
    0x2066: "LEFT-TO-RIGHT ISOLATE",
    0x2067: "RIGHT-TO-LEFT ISOLATE",
    0x2068: "FIRST STRONG ISOLATE",
    0x2069: "POP DIRECTIONAL ISOLATE",
    0x00A0: "NO-BREAK SPACE",
    0x202F: "NARROW NO-BREAK SPACE",
}

# Standard emoji/text presentation variation selectors: legitimate and common
# (e.g. distinguishing an emoji from its text glyph). Informational only.
VARIATION_SELECTORS_RANGE = (0xFE00, 0xFE0F)
VARIATION_SELECTORS_SUPPLEMENT_RANGE = (0xE0100, 0xE01EF)


@dataclass
class CharHit:
    codepoint: int
    name: str
    classification: UnicodeClassification
    position: int


def _in_range(cp: int, rng: tuple[int, int]) -> bool:
    return rng[0] <= cp <= rng[1]


def _classify_codepoint(cp: int) -> tuple[str, UnicodeClassification] | None:
    if cp in SAFE_TO_REMOVE:
        return SAFE_TO_REMOVE[cp], SAFE_REMOVE
    if _in_range(cp, UNICODE_TAGS_RANGE):
        return "UNICODE TAG CHARACTER (hidden-text steganography)", SAFE_REMOVE
    if cp in SAFE_TO_NORMALIZE_SPACES:
        return SAFE_TO_NORMALIZE_SPACES[cp], SAFE_NORMALIZE
    if cp in POTENTIALLY_SEMANTIC:
        return POTENTIALLY_SEMANTIC[cp], SEMANTIC
    if _in_range(cp, VARIATION_SELECTORS_RANGE):
        return "VARIATION SELECTOR", INFO
    if _in_range(cp, VARIATION_SELECTORS_SUPPLEMENT_RANGE):
        return "VARIATION SELECTOR SUPPLEMENT", INFO
    return None


def scan_text(text: str) -> list[CharHit]:
    """Return every suspicious/invisible character found in ``text``, in order."""

    hits: list[CharHit] = []
    for i, ch in enumerate(text):
        cp = ord(ch)
        classified = _classify_codepoint(cp)
        if classified is None:
            continue
        name, classification = classified
        # A BOM at the very start of a file/string is a standard encoding
        # marker, not a hidden signal. Downgrade it to informational.
        if cp == 0xFEFF and i == 0:
            classification = INFO
        hits.append(CharHit(codepoint=cp, name=name, classification=classification, position=i))
    return hits


def detect_hidden_unicode(text: str) -> DetectionResult:
    """Run the "Hidden Unicode" detector against a text string."""

    hits = scan_text(text)
    actionable = [h for h in hits if h.classification != INFO]

    by_classification: dict[str, int] = {}
    by_char: dict[str, int] = {}
    for h in hits:
        by_classification[h.classification.value] = by_classification.get(h.classification.value, 0) + 1
        key = f"U+{h.codepoint:04X} {h.name}"
        by_char[key] = by_char.get(key, 0) + 1

    status = Status.FOUND if actionable else Status.NOT_FOUND
    dominant = (
        SAFE_REMOVE
        if any(h.classification == SAFE_REMOVE for h in actionable)
        else (actionable[0].classification if actionable else None)
    )

    return DetectionResult(
        detector="unicode",
        label="Hidden Unicode",
        status=status,
        category=Category.UNICODE,
        confidence=Confidence.HIGH,
        removable=any(h.classification in (SAFE_REMOVE, SAFE_NORMALIZE) for h in hits),
        classification=dominant,
        details={
            "total_characters": len(text),
            "suspicious_characters": len(hits),
            "actionable_characters": len(actionable),
            "by_classification": by_classification,
            "by_character": by_char,
        },
    )
