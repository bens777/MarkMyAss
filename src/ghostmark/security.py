"""Shared security helpers: safe temp files, filename sanitization, size limits.

Every file GhostMark touches -- from the CLI or from an upload in the web
UI -- is treated as untrusted input. These helpers are the single place
that decides temp file naming, size limits, and path safety so the rule is
enforced consistently rather than re-implemented per call site.
"""

from __future__ import annotations

import re
import secrets
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB

SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv",
    ".pdf",
    ".png", ".jpg", ".jpeg", ".webp",
}

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


class UnsupportedFileTypeError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass


def sanitize_filename(name: str) -> str:
    """Strip any path component and unsafe characters from a user-supplied filename.

    Never trust a client-supplied filename as a filesystem path -- this
    collapses it to a bare, safe basename. A client-supplied filename may
    use either slash convention regardless of the OS GhostMark is running
    on, so both are normalized before using ``Path.name`` (which only
    treats "\\" as a separator on Windows).
    """

    normalized = name.replace("\\", "/")
    base = Path(normalized).name  # drops any directory components, defeats ../ traversal
    base = _UNSAFE_CHARS.sub("_", base)
    if not base or base in (".", ".."):
        base = "file"
    return base


def suffix_of(name: str) -> str:
    return Path(sanitize_filename(name)).suffix.lower()


def check_supported(name: str) -> None:
    ext = suffix_of(name)
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"'{ext or '(no extension)'}' is not a supported file type. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )


def check_size(num_bytes: int) -> None:
    if num_bytes > MAX_UPLOAD_BYTES:
        raise FileTooLargeError(
            f"File is {num_bytes / (1024 * 1024):.1f} MB, which exceeds the "
            f"{MAX_UPLOAD_BYTES / (1024 * 1024):.0f} MB limit."
        )


def random_suffix_name(suffix: str) -> str:
    """A randomized, collision-resistant filename for a temp file with the given extension."""

    token = secrets.token_hex(16)
    safe_suffix = _UNSAFE_CHARS.sub("", suffix)
    return f"ghostmark-{token}{safe_suffix}"


@contextmanager
def temp_workspace() -> Iterator[Path]:
    """A temp directory that is always removed, even on error."""

    with tempfile.TemporaryDirectory(prefix="ghostmark-") as tmp:
        yield Path(tmp)


def cleaned_output_path(original: Path) -> Path:
    """document.pdf -> document.ghostmark.pdf, never overwriting the source."""

    return original.with_name(f"{original.stem}.ghostmark{original.suffix}")
