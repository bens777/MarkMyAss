"""Unicode detection + cleaning: must catch hidden chars without destroying legitimate text."""

from __future__ import annotations

from ghostmark.cleaners.text import clean_text
from ghostmark.detectors.unicode import detect_hidden_unicode
from ghostmark.models import Status, UnicodeClassification

ZWSP = chr(0x200B)
WORD_JOINER = chr(0x2060)
ZWJ = chr(0x200D)
BOM = chr(0xFEFF)
NBSP = chr(0x00A0)
THIN_SPACE = chr(0x2009)


def test_clean_text_has_no_hidden_unicode():
    result = detect_hidden_unicode("Perfectly ordinary sentence.")
    assert result.status is Status.NOT_FOUND
    assert result.details["suspicious_characters"] == 0


def test_detects_zero_width_space():
    result = detect_hidden_unicode(f"hello{ZWSP}world")
    assert result.status is Status.FOUND
    assert result.classification is UnicodeClassification.SAFE_TO_REMOVE
    assert result.details["actionable_characters"] == 1


def test_clean_removes_zero_width_space():
    cleaned = clean_text(f"hello{ZWSP}world")
    assert cleaned.cleaned == "helloworld"
    assert cleaned.stats["removed"] == 1
    assert cleaned.action.removed is True


def test_clean_removes_word_joiner_and_bom_midtext():
    text = f"a{WORD_JOINER}b{BOM}c"
    cleaned = clean_text(text)
    assert cleaned.cleaned == "abc"
    assert cleaned.stats["removed"] == 2


def test_leading_bom_is_informational_not_found():
    text = f"{BOM}Hello world"
    result = detect_hidden_unicode(text)
    assert result.status is Status.NOT_FOUND, "a leading BOM is a standard encoding marker, not a hidden signal"
    cleaned = clean_text(text)
    assert cleaned.cleaned == text, "leading BOM must be preserved untouched"


def test_unicode_tag_steganography_detected_and_removed():
    hidden = "".join(chr(0xE0000 + ord(c)) for c in "secret")
    text = f"innocuous text{hidden}"
    result = detect_hidden_unicode(text)
    assert result.status is Status.FOUND
    assert result.classification is UnicodeClassification.SAFE_TO_REMOVE

    cleaned = clean_text(text)
    assert cleaned.cleaned == "innocuous text"


def test_unusual_whitespace_normalized_not_removed():
    text = f"a{THIN_SPACE}b"
    cleaned = clean_text(text)
    assert cleaned.cleaned == "a b"
    assert cleaned.stats["normalized"] == 1
    assert cleaned.stats["removed"] == 0


def test_zwj_preserved_by_default():
    """ZWJ is load-bearing for emoji sequences (family emoji, etc.) and Indic/Arabic scripts."""

    family_emoji = f"\U0001F468{ZWJ}\U0001F469{ZWJ}\U0001F467"
    result = detect_hidden_unicode(family_emoji)
    assert result.status is Status.FOUND
    assert result.classification is UnicodeClassification.POTENTIALLY_SEMANTIC

    cleaned = clean_text(family_emoji)
    assert cleaned.cleaned == family_emoji, "ZWJ must survive default cleaning"
    assert cleaned.stats["preserved_semantic"] == 2


def test_zwj_removed_when_explicitly_opted_in():
    family_emoji = f"a{ZWJ}b"
    cleaned = clean_text(family_emoji, remove_semantic=True)
    assert cleaned.cleaned == "ab"


def test_nbsp_preserved_by_default():
    text = f"Bonjour{NBSP}!"
    cleaned = clean_text(text)
    assert cleaned.cleaned == text, "NBSP has legitimate French typographic use and must not be silently changed"


def test_french_text_untouched():
    text = "J'aime l'intelligence artificielle. Ça fonctionne très bien."
    result = detect_hidden_unicode(text)
    assert result.status is Status.NOT_FOUND
    cleaned = clean_text(text)
    assert cleaned.cleaned == text


def test_german_text_untouched():
    text = "Übermäßige Änderungen dürfen den Text nicht beschädigen."
    result = detect_hidden_unicode(text)
    assert result.status is Status.NOT_FOUND
    cleaned = clean_text(text)
    assert cleaned.cleaned == text


def test_emoji_untouched():
    text = "Great work! 🎉🚀👍"
    cleaned = clean_text(text)
    assert cleaned.cleaned == text


def test_code_block_untouched():
    text = "```python\nprint('hello, world')\n```"
    cleaned = clean_text(text)
    assert cleaned.cleaned == text


def test_markdown_untouched():
    text = "# Heading\n\n- item one\n- item two\n\n**bold** and _italic_ and [link](https://example.com)"
    cleaned = clean_text(text)
    assert cleaned.cleaned == text


def test_stats_reported_before_after():
    text = f"clean{ZWSP}text{THIN_SPACE}here"
    result = detect_hidden_unicode(text)
    assert result.details["total_characters"] == len(text)
    cleaned = clean_text(text)
    assert cleaned.stats["total_characters"] == len(text)
    assert cleaned.stats["removed"] == 1
    assert cleaned.stats["normalized"] == 1


def test_mixed_multilingual_document_only_strips_hidden_chars():
    text = (
        f"English{ZWSP} text.\n"
        "Français: Ça va très bien.\n"
        "Deutsch: Straße, Übermut.\n"
        "Emoji: 😀\n"
    )
    cleaned = clean_text(text)
    assert ZWSP not in cleaned.cleaned
    assert "Ça va très bien" in cleaned.cleaned
    assert "Straße, Übermut" in cleaned.cleaned
    assert "😀" in cleaned.cleaned
