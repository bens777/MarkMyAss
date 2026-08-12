"""Image metadata detect/clean: EXIF/XMP/IPTC removed, pixels and ICC preserved."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from ghostmark.cleaners.c2pa import clean_c2pa_bytes
from ghostmark.cleaners.image import clean_image_bytes
from ghostmark.detectors.c2pa import detect as detect_c2pa
from ghostmark.detectors.metadata import inspect_image_metadata
from ghostmark.fixtures.generate import make_jpeg_fixture, make_png_fixture
from ghostmark.formats import jpeg, png, webp
from ghostmark.models import Status


def _pixels(data: bytes) -> bytes:
    import io

    return Image.open(io.BytesIO(data)).convert("RGB").tobytes()


def test_jpeg_fixture_detects_exif_xmp_iptc_comment(tmp_path: Path):
    path = tmp_path / "demo.jpg"
    make_jpeg_fixture(path)
    detections = {d.detector: d for d in inspect_image_metadata(path)}
    assert detections["exif"].status is Status.FOUND
    assert detections["xmp"].status is Status.FOUND
    assert detections["iptc"].status is Status.FOUND
    assert detections["comment"].status is Status.FOUND


def test_jpeg_clean_removes_metadata_preserves_pixels(tmp_path: Path):
    path = tmp_path / "demo.jpg"
    make_jpeg_fixture(path)
    original_bytes = path.read_bytes()

    cleaned_bytes, actions = clean_image_bytes(original_bytes, ".jpg")

    by_detector = {a.detector: a for a in actions}
    assert by_detector["exif"].removed is True
    assert by_detector["xmp"].removed is True
    assert by_detector["iptc"].removed is True
    assert by_detector["comment"].removed is True
    assert by_detector["icc"].preserved is True

    assert _pixels(cleaned_bytes) == _pixels(original_bytes), "pixel data must be byte-identical after cleaning"

    cleaned_path = tmp_path / "demo.ghostmark.jpg"
    cleaned_path.write_bytes(cleaned_bytes)
    after = {d.detector: d for d in inspect_image_metadata(cleaned_path)}
    assert after["exif"].status is Status.NOT_FOUND
    assert after["xmp"].status is Status.NOT_FOUND
    assert after["iptc"].status is Status.NOT_FOUND


def test_jpeg_icc_profile_preserved(tmp_path: Path):
    base = Image.new("RGB", (32, 32), color=(10, 20, 30))
    import io

    buf = io.BytesIO()
    base.save(buf, format="JPEG")
    data = buf.getvalue()

    segments, rest = jpeg.parse_header_segments(data)
    icc_segment = jpeg.Segment(marker=jpeg.APP2, payload=jpeg.ICC_PREFIX + b"\x01\x01" + b"\x00" * 20)
    with_icc = jpeg.rebuild([*segments[:-1], icc_segment, segments[-1]], rest)

    cleaned_bytes, actions = clean_image_bytes(with_icc, ".jpg")
    kept_segments, _ = jpeg.parse_header_segments(cleaned_bytes)
    assert any(s.kind() == "icc" for s in kept_segments), "ICC profile segment must survive cleaning"


def test_png_fixture_detects_exif_xmp_text(tmp_path: Path):
    path = tmp_path / "demo.png"
    make_png_fixture(path)
    detections = {d.detector: d for d in inspect_image_metadata(path)}
    assert detections["exif"].status is Status.FOUND
    assert detections["xmp"].status is Status.FOUND
    assert detections["png_text"].status is Status.FOUND


def test_png_clean_removes_metadata_preserves_pixels(tmp_path: Path):
    path = tmp_path / "demo.png"
    make_png_fixture(path)
    original_bytes = path.read_bytes()

    cleaned_bytes, actions = clean_image_bytes(original_bytes, ".png")
    assert _pixels(cleaned_bytes) == _pixels(original_bytes)

    cleaned_path = tmp_path / "demo.ghostmark.png"
    cleaned_path.write_bytes(cleaned_bytes)
    after = {d.detector: d for d in inspect_image_metadata(cleaned_path)}
    assert after["exif"].status is Status.NOT_FOUND
    assert after["xmp"].status is Status.NOT_FOUND
    assert after["png_text"].status is Status.NOT_FOUND


def test_png_critical_chunks_survive(tmp_path: Path):
    path = tmp_path / "demo.png"
    make_png_fixture(path)
    cleaned_bytes, _ = clean_image_bytes(path.read_bytes(), ".png")
    chunk_types = [c.type for c in png.parse_chunks(cleaned_bytes)]
    assert b"IHDR" in chunk_types
    assert b"IDAT" in chunk_types
    assert b"IEND" in chunk_types


def test_webp_metadata_strip_roundtrip():
    base = Image.new("RGB", (16, 16), color=(1, 2, 3))
    import io

    buf = io.BytesIO()
    base.save(buf, format="WEBP")
    data = buf.getvalue()

    chunks = webp.parse_chunks(data)
    exif_chunk = webp.Chunk(fourcc=b"EXIF", data=b"fake-exif-data")
    xmp_chunk = webp.Chunk(fourcc=b"XMP ", data=b"<xmp/>")
    with_meta = webp.rebuild([*chunks, exif_chunk, xmp_chunk])

    cleaned_bytes, actions = clean_image_bytes(with_meta, ".webp")
    assert actions[0].removed is True  # exif
    assert actions[1].removed is True  # xmp
    remaining = webp.parse_chunks(cleaned_bytes)
    assert not any(c.fourcc in (b"EXIF", b"XMP ") for c in remaining)


def test_c2pa_not_detected_on_plain_fixture(tmp_path: Path):
    path = tmp_path / "demo.jpg"
    make_jpeg_fixture(path)
    result = detect_c2pa(path)
    assert result.status is Status.NOT_FOUND


def test_c2pa_jpeg_marker_detected_and_removed(tmp_path: Path):
    path = tmp_path / "demo.jpg"
    make_jpeg_fixture(path)
    data = path.read_bytes()
    segments, rest = jpeg.parse_header_segments(data)
    jumbf_segment = jpeg.Segment(marker=jpeg.APP11, payload=b"JP" + b"\x00" * 10)
    with_c2pa = jpeg.rebuild([*segments[:-1], jumbf_segment, segments[-1]], rest)
    injected_path = tmp_path / "with_c2pa.jpg"
    injected_path.write_bytes(with_c2pa)

    result = detect_c2pa(injected_path)
    assert result.status is Status.FOUND

    cleaned_bytes, action = clean_c2pa_bytes(with_c2pa, ".jpg")
    assert action.removed is True
    cleaned_path = tmp_path / "cleaned_c2pa.jpg"
    cleaned_path.write_bytes(cleaned_bytes)
    assert detect_c2pa(cleaned_path).status is Status.NOT_FOUND
