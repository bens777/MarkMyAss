# Changelog

All notable changes to GhostMark are documented in this file.

## [Unreleased]

### Fixed

- `sanitize_filename` now strips backslash path components on every OS,
  not just Windows (`pathlib.Path.name` only treats `\` as a separator on
  Windows, so a crafted filename could survive mostly intact on
  Linux/macOS). Caught by CI on `ubuntu-latest`/`macos-latest`.

### Added

- Independent verification: `ghostmark verify` and the web UI's Verify
  step now additionally cross-check the cleaned file with
  [ExifTool](https://exiftool.org/), if installed, as a second opinion
  GhostMark doesn't control the outcome of. Reported honestly as
  `unknown` when ExifTool isn't available -- never faked.
- Web UI downloads are now single-use: the cleaned file (and the rest of
  that session's temp directory) is deleted immediately after the
  download completes, and any session that's never downloaded is purged
  automatically after 30 minutes.
- Download responses set `Content-Disposition: attachment` explicitly
  with a `name.ghostmark.ext` filename.
- Web UI's final button relabeled "Download Clean File".

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
