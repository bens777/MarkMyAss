"""Regression suite driven by the public, reproducible test corpus (src/ghostmark/corpus/).

Every fixture here is synthetic (see scripts/generate_corpus.py) and has a
documented expected result in manifest.json. This is the same corpus the
public /benchmarks page reports on -- these tests are what keep that page
honest: if a fixture stops behaving as documented, this suite fails.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ghostmark.cleaner import clean_file
from ghostmark.corpus_data import CORPUS_DIR, load_manifest
from ghostmark.inspector import inspect_file
from ghostmark.models import Status

MANIFEST = load_manifest()


def test_manifest_is_well_formed():
    assert MANIFEST, "corpus manifest must not be empty"
    for entry in MANIFEST:
        assert (CORPUS_DIR / entry["path"]).exists(), f"missing corpus fixture: {entry['path']}"
        assert "expected_before" in entry
        assert "expected_after" in entry


@pytest.mark.parametrize("entry", MANIFEST, ids=[e["path"] for e in MANIFEST])
def test_corpus_fixture_matches_documented_expectations(entry: dict, tmp_path: Path):
    fixture_path = CORPUS_DIR / entry["path"]
    # Work on a temp copy -- never write .ghostmark.* files back into the
    # committed corpus directory.
    working_path = tmp_path / fixture_path.name
    shutil.copyfile(fixture_path, working_path)

    before = inspect_file(working_path)
    found_before = {d.detector for d in before.detections if d.status is Status.FOUND}
    assert found_before == set(entry["expected_before"]), (
        f"{entry['path']}: expected {entry['expected_before']} found before cleaning, got {sorted(found_before)}"
    )

    clean_result = clean_file(working_path)
    cleaned_path = Path(clean_result.output)

    after = inspect_file(cleaned_path)
    found_after = {d.detector for d in after.detections if d.status is Status.FOUND}
    assert found_after == set(entry["expected_after"]), (
        f"{entry['path']}: expected {entry['expected_after']} found after cleaning, got {sorted(found_after)}"
    )
