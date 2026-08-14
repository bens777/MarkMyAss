"""PDF metadata detect/clean: DocInfo + XMP removed, document stays structurally readable."""

from __future__ import annotations

from pathlib import Path

import pikepdf

from ghostmark.cleaners.pdf import clean_pdf_file, verify_pdf_readable
from ghostmark.detectors.metadata import inspect_pdf_metadata
from ghostmark.fixtures.generate import make_pdf_fixture
from ghostmark.models import Status


def test_pdf_fixture_detects_docinfo_and_xmp(tmp_path: Path):
    path = tmp_path / "demo.pdf"
    make_pdf_fixture(path)
    detections = {d.detector: d for d in inspect_pdf_metadata(path)}
    assert detections["pdf_info"].status is Status.FOUND
    assert detections["pdf_xmp"].status is Status.FOUND
    # Native tag-level engine: normalized fields with raw tag names +
    # categories, alongside the raw key->value mapping.
    fields = detections["pdf_info"].details["fields"]
    tags = {f["tag"] for f in fields}
    assert "/Author" in tags and "/Title" in tags
    by_tag = {f["tag"]: f for f in fields}
    assert by_tag["/Author"]["category"] == "author"
    assert by_tag["/Producer"]["category"] == "producer"
    assert "/Title" in detections["pdf_info"].details["fields_raw"]
    # XMP packet contents are surfaced too (dc:creator from the fixture).
    xmp_tags = {f["tag"] for f in detections["pdf_xmp"].details.get("fields", [])}
    assert "dc:creator" in xmp_tags


def test_pdf_clean_removes_metadata(tmp_path: Path):
    path = tmp_path / "demo.pdf"
    make_pdf_fixture(path)
    output_path = tmp_path / "demo.ghostmark.pdf"

    actions = clean_pdf_file(path, output_path)
    by_detector = {a.detector: a for a in actions}
    assert by_detector["pdf_info"].removed is True
    assert by_detector["pdf_xmp"].removed is True

    after = {d.detector: d for d in inspect_pdf_metadata(output_path)}
    assert after["pdf_info"].status is Status.NOT_FOUND
    assert after["pdf_xmp"].status is Status.NOT_FOUND


def test_pdf_stays_readable_after_clean(tmp_path: Path):
    path = tmp_path / "demo.pdf"
    make_pdf_fixture(path)
    output_path = tmp_path / "demo.ghostmark.pdf"
    clean_pdf_file(path, output_path)

    page_count = verify_pdf_readable(output_path)
    assert page_count == 1


def test_pdf_page_geometry_preserved(tmp_path: Path):
    path = tmp_path / "demo.pdf"
    make_pdf_fixture(path)
    output_path = tmp_path / "demo.ghostmark.pdf"
    clean_pdf_file(path, output_path)

    with pikepdf.open(str(path)) as before, pikepdf.open(str(output_path)) as after:
        before_box = tuple(float(x) for x in before.pages[0].MediaBox)
        after_box = tuple(float(x) for x in after.pages[0].MediaBox)
    assert before_box == after_box


def test_pdf_without_metadata_reports_not_found(tmp_path: Path):
    path = tmp_path / "bare.pdf"
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(100, 100))
    pdf.save(str(path))
    pdf.close()

    detections = {d.detector: d for d in inspect_pdf_metadata(path)}
    assert detections["pdf_xmp"].status is Status.NOT_FOUND
