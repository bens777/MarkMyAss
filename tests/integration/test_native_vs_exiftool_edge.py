"""Differential edge-case corpus: native engine vs ExifTool on hard inputs.

Extends the base differential suite with the corpus the base fixtures
don't cover: big-endian TIFF, UTF-16-encoded XMP, multi-segment
Extended XMP, and malformed-but-readable metadata that real-world
writers actually produce. Same contract as the base suite: per-category
presence agreement within MarkMyAss's supported scope, and cleaned
files must agree as empty.
"""

from __future__ import annotations

import io
import shutil
import uuid
from pathlib import Path

import pytest
from PIL import Image

from ghostmark.cleaners.image import clean_image_bytes
from ghostmark.fixtures.generate import _ASCII, _UNDEFINED, build_iptc_8bim, build_tiff
from ghostmark.formats import jpeg

from .test_native_vs_exiftool import _SCOPE, _exiftool_categories, _native_categories

pytestmark = pytest.mark.skipif(
    shutil.which("exiftool") is None,
    reason="ExifTool is not installed locally; this suite runs in CI's independent-verification job.",
)


def _bare_jpeg_segments():
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), color=(80, 90, 100)).save(buf, format="JPEG", quality=85)
    segments, rest = jpeg.parse_header_segments(buf.getvalue())
    return segments[:-1], segments[-1], rest


def _write_jpeg(path: Path, extra_segments: list[jpeg.Segment]) -> None:
    header, sos, rest = _bare_jpeg_segments()
    path.write_bytes(jpeg.rebuild([*header, *extra_segments, sos], rest))


# --- corpus builders --------------------------------------------------------------------

def _big_endian_exif(path: Path) -> None:
    tiff = build_tiff(
        ifd0=[(0x013B, _ASCII, "Big Endian Artist"), (0x0131, _ASCII, "BE Writer 2.0")],
        gps_ifd=[(0x0001, _ASCII, "N")],
        byteorder="big",
    )
    _write_jpeg(path, [jpeg.Segment(marker=jpeg.APP1, payload=jpeg.EXIF_PREFIX + tiff)])


def _utf16_xmp(path: Path) -> None:
    xml = ('<?xpacket begin="﻿"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
           '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
           '<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/" '
           'xmlns:xmp="http://ns.adobe.com/xap/1.0/" '
           'xmp:CreatorTool="UTF-16 Tool">'
           "<dc:creator><rdf:Seq><rdf:li>UTF16 Author</rdf:li></rdf:Seq></dc:creator>"
           "</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end=\"w\"?>")
    packet = xml.encode("utf-16-le")  # BOM comes from ﻿ in the header
    _write_jpeg(path, [jpeg.Segment(marker=jpeg.APP1, payload=jpeg.XMP_PREFIX + packet)])


def _extended_xmp(path: Path) -> None:
    guid = uuid.uuid4().hex.upper().encode("ascii")[:32].ljust(32, b"0")
    extended_xml = (b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
                    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
                    b'<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/">'
                    b"<dc:description><rdf:Alt><rdf:li xml:lang='x-default'>"
                    b"Overflow description in extended packet</rdf:li></rdf:Alt>"
                    b"</dc:description></rdf:Description></rdf:RDF></x:xmpmeta>")
    main_xml = (b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
                b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
                b'<rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/"'
                b' xmlns:xmpNote="http://ns.adobe.com/xmp/note/"'
                b' xmp:CreatorTool="Main Packet Tool" xmpNote:HasExtendedXMP="'
                + guid + b'"/></rdf:RDF></x:xmpmeta>')
    ext_payload = (jpeg.EXTENDED_XMP_PREFIX + guid
                   + len(extended_xml).to_bytes(4, "big") + (0).to_bytes(4, "big")
                   + extended_xml)
    _write_jpeg(path, [
        jpeg.Segment(marker=jpeg.APP1, payload=jpeg.XMP_PREFIX + main_xml),
        jpeg.Segment(marker=jpeg.APP1, payload=ext_payload),
    ])


def _messy_iptc(path: Path) -> None:
    # Out-of-order datasets + 64 bytes of trailing null padding (iMatch-style).
    block = build_iptc_8bim([
        (2, 120, b"Caption written before byline"),
        (2, 80, b"Out Of Order Author"),
    ])
    # splice padding INSIDE the IIM data: rebuild resource with padded payload
    iim = (bytes([0x1C, 2, 120]) + (29).to_bytes(2, "big") + b"Caption written before byline"
           + bytes([0x1C, 2, 80]) + (19).to_bytes(2, "big") + b"Out Of Order Author"
           + b"\x00" * 64)
    block = (b"8BIM" + (0x0404).to_bytes(2, "big") + b"\x00\x00"
             + len(iim).to_bytes(4, "big") + iim)
    _write_jpeg(path, [jpeg.Segment(marker=jpeg.APP13, payload=jpeg.PHOTOSHOP_PREFIX + block)])


def _ricoh_style_usercomment(path: Path) -> None:
    # Vendor quirk: "Unicode\0" charset header (nonstandard casing) with
    # UTF-16LE payload -- both engines should still report a comment.
    comment = "Ricoh-style unicode comment".encode("utf-16-le")
    tiff = build_tiff(
        ifd0=[(0x0131, _ASCII, "QuirkCam 1.0")],
        exif_ifd=[(0x9286, _UNDEFINED, b"Unicode\x00" + comment)],
    )
    _write_jpeg(path, [jpeg.Segment(marker=jpeg.APP1, payload=jpeg.EXIF_PREFIX + tiff)])


def _unwrapped_single_quote_xmp(path: Path) -> None:
    # No <?xpacket?> wrapper, single-quoted attributes -- still valid XMP.
    xml = (b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
           b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
           b"<rdf:Description xmlns:xmp='http://ns.adobe.com/xap/1.0/'"
           b" xmp:CreatorTool='Sparse Writer'/></rdf:RDF></x:xmpmeta>")
    _write_jpeg(path, [jpeg.Segment(marker=jpeg.APP1, payload=jpeg.XMP_PREFIX + xml)])


_CORPUS = {
    "big_endian_exif": _big_endian_exif,
    "utf16_xmp": _utf16_xmp,
    "extended_xmp": _extended_xmp,
    "messy_iptc": _messy_iptc,
    "ricoh_usercomment": _ricoh_style_usercomment,
    "unwrapped_xmp": _unwrapped_single_quote_xmp,
}


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_edge_corpus_native_and_exiftool_agree(tmp_path, name):
    path = tmp_path / f"{name}.jpg"
    _CORPUS[name](path)
    native = _native_categories(path) & _SCOPE
    oracle = _exiftool_categories(path) & _SCOPE
    assert native == oracle, (
        f"{name}: native={sorted(native)} exiftool={sorted(oracle)} "
        f"(missing from native: {sorted(oracle - native)}; "
        f"native-only: {sorted(native - oracle)})"
    )
    assert native, f"{name}: corpus file must actually contain scoped signals"


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_edge_corpus_cleans_to_agreement(tmp_path, name):
    path = tmp_path / f"{name}.jpg"
    _CORPUS[name](path)
    cleaned, _ = clean_image_bytes(path.read_bytes(), ".jpg")
    out = tmp_path / f"{name}.cleaned.jpg"
    out.write_bytes(cleaned)
    assert _native_categories(out) & _SCOPE == set()
    assert _exiftool_categories(out) & _SCOPE == set()
