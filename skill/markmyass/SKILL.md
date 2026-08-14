---
name: markmyass
description: Inspect, clean and verify supported AI watermark, metadata and provenance signals (hidden Unicode, EXIF/XMP, PDF/PNG metadata, C2PA) in files or text, using the local MarkMyAss CLI.
---

# MarkMyAss — inspect, clean, verify

MarkMyAss (engine name: `ghostmark`) is a free, open-source, 100% local
tool that detects and removes **supported** watermark/metadata/provenance
signals and then verifies the result. It never uploads anything.

## Setup (once)

Check availability first; only install if missing:

```bash
ghostmark --version || pipx install "git+https://github.com/bens777/MarkMyAss" || pip install "git+https://github.com/bens777/MarkMyAss"
```

## Workflow

Always follow inspect → clean → verify, and show the user real results
at each step — never claim something was removed without the verify
output.

1. **Inspect** — what supported signals are present?
   ```bash
   ghostmark inspect FILE --json
   ghostmark inspect-text "TEXT" --json
   ```
2. **Clean** — write a sanitized copy (the original is never modified):
   ```bash
   ghostmark clean FILE            # writes FILE.cleaned.<ext> next to it
   ghostmark clean-text "TEXT"     # prints cleaned text to stdout
   ```
3. **Verify** — re-inspect the cleaned copy and report what was
   actually removed:
   ```bash
   ghostmark verify CLEANED_FILE --json
   ```
   If ExifTool is installed on the machine, `verify` also runs it as an
   independent cross-check and reports agreement/disagreement.

Supported file types: PDF, JPG/JPEG, PNG, WebP, and text
(TXT/MD/JSON/CSV or pasted strings).

## Honesty rules (do not violate these)

- Report status labels exactly as the tool prints them (FOUND /
  NOT FOUND / REMOVED / PARTIAL / UNKNOWN / UNSUPPORTED /
  VERIFIED CLEAN). Never soften UNKNOWN into "clean".
- Supported signals: hidden Unicode, EXIF/XMP/IPTC, PDF DocInfo+XMP,
  PNG text/time/eXIf chunks, WebP EXIF/XMP, and structural C2PA
  container removal (partial support — not cryptographic validation).
- NOT removable by this tool (say so if asked): statistical model-level
  watermarks (Claude / Gemini / GPT) — no public verifier exists, so
  their status is always UNKNOWN. Never claim "100% AI-undetectable"
  or guaranteed detector bypass.
- The original file must never be modified; always work on the cleaned
  copy the tool produces.
