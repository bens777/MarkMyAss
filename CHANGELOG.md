# Changelog

All notable changes to GhostMark are documented in this file.

## [0.5.0] - 2026-08-13

Technical SEO and public discoverability, built from current Google
Search documentation and real SERP research -- not guesswork, and not
programmatic keyword-swap pages. See `SEO_LAUNCH_CHECKLIST.md` for the
manual Search Console steps this enables.

### Added

- **New canonical hostname**: `https://ghostmark.moseisley.sh`.
  `WebConfig`'s default `public_url` now points there (root base path);
  the existing subpath deployment style
  (`GHOSTMARK_BASE_PATH=/ghostmark/`) remains fully supported for anyone
  who prefers it -- see `docker-compose.prod.yml` and
  `deploy/Caddyfile.snippet` (now documents both options).
- **Seven new SEO landing pages**, each targeting a genuinely distinct
  search intent (no doorway-page keyword-swap duplicates -- see
  `tests/test_seo.py`'s similarity guard): `/claude-watermark-remover`,
  `/claude-watermark-detector`, `/ai-watermark-remover`,
  `/ai-metadata-cleaner`, `/c2pa-remover`, `/content-credentials-remover`,
  `/hidden-unicode-remover`. Cross-linked with the existing `/lab` pages
  and each other; every page links back to the actual tool.
- `/run-local` renamed to `/run-ai-locally` (clearer, matches the new
  landing pages' naming); the old URL 301-redirects permanently rather
  than serving duplicate content at two URLs.
- **Structured data** (`ghostmark/web/seo.py`): `SoftwareApplication` and
  `WebSite` JSON-LD on the homepage, `BreadcrumbList` on every landing
  and Lab page. No fabricated `aggregateRating`/`review` -- GhostMark has
  no real review corpus and won't invent one just to qualify for a rich
  result. No `FAQPage` markup: Google removed FAQ rich results from
  Search entirely in 2026, so implementing that schema would have zero
  effect (confirmed via current Search Central documentation before
  deciding not to build it).
- **`/robots.txt`** (allows public pages, disallows `/api/`) and
  **`/sitemap.xml`** (lists exactly the indexable pages, canonical URLs
  only -- no session/download/API routes), both generated from the same
  `INDEXABLE_PAGES` list the test suite checks against.
- Homepage: new H1 ("Claude Watermark Remover & AI Provenance Cleaner"),
  title, and meta description matching actual search intent; an
  originally-drawn OG/Twitter card image (`scripts/generate_og_image.py`,
  built with Pillow -- no external assets, no AI image generation); a
  crawlable footer sitemap linking every page with plain `<a href>`
  (never JavaScript-only navigation).
- `tests/test_seo.py`: every indexable page checked for a 200 status,
  title, description, single H1, correct canonical, no accidental
  `noindex`, only relative internal links; `robots.txt`/`sitemap.xml`
  correctness; structured data validity; and a lightweight anti-doorway
  duplicate-content guard across the new landing pages.
- `SEO_LAUNCH_CHECKLIST.md`: plain-language Google Search Console setup
  steps for the new hostname. Explicit that none of this guarantees
  rankings.

### Changed

- `/lab/claude-watermark` updated to reflect Anthropic's August 11-12,
  2026 confirmation that Claude text watermarking is real (previously
  undocumented publicly) -- source:
  [Anthropic Help Center](https://support.claude.com/en/articles/16266773-how-claude-marks-ai-generated-content).
  GhostMark's own capability is unchanged: no public detector exists yet,
  so the status stays Unknown, now with the primary source cited instead
  of "Anthropic has not published anything."
- Fixed stale `tests/corpus/...` example paths in Lab page content left
  over from the 0.4.0 corpus relocation into `src/ghostmark/corpus/`.
- `PRIVACY.md`/`SECURITY.md` corrected a leftover "deleted immediately
  after download" claim that predated 0.4.0's session-persistence change.



The "moat build": GhostMark repositions from a metadata cleaner to a
public reference lab for AI watermark and provenance verification --
"Proof, not promises." Every claim GhostMark makes is now backed by an
independent check, a reproducible corpus, or an honest "unverified"/
"unknown" label instead of a bare assertion.

### Added

- **Verification Receipt.** `ghostmark verify --receipt PATH` (CLI) and
  `GET /api/receipt/{session}/download?format=json|html|txt` (web) produce
  a downloadable receipt with before/after signal tables, independent
  verifier results, SHA-256 hashes of the original and cleaned files, the
  GhostMark version, and a timestamp. Explicitly labeled a "Verification
  Receipt," not a certificate of authorship -- `receipt.py` bakes in a
  disclaimer that it "is not a certificate of authorship or a claim that
  no other signal could exist." Statistical/model-level watermarks
  (Claude, Gemini, GPT) always render as unverified on the receipt; there
  is no code path that can mark them removed.
- **Five-state verdict system.** `VerificationVerdict` is now
  `VERIFIED_CLEAN` / `PARTIAL` / `UNVERIFIED` / `NOT_APPLICABLE` /
  `FAILED`, computed by `VerificationSummary.verdict` from GhostMark's own
  result plus whichever independent verifiers actually ran. GhostMark can
  never award itself `VERIFIED_CLEAN` -- that requires at least one
  available, applicable external verifier and full agreement; disagreement
  is `PARTIAL`; no verifier able to run at all is `UNVERIFIED`, not
  `PARTIAL`. See `tests/test_verdict.py` for the full decision table.
- **c2patool as a second, optional independent verifier**
  (`C2paToolVerifier` in `independent_verify.py`), alongside ExifTool.
  Runs the official `c2patool` binary read-only against JPEG/PNG/PDF to
  check for a C2PA manifest. Explicitly documented as *not* a
  cryptographic trust/signature validator -- it only reports whether a
  manifest is present, and GhostMark never treats a clean c2patool result
  as proof that a statistical text watermark was removed. Degrades to
  "unavailable" gracefully when the binary isn't installed, and never
  guesses when the tool errors ambiguously. Installed via a multi-stage
  Docker build (`cargo install c2patool` in a throwaway Rust build stage;
  only the compiled binary is copied into the final image).
- **AI Watermark Lab** at `/lab`, with a capability matrix (signal /
  detect / remove / independent verification / status / last tested)
  driven entirely by `web/lab_data.py` -- the same data backs the HTML
  table, the Markdown table, and the new `/api/lab/status` JSON endpoint,
  so they can't drift apart. No signal is ever marked "Yes" for
  independent verification unless a real external tool actually checks
  it. Individual pages at `/lab/claude-watermark`, `/lab/c2pa`,
  `/lab/hidden-unicode`, and `/lab/pdf-metadata`, each with a "Last
  reviewed" date and a correction CTA linking to GitHub issues/PRs. The
  Claude page explicitly separates file/metadata provenance, hidden
  Unicode, and statistical model-level watermarking, and states plainly
  that hidden Unicode is not the Claude statistical watermark.
- **Reproducible benchmark corpus.** Synthetic-only fixtures (no
  copyrighted material) now ship inside the installed package at
  `src/ghostmark/corpus/` (moved from `tests/corpus/` so they're actually
  present in the Docker image, not just the source checkout), with a
  `manifest.json` documenting expected detections before and after
  cleaning. `web/benchmarks.py` runs the real inspect -> clean -> inspect
  -> independently-verify pipeline against every fixture and publishes
  the actual results at `/benchmarks` (human-readable) and
  `/api/benchmarks` (JSON) -- failures are reported, not hidden. The page
  explicitly discloses that the corpus does not include C2PA fixtures.
- **Homepage repositioning**: new headline "Proof, not promises.", trust
  bar (Free / Open source / No account / Independent verification /
  Download your cleaned file), an explicit "No fake '100% undetectable'
  scores" note, an "Explain" panel that translates each detected signal
  into a plain-English sentence, and receipt download buttons
  (JSON/HTML/TXT) alongside the existing cleaned-file download -- the
  cleaned file remains downloadable in every case; nothing was replaced
  with a report-only flow.
- `/health` and `/api/config` now also report `c2patool_available` (and
  `/api/config` reports `c2patool_version`), alongside the existing
  ExifTool fields.

## [0.3.0] - 2026-08-13

### Added

- New `/run-local` page: a developer guide to avoiding provider-side
  provenance at the source by running open-weight models locally, on a
  workstation, or on a rented GPU. Covers hosted-vs-open-weight models
  (with an explicit "no, you can't run the frontier closed models
  locally" answer), a hardware/budget decision matrix, current
  recommended open-weight model families (coding, general reasoning,
  lightweight) with verified official links and license notes, local
  inference tools (Ollama, llama.cpp, vLLM, LM Studio,
  text-generation-webui), GPU rental platforms and when renting beats
  buying, and an explicit "what this page does not claim" honesty
  section. Every external link was checked and returns 200 at time of
  writing; sourced and dated ("Last reviewed"), with a correction CTA
  linking to GitHub issues.
- Content lives in `src/ghostmark/web/content/run_local.md` (Markdown),
  rendered via the new `ghostmark.web.content_render` module -- kept
  separate from rendering logic so future edits don't require touching
  Python. New `markdown` (BSD-3-Clause) dependency for this.
- Subtle, discoverable link from the main cleaner page ("Want to avoid
  provider-side provenance at the source? Learn how to run models
  locally →"), and a link back from the guide to the cleaner. Works
  under both local (`/`) and hosted (`/ghostmark/`) base paths, same as
  the rest of the app.

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
