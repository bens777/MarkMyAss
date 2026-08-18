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


def test_verify_receipt_json(tmp_path: Path):
    src = tmp_path / "document.txt"
    src.write_text(f"Hello{ZWSP}World", encoding="utf-8")
    runner.invoke(app, ["clean", str(src)])
    output = tmp_path / "document.ghostmark.txt"
    receipt_path = tmp_path / "receipt.json"

    result = runner.invoke(app, ["verify", str(output), "--receipt", str(receipt_path)])
    assert result.exit_code == 0
    assert receipt_path.exists()
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["ghostmark_verification_receipt"] is True
    assert payload["file"] == "document.ghostmark.txt"
    assert "sha256_original" in payload
    assert "sha256_cleaned" in payload


def test_verify_receipt_html_and_txt(tmp_path: Path):
    src = tmp_path / "document.txt"
    src.write_text(f"Hello{ZWSP}World", encoding="utf-8")
    runner.invoke(app, ["clean", str(src)])
    output = tmp_path / "document.ghostmark.txt"

    html_path = tmp_path / "receipt.html"
    result = runner.invoke(app, ["verify", str(output), "--receipt", str(html_path)])
    assert result.exit_code == 0
    assert "<!doctype html>" in html_path.read_text(encoding="utf-8")

    txt_path = tmp_path / "receipt.txt"
    result = runner.invoke(app, ["verify", str(output), "--receipt", str(txt_path)])
    assert result.exit_code == 0
    assert "GHOSTMARK VERIFICATION RECEIPT" in txt_path.read_text(encoding="utf-8")


def test_demo_command_passes():
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "GhostMark is working." in result.stdout
    assert "6/6 tests successful." in result.stdout


def _make_png(path: Path) -> None:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (48, 48), (200, 90, 40)).save(buf, format="PNG")
    path.write_bytes(buf.getvalue())


def test_reprocess_writes_output_and_preserves_original(tmp_path: Path):
    src = tmp_path / "pic.png"
    _make_png(src)
    before = src.read_bytes()
    result = runner.invoke(app, ["reprocess", str(src), "--profile", "medium"])
    assert result.exit_code == 0
    out = tmp_path / "pic.reprocessed.png"
    assert out.exists()
    assert src.read_bytes() == before  # original untouched


def test_reprocess_rejects_non_image(tmp_path: Path):
    bad = tmp_path / "notes.txt"
    bad.write_text("plain text")
    result = runner.invoke(app, ["reprocess", str(bad)])
    assert result.exit_code == 1


def test_reprocess_report_json_is_observational(tmp_path: Path):
    src = tmp_path / "pic.png"
    _make_png(src)
    result = runner.invoke(app, ["reprocess", str(src), "--report", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["robustness"]["observational"] is True
    assert payload["robustness"]["statistical_watermark"]["locally_verifiable"] is False
