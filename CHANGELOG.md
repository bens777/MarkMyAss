# Changelog

All notable changes to GhostMark are documented in this file.

## [0.2.0] - 2026-08-12

Adds a production-ready public web deployment (moseisley.sh/ghostmark)
alongside the existing local CLI/UI, plus a real independent-verification
model backed by ExifTool.

### Fixed

- `sanitize_filename` now strips backslash path components on every OS,
  not just Windows (`pathlib.Path.name` only treats `\` as a separator on
  Windows, so a crafted filename could survive mostly intact on
  Linux/macOS). Caught by CI on `ubuntu-latest`/`macos-latest`.
- Packaging: a duplicated `force-include` entry for the web static assets
  made a real (non-editable) wheel build fail outright -- invisible with
  `pip install -e .`, but broke every Docker build. Fixed by relying on
  `packages` alone, which already includes them.

### Added

- **Independent verification, restructured.** `ExifToolVerifier`
  (`ghostmark/independent_verify.py`) now categorizes every property
  ExifTool reports into `embedded_metadata` / `structural` / `filesystem`
  / `computed` / `unknown`, so file size, computed composites, and
  structural facts (ICC profile, PDF page count, ...) are never confused
  with metadata GhostMark claims to remove. `verify_file()` produces a
  `VerificationSummary` with an explicit `VERIFIED CLEAN` / `PARTIAL` /
  `UNVERIFIED` verdict -- `VERIFIED CLEAN` only when GhostMark's own
  re-inspection AND ExifTool both agree.
- A dedicated real-ExifTool integration test suite
  (`tests/integration/`) and a new CI job, "Independent ExifTool
  Verification", that installs ExifTool on Ubuntu and requires it to
  pass.
- **Public web deployment support**, while local `ghostmark ui` is
  unchanged by default:
  - Reverse-proxy subpath support (`GHOSTMARK_BASE_PATH`) via a
    server-injected `<base href>` and fully relative frontend URLs, so
    the same app works at `/` locally and `/ghostmark/` when hosted.
  - `GHOSTMARK_MODE=hosted` switches the UI's privacy copy to the
    accurate hosted-deployment policy and reveals the Moseisley.sh promo
    elements (hidden entirely in local mode).
  - Security hardening for public exposure: per-IP rate limiting,
    a concurrent-job cap with per-job timeouts, security response
    headers (CSP, X-Frame-Options, no-sniff), no CORS, magic-byte MIME
    sniffing, a bounded/streaming upload reader, and a configurable
    upload size limit (20 MB by default in production).
  - Session TTL lowered and clamped to a 10-15 minute maximum for the
    hosted deployment; downloads are single-use (the cleaned file and
    its temp directory are deleted immediately after download).
  - `Dockerfile` installs ExifTool via `apt` and runs as a non-root
    user; new `docker-compose.prod.yml`, `deploy/Caddyfile.snippet`, and
    `DEPLOY_MOSEISLEY.md`.
  - `/health` reports `{"status", "ghostmark", "exiftool_available"}`
    without leaking filesystem paths; new `/api/config` endpoint for the
    frontend's mode-dependent behavior.
- Web UI redesigned around the STEP 1/2/3 (Inspect / Clean / Verify)
  flow with before/after tables, an ExifTool panel, and an explicit
  verdict badge; final button relabeled "Download Clean File"; SEO
  meta/OpenGraph/canonical tags.
- `PRIVACY.md` documenting the local-vs-hosted privacy difference
  explicitly.

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
