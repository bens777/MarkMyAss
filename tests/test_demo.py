"""Fixture generation used by `ghostmark demo` and the rest of the test suite."""

from __future__ import annotations

from pathlib import Path

from ghostmark.fixtures.generate import demo_text, generate_all
from ghostmark.inspector import inspect_file
from ghostmark.models import Status


def test_generate_all_creates_every_fixture(tmp_path: Path):
    fixtures = generate_all(tmp_path)
    assert set(fixtures.keys()) == {"text", "jpeg", "png", "webp", "pdf"}
    for path in fixtures.values():
        assert path.exists()
        assert path.stat().st_size > 0


def test_demo_text_contains_detectable_hidden_unicode():
    text = demo_text()
    assert chr(0x200B) in text  # zero-width space
    assert "Ça fonctionne très bien" in text
    assert "Übermäßige Änderungen" in text


def test_every_generated_fixture_has_findable_signals(tmp_path: Path):
    fixtures = generate_all(tmp_path)
    text_report = None
    for key, path in fixtures.items():
        if key == "text":
            continue
        report = inspect_file(path)
        assert report.signal_count() > 0, f"{key} fixture should have at least one detectable signal"
    text_report = inspect_file(fixtures["text"])
    assert any(d.status is Status.FOUND for d in text_report.detections)
