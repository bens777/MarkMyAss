"""Independent ExifTool cross-check: graceful when absent, correct when present."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ghostmark import independent_verify as iv
from ghostmark.models import Status


def test_not_applicable_for_text_files(tmp_path: Path):
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")
    result = iv.exiftool_check(path)
    assert result.status is Status.UNKNOWN
    assert result.detector == "exiftool_independent"


def test_unavailable_when_exiftool_not_installed(tmp_path: Path, monkeypatch):
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(iv, "exiftool_available", lambda: False)
    result = iv.exiftool_check(path)
    assert result.status is Status.UNKNOWN
    assert "not installed" in result.details["note"]


def test_reports_found_when_exiftool_sees_remaining_tags(tmp_path: Path, monkeypatch):
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(iv, "exiftool_available", lambda: True)

    fake_output = json.dumps([{"SourceFile": str(path), "File:FileSize": "123", "EXIF:Make": "Acme"}])
    fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout=fake_output.encode(), stderr=b"")
    monkeypatch.setattr(iv.subprocess, "run", lambda *a, **kw: fake_proc)

    result = iv.exiftool_check(path)
    assert result.status is Status.FOUND
    assert "EXIF:Make" in result.details["remaining_tags"]


def test_reports_not_found_when_only_structural_tags_remain(tmp_path: Path, monkeypatch):
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(iv, "exiftool_available", lambda: True)

    fake_output = json.dumps([{"SourceFile": str(path), "File:FileSize": "123", "ExifTool:Version": "12.0"}])
    fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout=fake_output.encode(), stderr=b"")
    monkeypatch.setattr(iv.subprocess, "run", lambda *a, **kw: fake_proc)

    result = iv.exiftool_check(path)
    assert result.status is Status.NOT_FOUND


def test_nonzero_exit_code_reported_as_unknown_not_crash(tmp_path: Path, monkeypatch):
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(iv, "exiftool_available", lambda: True)

    fake_proc = subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"bad file")
    monkeypatch.setattr(iv.subprocess, "run", lambda *a, **kw: fake_proc)

    result = iv.exiftool_check(path)
    assert result.status is Status.UNKNOWN


def test_verify_file_includes_independent_check(tmp_path: Path, monkeypatch):
    from ghostmark.cleaner import clean_file
    from ghostmark.fixtures.generate import make_jpeg_fixture
    from ghostmark.verifier import verify_file

    monkeypatch.setattr(iv, "exiftool_available", lambda: False)

    path = tmp_path / "demo.jpg"
    make_jpeg_fixture(path)
    result = clean_file(path)

    verify_result = verify_file(path, Path(result.output))
    assert verify_result.after.get("exiftool_independent") is not None
    assert "exiftool_independent" in verify_result.unknown
