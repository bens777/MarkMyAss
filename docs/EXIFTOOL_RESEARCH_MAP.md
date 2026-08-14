# ExifTool Research Map

Engineering research notes for MarkMyAss's native metadata engine.

**Purpose.** MarkMyAss is reducing its operational dependency on ExifTool:
ExifTool becomes a *reference implementation*, a *differential-testing
oracle*, and an optional *independent external verifier* — not the engine
MarkMyAss needs in order to inspect, clean, or verify.

**Source-code rule followed here.** ExifTool source (the Debian-packaged
`Image::ExifTool` 12.76 Perl modules) was inspected as engineering
research only — to understand containers, dispatch behavior, and
real-world edge cases. No source text, comments, tag tables, or function
structure were copied or mechanically translated into MarkMyAss. Where a
public specification exists, the native implementation was written from
the specification; ExifTool study only informed *which* edge cases
deserve handling. Everything below is written in our own engineering
language.

Per-module provenance is also declared in each native module's docstring
(`Provenance:` line) using the vocabulary: `PUBLIC_SPEC`,
`EXIFTOOL_BEHAVIOR`, `EXIFTOOL_SOURCE_RESEARCH`, `EXISTING_MARKMYASS_CODE`,
`THIRD_PARTY_LIBRARY`, `OWN_IMPLEMENTATION`.

---

## JPEG container

- **Relevant ExifTool module(s):** `JPEG.pm` (segment dispatch),
  `Photoshop.pm` (APP13 resource blocks).
- **What behavior was studied:** how one physical segment type (APP1) is
  disambiguated into logical payloads by *content prefix*, not by marker
  alone — `Exif\0` for EXIF, the `http://ns.adobe.com/xap/1.0/` URI for
  XMP, a separate extension-URI for multi-segment "Extended XMP"; that
  APP13 IPTC travels inside Photoshop "8BIM" image-resource blocks; that
  some writers put EXIF-shaped payloads in odd places (APP3 `Meta\0\0`)
  which we deliberately do NOT chase.
- **Relevant public specification:** ITU-T T.81 (JPEG interchange,
  marker/segment structure); Exif 2.32 / CIPA DC-008 (APP1 Exif payload);
  Adobe XMP Specification Part 3 (XMP packet placement in JPEG);
  Adobe Photoshop File Formats spec (8BIM image resource blocks).
- **What MarkMyAss actually needs:** APP1-Exif, APP1-XMP, APP13-IPTC,
  COM comments, APP11 C2PA/JUMBF presence. Whole-segment removal (already
  shipped) plus tag-level *reading* inside EXIF/XMP/IPTC for reporting.
- **What MarkMyAss does NOT need:** Extended XMP reassembly, MPF, FlashPix,
  vendor preview images, trailer data, APP segments from specific cameras.
- **Implementation approach:** container walking already existed
  (`formats/jpeg.py`, spec-based). Tag-level reading added in
  `native/` (see EXIF/XMP/IPTC sections below) operating on the payloads
  the container layer already isolates.

## EXIF / TIFF (JPEG APP1, PNG eXIf, WebP EXIF)

- **Relevant ExifTool module(s):** `Exif.pm`.
- **What behavior was studied:** overall shape only — that ExifTool walks
  TIFF IFDs generically with guard rails (bounded sub-IFD counts,
  IFD validation, tolerance for broken offsets), and two real-world
  quirks worth handling: `UserComment` carries an 8-byte character-code
  header that some vendors fill incorrectly (e.g. `Unicode\0` casing),
  and writers disagree about whether the WebP EXIF chunk payload starts
  with the `Exif\0\0` prefix or raw TIFF (see WebP section). ExifTool's
  enormous per-vendor tag tables were explicitly NOT studied in detail
  and nothing from them was reproduced.
- **Relevant public specification:** TIFF 6.0 (byte order, IFD layout,
  field types/sizes); Exif 2.32 / CIPA DC-008-2019 (tag IDs for IFD0 /
  Exif IFD / GPS IFD, UserComment encoding header, pointer tags 0x8769 /
  0x8825).
- **What MarkMyAss actually needs:** walk IFD0 → Exif IFD → GPS IFD and
  surface a small, privacy/provenance-focused whitelist: ImageDescription,
  Make, Model, Software, Artist, Copyright, DateTime[Original/Digitized],
  UserComment, and the *presence* of any GPS tags. That is what our users
  are cleaning; nothing vendor-specific.
- **What MarkMyAss does NOT need:** MakerNotes, interoperability IFDs,
  thumbnails/IFD1 contents, color/rendering tags, the thousands of
  camera-specific tags.
- **Implementation approach:** `native/exif_tiff.py`, an independent
  bounded IFD walker written from the TIFF/Exif specifications: strict
  offset bounds-checking against the payload, entry-count caps, a
  visited-offset set to break cycles, value previews truncated, unknown
  tags surfaced only as counts. Tag names come from the public Exif
  specification's own tag names.

## XMP (JPEG APP1, PNG iTXt, WebP `XMP ` chunk, PDF /Metadata)

- **Relevant ExifTool module(s):** `XMP.pm`.
- **What behavior was studied:** shape only — XMP is RDF/XML with the
  same logical property expressible as an XML attribute or a child
  element, and multi-valued properties (e.g. creators) as RDF
  Seq/Bag/Alt item lists; property namespaces (dc, xmp, xmpMM,
  photoshop, Iptc4xmpExt) matter more than exact serialization.
- **Relevant public specification:** Adobe XMP Specification Part 1
  (data model, core namespaces) and Part 3 (embedding); Dublin Core;
  IPTC Extension schema (notably `Iptc4xmpExt:DigitalSourceType`, whose
  `trainedAlgorithmicMedia` value is the standard "this is AI-generated"
  marker).
- **What MarkMyAss actually needs:** detect and preview a whitelist of
  provenance/privacy properties: dc:creator, dc:description, dc:rights,
  xmp:CreatorTool, xmp:CreateDate/ModifyDate, photoshop:Credit/Source,
  pdf:Producer, xmpMM:DocumentID/InstanceID/History (provenance chain),
  Iptc4xmpExt:DigitalSourceType (AI-provenance), exif:GPS* mirrors.
- **What MarkMyAss does NOT need:** full RDF data-model parsing,
  Extended XMP reassembly, schema validation, writing XMP.
- **Implementation approach:** `native/xmp.py` — a deliberately
  non-XML-parser extractor: size-capped, pattern-based scanning for the
  whitelisted properties in both attribute and element/list forms.
  Rationale: uploaded files are hostile; a bounded scanner has no entity
  expansion, no parser state explosion, and can't be made quadratic by
  crafted nesting. Removal remains whole-container (already shipped).

## IPTC IIM (JPEG APP13 via Photoshop 8BIM)

- **Relevant ExifTool module(s):** `IPTC.pm`, `Photoshop.pm`.
- **What behavior was studied:** the dataset wire format's real-world
  tolerances — the 5-byte dataset header (0x1C marker byte, record
  number, dataset number, 16-bit big-endian length); the "extended"
  length form where the high bit of the 16-bit length flags that the low
  15 bits give the byte-count of a following variable-length big-endian
  length integer; that some writers null-pad the IPTC block; that records
  can appear out of order.
- **Relevant public specification:** IPTC-NAA Information Interchange
  Model (IIM) v4 (record/dataset numbers and meanings); Adobe Photoshop
  File Formats spec (8BIM resource framing: `8BIM` signature, 16-bit
  resource ID — 0x0404 for IPTC — Pascal-padded name, 32-bit size,
  even-padded data).
- **What MarkMyAss actually needs:** record 2 (application) datasets that
  carry identity/provenance: By-line (2:80), By-line Title (2:85),
  Credit (2:110), Source (2:115), Copyright Notice (2:116),
  Headline (2:105), Caption/Abstract (2:120), Writer/Editor (2:122),
  Keywords (2:25), Originating Program (2:65) + Program Version (2:70),
  creation date/time (2:55, 2:60). Everything else surfaces as a count.
- **What MarkMyAss does NOT need:** record 1 envelope routing datasets,
  record 3+ (pre-object/objectdata), writing IIM, character-set
  negotiation via 1:90 (values are previewed as UTF-8-with-fallback).
- **Implementation approach:** `native/iptc.py` — 8BIM walker + IIM
  dataset walker written from the two public specs, with the studied
  tolerances (null padding, extended lengths, bounds checks, dataset
  count cap) implemented independently.

## PNG

- **Relevant ExifTool module(s):** `PNG.pm`.
- **What behavior was studied:** which chunks carry metadata in practice
  (tEXt/zTXt/iTXt, tIME, the standardized `eXIf` chunk holding raw TIFF)
  plus awareness of the nonstandard `zxIf` experiment (ignored by us);
  that XMP lives in an iTXt with keyword `XML:com.adobe.xmp` and is
  supposed to be uncompressed there; that AI image generators commonly
  write their generation parameters into text chunks (e.g. a `parameters`
  tEXt for Stable Diffusion family tools).
- **Relevant public specification:** PNG (Third Edition, W3C) — chunk
  layout, tEXt/zTXt/iTXt field structure, eXIf chunk; XMP Spec Part 3
  (PNG embedding rules).
- **What MarkMyAss actually needs:** keyword→value extraction from all
  three text chunk types (with bounded zlib inflation for zTXt/compressed
  iTXt), classification of well-known keywords (Author, Software,
  Comment, Description, Title, Source, Copyright, Creation Time) plus
  AI-generator keys (`parameters`, `prompt`, `workflow`, ...) as
  provenance, eXIf routed through the native TIFF walker.
- **What MarkMyAss does NOT need:** color/physical chunks as signals,
  APNG internals, `zxIf`.
- **Implementation approach:** container walking existed
  (`formats/png.py`); `native/png_text.py` adds spec-based field parsing
  of the three text chunk layouts with a hard cap on decompressed size
  (zip-bomb defense) and keyword classification.

## WebP (RIFF)

- **Relevant ExifTool module(s):** `RIFF.pm`.
- **What behavior was studied:** one concrete interoperability fact — the
  `EXIF` chunk payload is raw TIFF per the WebP spec, but real files also
  exist with a leading `Exif\0\0` prefix, and a robust reader accepts
  both.
- **Relevant public specification:** WebP Container Specification
  (Google) — RIFF framing, `EXIF` and `XMP ` chunks, even-byte padding.
- **What MarkMyAss actually needs:** EXIF chunk → native TIFF walker
  (with optional prefix sniffing); `XMP ` chunk → native XMP extractor.
- **What MarkMyAss does NOT need:** animation/frame internals, ICC as a
  signal, other RIFF form types (AVI/WAV).
- **Implementation approach:** container walking existed
  (`formats/webp.py`); tag-level reading is pure reuse of the two native
  parsers plus the prefix sniff.

## PDF

- **Relevant ExifTool module(s):** `PDF.pm`.
- **What behavior was studied:** shape only — DocInfo lives in the
  trailer's /Info dictionary; incremental updates can leave multiple
  /Info generations (latest wins); XMP lives in /Root /Metadata. We
  deliberately do not parse PDF object syntax ourselves.
- **Relevant public specification:** ISO 32000-1 (Document information
  dictionary §14.3.3, Metadata streams §14.3.2).
- **What MarkMyAss actually needs:** the standard DocInfo keys (Title,
  Author, Subject, Keywords, Creator, Producer, CreationDate, ModDate,
  plus any custom keys surfaced generically) and the XMP packet routed
  through the native XMP extractor.
- **What MarkMyAss does NOT need:** encrypted-PDF credential handling
  beyond what pikepdf exposes, embedded-file traversal, JavaScript,
  form fields.
- **Implementation approach:** THIRD_PARTY_LIBRARY — pikepdf (MPL-2.0,
  already a dependency) resolves the object graph safely;
  `native/pdf_info.py` only classifies the resolved DocInfo keys and
  feeds /Metadata bytes to the XMP extractor. Incremental-update
  semantics are pikepdf's resolved view, which matches "latest wins."

## Text / hidden Unicode

- **Relevant ExifTool module(s):** none — out of ExifTool's scope.
- **Specification:** Unicode Standard (format/invisible characters, Tags
  block U+E0000–E007F).
- **Status:** already fully native (`detectors/unicode.py`), unchanged by
  this work.

## C2PA / Content Credentials

- **Relevant ExifTool module(s):** `Jpeg2000.pm`/JUMBF handling was NOT
  studied; scope unchanged.
- **Specification:** C2PA spec + ISO/IEC 19566-5 (JUMBF).
- **Status:** unchanged — structural container detection/removal
  (PARTIAL), with c2patool as the optional independent check. This work
  does not expand C2PA claims.

---

## Differential-testing corpus

Two suites, both ExifTool-gated (they run in CI's independent-
verification job and in the WSL environment):

- **Base corpus** (`tests/integration/test_native_vs_exiftool.py`):
  the rich generated fixtures (JPEG / PNG / WebP / PDF, plus a bare
  control file), inspected and cleaned.
- **Edge corpus** (`tests/integration/test_native_vs_exiftool_edge.py`):
  big-endian (`MM`) TIFF EXIF; UTF-16-encoded XMP packets (transcoded
  before scanning); multi-segment Extended XMP (main packet +
  extension-URI APP1 overflow segments -- also *removed together*, so a
  cleaned file can't retain overflow XMP); out-of-order,
  null-padded IPTC blocks; vendor-cased `Unicode\0` UserComment with
  UTF-16 payload; wrapper-less single-quoted XMP. Every edge file is
  asserted both on inspect agreement and on clean-to-empty agreement.

## Differential-testing contract

For every supported fixture: MarkMyAss native inspect and
`exiftool -j -G1 -a -s` are both run; ExifTool's output is normalized
through the existing origin classifier (embedded vs structural vs
filesystem vs computed) and then mapped tag-by-tag into MarkMyAss's
signal categories; the comparison asserts per-category presence
agreement **within MarkMyAss's supported scope only**. Cleaning tests
additionally assert: native detect → clean → output still parses →
native verify reports the signal gone → ExifTool independently reports
no embedded metadata → pixel/page payload untouched where our guarantees
require it. Disagreement is surfaced, never silently upgraded to
VERIFIED CLEAN (existing PARTIAL verdict semantics).
