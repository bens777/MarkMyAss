"""End-to-end verification against the REAL ExifTool binary.

This automates exactly the manual process it replaces:

    ORIGINAL FILE
    GhostMark inspect      -> metadata FOUND
    ExifTool inspect       -> metadata FOUND
    GhostMark clean        -> cleaned file generated
    GhostMark inspect (cleaned) -> metadata NOT FOUND
    ExifTool inspect (cleaned)  -> targeted embedded metadata NOT FOUND

Skips (does not fail) when ExifTool isn't installed, so local `pytest`
runs are unaffected. CI's "Independent Verification (ExifTool +
c2patool)" job installs ExifTool and this suite MUST pass there -- see
.github/workflows/ci.yml.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ghostmark.cleaner import clean_file
from ghostmark.fixtures.generate import make_jpeg_fixture, make_pdf_fixture, make_png_fixture
from ghostmark.independent_verify import ExifToolVerifier
from ghostmark.inspector import inspect_file
from ghostmark.models import Status
from ghostmark.verifier import verify_file

verifier = ExifToolVerifier()

pytestmark = pytest.mark.skipif(
    not verifier.available(),
    reason="ExifTool is not installed locally; this suite runs in CI's independent-verification job.",
)


@pytest.mark.parametrize(
    ("make_fixture", "filename", "ghostmark_detector"),
    [
        (make_pdf_fixture, "demo.pdf", "pdf_info"),
        (make_jpeg_fixture, "demo.jpg", "exif"),
        (make_png_fixture, "demo.png", "exif"),
    ],
)
def test_real_exiftool_confirms_metadata_removed(tmp_path: Path, make_fixture, filename, ghostmark_detector):
    path = tmp_path / filename
    make_fixture(path)

    # ORIGINAL: GhostMark's own detector must find metadata.
    before_report = inspect_file(path)
    before_detection = before_report.get(ghostmark_detector)
    assert before_detection is not None
    assert before_detection.status is Status.FOUND, f"GhostMark should detect {ghostmark_detector} in the fixture"

    # ORIGINAL: the REAL ExifTool binary must also see embedded metadata.
    before_external = verifier.inspect(path)
    assert before_external.available is True
    assert before_external.has_embedded_metadata is True, (
        f"Real ExifTool found no embedded metadata in the fixture -- tags: {before_external.tags_by_origin}"
    )

    # Clean.
    clean_result = clean_file(path)
    cleaned_path = Path(clean_result.output)
    assert cleaned_path.exists()

    # CLEANED: GhostMark's own re-inspection must show it gone.
    after_report = inspect_file(cleaned_path)
    after_detection = after_report.get(ghostmark_detector)
    assert after_detection is not None
    assert after_detection.status is Status.NOT_FOUND

    # CLEANED: the REAL ExifTool binary must independently agree.
    after_external = verifier.inspect(cleaned_path)
    assert after_external.has_embedded_metadata is False, (
        f"ExifTool still finds embedded metadata after cleaning: {after_external.embedded_metadata_tags}"
    )


@pytest.mark.parametrize(
    ("make_fixture", "filename"),
    [
        (make_pdf_fixture, "demo.pdf"),
        (make_jpeg_fixture, "demo.jpg"),
        (make_png_fixture, "demo.png"),
    ],
)
def test_full_verification_pipeline_reaches_verified_clean(tmp_path: Path, make_fixture, filename):
    """The same pipeline the web UI and CLI `verify` command use end to end."""

    path = tmp_path / filename
    make_fixture(path)
    clean_result = clean_file(path)
    cleaned_path = Path(clean_result.output)

    result = verify_file(path, cleaned_path)

    assert result.summary_v2 is not None
    assert result.summary_v2.ghostmark_pass is True
    assert result.summary_v2.exiftool_pass is True
    assert result.summary_v2.exiftool_available is True
    assert result.summary_v2.verdict.value == "verified_clean"
    assert result.external_after.has_embedded_metadata is False


def test_exiftool_version_is_reported():
    version = verifier.version()
    assert version is not None
    assert version[0].isdigit()
