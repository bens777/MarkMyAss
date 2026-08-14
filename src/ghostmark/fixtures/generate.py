"""Generators for synthetic demo/test fixtures containing safe example metadata.

The EXIF payloads are built by :func:`build_tiff` -- an independent,
spec-correct little TIFF writer (TIFF 6.0 + Exif 2.32 layouts; provenance:
PUBLIC_SPEC / OWN_IMPLEMENTATION) -- so fixtures carry REAL tag-level
metadata (Artist, Software, GPS, dates, UserComment) that both
MarkMyAss's native engine and ExifTool can read. That makes these
fixtures the substrate for the native-vs-ExifTool differential tests.
"""

from __future__ import annotations

import io
import zlib
from pathlib import Path

from PIL import Image

from ghostmark.formats import jpeg, png, webp

# ---------------------------------------------------------------------------
# Minimal spec-correct TIFF/Exif builder (little-endian).
# ---------------------------------------------------------------------------

_ASCII = 2
_SHORT = 3
_LONG = 4
_RATIONAL = 5
_UNDEFINED = 7

_TYPE_SIZES = {_ASCII: 1, _SHORT: 2, _LONG: 4, _RATIONAL: 8, _UNDEFINED: 1}


def _encode_value(vtype: int, value, byteorder: str = "little") -> bytes:
    if vtype == _ASCII:
        return value.encode("ascii") + b"\x00"
    if vtype == _SHORT:
        return value.to_bytes(2, byteorder)
    if vtype == _LONG:
        return value.to_bytes(4, byteorder)
    if vtype == _RATIONAL:
        out = b""
        for num, den in value:
            out += num.to_bytes(4, byteorder) + den.to_bytes(4, byteorder)
        return out
    if vtype == _UNDEFINED:
        return value
    raise ValueError(f"unsupported TIFF type {vtype}")


def _count_for(vtype: int, encoded: bytes) -> int:
    return len(encoded) // _TYPE_SIZES[vtype]


def build_tiff(ifd0: list[tuple[int, int, object]],
               exif_ifd: list[tuple[int, int, object]] | None = None,
               gps_ifd: list[tuple[int, int, object]] | None = None,
               *, byteorder: str = "little") -> bytes:
    """Build a TIFF (``II`` little- or ``MM`` big-endian) with sub-IFDs.

    Each entry is ``(tag_id, tiff_type, value)``. Layout: header, IFD0,
    Exif IFD, GPS IFD, then all out-of-line values.
    """

    ifd0 = list(ifd0)
    pointers: list[tuple[int, int]] = []  # (tag_id, target index) resolved later

    sub_ifds: list[list[tuple[int, int, object]]] = []
    if exif_ifd:
        pointers.append((0x8769, len(sub_ifds)))
        sub_ifds.append(list(exif_ifd))
    if gps_ifd:
        pointers.append((0x8825, len(sub_ifds)))
        sub_ifds.append(list(gps_ifd))

    def ifd_size(entries_count: int) -> int:
        return 2 + entries_count * 12 + 4

    header_len = 8
    ifd0_count = len(ifd0) + len(pointers)
    ifd0_off = header_len
    sub_offsets: list[int] = []
    cursor = ifd0_off + ifd_size(ifd0_count)
    for sub in sub_ifds:
        sub_offsets.append(cursor)
        cursor += ifd_size(len(sub))
    data_off = cursor  # out-of-line value area starts here

    data_area = bytearray()

    def render_entries(entries: list[tuple[int, int, object]],
                       extra_pointers: list[tuple[int, int]] | None = None) -> bytes:
        nonlocal data_area
        rows: list[tuple[int, bytes]] = []
        for tag_id, vtype, value in entries:
            encoded = _encode_value(vtype, value, byteorder)
            count = _count_for(vtype, encoded)
            if len(encoded) <= 4:
                field = encoded + b"\x00" * (4 - len(encoded))
            else:
                off = data_off + len(data_area)
                data_area += encoded
                if len(encoded) % 2:
                    data_area += b"\x00"
                field = off.to_bytes(4, byteorder)
            rows.append((tag_id, vtype.to_bytes(2, byteorder)
                         + count.to_bytes(4, byteorder) + field))
        for tag_id, sub_index in (extra_pointers or []):
            field = sub_offsets[sub_index].to_bytes(4, byteorder)
            rows.append((tag_id, _LONG.to_bytes(2, byteorder)
                         + (1).to_bytes(4, byteorder) + field))
        rows.sort(key=lambda r: r[0])  # TIFF requires ascending tag order
        out = len(rows).to_bytes(2, byteorder)
        for tag_id, rest in rows:
            out += tag_id.to_bytes(2, byteorder) + rest
        out += (0).to_bytes(4, byteorder)  # no next IFD
        return out

    ifd0_bytes = render_entries(ifd0, pointers)
    sub_bytes = [render_entries(sub) for sub in sub_ifds]

    out = bytearray()
    mark = b"II*\x00" if byteorder == "little" else b"MM\x00*"
    out += mark + ifd0_off.to_bytes(4, byteorder)
    out += ifd0_bytes
    for sb in sub_bytes:
        out += sb
    out += data_area
    return bytes(out)


def demo_exif_tiff() -> bytes:
    """A TIFF payload with identity, software, timestamp, comment and GPS tags."""

    user_comment = b"ASCII\x00\x00\x00" + b"MarkMyAss demo user comment"
    return build_tiff(
        ifd0=[
            (0x010E, _ASCII, "MarkMyAss demo image description"),
            (0x0131, _ASCII, "MarkMyAss Demo Suite 1.0"),
            (0x0132, _ASCII, "2026:01:02 03:04:05"),
            (0x013B, _ASCII, "Demo Artist"),
            (0x8298, _ASCII, "Copyright Demo Holder"),
        ],
        exif_ifd=[
            (0x9003, _ASCII, "2026:01:02 03:04:05"),
            (0x9286, _UNDEFINED, user_comment),
        ],
        gps_ifd=[
            (0x0001, _ASCII, "N"),
            (0x0002, _RATIONAL, [(48, 1), (51, 1), (24, 1)]),
            (0x0003, _ASCII, "E"),
            (0x0004, _RATIONAL, [(2, 1), (21, 1), (3, 1)]),
        ],
    )


_DEMO_XMP = b"""<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/"
    xmp:CreatorTool="MarkMyAss Demo Generator">
   <dc:creator><rdf:Seq><rdf:li>GhostMark Demo Fixture</rdf:li></rdf:Seq></dc:creator>
   <dc:description><rdf:Alt><rdf:li xml:lang="x-default">Synthetic demo file</rdf:li></rdf:Alt></dc:description>
   <Iptc4xmpExt:DigitalSourceType>http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia</Iptc4xmpExt:DigitalSourceType>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


def build_iptc_8bim(datasets: list[tuple[int, int, bytes]]) -> bytes:
    """Wrap IIM datasets in a spec-correct Photoshop 8BIM resource block."""

    iim = b""
    for record, dataset, value in datasets:
        iim += bytes([0x1C, record, dataset]) + len(value).to_bytes(2, "big") + value
    block = b"8BIM" + (0x0404).to_bytes(2, "big") + b"\x00\x00"  # empty Pascal name, padded
    block += len(iim).to_bytes(4, "big") + iim
    if len(iim) % 2:
        block += b"\x00"
    return block


def demo_iptc_payload() -> bytes:
    return jpeg.PHOTOSHOP_PREFIX + build_iptc_8bim([
        (2, 80, b"Demo By-line Author"),
        (2, 110, b"MarkMyAss Demo Credit"),
        (2, 116, b"Copyright Demo Holder"),
        (2, 120, b"Synthetic demo caption"),
    ])


def demo_text() -> str:
    """Multilingual text containing safe-to-detect hidden Unicode signals."""

    zwsp = chr(0x200B)  # ZERO WIDTH SPACE
    word_joiner = chr(0x2060)  # WORD JOINER
    tag_chars = "".join(chr(0xE0000 + ord(c)) for c in "ghostmark" if 0x20 <= ord(c) <= 0x7E)

    return (
        "GhostMark demo fixture.\n\n"
        f"English: This{zwsp} text{zwsp} contains{word_joiner} hidden characters.\n"
        "French: J'aime l'intelligence artificielle. Ça fonctionne très bien.\n"
        "German: Übermäßige Änderungen dürfen den Text nicht beschädigen.\n"
        "Emoji: 👻 🔍 ✅\n"
        f"Hidden tag block: {tag_chars}\n"
        "```python\nprint('code blocks are preserved')\n```\n"
    )


def make_jpeg_fixture(path: Path) -> None:
    """A small JPEG with tag-level EXIF, XMP, IPTC and comment segments."""

    base = Image.new("RGB", (64, 64), color=(120, 160, 200))
    buf = io.BytesIO()
    base.save(buf, format="JPEG", quality=90)
    data = buf.getvalue()

    segments, rest = jpeg.parse_header_segments(data)
    sos = segments[-1]
    header_segments = segments[:-1]

    new_segments = [
        *header_segments,
        jpeg.Segment(marker=jpeg.APP1, payload=jpeg.EXIF_PREFIX + demo_exif_tiff()),
        jpeg.Segment(marker=jpeg.APP1, payload=jpeg.XMP_PREFIX + _DEMO_XMP),
        jpeg.Segment(marker=jpeg.APP13, payload=demo_iptc_payload()),
        jpeg.Segment(marker=jpeg.COM,
                     payload=b"Generated by GhostMark demo fixtures. Not real camera output."),
        sos,
    ]
    path.write_bytes(jpeg.rebuild(new_segments, rest))


def make_png_fixture(path: Path) -> None:
    """A small PNG with tEXt/zTXt/iTXt text, AI-generator keys, XMP and eXIf."""

    base = Image.new("RGB", (64, 64), color=(200, 140, 120))
    buf = io.BytesIO()
    base.save(buf, format="PNG")
    data = buf.getvalue()

    chunks = png.parse_chunks(data)
    iend_index = next(i for i, c in enumerate(chunks) if c.type == b"IEND")

    ztxt_value = zlib.compress(b"Compressed demo comment via zTXt")
    itxt_body = (b"Description\x00\x00\x00en\x00\x00"
                 b"International demo description via iTXt")
    new_chunks = chunks[:iend_index] + [
        png.Chunk(type=b"tEXt", data=b"Author\x00Demo PNG Author"),
        png.Chunk(type=b"tEXt", data=b"Software\x00MarkMyAss Demo Suite 1.0"),
        png.Chunk(type=b"tEXt",
                  data=b"parameters\x00demo prompt, sampler=demo, steps=1"),
        png.Chunk(type=b"zTXt", data=b"Comment\x00\x00" + ztxt_value),
        png.Chunk(type=b"iTXt", data=itxt_body),
        png.Chunk(type=b"iTXt", data=b"XML:com.adobe.xmp\x00\x00\x00\x00\x00" + _DEMO_XMP),
        png.Chunk(type=b"eXIf", data=demo_exif_tiff()),
    ] + chunks[iend_index:]
    path.write_bytes(png.rebuild(new_chunks))


def make_webp_fixture(path: Path) -> None:
    """A small WebP with EXIF (raw TIFF form) and XMP chunks."""

    base = Image.new("RGB", (64, 64), color=(140, 200, 160))
    buf = io.BytesIO()
    base.save(buf, format="WEBP", lossless=True)
    data = buf.getvalue()

    chunks = webp.parse_chunks(data)
    chunks.append(webp.Chunk(fourcc=b"EXIF", data=demo_exif_tiff()))
    chunks.append(webp.Chunk(fourcc=b"XMP ", data=_DEMO_XMP))
    path.write_bytes(webp.rebuild(chunks))


def make_pdf_fixture(path: Path) -> None:
    """A small single-page PDF with DocInfo and XMP metadata."""

    import pikepdf

    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    with pdf.open_metadata() as meta:
        meta["dc:title"] = "GhostMark Demo Fixture"
        meta["dc:creator"] = ["GhostMark demo fixtures"]
        meta["xmp:CreatorTool"] = "GhostMark demo generator"
    pdf.docinfo["/Title"] = "GhostMark Demo Fixture"
    pdf.docinfo["/Author"] = "GhostMark demo fixtures"
    pdf.docinfo["/Producer"] = "GhostMark"
    pdf.save(str(path))
    pdf.close()


def generate_all(directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "text": directory / "demo.txt",
        "jpeg": directory / "demo.jpg",
        "png": directory / "demo.png",
        "webp": directory / "demo.webp",
        "pdf": directory / "demo.pdf",
    }
    paths["text"].write_text(demo_text(), encoding="utf-8")
    make_jpeg_fixture(paths["jpeg"])
    make_png_fixture(paths["png"])
    make_webp_fixture(paths["webp"])
    make_pdf_fixture(paths["pdf"])
    return paths
