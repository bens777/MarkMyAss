<p class="article-hero">
<img src="static/art/page-benchmarks.webp" alt="Illustration: the pirate captain writes in the leather-bound captain's log while a small ghost holds up a tally slate" width="440" height="295" class="hero-illustration" />
</p>

# Captain's Log — MarkMyAss Benchmarks

### Every supported test. Every failure. Nothing hidden.

This page is the ship's log: generated at server startup by actually running MarkMyAss's
[public, reproducible test corpus](https://github.com/bens777/MarkMyAss/tree/main/src/ghostmark/corpus)
through the real inspect → clean → verify pipeline -- the same one you get
from `ghostmark inspect` / `ghostmark clean` / `ghostmark verify`. Nothing
on this page is a hand-typed number. Failures, if any, are shown here,
not hidden.

[← Back to the MarkMyAss cleaner](.) &middot; [AI Watermark Lab →](lab)

---

## Summary

{{SUMMARY}}

## Per-fixture results

{{TABLE}}

---

## What this corpus does and doesn't cover

The corpus currently covers **hidden Unicode (text), EXIF/XMP/IPTC
(JPEG), EXIF/XMP/PNG-text (PNG), and DocInfo/XMP (PDF)** -- the
mechanisms MarkMyAss's support matrix lists as **Verified**. It does
**not** currently include synthetic C2PA/JUMBF fixtures, so this page
makes no pass/fail claim about C2PA -- that mechanism's status remains
what [/lab/c2pa](lab/c2pa) says it is: **Partial**, regardless of what
this corpus does or doesn't test. Statistical/model-level text
watermarks are not benchmarked here either, for the same reason they're
not benchmarked anywhere: no public detector exists to test against. See
[/lab](lab) for the full, honest capability matrix.

## Reproduce this yourself

```bash
git clone https://github.com/bens777/MarkMyAss.git
cd ghostmark
pip install -e ".[dev]"
pytest tests/test_corpus.py -v
```

Every row on this page corresponds to an assertion in
[`tests/test_corpus.py`](https://github.com/bens777/MarkMyAss/blob/main/tests/test_corpus.py),
run against the fixtures in
[`src/ghostmark/corpus/`](https://github.com/bens777/MarkMyAss/tree/main/src/ghostmark/corpus)
per the expectations documented in
[`manifest.json`](https://github.com/bens777/MarkMyAss/blob/main/src/ghostmark/corpus/manifest.json).
Machine-readable capability data (not this specific benchmark run) is
also available at [`/api/lab/status`](api/lab/status).

## Something outdated or inaccurate?

If a fixture's documented expectation looks wrong, or you think the
corpus should cover something it doesn't yet,
[open an issue](https://github.com/bens777/MarkMyAss/issues) or submit a
pull request against
[`src/ghostmark/corpus/manifest.json`](https://github.com/bens777/MarkMyAss/blob/main/src/ghostmark/corpus/manifest.json)
and [`scripts/generate_corpus.py`](https://github.com/bens777/MarkMyAss/blob/main/scripts/generate_corpus.py).

**Last reviewed:** 2026-08-13
