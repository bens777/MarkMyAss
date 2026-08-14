"""Differential tests: MarkMyAss's native engine vs ExifTool as oracle.

ExifTool here is a REFERENCE implementation, not a dependency: these
tests only run where it is installed (CI's independent-verification job
and the WSL suite locally). For every fixture, both engines inspect the
same file; ExifTool's ``-j -G1 -a -s`` output is normalized through the
existing embedded/structural/filesystem/computed classifier and then
mapped into MarkMyAss's signal categories; the comparison asserts
per-category presence agreement WITHIN MARKMYASS'S SUPPORTED SCOPE only
(we are not trying to reproduce all of ExifTool).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ghostmark.cleaners.image import clean_image_bytes
from ghostmark.detectors.metadata import inspect_image_metadata, inspect_pdf_metadata
from ghostmark.fixtures.generate import generate_all
from ghostmark.independent_verify import categorize_tag
from ghostmark.models import MetadataOrigin

pytestmark = pytest.mark.skipif(
    shutil.which("exiftool") is None,
    reason="ExifTool is not installed locally; this suite runs in CI's independent-verification job.",
)

# ExifTool tag name (lower-cased, group-stripped) -> MarkMyAss category.
# Only the supported differential scope is mapped; everything else
# ExifTool reports is out of contract for this comparison.
_EXIFTOOL_TAG_CATEGORY = {
    "artist": "author",
    "by-line": "author",
    "creator": "author",          # XMP-dc:Creator
    "copyright": "author",
    "copyrightnotice": "author",
    "author": "author",           # PDF /Author, PNG Author
    "credit": "creator",
    "source": "creator",
    "software": "software",
    "creatortool": "software",
    "originatingprogram": "software",
    "usercomment": "comments",
    "comment": "comments",
    "imagedescription": "description",
    "description": "description",
    "caption-abstract": "description",
    "title": "description",
    "headline": "description",
    "digitalsourcetype": "provenance",
    "parameters": "provenance",
    "producer": "producer",
}


def _exiftool_categories(path: Path) -> set[str]:
    out = subprocess.run(
        ["exiftool", "-j", "-G1", "-a", "-s", str(path)],
        capture_output=True, timeout=30, check=True,
    )
    data = json.loads(out.stdout.decode("utf-8", errors="replace"))[0]
    categories: set[str] = set()
    for key in data:
        if categorize_tag(key) is not MetadataOrigin.EMBEDDED_METADATA:
            continue
        group, _, tag = key.partition(":")
        group_l, tag_l = group.lower(), tag.lower()
        # "Creator" is group-dependent: XMP dc:creator names a PERSON
        # (author), while PDF /Creator names the creating APPLICATION
        # (creator) -- mirror MarkMyAss's own per-container mapping.
        if tag_l == "creator" and group_l == "pdf":
            categories.add("creator")
            continue
        mapped = _EXIFTOOL_TAG_CATEGORY.get(tag_l)
        if mapped:
            categories.add(mapped)
        if group_l.startswith("gps") or tag_l.startswith("gps"):
            categories.add("gps")
    return categories


def _native_categories(path: Path) -> set[str]:
    if path.suffix.lower() == ".pdf":
        detections = inspect_pdf_metadata(path)
    else:
        detections = inspect_image_metadata(path)
    categories: set[str] = set()
    for d in detections:
        for f in d.details.get("fields", []):
            categories.add(f["category"])
    # The differential contract covers the scoped identity categories,
    # not our internal catch-alls.
    return categories & {
        "author", "creator", "producer", "software", "comments",
        "description", "gps", "timestamp", "provenance",
    }


_SCOPE = {"author", "creator", "producer", "software", "comments",
          "description", "gps", "provenance"}


@pytest.fixture(scope="module")
def fixture_paths(tmp_path_factory) -> dict[str, Path]:
    return generate_all(tmp_path_factory.mktemp("diff-fixtures"))


@pytest.mark.parametrize("kind", ["jpeg", "png", "webp", "pdf"])
def test_native_and_exiftool_agree_on_supported_categories(fixture_paths, kind):
    path = fixture_paths[kind]
    native = _native_categories(path) & _SCOPE
    oracle = _exiftool_categories(path) & _SCOPE
    assert native == oracle, (
        f"{kind}: native={sorted(native)} exiftool={sorted(oracle)} "
        f"(missing from native: {sorted(oracle - native)}; "
        f"native-only: {sorted(native - oracle)})"
    )


@pytest.mark.parametrize("kind,suffix", [("jpeg", ".jpg"), ("png", ".png"), ("webp", ".webp")])
def test_cleaned_files_agree_as_empty(fixture_paths, tmp_path, kind, suffix):
    src = fixture_paths[kind]
    cleaned, _ = clean_image_bytes(src.read_bytes(), suffix)
    out = tmp_path / f"cleaned{suffix}"
    out.write_bytes(cleaned)
    assert _native_categories(out) & _SCOPE == set()
    assert _exiftool_categories(out) & _SCOPE == set()


def test_cleaned_pdf_agrees_as_empty(fixture_paths, tmp_path):
    from ghostmark.cleaners.pdf import clean_pdf_file
    out = tmp_path / "cleaned.pdf"
    clean_pdf_file(fixture_paths["pdf"], out)
    assert _native_categories(out) & _SCOPE == set()
    assert _exiftool_categories(out) & _SCOPE == set()


def test_already_clean_file_agrees_as_empty(tmp_path):
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(9, 9, 9)).save(buf, format="JPEG")
    path = tmp_path / "bare.jpg"
    path.write_bytes(buf.getvalue())
    assert _native_categories(path) & _SCOPE == set()
    assert _exiftool_categories(path) & _SCOPE == set()
