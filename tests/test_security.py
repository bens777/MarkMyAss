"""Security helpers: filename sanitization, path traversal, size and type limits."""

from __future__ import annotations

from pathlib import Path

import pytest

from ghostmark.security import (
    MAX_UPLOAD_BYTES,
    FileTooLargeError,
    UnsupportedFileTypeError,
    check_size,
    check_supported,
    cleaned_output_path,
    sanitize_filename,
)


def test_sanitize_filename_strips_directory_components():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\evil.txt") == "evil.txt"


def test_sanitize_filename_strips_unsafe_characters():
    result = sanitize_filename("weird<>:name?.txt")
    assert "<" not in result
    assert ">" not in result
    assert ":" not in result
    assert "?" not in result


def test_sanitize_filename_never_empty():
    assert sanitize_filename("") == "file"
    assert sanitize_filename("..") == "file"
    assert sanitize_filename(".") == "file"


def test_check_supported_accepts_known_extensions():
    for name in ("a.txt", "b.md", "c.json", "d.csv", "e.pdf", "f.png", "g.jpg", "h.jpeg", "i.webp"):
        check_supported(name)  # must not raise


def test_check_supported_rejects_unknown_extension():
    with pytest.raises(UnsupportedFileTypeError):
        check_supported("virus.exe")


def test_check_size_rejects_oversized_input():
    with pytest.raises(FileTooLargeError):
        check_size(MAX_UPLOAD_BYTES + 1)
    check_size(MAX_UPLOAD_BYTES)  # must not raise at the boundary


def test_cleaned_output_path_never_overwrites_original():
    original = Path("document.pdf")
    output = cleaned_output_path(original)
    assert output != original
    assert output.name == "document.ghostmark.pdf"


def test_cleaned_output_path_preserves_directory():
    original = Path("/some/dir/photo.png")
    output = cleaned_output_path(original)
    assert output.parent == original.parent
    assert output.name == "photo.ghostmark.png"
