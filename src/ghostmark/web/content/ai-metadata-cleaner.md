<p class="article-hero">
<img src="static/art/mascot-captain.svg" alt="" width="200" height="154" class="hero-illustration" />
</p>

<p class="kicker">Ghosts in the cargo hold.</p>

# AI Metadata Cleaner

### File-format-level metadata removal, independently verified — not a black box

This page covers exactly one category from the broader
[AI watermark remover](ai-watermark-remover) overview: **embedded file
metadata** in documents and images. If you need PDF, JPEG, PNG, or WebP
files stripped of author/tool/location fields and want to actually
confirm they're gone (not just trust a progress bar), this is the
relevant mechanism.

[Clean a file now →](.)

---

## Supported formats and fields

| Format | Fields removed | How |
| --- | --- | --- |
| PDF | DocInfo dictionary (`/Info`: Author, Producer, Creator, etc.), XMP metadata stream | [pikepdf](https://github.com/pikepdf/pikepdf) object-graph editing |
| JPEG | EXIF (including GPS coordinates, camera/tool info), XMP, IPTC, comment segments | Direct segment deletion, no re-encoding |
| PNG | EXIF (`eXIf` chunk), XMP/text chunks, `tIME` | Direct chunk deletion, no re-encoding |
| WebP | EXIF and XMP RIFF chunks | Direct chunk deletion, no re-encoding |

GPS coordinates aren't a separate feature — they live inside the EXIF
segment, so removing EXIF removes them as part of the same operation.

## Why byte-level matters

MarkMyAss's image cleaning works at the **byte/segment level**, not by
decoding and re-encoding the image. That means:

```text
EXIF                  removed
XMP                   removed
ICC color profile     preserved
Pixel dimensions      unchanged
Visual content        unchanged (byte-identical pixel data)
```

A tool that decodes and re-encodes your image to "clean" it is doing
more than removing metadata — it's also silently altering compression
and potentially quality. MarkMyAss doesn't do that: pixel data is never
touched, only the metadata segments/chunks around it.

PDF cleaning works the same way conceptually: pikepdf edits the
document's object graph directly, so pages, fonts, images, text, and
links are untouched — only `/Info` and the XMP metadata stream are
removed. MarkMyAss reopens the cleaned PDF and confirms it's still
structurally valid before handing it back.

## Independent verification with ExifTool

MarkMyAss doesn't ask you to trust its own "removed" claim. If
[ExifTool](https://exiftool.org/) is installed (it is, automatically, in
the hosted deployment), `ghostmark verify` re-scans the cleaned file with
that separate, independently maintained tool and reports whether it
agrees:

```bash
ghostmark clean photo.jpg
ghostmark verify photo.ghostmark.jpg --original photo.jpg
```

```text
MarkMyAss verification:  PASS
ExifTool verification:   PASS
Overall:                  VERIFIED CLEAN
```

Every property ExifTool reports is categorized (embedded metadata vs.
structural/filesystem/computed information), so a preserved ICC profile
or the file's byte size is never mistaken for "metadata MarkMyAss failed
to remove." Full methodology: [/lab/pdf-metadata](lab/pdf-metadata).

## What this page doesn't cover

This page is about file-format metadata specifically. It says nothing
about statistical text watermarks, C2PA provenance manifests, or hidden
Unicode — those are separate mechanisms with their own pages:
[/c2pa-remover](c2pa-remover), [/hidden-unicode-remover](hidden-unicode-remover),
and the broader [/ai-watermark-remover](ai-watermark-remover) overview.

## Sources

- [ExifTool](https://exiftool.org/)
- [pikepdf documentation](https://pikepdf.readthedocs.io/)
