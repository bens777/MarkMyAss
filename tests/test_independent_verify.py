"""Independent ExifTool cross-check: graceful when absent, correct categorization when present."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ghostmark.independent_verify import C2paToolVerifier, ExifToolVerifier, categorize_tag
from ghostmark.models import MetadataOrigin


def _fake_run(monkeypatch, module, *, returncode=0, stdout=b"", stderr=b""):
    fake_proc = subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)
    monkeypatch.setattr(module, "shutil", module.shutil)
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/exiftool")
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw: fake_proc)


def test_categorize_embedded_metadata_groups():
    assert categorize_tag("EXIF:Make") is MetadataOrigin.EMBEDDED_METADATA
    assert categorize_tag("GPS:GPSLatitude") is MetadataOrigin.EMBEDDED_METADATA
    assert categorize_tag("IPTC:Keywords") is MetadataOrigin.EMBEDDED_METADATA
    assert categorize_tag("XMP-dc:Creator") is MetadataOrigin.EMBEDDED_METADATA
    assert categorize_tag("Photoshop:CaptionWriter") is MetadataOrigin.EMBEDDED_METADATA


def test_categorize_pdf_splits_metadata_from_structural():
    assert categorize_tag("PDF:Author") is MetadataOrigin.EMBEDDED_METADATA
    assert categorize_tag("PDF:Producer") is MetadataOrigin.EMBEDDED_METADATA
    assert categorize_tag("PDF:PageCount") is MetadataOrigin.STRUCTURAL
    assert categorize_tag("PDF:Linearized") is MetadataOrigin.STRUCTURAL


def test_categorize_png_splits_metadata_from_structural():
    assert categorize_tag("PNG:Comment") is MetadataOrigin.EMBEDDED_METADATA
    assert categorize_tag("PNG:ImageWidth") is MetadataOrigin.STRUCTURAL
    assert categorize_tag("PNG:BitDepth") is MetadataOrigin.STRUCTURAL


def test_categorize_filesystem_and_computed_never_metadata():
    assert categorize_tag("File:FileSize") is MetadataOrigin.FILESYSTEM
    assert categorize_tag("SourceFile") is MetadataOrigin.FILESYSTEM
    assert categorize_tag("ExifTool:ExifToolVersion") is MetadataOrigin.COMPUTED
    assert categorize_tag("Composite:ImageSize") is MetadataOrigin.COMPUTED


def test_categorize_icc_profile_is_structural_not_metadata():
    assert categorize_tag("ICC-header:ProfileVersion") is MetadataOrigin.STRUCTURAL


def test_categorize_unknown_group_falls_back_to_unknown():
    assert categorize_tag("SomeWeirdGroup:Whatever") is MetadataOrigin.UNKNOWN


def test_not_applicable_for_text_files(tmp_path: Path):
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")
    verifier = ExifToolVerifier()
    result = verifier.inspect(path)
    assert result.applicable is False


def test_unavailable_when_exiftool_not_installed(tmp_path: Path, monkeypatch):
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(ExifToolVerifier, "available", lambda self: False)
    verifier = ExifToolVerifier()
    result = verifier.inspect(path)
    assert result.available is False
    assert result.applicable is True
    assert "not installed" in result.note


def test_reports_embedded_metadata_when_present(tmp_path: Path, monkeypatch):
    import ghostmark.independent_verify as iv

    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(ExifToolVerifier, "available", lambda self: True)
    monkeypatch.setattr(ExifToolVerifier, "version", lambda self: "13.00")

    fake_output = json.dumps(
        [{"SourceFile": str(path), "File:FileSize": "123", "EXIF:Make": "Acme", "PDF:PageCount": "1"}]
    )
    _fake_run(monkeypatch, iv, stdout=fake_output.encode())

    verifier = ExifToolVerifier()
    result = verifier.inspect(path)
    assert result.has_embedded_metadata is True
    assert "EXIF:Make" in result.embedded_metadata_tags
    assert "File:FileSize" not in result.embedded_metadata_tags
    assert result.version == "13.00"
    assert result.ran_successfully is True


def test_reports_clean_when_only_structural_filesystem_computed_tags_remain(tmp_path: Path, monkeypatch):
    import ghostmark.independent_verify as iv

    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(ExifToolVerifier, "available", lambda self: True)
    monkeypatch.setattr(ExifToolVerifier, "version", lambda self: "13.00")

    fake_output = json.dumps(
        [{"SourceFile": str(path), "File:FileSize": "123", "ExifTool:Version": "12.0", "Composite:ImageSize": "8x8"}]
    )
    _fake_run(monkeypatch, iv, stdout=fake_output.encode())

    verifier = ExifToolVerifier()
    result = verifier.inspect(path)
    assert result.has_embedded_metadata is False
    assert result.ran_successfully is True


def test_nonzero_exit_code_reported_gracefully_not_crash(tmp_path: Path, monkeypatch):
    import ghostmark.independent_verify as iv

    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(ExifToolVerifier, "available", lambda self: True)
    monkeypatch.setattr(ExifToolVerifier, "version", lambda self: "13.00")
    _fake_run(monkeypatch, iv, returncode=1, stderr=b"bad file")

    verifier = ExifToolVerifier()
    result = verifier.inspect(path)
    assert result.available is True
    assert not result.tags_by_origin
    # A genuine tool failure must never look identical to "ran and found
    # nothing" -- see ran_successfully's docstring in models.py and the
    # regression this guards in verifier._exiftool_outcome.
    assert result.ran_successfully is False


def test_exiftool_timeout_does_not_look_like_a_successful_clean_run(tmp_path: Path, monkeypatch):
    """A verifier that times out must be reported as unrun, not as passed.

    Regression test: ExternalVerificationResult's tags_by_origin defaults
    to an empty dict, and has_embedded_metadata on an empty dict is False
    -- so before ran_successfully existed, a timeout (available=True,
    applicable=True, but the run itself never completed) was
    indistinguishable from "ExifTool ran and confirmed zero embedded
    metadata," which let verifier._exiftool_outcome report passed=True for
    a check that never actually happened.
    """
    import ghostmark.independent_verify as iv

    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(ExifToolVerifier, "available", lambda self: True)
    monkeypatch.setattr(ExifToolVerifier, "version", lambda self: "13.00")

    def _raise_timeout(*a, **kw):
        raise iv.subprocess.TimeoutExpired(cmd=["exiftool"], timeout=15)

    monkeypatch.setattr(iv.shutil, "which", lambda name: "/usr/bin/exiftool")
    monkeypatch.setattr(iv.subprocess, "run", _raise_timeout)

    result = ExifToolVerifier().inspect(path)
    assert result.available is True
    assert result.applicable is True
    assert result.has_embedded_metadata is False  # empty by default -- the trap
    assert result.ran_successfully is False  # ...but this must catch it
    assert "timed out" in result.note.lower()

    from ghostmark.verifier import _exiftool_outcome

    outcome = _exiftool_outcome(result)
    assert outcome.passed is None, "a timed-out verifier must never report passed=True"


def test_exiftool_malformed_json_output_is_reported_unknown_not_clean(tmp_path: Path, monkeypatch):
    import ghostmark.independent_verify as iv

    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(ExifToolVerifier, "available", lambda self: True)
    monkeypatch.setattr(ExifToolVerifier, "version", lambda self: "13.00")
    _fake_run(monkeypatch, iv, stdout=b"not valid json { { {")

    result = ExifToolVerifier().inspect(path)
    assert result.available is True
    assert "could not parse" in result.note.lower()
    assert result.ran_successfully is False
    assert result.has_embedded_metadata is False  # empty by default -- the trap

    from ghostmark.verifier import _exiftool_outcome

    assert _exiftool_outcome(result).passed is None, "unparseable output must never report passed=True"


def test_verify_file_produces_verification_summary(tmp_path: Path, monkeypatch):
    from ghostmark.cleaner import clean_file
    from ghostmark.fixtures.generate import make_jpeg_fixture
    from ghostmark.verifier import verify_file

    # Patch BOTH verifiers unavailable -- deterministic regardless of what's
    # actually installed on the machine running this test (a previous
    # version of this test only patched ExifTool and silently relied on
    # c2patool not being installed locally, which broke the moment c2patool
    # was installed for the real-binary integration suite in the same repo).
    monkeypatch.setattr(ExifToolVerifier, "available", lambda self: False)
    monkeypatch.setattr(C2paToolVerifier, "available", lambda self: False)

    path = tmp_path / "demo.jpg"
    make_jpeg_fixture(path)
    result = clean_file(path)

    verify_result = verify_file(path, Path(result.output))
    assert verify_result.external_after is not None
    assert verify_result.summary_v2 is not None
    assert verify_result.summary_v2.ghostmark_pass is True
    assert verify_result.summary_v2.exiftool_pass is None  # unavailable in this test
    # No independent verifier was available/applicable at all (both patched
    # unavailable) -- GhostMark's own claim is unverified, not "partial"
    # (that's reserved for when a verifier DID run and disagreed).
    assert verify_result.summary_v2.verdict.value == "unverified"


def test_verify_file_reports_partial_when_exiftool_disagrees_with_ghostmark(tmp_path: Path, monkeypatch):
    """A real (mocked-at-the-subprocess-level, not the abstract-model level)
    disagreement: GhostMark's own re-inspection says the cleaned file is
    clear, but ExifTool -- actually run through the full inspect() code
    path -- reports embedded metadata remains. This must surface as
    PARTIAL, never VERIFIED CLEAN and never silently dropped."""

    import ghostmark.independent_verify as iv
    from ghostmark.cleaner import clean_file
    from ghostmark.fixtures.generate import make_jpeg_fixture
    from ghostmark.verifier import verify_file

    monkeypatch.setattr(C2paToolVerifier, "available", lambda self: False)
    monkeypatch.setattr(ExifToolVerifier, "available", lambda self: True)
    monkeypatch.setattr(ExifToolVerifier, "version", lambda self: "13.00")

    # ExifTool claims to find EXIF:Make survived cleaning -- disagreeing
    # with GhostMark's own detector, which (per the real cleaner) reports
    # nothing left.
    fake_output = json.dumps([{"SourceFile": "x.jpg", "EXIF:Make": "Acme"}])
    _fake_run(monkeypatch, iv, stdout=fake_output.encode())

    path = tmp_path / "demo.jpg"
    make_jpeg_fixture(path)
    result = clean_file(path)

    verify_result = verify_file(path, Path(result.output))
    summary = verify_result.summary_v2
    assert summary.ghostmark_pass is True  # GhostMark's own re-inspection thinks it's clean
    assert summary.exiftool_pass is False  # but ExifTool actually disagrees
    assert summary.verdict.value == "partial"
    assert summary.verdict.value != "verified_clean"


# --- c2patool ------------------------------------------------------------------------


def test_c2patool_not_applicable_for_text_files(tmp_path: Path):
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")
    result = C2paToolVerifier().inspect(path)
    assert result.applicable is False


def test_c2patool_unavailable_when_not_installed(tmp_path: Path, monkeypatch):
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(C2paToolVerifier, "available", lambda self: False)
    result = C2paToolVerifier().inspect(path)
    assert result.available is False
    assert result.applicable is True
    assert "not installed" in result.note


def test_c2patool_reports_manifest_found(tmp_path: Path, monkeypatch):
    import ghostmark.independent_verify as iv

    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(C2paToolVerifier, "available", lambda self: True)
    monkeypatch.setattr(C2paToolVerifier, "version", lambda self: "0.27.12")
    fake_manifest = json.dumps({"active_manifest": "urn:uuid:1234", "manifests": {}})
    _fake_run(monkeypatch, iv, stdout=fake_manifest.encode())

    result = C2paToolVerifier().inspect(path)
    assert result.found is True
    assert result.version == "0.27.12"
    assert result.ran_successfully is True


def test_c2patool_reports_no_manifest_via_error_message(tmp_path: Path, monkeypatch):
    import ghostmark.independent_verify as iv

    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(C2paToolVerifier, "available", lambda self: True)
    monkeypatch.setattr(C2paToolVerifier, "version", lambda self: "0.27.12")
    _fake_run(monkeypatch, iv, returncode=1, stderr=b"Error: No claim found")

    result = C2paToolVerifier().inspect(path)
    assert result.found is False
    assert result.available is True
    assert result.ran_successfully is True  # confidently recognized "no manifest" message


def test_c2patool_malformed_json_output_is_reported_unknown_not_clean(tmp_path: Path, monkeypatch):
    import ghostmark.independent_verify as iv

    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(C2paToolVerifier, "available", lambda self: True)
    monkeypatch.setattr(C2paToolVerifier, "version", lambda self: "0.27.12")
    _fake_run(monkeypatch, iv, stdout=b"not valid json { { {")

    result = C2paToolVerifier().inspect(path)
    assert result.available is True
    assert "could not parse" in result.note.lower()
    assert result.ran_successfully is False
    assert result.found is False  # dataclass default -- the trap

    from ghostmark.verifier import _c2patool_outcome

    assert _c2patool_outcome(result).passed is None, "unparseable output must never report passed=True"


def test_c2patool_timeout_does_not_look_like_a_successful_clean_run(tmp_path: Path, monkeypatch):
    import ghostmark.independent_verify as iv

    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(C2paToolVerifier, "available", lambda self: True)
    monkeypatch.setattr(C2paToolVerifier, "version", lambda self: "0.27.12")

    def _raise_timeout(*a, **kw):
        raise iv.subprocess.TimeoutExpired(cmd=["c2patool"], timeout=15)

    monkeypatch.setattr(iv.shutil, "which", lambda name: "/usr/local/bin/c2patool")
    monkeypatch.setattr(iv.subprocess, "run", _raise_timeout)

    result = C2paToolVerifier().inspect(path)
    assert result.available is True
    assert result.found is False  # dataclass default -- the trap
    assert result.ran_successfully is False  # ...but this must catch it
    assert "timed out" in result.note.lower()

    from ghostmark.verifier import _c2patool_outcome

    assert _c2patool_outcome(result).passed is None, "a timed-out c2patool run must never report passed=True"


def test_c2patool_genuine_error_does_not_guess_found_status(tmp_path: Path, monkeypatch):
    import ghostmark.independent_verify as iv

    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(C2paToolVerifier, "available", lambda self: True)
    monkeypatch.setattr(C2paToolVerifier, "version", lambda self: "0.27.12")
    _fake_run(monkeypatch, iv, returncode=101, stderr=b"panicked at src/main.rs:42")

    result = C2paToolVerifier().inspect(path)
    assert result.found is False  # dataclass default, not asserted as a real finding
    assert result.note  # but the failure is visible in the note
    assert "panicked" in result.note
    # Regression guard: found's dataclass default (False) must never be
    # mistaken for "c2patool ran and confirmed no manifest" -- confirm both
    # the low-level flag and the verdict-facing outcome agree it's unknown.
    assert result.ran_successfully is False

    from ghostmark.verifier import _c2patool_outcome

    outcome = _c2patool_outcome(result)
    assert outcome.passed is None, "a crashed c2patool run must never report passed=True"
