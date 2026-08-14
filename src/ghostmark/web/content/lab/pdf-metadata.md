# Lab: PDF Metadata

{{STATUS_LINE}}

[← Back to the Lab](lab) &middot; [← Back to the GhostMark cleaner](.)

---

## What this signal is

PDF files carry two independent metadata containers:

- **DocInfo** (the `/Info` dictionary): Title, Author, Producer, Creator,
  creation/modification timestamps, and other legacy fields.
- **XMP** (`/Metadata` stream): a structured XML metadata packet, which
  can duplicate or extend DocInfo and is what most modern tools
  (including many AI/PDF-export pipelines) actually write to.

Either can carry provenance information -- the tool that generated the
PDF, an author name, timestamps -- independent of anything about the PDF's
visible content.

## What GhostMark can test

Detection reads both containers directly from the PDF object graph via
[pikepdf](https://github.com/pikepdf/pikepdf) (a Python binding to
qpdf). Implementation:
[`src/ghostmark/detectors/metadata.py`](https://github.com/bens777/MarkMyAss/blob/main/src/ghostmark/detectors/metadata.py).

## What GhostMark can remove

Both the `/Info` dictionary and the `/Metadata` (XMP) stream are deleted
entirely from the PDF's object graph -- not blanked, removed. Pages,
fonts, images, text, links, and page order are untouched; GhostMark edits
the PDF's object graph directly rather than rasterizing or re-rendering
it. Implementation:
[`src/ghostmark/cleaners/pdf.py`](https://github.com/bens777/MarkMyAss/blob/main/src/ghostmark/cleaners/pdf.py).

After cleaning, GhostMark reopens the produced PDF and confirms it's
still structurally valid (parses, page count matches) before handing it
back -- a metadata-removal bug that corrupts the file is treated as a
cleaning failure, not a success.

## What GhostMark cannot test

- Metadata embedded in individual PDF objects in nonstandard,
  non-DocInfo/non-XMP locations (rare, but possible in hand-crafted or
  unusual PDFs). GhostMark's detector targets the two standard
  containers.
- Any provenance signal embedded in images placed *inside* the PDF (those
  are covered separately by GhostMark's image EXIF/XMP/IPTC detectors
  when you clean the image directly, not automatically unpacked from
  inside a PDF).

## Verification methodology

Independent verification uses [ExifTool](https://exiftool.org/)
(`exiftool -j -G1 -a -s FILE`), a long-established, widely trusted
third-party tool GhostMark does not control. Every property ExifTool
reports is categorized into `embedded_metadata` / `structural` /
`filesystem` / `computed` so that, for example, `PDF:PageCount` (a
structural fact needed for the file to make sense) is never confused
with `PDF:Author` (metadata GhostMark actually targets). See
[`src/ghostmark/independent_verify.py`](https://github.com/bens777/MarkMyAss/blob/main/src/ghostmark/independent_verify.py)
for the exact categorization rules.

A result only counts as independently verified clean when ExifTool finds
zero `embedded_metadata`-category tags in the cleaned output.

## Reproducible test commands

```bash
ghostmark inspect src/ghostmark/corpus/pdf/docinfo-xmp.pdf --json
ghostmark clean src/ghostmark/corpus/pdf/docinfo-xmp.pdf
ghostmark verify src/ghostmark/corpus/pdf/docinfo-xmp.ghostmark.pdf --receipt receipt.json

# Independently, with ExifTool directly:
exiftool -j -G1 -a -s src/ghostmark/corpus/pdf/docinfo-xmp.pdf
exiftool -j -G1 -a -s src/ghostmark/corpus/pdf/docinfo-xmp.ghostmark.pdf
```

Covered by the automated regression suite:
[`tests/test_pdf.py`](https://github.com/bens777/MarkMyAss/blob/main/tests/test_pdf.py),
[`tests/test_corpus.py`](https://github.com/bens777/MarkMyAss/blob/main/tests/test_corpus.py),
and the real-ExifTool integration suite
[`tests/integration/test_exiftool_real.py`](https://github.com/bens777/MarkMyAss/blob/main/tests/integration/test_exiftool_real.py).

## Related pages

- [AI Metadata Cleaner](ai-metadata-cleaner) -- the practical,
  format-by-format version of this page, covering PDF, JPEG, PNG, and WebP.

## Sources

- [PDF 2.0 specification (ISO 32000-2)](https://www.iso.org/standard/75839.html) -- `/Info` dictionary and `/Metadata` stream
- [XMP Specification, Adobe/ISO 16684](https://developer.adobe.com/xmp/docs/)
- [pikepdf documentation](https://pikepdf.readthedocs.io/)
- [ExifTool](https://exiftool.org/)

## Something outdated or inaccurate?

[Open an issue](https://github.com/bens777/MarkMyAss/issues) or submit a
pull request against
[`src/ghostmark/web/content/lab/pdf-metadata.md`](https://github.com/bens777/MarkMyAss/blob/main/src/ghostmark/web/content/lab/pdf-metadata.md).

**Last reviewed:** 2026-08-13
