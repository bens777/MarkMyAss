# Contributing to GhostMark

Thanks for considering a contribution. GhostMark is a small, local-first tool
and aims to stay that way -- please keep changes focused and avoid adding
network calls, telemetry, or new mandatory dependencies.

## Development setup

```bash
git clone https://github.com/bens777/MarkMyAss.git
cd ghostmark
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -e ".[dev]"

ghostmark --help
ghostmark demo
```

## Before opening a PR

```bash
pytest
ruff check .
```

Both must pass. CI runs the same checks on Ubuntu, Windows, and macOS.

## Project layout

```text
src/ghostmark/
    models.py       # shared result types (DetectionResult, CleanResult, VerifyResult, ...)
    inspector.py     # dispatches a text/file input to the right detectors
    cleaner.py       # dispatches a text/file input to the right cleaners
    verifier.py      # compares a before/after inspection, builds VerificationSummary
    receipt.py        # VerificationReceipt: JSON/HTML/TXT downloadable proof of a verify run
    security.py         # filename sanitization, size limits, temp file safety
    independent_verify.py  # ExifToolVerifier + C2paToolVerifier: external cross-checks + tag categorization
    corpus_data.py          # loads the reproducible test corpus (manifest.json + fixtures)
    corpus/                  # synthetic-only fixtures used by tests/ and /benchmarks (ships in the package)
    detectors/                # unicode.py, metadata.py, c2pa.py, statistical.py
    cleaners/                   # text.py, image.py, pdf.py, c2pa.py
    formats/                      # low-level JPEG/PNG/WebP byte parsers (no recompression)
    experimental/                   # opt-in, clearly-labeled unproven features
    fixtures/                         # synthetic fixture generation for demo/tests/corpus
    cli.py                              # Typer CLI
    web/                                 # FastAPI app (shared by local `ghostmark ui` and hosted deploy)
        app.py                              # routes, session lifecycle
        config.py                            # env-driven WebConfig (local vs hosted mode, limits)
        security_middleware.py                # rate limiting, security headers
        concurrency.py                          # bounded/timed job runner
        content_render.py                        # Markdown -> HTML rendering + {{PLACEHOLDER}} injection
        lab_data.py                                # single source of truth for the /lab capability matrix
        benchmarks.py                                # runs the corpus through the real pipeline for /benchmarks
        content/                                       # Markdown source for /run-local, /lab/*, /benchmarks
        static/                                          # vanilla HTML/CSS/JS frontend

tests/
    integration/      # tests against the REAL exiftool/c2patool binaries (skip if not installed)
```

The CLI and the web UI both call into `inspector.py` / `cleaner.py` /
`verifier.py` -- never duplicate detection/cleaning logic in either
front end.

## Adding a new detector

1. Add a module (or function) under `src/ghostmark/detectors/`. It should
   read input and return one or more `DetectionResult` objects from
   `ghostmark.models`. Detectors must never mutate their input.
2. Pick an honest `Status`: `FOUND`, `NOT_FOUND`, or `UNKNOWN` -- use
   `UNKNOWN` rather than guessing when you can't actually tell.
3. Wire it into `ghostmark/inspector.py`'s `inspect_text` or `inspect_file`
   for the relevant file type(s).
4. Add tests under `tests/` covering both the found and not-found cases,
   plus any edge cases (e.g. legitimate content that must not be
   misclassified).

## Adding a new cleaner

1. Add a module under `src/ghostmark/cleaners/` with a function that takes
   the raw content and returns `(cleaned_content, CleanAction | list[CleanAction])`.
2. Only remove what the matching detector classified as safe to remove.
   Never silently destroy content that could be semantically meaningful --
   see `ghostmark/detectors/unicode.py` for the classification scheme
   (`safe_to_remove` / `safe_to_normalize` / `potentially_semantic` /
   `informational`) that all cleaners should respect.
3. Wire it into `ghostmark/cleaner.py`.
4. Add regression tests, including a test that the cleaned output is still
   valid/readable in its format (see `tests/test_pdf.py` for the pattern).

## Adding support for a new statistical watermark detector

See `src/ghostmark/detectors/statistical.py` for the `StatisticalWatermarkDetector`
protocol. GhostMark will not report a detection result it cannot actually
justify -- if you're adding a real detector, it needs to be reproducible and
its methodology documented, not a heuristic dressed up as certainty.

## Updating the AI Watermark Lab (`/lab`)

The Lab's whole point is that it stays accurate, so this is one of the
most valuable things to contribute.

1. **Capability matrix data** lives in `src/ghostmark/web/lab_data.py`
   (`LAB_SIGNALS`, a plain list of `LabSignal` dataclasses). This one file
   feeds the `/lab` HTML table, the Markdown table on each sub-page, and
   the `GET /api/lab/status` JSON endpoint -- edit it once, everywhere
   updates together. Never write `"Yes"` for `independent_verification`
   unless a real external tool actually checks that signal; if you're not
   sure, use `"Unknown"` or `"Partial"` and explain why in the linked
   page.
2. **Prose pages** live under `src/ghostmark/web/content/lab/*.md`
   (plain Markdown, rendered via `content_render.py`). Every page needs:
   a "Last reviewed: YYYY-MM-DD" line (update it when you change
   anything substantive), a "what GhostMark can/cannot test" section
   that's honest about the limits of the check, reproducible commands a
   reader can run themselves, and a correction CTA
   ("Something outdated or inaccurate? Open an issue or submit a pull
   request"). `LAST_REVIEWED` in `lab_data.py` is the site-wide fallback
   date -- bump it too if you touch shared matrix data.
3. Links between Lab pages must **not** start with `/` and sibling pages
   need the `lab/` prefix (e.g. `[C2PA](lab/c2pa)`, not `[C2PA](c2pa)`)
   -- the page uses a server-injected `<base href>` pointing at the site
   root, not the current page, so a bare slug or a leading slash resolves
   to the wrong place under a reverse-proxy subpath. `tests/test_lab.py`
   has a regression test for this
   (`test_lab_sibling_links_include_lab_prefix`) -- run it after editing
   any Lab content.
4. If a provider ships a real, reproducible statistical watermark
   detector, wire it in via `src/ghostmark/detectors/statistical.py`'s
   `StatisticalWatermarkDetector` protocol, then update the relevant
   `LabSignal` entry and page -- don't just change the status text
   without a working detector behind it.

## Updating the test corpus and `/benchmarks`

- Fixtures live in `src/ghostmark/corpus/` (inside the installed
  package, not `tests/`, so they actually ship in the Docker image) with
  a `manifest.json` describing `expected_before` / `expected_after`
  detections for each one. Regenerate fixtures with
  `python scripts/generate_corpus.py` (reuses
  `ghostmark.fixtures.generate`) rather than hand-editing binary files.
- Only synthetic, GhostMark-generated content belongs in the corpus --
  never real or copyrighted files.
- `src/ghostmark/web/benchmarks.py` runs every corpus fixture through the
  real inspect → clean → inspect → independently-verify pipeline and
  reports actual results; it does not hand-hardcode pass/fail. If you add
  a fixture that's expected to fail cleaning (e.g. to document a known
  gap), the benchmarks page will report it as a known failure -- don't
  work around that by making the manifest expect the failure silently;
  the point of `/benchmarks` is that failures are visible, not hidden.

## Style

- Type hints throughout; `ruff check .` enforces import order and a handful
  of lint rules (see `pyproject.toml`).
- No comments explaining *what* code does -- prefer clear names. Comments
  are for non-obvious *why*.
- No new dependencies without a good reason; prefer the standard library.
- No telemetry, analytics, or outbound network calls, ever.

## Reporting bugs / requesting features

Use the issue templates. For security issues, see `SECURITY.md` -- please
do not open a public issue for a vulnerability.

## License

By contributing, you agree your contribution is licensed under the MIT
License (see `LICENSE`). No CLA is required.
