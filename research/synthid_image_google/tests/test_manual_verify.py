"""Tests for manual external-verification recording (research only)."""

from synthid_image.manual_verify import ManualExternalRecord, append_record, load_records


def test_record_roundtrip_and_append(tmp_path):
    append_record(tmp_path, ManualExternalRecord(
        source_image="smoke_gemini_001.png", transform_profile="none",
        external_verifier="gemini-app", result_text="Created with Google AI",
        timestamp="2026-08-15T10:00:00", notes="baseline"))
    append_record(tmp_path, ManualExternalRecord(
        source_image="smoke_gemini_001.png", transform_profile="strong",
        external_verifier="gemini-app", result_text="No indication of Google AI",
        timestamp="2026-08-15T10:05:00"))

    records = load_records(tmp_path)
    assert len(records) == 2
    assert records[0]["manual"] is True
    assert records[0]["external_verifier"] == "gemini-app"
    assert records[1]["transform_profile"] == "strong"
    assert records[1]["result_text"] == "No indication of Google AI"


def test_timestamp_autofilled_when_empty(tmp_path):
    rec = ManualExternalRecord(source_image="x.png", transform_profile="light",
                               external_verifier="gemini-app", result_text="…")
    assert rec.timestamp  # non-empty ISO-ish stamp
    assert rec.manual is True
