# Lab: Hidden Unicode

{{STATUS_LINE}}

[← Back to the Lab](lab) &middot; [← Back to the MarkMyAss cleaner](.)

---

## What this signal is

Invisible or near-invisible Unicode characters embedded in plain text:
zero-width spaces, word joiners, bidi control marks, and -- most
relevant to hidden-instruction/steganography concerns -- the Unicode
"Tags" block (U+E0000-U+E007F), which renders as nothing in every
mainstream text renderer and has no legitimate typographic use.

This is a **text-encoding** signal. It is entirely independent of any
statistical/model-level watermark (see [/lab/claude-watermark](lab/claude-watermark))
-- hidden Unicode can appear in text from any source, human-typed or
AI-generated, and its presence or absence says nothing about which
model (if any) produced the text.

## What MarkMyAss can test

- Detection: every character in the input is scanned and classified
  (see methodology below). Implementation:
  [`src/ghostmark/detectors/unicode.py`](https://github.com/bens777/MarkMyAss/blob/main/src/ghostmark/detectors/unicode.py).
- Cleaning: characters classified `safe_to_remove` are deleted;
  `safe_to_normalize` characters (unusual whitespace) are collapsed to a
  normal space. Implementation:
  [`src/ghostmark/cleaners/text.py`](https://github.com/bens777/MarkMyAss/blob/main/src/ghostmark/cleaners/text.py).

## What MarkMyAss can remove

Only what it can classify as safe. Characters classified
`potentially_semantic` -- bidi marks, ZWJ/ZWNJ (load-bearing in
Arabic/Persian/Hebrew/Indic scripts and emoji sequences), NBSP (French
typography) -- are **preserved by default**, never silently deleted,
because removing them could change what the text actually says.

## What MarkMyAss cannot test

- Whether a hidden-Unicode payload, if present, decodes to a meaningful
  hidden message. MarkMyAss strips the safe-to-remove characters; it
  does not attempt to decode or interpret them.
- Any statistical/model-level watermark -- a completely different
  mechanism (see above).

## Verification methodology

Independent verification here is **deterministic, not a third-party
tool**: re-running the same open-source detector against the cleaned
output and confirming zero `safe_to_remove`/`safe_to_normalize`
characters remain. This is legitimate because the detector's
classification rules are public, static, and don't depend on any
provider's private state (unlike a statistical watermark, where only the
provider can check). The full ruleset (which codepoints are
`safe_to_remove` vs `potentially_semantic` vs `informational`) is in the
linked source file above -- anyone can audit it.

## Reproducible test commands

```bash
# Using MarkMyAss's own reproducible corpus fixture:
ghostmark inspect src/ghostmark/corpus/text/hidden-unicode.txt --json
ghostmark clean src/ghostmark/corpus/text/hidden-unicode.txt
ghostmark inspect src/ghostmark/corpus/text/hidden-unicode.ghostmark.txt --json
```

Or directly on any text containing a zero-width space (U+200B) -- build
the string explicitly rather than pasting an invisible character, so the
command stays reviewable:

```bash
python3 -c "print('hello' + chr(0x200B) + 'world')" | xargs -0 -I{} ghostmark inspect-text "{}"
```

This exact scenario is also covered by the automated regression suite:
[`tests/test_unicode.py`](https://github.com/bens777/MarkMyAss/blob/main/tests/test_unicode.py)
and [`tests/test_corpus.py`](https://github.com/bens777/MarkMyAss/blob/main/tests/test_corpus.py).

## Related pages

- [Hidden Unicode Remover](hidden-unicode-remover) -- the practical,
  action-oriented version of this page, with a live before/after example.

## Sources

- [Unicode Technical Standard #39 -- Unicode Security Mechanisms](https://www.unicode.org/reports/tr39/)
- [Unicode "Tags" block, Unicode Character Database](https://www.unicode.org/charts/PDF/UE0000.pdf)

## Something outdated or inaccurate?

[Open an issue](https://github.com/bens777/MarkMyAss/issues) or submit a
pull request against
[`src/ghostmark/web/content/lab/hidden-unicode.md`](https://github.com/bens777/MarkMyAss/blob/main/src/ghostmark/web/content/lab/hidden-unicode.md).

**Last reviewed:** 2026-08-13
