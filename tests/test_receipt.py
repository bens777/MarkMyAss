"""Verification Receipt: JSON/text/HTML rendering, integrity hashes, honesty about what's unverified."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ghostmark.cleaner import clean_file
from ghostmark.fixtures.generate import make_pdf_fixture
from ghostmark.receipt import STATISTICAL_WATERMARK_LABELS, build_receipt
from ghostmark.verifier import verify_file


def _make_receipt(tmp_path: Path):
    path = tmp_path / "demo.pdf"
    make_pdf_fixture(path)
    clean_result = clean_file(path)
    cleaned_path = Path(clean_result.output)
    verify_result = verify_file(path, cleaned_path)
    receipt = build_receipt(
        file_name=cleaned_path.name,
        before_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
        after_hash=hashlib.sha256(cleaned_path.read_bytes()).hexdigest(),
        verify_result=verify_result,
    )
    return receipt, path, cleaned_path


def test_receipt_json_has_required_fields(tmp_path: Path):
    receipt, path, cleaned_path = _make_receipt(tmp_path)
    payload = receipt.to_dict()

    assert payload["ghostmark_verification_receipt"] is True
    assert payload["file"] == cleaned_path.name
    assert payload["sha256_original"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert payload["sha256_cleaned"] == hashlib.sha256(cleaned_path.read_bytes()).hexdigest()
    assert "before" in payload and "after" in payload
    assert "independent_verification" in payload
    assert payload["supported_signals_removed"]["resolved"] >= 1
    assert payload["verdict"] in {"verified_clean", "partial", "unverified", "not_applicable", "failed"}
    assert set(payload["statistical_watermark_status"]) == set(STATISTICAL_WATERMARK_LABELS)
    assert all(v == "unverified" for v in payload["statistical_watermark_status"].values())


def test_receipt_json_is_valid_json(tmp_path: Path):
    receipt, _, _ = _make_receipt(tmp_path)
    parsed = json.loads(receipt.to_json())
    assert parsed["file"]


def test_receipt_never_claims_statistical_watermark_verified(tmp_path: Path):
    receipt, _, _ = _make_receipt(tmp_path)
    payload = receipt.to_dict()
    for label in STATISTICAL_WATERMARK_LABELS:
        assert payload["statistical_watermark_status"][label] == "unverified"


def test_receipt_text_contains_required_sections(tmp_path: Path):
    receipt, path, cleaned_path = _make_receipt(tmp_path)
    text = receipt.to_text()

    assert "GHOSTMARK VERIFICATION RECEIPT" in text
    assert cleaned_path.name in text
    assert "BEFORE" in text
    assert "AFTER" in text
    assert "INDEPENDENT VERIFICATION" in text
    assert "SUPPORTED SIGNALS REMOVED" in text
    assert "UNVERIFIED" in text
    for label in STATISTICAL_WATERMARK_LABELS:
        assert label in text
    assert "SHA-256 original:" in text
    assert hashlib.sha256(path.read_bytes()).hexdigest() in text
    assert "SHA-256 cleaned:" in text
    assert hashlib.sha256(cleaned_path.read_bytes()).hexdigest() in text
    assert "GhostMark version:" in text
    assert "Verification timestamp:" in text


def test_receipt_text_never_calls_itself_a_certificate(tmp_path: Path):
    receipt, _, _ = _make_receipt(tmp_path)
    text = receipt.to_text().lower()
    assert "certificate" not in text
    assert "human authorship" not in text


def test_receipt_html_is_self_contained_and_well_formed(tmp_path: Path):
    receipt, path, cleaned_path = _make_receipt(tmp_path)
    html = receipt.to_html()

    assert html.strip().startswith("<!doctype html>")
    assert "<style>" in html  # inline CSS -- openable standalone, no external assets
    assert 'src="' not in html
    assert 'href="static/' not in html
    assert cleaned_path.name in html
    assert hashlib.sha256(path.read_bytes()).hexdigest() in html
    # The word "certificate" may appear only inside the explicit disclaimer
    # that this is NOT one -- it must never be used as a self-description.
    assert "certificate of human authorship" not in html.lower()
    assert "not a certificate" in html.lower()
    for label in STATISTICAL_WATERMARK_LABELS:
        assert label in html


def test_receipt_html_escapes_file_name(tmp_path: Path):
    receipt, _, _ = _make_receipt(tmp_path)
    receipt.file_name = "<script>alert(1)</script>.pdf"
    html = receipt.to_html()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
