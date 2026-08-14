"""Unit tests for the native tag-level metadata engine (no ExifTool needed).

Covers: spec-correct parsing on rich fixtures, hostile-input bounds
(zip bombs, cyclic IFDs, truncation), and the clean -> native-verify
round trip for every supported format.
"""

from __future__ import annotations

import zlib
from pathlib import Path

import pytest

from ghostmark.cleaners.image import clean_image_bytes
from ghostmark.detectors.metadata import inspect_image_metadata, inspect_pdf_metadata
from ghostmark.fixtures.generate import (
    build_iptc_8bim,
    demo_exif_tiff,
    generate_all,
    make_jpeg_fixture,
    make_png_fixture,
    make_webp_fixture,
)
from ghostmark.models import Status
from ghostmark.native import exif_tiff, iptc, png_text, xmp
from ghostmark.native.signals import SignalCategory

# --- EXIF/TIFF walker -----------------------------------------------------------------

def test_exif_walker_extracts_whitelisted_tags_and_gps_presence():
    fields = exif_tiff.parse_exif_fields(demo_exif_tiff())
    by_tag = {f.tag: f for f in fields}
    assert by_tag["Artist"].category is SignalCategory.AUTHOR
    assert by_tag["Artist"].preview == "Demo Artist"
    assert by_tag["Software"].category is SignalCategory.SOFTWARE
    assert by_tag["UserComment"].preview == "MarkMyAss demo user comment"
    assert by_tag["DateTimeOriginal"].category is SignalCategory.TIMESTAMP
    gps = [f for f in fields if f.category is SignalCategory.GPS]
    assert {f.tag for f in gps} >= {"GPSLatitude", "GPSLongitude"}
    # GPS previews never leak coordinates.
    assert all(f.preview == "(location data present)" for f in gps)


def test_exif_walker_accepts_exif_prefix_and_raw_tiff():
    raw = demo_exif_tiff()
    with_prefix = exif_tiff.EXIF_PREFIX + raw
    assert exif_tiff.parse_exif_fields(raw) == exif_tiff.parse_exif_fields(with_prefix)


def test_exif_walker_survives_cyclic_ifd_pointers():
    # IFD0 whose Exif-IFD pointer points back at IFD0 itself (offset 8).
    tiff = bytearray(b"II*\x00" + (8).to_bytes(4, "little"))
    tiff += (1).to_bytes(2, "little")  # one entry
    tiff += (0x8769).to_bytes(2, "little") + (4).to_bytes(2, "little")
    tiff += (1).to_bytes(4, "little") + (8).to_bytes(4, "little")  # points to IFD0
    tiff += (0).to_bytes(4, "little")
    fields = exif_tiff.parse_exif_fields(bytes(tiff))  # must terminate
    assert isinstance(fields, list)


def test_exif_walker_survives_truncated_payloads():
    raw = demo_exif_tiff()
    for cut in (9, 12, 20, len(raw) // 2):
        fields = exif_tiff.parse_exif_fields(raw[:cut])
        assert isinstance(fields, list)
    with pytest.raises(exif_tiff.ExifParseError):
        exif_tiff.parse_exif_fields(b"XX")


# --- XMP extractor --------------------------------------------------------------------

def test_xmp_extractor_reads_element_attribute_and_list_forms():
    packet = (b'<x:xmpmeta><rdf:Description xmp:CreatorTool="Attr Tool">'
              b"<dc:creator><rdf:Seq><rdf:li>First Author</rdf:li>"
              b"<rdf:li>Second Author</rdf:li></rdf:Seq></dc:creator>"
              b"<Iptc4xmpExt:DigitalSourceType>trainedAlgorithmicMedia"
              b"</Iptc4xmpExt:DigitalSourceType></rdf:Description></x:xmpmeta>")
    fields = {f.tag: f for f in xmp.parse_xmp_fields(packet)}
    assert fields["xmp:CreatorTool"].preview == "Attr Tool"
    assert "First Author" in fields["dc:creator"].preview
    assert "Second Author" in fields["dc:creator"].preview
    assert fields["Iptc4xmpExt:DigitalSourceType"].category is SignalCategory.PROVENANCE


def test_xmp_extractor_is_size_capped():
    # A property hidden past the scan cap must simply be ignored, fast.
    packet = b"x" * (600 * 1024) + b"<dc:creator>late</dc:creator>"
    assert xmp.parse_xmp_fields(packet) == []


# --- IPTC parser ----------------------------------------------------------------------

def test_iptc_parser_reads_record2_datasets():
    payload = build_iptc_8bim([
        (2, 80, b"Jane Byline"),
        (2, 116, b"(c) Someone"),
        (2, 65, b"GeneratorApp"),
    ])
    fields = {f.tag: f for f in iptc.parse_iptc_fields(payload)}
    assert fields["By-line"].preview == "Jane Byline"
    assert fields["By-line"].category is SignalCategory.AUTHOR
    assert fields["OriginatingProgram"].category is SignalCategory.SOFTWARE


def test_iptc_parser_handles_extended_length_and_null_padding():
    value = b"V" * 70000  # forces the extended-length form in a writer...
    # ...but we hand-build it: 5-byte header with high-bit length flag.
    ext = bytes([0x1C, 2, 120]) + (0x8000 | 4).to_bytes(2, "big") + len(value).to_bytes(4, "big") + value
    block = b"8BIM" + (0x0404).to_bytes(2, "big") + b"\x00\x00" + len(ext + b"\x00\x00").to_bytes(4, "big") + ext + b"\x00\x00"
    fields = iptc.parse_iptc_fields(block)
    tags = {f.tag for f in fields}
    assert "Caption-Abstract" in tags


# --- PNG text parser ------------------------------------------------------------------

def test_png_ztxt_inflation_is_bounded():
    bomb = zlib.compress(b"A" * (50 * 1024 * 1024))  # 50MB inflates from ~50KB
    field = png_text.parse_text_chunk_field(b"zTXt", b"Comment\x00\x00" + bomb)
    assert field is not None
    assert len(field.preview) <= 121  # preview cap, not 50MB


def test_png_ai_generator_keywords_are_provenance():
    field = png_text.parse_text_chunk_field(b"tEXt", b"parameters\x00steps: 20, cfg: 7")
    assert field is not None and field.category is SignalCategory.PROVENANCE


# --- clean -> native verify round trips ------------------------------------------------

@pytest.mark.parametrize("maker,suffix", [
    (make_jpeg_fixture, ".jpg"),
    (make_png_fixture, ".png"),
    (make_webp_fixture, ".webp"),
])
def test_clean_removes_all_native_fields(tmp_path: Path, maker, suffix):
    src = tmp_path / f"fixture{suffix}"
    maker(src)

    before = inspect_image_metadata(src)
    before_fields = [f for d in before for f in d.details.get("fields", [])]
    assert before_fields, "fixture must contain tag-level metadata"

    cleaned, _actions = clean_image_bytes(src.read_bytes(), suffix)
    out = tmp_path / f"cleaned{suffix}"
    out.write_bytes(cleaned)

    after = inspect_image_metadata(out)
    for d in after:
        assert d.status is Status.NOT_FOUND, f"{d.detector} still FOUND after clean"
        assert not d.details.get("fields"), f"{d.detector} still has fields after clean"


def test_clean_pdf_removes_all_native_fields(tmp_path: Path):
    from ghostmark.cleaners.pdf import clean_pdf_file
    paths = generate_all(tmp_path)
    out = tmp_path / "cleaned.pdf"
    clean_pdf_file(paths["pdf"], out)
    after = inspect_pdf_metadata(out)
    for d in after:
        assert d.status is Status.NOT_FOUND
        assert not d.details.get("fields")


def test_cleaning_preserves_pixels(tmp_path: Path):
    from PIL import Image
    src = tmp_path / "fixture.png"
    make_png_fixture(src)
    cleaned, _ = clean_image_bytes(src.read_bytes(), ".png")
    out = tmp_path / "cleaned.png"
    out.write_bytes(cleaned)
    assert Image.open(src).convert("RGB").tobytes() == \
           Image.open(out).convert("RGB").tobytes()
