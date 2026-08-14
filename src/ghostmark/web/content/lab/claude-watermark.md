# Lab: "Claude Watermark"

{{STATUS_LINE}}

[← Back to the Lab](lab) &middot; [← Back to the GhostMark cleaner](.)

---

People searching for "Claude watermark" usually mean one of three
**completely different mechanisms**. Conflating them is the single most
common source of confusion in this space, so this page exists
specifically to keep them separate.

## The three things people mean

### 1. File / metadata provenance

If you ask Claude to help produce a file (a document, an exported image,
etc.) through some pipeline, that pipeline may embed ordinary file
metadata: an author field, a "Producer" string, XMP data, or (for
images) a C2PA Content Credentials manifest. As of the same August 2026
announcement above, Anthropic states that supported image outputs (SVG,
PNG, JPG) now get **signed C2PA provenance metadata attached directly by
Claude**, not just by a downstream export pipeline -- see the same
[Anthropic Help Center article](https://support.claude.com/en/articles/16266773-how-claude-marks-ai-generated-content).
Either way, this is the same category of signal any C2PA-aware
document/image tool can add, and it's exactly what GhostMark's
PDF-metadata, EXIF/XMP, and C2PA detectors target -- see
[/lab/pdf-metadata](lab/pdf-metadata) and [/lab/c2pa](lab/c2pa) for what
GhostMark can and cannot do with a *signed* manifest specifically
(short version: GhostMark detects/strips the JUMBF container
structurally; it does not validate or forge cryptographic signatures).

**GhostMark's status: Supported.** Detect: Yes. Remove: Yes. Independently
verified: Yes, via ExifTool (and c2patool for the C2PA container).

### 2. Hidden Unicode characters in text

Some people call invisible Unicode characters (zero-width spaces,
Unicode "Tags" block steganography, etc.) found in AI-generated text a
"watermark." **This is not correct, and GhostMark does not call it
one.** Hidden Unicode is a text-encoding artifact that can appear in text
from any source -- it is not a statistical signature tied to a specific
model, and its presence doesn't identify which model (if any) produced
the surrounding text. See [/lab/hidden-unicode](lab/hidden-unicode) for
the full, separate writeup of this mechanism.

**GhostMark's status: Supported (as its own, distinct signal).** Detect:
Yes. Remove: Yes (with load-bearing characters like ZWJ/NBSP preserved by
default). Independently verified: Yes, deterministically.

### 3. Statistical / model-level text watermarking

This is what people usually mean when they ask "does Claude watermark
its text so it can be detected later." The idea: a provider could bias
how its model samples tokens in a detectable-but-imperceptible way, such
that only the provider (holding a private key/seed) could later run a
statistical test against a piece of text and estimate the odds it came
from their model.

**On August 11-12, 2026, Anthropic publicly confirmed this mechanism is
real**, not hypothetical. Its support article states Claude "embeds an
imperceptible watermark directly into the text itself" that "will travel
with the text when it's copied and pasted elsewhere," rolling out to
models launched on or after August 2, 2026 (with older models being
retrofitted), across claude.ai, the API, Claude Code, Claude Cowork, and
Claude Tag, worldwide. Source:
[Anthropic Help Center -- "How Claude marks AI-generated content"](https://support.claude.com/en/articles/16266773-how-claude-marks-ai-generated-content).

That same article is explicit that **no detector exists publicly yet**:
"We're also working to enable users and other third parties to detect
Claude's embedded watermarks and provenance metadata... We'll share
details on detection mechanisms in forthcoming technical documentation."
Until that documentation ships, there is nothing independently runnable
for GhostMark (or anyone outside Anthropic) to implement or test against.
GhostMark will not fabricate a detection result for a mechanism nobody
outside the provider can currently verify.

**GhostMark's status: Unknown.** Detect: Unknown. Remove: Unknown.
Independent verification: No public verifier exists yet.

## Why GhostMark reports "Unknown" instead of a score

Reporting a confidence percentage here -- "87% likely watermarked," "0%
detectable" -- would require either (a) Anthropic's own private
detection key, which GhostMark does not have and never will, or (b) an
independently published, peer-reviewed detection methodology GhostMark
could implement and that others could verify GhostMark implemented
correctly. Neither exists publicly today. Any tool claiming otherwise is
either guessing or measuring something else (like hidden Unicode or
formatting) and mislabeling it as "the watermark."

`ghostmark inspect` and `ghostmark inspect-text` report this explicitly
as a distinct row: `Claude statistical watermark: UNKNOWN / NOT CURRENTLY
VERIFIABLE`. Implementation and the plug-in interface a future real
detector would use:
[`src/ghostmark/detectors/statistical.py`](https://github.com/bens777/MarkMyAss/blob/main/src/ghostmark/detectors/statistical.py).

## What would change this page

Anthropic has already committed to publishing "forthcoming technical
documentation" on detection. When that ships -- or if an independent
researcher publishes a reproducible detection methodology and open code
first -- GhostMark would implement it behind the same
`StatisticalWatermarkDetector` interface already defined for this
purpose, and this page's status would change from Unknown to whatever
the evidence actually supports. Until then, this page states the current
state of public knowledge, not a guess.

## Reproducible test commands

```bash
ghostmark inspect-text "any text you like" --json
# -> "statistical_claude": {"status": "unknown", ...}
```

## Related pages

- [Claude Watermark Remover](claude-watermark-remover) -- the practical,
  action-oriented version of this page: what GhostMark actually cleans.
- [Claude Watermark Detector](claude-watermark-detector) -- for
  "how do I check a file/text," rather than "how does the mechanism work."

## Sources

- [Anthropic Help Center -- "How Claude marks AI-generated content"](https://support.claude.com/en/articles/16266773-how-claude-marks-ai-generated-content)
  -- the primary source for everything on this page about what Anthropic
  has and hasn't confirmed. No public statistical watermark detector is
  published here or elsewhere by Anthropic as of this writing.
- [Kirchenbauer et al., "A Watermark for Large Language Models" (2023)](https://arxiv.org/abs/2301.10226)
  -- the general statistical-watermarking technique this category refers
  to; describes the *concept*, not a Claude-specific, publicly runnable
  detector
- [C2PA -- Coalition for Content Provenance and Authenticity](https://c2pa.org/)
  (relevant to mechanism #1 for image/file outputs, not to text)

## Something outdated or inaccurate?

If Anthropic (or anyone) publishes something that changes the facts on
this page, please tell us: [open an issue](https://github.com/bens777/MarkMyAss/issues)
or submit a pull request against
[`src/ghostmark/web/content/lab/claude-watermark.md`](https://github.com/bens777/MarkMyAss/blob/main/src/ghostmark/web/content/lab/claude-watermark.md).

**Last reviewed:** 2026-08-13
