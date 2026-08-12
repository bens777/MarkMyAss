"""CLI behavior: commands, JSON output, exit codes, and file-safety guarantees."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ghostmark import __version__
from ghostmark.cli import app

runner = CliRunner()

ZWSP = chr(0x200B)


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "inspect" in result.stdout
    assert "clean" in result.stdout
    assert "verify" in result.stdout
    assert "demo" in result.stdout


def test_inspect_text_human():
    result = runner.invoke(app, ["inspect-text", f"hidden{ZWSP}space"])
    assert result.exit_code == 0
    assert "Hidden Unicode: FOUND" in result.stdout


def test_inspect_text_json_is_valid_json():
    result = runner.invoke(app, ["inspect-text", "clean text", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["target_type"] == "text"
    assert any(d["detector"] == "unicode" for d in payload["detections"])


def test_clean_text_prints_cleaned_output():
    result = runner.invoke(app, ["clean-text", f"a{ZWSP}b"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "ab"


def test_inspect_file_not_found():
    result = runner.invoke(app, ["inspect", "does-not-exist.txt"])
    assert result.exit_code != 0


def test_inspect_unsupported_extension(tmp_path: Path):
    bad = tmp_path / "file.exe"
    bad.write_bytes(b"not really an exe")
    result = runner.invoke(app, ["inspect", str(bad)])
    assert result.exit_code == 1
    assert "not a supported file type" in result.stdout or "not a supported file type" in (result.stderr or "")


def test_clean_file_creates_ghostmark_copy_and_preserves_original(tmp_path: Path):
    src = tmp_path / "document.txt"
    original_content = f"Hello{ZWSP}World"
    src.write_text(original_content, encoding="utf-8")

    result = runner.invoke(app, ["clean", str(src)])
    assert result.exit_code == 0

    output = tmp_path / "document.ghostmark.txt"
    assert output.exists()
    assert output.read_text(encoding="utf-8") == "HelloWorld"
    assert src.read_text(encoding="utf-8") == original_content, "original file must never be modified"


def test_clean_json_output_is_valid_json(tmp_path: Path):
    src = tmp_path / "document.txt"
    src.write_text("plain text", encoding="utf-8")
    result = runner.invoke(app, ["clean", str(src), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["source"].endswith("document.txt")


def test_verify_after_clean_reports_resolved(tmp_path: Path):
    src = tmp_path / "document.txt"
    src.write_text(f"Hello{ZWSP}World", encoding="utf-8")
    runner.invoke(app, ["clean", str(src)])

    output = tmp_path / "document.ghostmark.txt"
    result = runner.invoke(app, ["verify", str(output)])
    assert result.exit_code == 0
    assert "successfully removed" in result.stdout


def test_verify_json_output(tmp_path: Path):
    src = tmp_path / "document.txt"
    src.write_text(f"Hello{ZWSP}World", encoding="utf-8")
    runner.invoke(app, ["clean", str(src)])
    output = tmp_path / "document.ghostmark.txt"

    result = runner.invoke(app, ["verify", str(output), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "resolved" in payload
    assert "unicode" in payload["resolved"]


def test_demo_command_passes():
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "GhostMark is working." in result.stdout
    assert "5/5 tests successful." in result.stdout
