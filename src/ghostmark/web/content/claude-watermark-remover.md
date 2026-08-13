# Claude Watermark Remover

### GhostMark removes and verifies *supported* signals — not everything people call "the Claude watermark"

If you landed here searching for "Claude watermark remover," you probably
mean one of three genuinely different things. GhostMark is built around
keeping them separate, because a tool that quietly conflates them is a
tool that can lie to you without saying anything false.

| Mechanism | GhostMark's status |
| --- | --- |
| Hidden Unicode characters in text | **Supported** — detect and remove |
| File metadata (EXIF/XMP/IPTC/PDF DocInfo) | **Supported where applicable** — detect and remove |
| C2PA / Content Credentials container | **Partial** — structural detection/removal, not cryptographic validation |
| Claude statistical model watermark | **Not currently publicly verifiable** — see why below |

GhostMark will not tell you it removed something it can't actually
confirm. The last row is the important one, and most "watermark remover"
tools online skip past it.

[Clean a file or text now →](.)

---

## What GhostMark actually does here

### 1. Hidden Unicode — fully supported

Text copied from a chat interface can carry invisible Unicode characters:
zero-width spaces, Unicode "Tags" block characters, stray bidi marks.
These aren't a Claude-specific signature — any text-producing pipeline
can introduce them — but they're real, detectable, and GhostMark removes
them deterministically while preserving characters that are actually
load-bearing (emoji sequences, right-to-left scripts, French typography).

```bash
ghostmark inspect-text "your pasted text here" --json
ghostmark clean-text "your pasted text here"
```

Full methodology: [/lab/hidden-unicode](lab/hidden-unicode).

### 2. File metadata — supported where applicable

If you exported a document, image, or PDF through some pipeline
downstream of Claude, that pipeline may have embedded ordinary file
metadata (author, producer, XMP fields). GhostMark strips this
byte/segment-level for JPEG, PNG, WebP, and PDF, and independently
verifies removal with [ExifTool](https://exiftool.org/).

```bash
ghostmark clean document.pdf
ghostmark verify document.ghostmark.pdf --original document.pdf
```

Full methodology: [/ai-metadata-cleaner](ai-metadata-cleaner) and
[/lab/pdf-metadata](lab/pdf-metadata).

### 3. C2PA / Content Credentials — partial

As of August 2026, Anthropic's own documentation states that Claude
attaches signed C2PA provenance metadata to supported image outputs
(SVG, PNG, JPG) — see
[Anthropic Help Center](https://support.claude.com/en/articles/16266773-how-claude-marks-ai-generated-content).
GhostMark detects and strips the JUMBF container structure a C2PA
manifest lives in, and cross-checks with the official
[c2patool](https://github.com/contentauth/c2pa-rs) where installed. This
is **structural container removal, not cryptographic manifest
validation** — GhostMark doesn't forge or verify signatures.

Full methodology: [/c2pa-remover](c2pa-remover) and [/lab/c2pa](lab/c2pa).

### 4. The statistical text watermark — honestly, not yet

This is what most people actually mean by "Claude watermark": an
imperceptible bias in how the model samples tokens, meant to be
detectable later without changing what the text says. Anthropic
confirmed on August 11–12, 2026 that this mechanism is real and rolling
out to models launched after August 2, 2026, but its own documentation
states plainly that **no public detector exists yet** — "we'll share
details on detection mechanisms in forthcoming technical documentation."

**GhostMark cannot detect, remove, or verify removal of a mechanism with
no published, independently reproducible detection method.** Any tool
that claims otherwise is either measuring something else (hidden Unicode,
formatting) and mislabeling it, or guessing. `ghostmark inspect-text`
reports this row explicitly as `UNKNOWN / NOT CURRENTLY VERIFIABLE`
rather than a fabricated pass.

**See the [GhostMark Claude Watermark Lab methodology →](lab/claude-watermark)**
for the full breakdown, sources, and what would change this page.

---

## FAQ

**Does GhostMark remove Claude's invisible statistical watermark?**
No. No public detector exists for GhostMark (or anyone outside
Anthropic) to test against, so there's nothing to verify removal of.
GhostMark reports this status as unknown rather than claiming success.

**Is hidden Unicode the same thing as the Claude watermark?**
No, and GhostMark never calls it that. Hidden Unicode is a
text-encoding artifact any source can introduce; it's unrelated to
model-level statistical watermarking. See
[/lab/claude-watermark](lab/claude-watermark) for the full distinction.

**Will removing metadata make an image "undetectable" as AI-generated?**
No claim like that exists on this site. GhostMark removes the specific,
named signals in the table above and reports exactly what it did and
didn't verify — not a synthetic confidence score.

**What if Anthropic publishes a detector later?**
GhostMark already has a pluggable interface for this
([`src/ghostmark/detectors/statistical.py`](https://github.com/bens777/ghostmark/blob/main/src/ghostmark/detectors/statistical.py))
and would implement it the moment a reproducible methodology exists. The
[Lab page](lab/claude-watermark) tracks this.

## Sources

- [Anthropic Help Center — "How Claude marks AI-generated content"](https://support.claude.com/en/articles/16266773-how-claude-marks-ai-generated-content)
- [ExifTool](https://exiftool.org/)
- [C2PA specification](https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html)
