# 👻 GhostMark

**Open-source AI watermark & provenance cleaner.**

Inspect → Clean → Verify

**100% local. No uploads. No telemetry. Free and open source.**

GhostMark inspects files and text for hidden Unicode characters, embedded
metadata, and provenance signals, removes the ones it can safely remove,
and then re-inspects its own output so it can tell you -- with evidence,
not vibes -- what actually changed.

```bash
ghostmark inspect document.pdf
ghostmark clean document.pdf
ghostmark verify document.ghostmark.pdf
```

---

## Why GhostMark is honest about what "AI watermark" means

"AI watermark" gets used for at least seven different things. GhostMark
treats them as genuinely separate mechanisms, because they are:

1. **Hidden Unicode characters** -- zero-width spaces, Unicode "tag"
   steganography, bidi control marks, etc.
2. **Formatting artifacts** -- unusual whitespace, odd normalization.
3. **EXIF / XMP / document metadata** -- camera/tool/author info embedded
   in images and PDFs.
4. **C2PA / Content Credentials provenance metadata** -- a structured,
   embeddable manifest describing content origin.
5. **Embedded file-level provenance structures** -- the JUMBF containers
   C2PA (and similar schemes) are packaged in.
6. **Statistical / model-level text watermarks** -- a bias in how an LLM
   samples tokens, detectable (in principle) only by the provider with
   their private detection key.
7. **Visible image watermarks** -- a logo or text baked into the pixels.

GhostMark **detects and cleans 1-5** to varying degrees (see the table
below). It does **not** implement 6 or 7 in this release, and says so
plainly in its own output rather than pretending otherwise. If GhostMark
can't verify something, it reports `UNKNOWN` or `UNVERIFIED` -- never a
fabricated result.

---

## Quick start

```bash
git clone https://github.com/bens777/ghostmark.git
cd ghostmark
pip install -e .

ghostmark demo     # generates synthetic fixtures and proves the pipeline works
ghostmark ui       # opens http://127.0.0.1:8765 in your browser
```

Not comfortable with a terminal? Double-click:

- **Windows:** `START-GHOSTMARK.bat` (or `START-GHOSTMARK.ps1`)
- **Linux / macOS:** `start-ghostmark.sh`

These scripts check for Python, set up a virtual environment, install
GhostMark, and open the web UI for you -- with plain-language errors if
something's missing.

## The web UI

```text
👻 GhostMark
AI watermark & provenance cleaner

[ Paste Text ]  [ Upload File ]

---------------------------------
Inspection results

Hidden Unicode         FOUND
Document metadata      FOUND
XMP metadata           FOUND
C2PA / provenance      NOT DETECTED
Statistical watermark  UNKNOWN

[ Clean ]
---------------------------------
Verification

Hidden Unicode         REMOVED
Metadata               REMOVED
C2PA                   UNSUPPORTED
Statistical watermark  UNVERIFIED

[ Save cleaned file ]
```

The server binds to `127.0.0.1` only -- it is never reachable from other
devices, and nothing is ever uploaded anywhere outside your machine.

## CLI

```bash
ghostmark inspect FILE [--json]
ghostmark clean FILE [--output PATH] [--json]
ghostmark verify FILE [--original PATH] [--json]
ghostmark inspect-text "TEXT" [--json]
ghostmark clean-text "TEXT" [--json]
ghostmark demo
ghostmark ui [--port 8765] [--no-browser]
ghostmark --version
ghostmark --help
```

Example:

```text
$ ghostmark inspect example.pdf
GhostMark inspection

File: example.pdf
✓ File readable
⚠ Document metadata: FOUND
⚠ XMP metadata: FOUND
✓ C2PA / provenance: NOT FOUND

Risk / provenance signals found: 2
```

The original file is **never** modified. Cleaning always writes a new file:

```text
document.pdf  →  document.ghostmark.pdf
photo.png     →  photo.ghostmark.png
```

Exit codes: `0` on success, `1` on a handled error (unsupported file type,
file too large, demo failure), non-zero on usage errors.

## Support matrix

| Mechanism                     |                             Detect |            Clean |          Verify |
| ------------------------------ | -----------------------------------: | ------------------: | -----------------: |
| Hidden Unicode (text/.md/.json/.csv) |                                 Yes |                 Yes |               Yes |
| EXIF (JPEG/PNG/WebP)           |                                 Yes |                 Yes |               Yes |
| XMP (JPEG/PNG/WebP/PDF)        |                                 Yes |                 Yes |               Yes |
| IPTC (JPEG)                    |                                 Yes |                 Yes |               Yes |
| PNG text chunks                |                                 Yes |                 Yes |               Yes |
| PDF DocInfo metadata           |                                 Yes |                 Yes |               Yes |
| ICC color profile              |                     Yes (preserved) |     N/A (preserved) |               Yes |
| C2PA / JUMBF (JPEG, PNG)       | Partial (heuristic byte-marker scan) |             Partial |           Partial |
| C2PA / JUMBF (PDF)             |                    Partial (heuristic) |        Unsupported |     Unsupported |
| Claude statistical watermark   |                          Unverified |     Not implemented |    Not applicable |
| Gemini statistical watermark   |                          Unverified |     Not implemented |    Not applicable |
| GPT statistical watermark      |                          Unverified |     Not implemented |    Not applicable |
| Visible image watermark        |                        Not implemented |     Not implemented |    Not applicable |
| DOCX                            |                        Not implemented (roadmap) |            -- |               -- |

"Partial" for C2PA means: GhostMark scans for the JUMBF container structure
(JPEG APP11 segment, PNG `caBX` chunk) a C2PA manifest is embedded in, and
can strip that container. It does **not** parse or cryptographically
validate a C2PA manifest -- absence of the container is a strong signal,
not formal proof, and removal is a structural strip, not an audited
guarantee against every possible embedding technique.

"Unverified" for statistical watermarks means exactly that: no provider has
published a public, independently reproducible detector GhostMark could
implement, so GhostMark reports `UNKNOWN` rather than guessing. See
[`src/ghostmark/detectors/statistical.py`](src/ghostmark/detectors/statistical.py)
for the interface a future real detector would plug into.

## Supported file types

| Category | Formats |
| --- | --- |
| Text | `.txt`, `.md`, `.json`, `.csv` |
| Documents | `.pdf` |
| Images | `.png`, `.jpg` / `.jpeg`, `.webp` |

`.docx` is on the roadmap but not in this release -- rather than delay a
working V0, it was left out.

## How cleaning works (and why it's honest about pixels)

Image and JPEG/PNG/WebP metadata cleaning works at the **byte/segment
level**, not by decoding and re-encoding the image. EXIF/XMP/IPTC/comment
segments (JPEG), text/`tIME`/`eXIf` chunks (PNG), or `EXIF`/`XMP ` RIFF
chunks (WebP) are deleted directly from the container; pixel data and ICC
color profiles are never touched. That means:

```text
EXIF                  removed
XMP                   removed
ICC color profile     preserved
Pixel dimensions      unchanged
Visual content        unchanged (byte-identical pixel data)
```

PDF cleaning uses [pikepdf](https://github.com/pikepdf/pikepdf) to edit the
document's object graph directly -- pages, fonts, images, text, and links
are untouched; only the `/Info` dictionary and `/Metadata` (XMP) stream are
removed. GhostMark reopens the cleaned PDF and confirms it's still
structurally readable before handing it back to you.

Text cleaning classifies every suspicious Unicode character before
touching it:

- `safe_to_remove` -- no legitimate role in ordinary text (zero-width
  space, Unicode "tag" steganography characters). Removed automatically.
- `safe_to_normalize` -- unusual whitespace collapsed to a normal space.
- `potentially_semantic` -- bidi marks, ZWJ/ZWNJ, NBSP. These **are**
  sometimes load-bearing (Arabic/Persian/Hebrew/Indic scripts, emoji
  sequences, French typography) and are preserved by default.
- `informational` -- e.g. a BOM at the very start of a file (a normal
  encoding marker, not a hidden signal).

French, German, emoji, code blocks, and Markdown are covered by the test
suite specifically to make sure cleaning doesn't mangle legitimate content.

## Privacy

- **Local-only.** No uploads, no cloud processing, no external API calls.
- **No telemetry, analytics, or tracking** of any kind.
- **No user accounts.**
- **No CDN JavaScript or remote fonts** -- the web UI is self-contained
  vanilla HTML/CSS/JS.
- The web server binds to `127.0.0.1` only, never `0.0.0.0`.
- Uploaded files live only in a randomized per-session temp directory and
  are deleted when the session ends or the process exits.

If a future optional feature ever needs network access, it will be
disabled by default and clearly labeled.

## Security

- Upload size limit (50 MB) enforced before any parsing.
- Filenames are sanitized (path components and unsafe characters stripped)
  before ever touching the filesystem -- no path traversal via a crafted
  filename.
- File extension is checked against an explicit allow-list.
- Temp files use randomized names in a per-session directory, cleaned up on
  completion and on process exit.
- Untrusted file content is never executed, and parsing failures return a
  clean error instead of a stack trace with local filesystem paths.

See [`SECURITY.md`](SECURITY.md) for the full threat model and how to
report a vulnerability.

## Enhanced metadata support (optional)

GhostMark's core detectors are pure Python and need nothing extra. If
[ExifTool](https://exiftool.org/) is installed and on your `PATH`,
GhostMark reports:

```text
Enhanced metadata support: available
```

Nothing in V0 currently shells out to it -- the flag exists so the
CLI/UI are honest about what's available, and so a future contributor has
a documented place to wire in deeper inspection.

## Docker (optional)

Docker is not required and not the primary way to run GhostMark -- use the
launch scripts or `pip install -e .` above. If you'd like to run the web UI
in a container anyway:

```bash
docker compose up
```

This maps the UI to `127.0.0.1:8765` on your host only (see
`docker-compose.yml`); it is not exposed to your network.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the project layout and how to
add a new detector or cleaner.

## Roadmap

- DOCX metadata support.
- Full C2PA manifest parsing/validation (not just container detection).
- Optional ExifTool integration for deeper metadata inspection.
- Real statistical watermark detectors, if/when providers publish
  reproducible methodology.

## License

MIT -- see [`LICENSE`](LICENSE). Third-party dependency licenses are listed
in [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
