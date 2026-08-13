<p class="article-hero">
<img src="static/art/page-hidden-unicode.webp" alt="Illustration: a pirate examines a scroll with a magnifying glass, revealing tiny ghosts hiding between the lines of writing" width="440" height="295" class="hero-illustration" />
</p>

<p class="kicker">Tiny stowaways hide between the letters.</p>

# Hidden Unicode Remover

### Strip invisible characters from copy-pasted text — free, in your browser or via CLI

Text copied out of a chat interface, a document, or a scraped web page
can carry Unicode characters that render as nothing: zero-width spaces,
stray bidi control marks, and — the one worth actually worrying about —
the Unicode "Tags" block (U+E0000–U+E007F), which has no legitimate
typographic use and has been used for prompt-injection and
steganography payloads hidden in plain-looking text.

[Paste text to check now →](.)

---

## Common situations this comes up in

- **Pasting AI-generated text** into a document, email, or CMS and
  wanting to confirm nothing invisible came along with it.
- **Reviewing text from an untrusted source** (a resume, a form
  submission, a scraped page) before feeding it into another system —
  hidden Unicode has been used to smuggle instructions past naive text
  filters.
- **Academic or editorial integrity checks** where invisible characters
  specifically (not "AI-ness" in general) are the concern.

## What it actually looks like

Zero-width characters are invisible by definition, so rather than paste
one directly into this page (which would make the source unreviewable —
you'd have to trust that what's there is what it claims to be), here's
the same short string built explicitly, with and without one:

```text
"hello" + U+200B (zero-width space) + "world"   -- looks like one word, or two with a gap
Inspect: 1 hidden Unicode character found at position 5 (U+200B, zero-width space)
"helloworld"                                     -- after cleaning
```

```bash
python3 -c "print('hello' + chr(0x200B) + 'world')" | xargs -0 -I{} ghostmark inspect-text "{}"
python3 -c "print('hello' + chr(0x200B) + 'world')" | xargs -0 -I{} ghostmark clean-text "{}"
```

## What MarkMyAss removes vs. preserves

Not every unusual Unicode character is safe to delete — some are
load-bearing. MarkMyAss classifies before touching anything:

- **Removed automatically**: zero-width spaces, Unicode "Tags" block
  characters — no legitimate role in ordinary text.
- **Normalized, not deleted**: unusual whitespace variants, collapsed to
  a regular space.
- **Preserved by default**: bidi marks, ZWJ/ZWNJ (load-bearing in
  Arabic/Persian/Hebrew/Indic scripts and emoji sequences), NBSP (French
  typography). Deleting these would change what the text actually says,
  not just how it's encoded.

This means MarkMyAss won't mangle legitimate multilingual text, code, or
emoji while cleaning what's actually invisible-and-unnecessary. Full
classification methodology and the complete rule set:
[/lab/hidden-unicode](lab/hidden-unicode).

## This is not "the AI watermark"

Hidden Unicode is a text-encoding artifact, not a statistical signature
tied to a specific model — it can appear in text from any source, and
its presence or absence doesn't identify what (if anything) generated
the surrounding text. If you're specifically trying to reason about
Claude-generated text, see [/claude-watermark-remover](claude-watermark-remover)
for why that's a separate, much less certain question.

## Sources

- [Unicode Technical Standard #39 — Unicode Security Mechanisms](https://www.unicode.org/reports/tr39/)
- [Unicode "Tags" block, Unicode Character Database](https://www.unicode.org/charts/PDF/UE0000.pdf)
