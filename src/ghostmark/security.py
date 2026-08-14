"""Shared security helpers: safe temp files, filename sanitization, size limits.

Every file GhostMark touches -- from the CLI or from an upload in the web
UI -- is treated as untrusted input. These helpers are the single place
that decides temp file naming, size limits, and path safety so the rule is
enforced consistently rather than re-implemented per call site.
"""

from __future__ import annotations

import os
import re
import secrets
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_DEFAULT_MAX_UPLOAD_MB = 50


def _max_upload_bytes() -> int:
    """Upload size limit, configurable via GHOSTMARK_MAX_UPLOAD_MB.

    Defaults to 50 MB for local/CLI use. The production web deployment
    sets this lower (see docker-compose.prod.yml) since it's exposed to
    the public internet.
    """

    raw = os.environ.get("GHOSTMARK_MAX_UPLOAD_MB", "").strip()
    try:
        mb = int(raw) if raw else _DEFAULT_MAX_UPLOAD_MB
    except ValueError:
        mb = _DEFAULT_MAX_UPLOAD_MB
    return max(1, mb) * 1024 * 1024


MAX_UPLOAD_BYTES = _max_upload_bytes()

SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv",
    ".pdf",
    ".png", ".jpg", ".jpeg", ".webp",
}

# Text formats get a much lower ceiling than the global upload limit.
# Load testing (2026-08) showed hidden-unicode cleaning is CPU-bound at
# roughly 5s/MB on the production container: >~3MB text cannot finish
# inside the 30s processing timeout, and a timed-out job's worker thread
# keeps burning CPU/RAM after the client already got its 503 (Python
# threads cannot be killed). Binary formats (images/PDF) are byte/segment
# level and stay fast at any supported size, so they keep the global
# limit. Enforced server-side BEFORE any parsing/cleaning begins.
TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv"}
MAX_TEXT_UPLOAD_MB = 2
MAX_TEXT_UPLOAD_BYTES = MAX_TEXT_UPLOAD_MB * 1024 * 1024
TEXT_LIMIT_MESSAGE = f"Text files are currently limited to {MAX_TEXT_UPLOAD_MB} MB."

# Magic-byte sniffing for defense-in-depth against a disguised upload (e.g.
# an executable renamed to .png). Text formats have no reliable magic bytes
# and are intentionally not checked here.
_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".webp": (b"RIFF",),  # full check also requires b"WEBP" at offset 8, see below
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


def check_size(num_bytes: int, *, max_bytes: int | None = None) -> None:
    """Enforce an upload size limit.

    ``max_bytes`` lets a caller with its own resolved config (the web app's
    ``WebConfig.max_upload_mb``) pass the exact limit it is already using
    elsewhere, so there is exactly one source of truth instead of two
    independent readers of the same environment variable. Falls back to
    ``GHOSTMARK_MAX_UPLOAD_MB`` (read live) for callers -- e.g. the CLI --
    that have no config object of their own.
    """

    limit = max_bytes if max_bytes is not None else _max_upload_bytes()
    if num_bytes > limit:
        raise FileTooLargeError(
            f"File is {num_bytes / (1024 * 1024):.1f} MB, which exceeds the "
            f"{limit / (1024 * 1024):.0f} MB limit."
        )


def sniff_mime_matches_extension(data: bytes, ext: str) -> bool:
    """Best-effort magic-byte check that file content roughly matches its extension.

    Defense in depth only -- a missing/unknown signature (e.g. plain text
    formats) is treated as OK rather than rejected, since GhostMark's real
    parsers (Pillow/pikepdf/our own segment parsers) will reject genuinely
    malformed content anyway.
    """

    ext = ext.lower()
    signatures = _MAGIC_BYTES.get(ext)
    if signatures is None:
        return True
    if not any(data.startswith(sig) for sig in signatures):
        return False
    if ext == ".webp":
        return len(data) >= 12 and data[8:12] == b"WEBP"
    return True


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
