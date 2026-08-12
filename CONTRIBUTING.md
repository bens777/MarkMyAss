# Contributing to GhostMark

Thanks for considering a contribution. GhostMark is a small, local-first tool
and aims to stay that way -- please keep changes focused and avoid adding
network calls, telemetry, or new mandatory dependencies.

## Development setup

```bash
git clone https://github.com/ghostmark-project/ghostmark.git
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
    verifier.py      # compares a before/after inspection
    security.py      # filename sanitization, size limits, temp file safety
    detectors/        # unicode.py, metadata.py, c2pa.py, statistical.py
    cleaners/          # text.py, image.py, pdf.py, c2pa.py
    formats/            # low-level JPEG/PNG/WebP byte parsers (no recompression)
    experimental/        # opt-in, clearly-labeled unproven features
    fixtures/              # synthetic fixture generation for demo/tests
    cli.py                  # Typer CLI
    web/                     # FastAPI local UI + static frontend
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
