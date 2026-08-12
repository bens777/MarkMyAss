# Changelog

All notable changes to GhostMark are documented in this file.

## [0.1.0] - 2026-08-12

Initial open-source release.

### Added

- Hidden Unicode detection and cleaning for text, `.md`, `.json`, `.csv`
  (zero-width characters, Unicode "tag" steganography, bidi controls,
  unusual whitespace, variation selectors), with a safety classification
  system so legitimate multilingual text, emoji, code, and Markdown are
  never destroyed.
- EXIF / XMP / IPTC / comment detection and lossless (non-recompressing)
  removal for JPEG, PNG, and WebP, with ICC color profiles always
  preserved.
- PDF DocInfo and XMP metadata detection and removal via `pikepdf`, with
  post-clean structural readability verification.
- Heuristic C2PA/JUMBF container detection and removal for JPEG and PNG,
  clearly labeled as partial/structural rather than full manifest
  validation.
- Honest "unverified" reporting for statistical/model-level text
  watermarks (Claude, Gemini, GPT), with a `StatisticalWatermarkDetector`
  protocol for future real implementations.
- `ghostmark inspect|clean|verify|inspect-text|clean-text|demo|ui` CLI with
  `--json` machine-readable output.
- Local-only web UI (FastAPI + vanilla HTML/CSS/JS), binds to
  `127.0.0.1` only.
- `ghostmark demo` synthetic-fixture end-to-end smoke test.
- One-click launch scripts for Windows, Linux, and macOS.
- Full test suite (pytest) and CI (GitHub Actions, Ubuntu/Windows/macOS).
