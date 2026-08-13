<p class="article-hero">
<img src="static/art/compass-rose.svg" alt="" width="120" height="120" class="hero-illustration" />
</p>

# MarkMyAss AI Watermark Lab

### Chart the unknown waters of AI provenance

MarkMyAss's core promise is that it shows exactly what it found, what it
removed, what was independently verified, and what cannot currently be
proven -- never the reverse. This Lab is where that promise is written
down in detail, signal by signal, kept current, and open to correction.
It's the reference map for what the rest of MarkMyAss's fleet of pages
(the [remover and detector guides](ai-watermark-remover),
[benchmarks](benchmarks), [receipts](.)) all point back to.

[← Back to the MarkMyAss cleaner](.)

---

## Capability matrix

This table is generated directly from MarkMyAss's own capability data
(`src/ghostmark/web/lab_data.py`), not typed by hand into this page -- it
cannot say MarkMyAss can do something the code doesn't actually do. The
same data backs the [`/api/lab/status`](api/lab/status) JSON endpoint
(links below use paths relative to the site root, e.g. `lab/c2pa`).

{{MATRIX_TABLE}}

**Detect** and **Remove** describe MarkMyAss's own Python detectors/cleaners.
**Independent verification** describes whether (and how) a separate tool
cross-checks MarkMyAss's own claim -- see each linked page for methodology.
**Status** is the honest summary: *Verified* (both MarkMyAss and an
independent tool agree, repeatedly, in the test corpus), *Partial*
(heuristic/structural detection only, not a full validator), or *Unknown*
(no public, independently reproducible method exists at all).

---

## How to read "Partial" and "Unknown"

Think of the matrix above as a chart of AI provenance territory: some
waters are fully **charted** (Verified), some are only **partially
charted** (Partial), and some remain genuinely **uncharted** (Unknown --
fog on the map, not a hidden island we're pretending isn't there). The
map metaphor is decoration; the words *Verified* / *Partial* / *Unknown*
in the table are the actual claim, and they're what you should trust.

- **Partial** (currently: C2PA) means MarkMyAss detects/removes a
  *structural* signal (e.g. the JUMBF container a C2PA manifest lives in)
  but does not perform full manifest parsing or cryptographic signature
  validation. Absence of the container is a strong signal, not formal
  proof. See [/lab/c2pa](lab/c2pa).
- **Unknown** (currently: all statistical/model-level text watermarks)
  means no provider has published a public, independently reproducible
  detector. MarkMyAss will not report a confidence score it cannot back
  up -- see [/lab/claude-watermark](lab/claude-watermark) for the fullest
  writeup of why, which generalizes to Gemini and GPT.

---

## Proof, not promises

Every "Verified" row above is backed by MarkMyAss's public, reproducible
test corpus (`src/ghostmark/corpus/`) and regression suite (`tests/test_corpus.py`)
-- see the [Benchmarks page](benchmarks) for the actual pass/fail counts
from the current test run, generated from that same corpus, not
hand-typed.

## Related pages

Practical, action-oriented versions of the mechanisms above:
[AI Watermark Remover](ai-watermark-remover) (overview of all signals),
[AI Metadata Cleaner](ai-metadata-cleaner),
[C2PA Remover](c2pa-remover),
[Content Credentials Remover](content-credentials-remover),
[Hidden Unicode Remover](hidden-unicode-remover),
[Claude Watermark Remover](claude-watermark-remover), and
[Claude Watermark Detector](claude-watermark-detector).

## Something outdated or inaccurate?

This is a fast-moving space -- model capabilities, provenance standards,
and available tooling all change. [Open an issue](https://github.com/bens777/ghostmark/issues)
or submit a pull request against
[`src/ghostmark/web/lab_data.py`](https://github.com/bens777/ghostmark/blob/main/src/ghostmark/web/lab_data.py)
(for the matrix) or the relevant page under
[`src/ghostmark/web/content/lab/`](https://github.com/bens777/ghostmark/tree/main/src/ghostmark/web/content/lab)
on GitHub.

**Last reviewed:** 2026-08-13
