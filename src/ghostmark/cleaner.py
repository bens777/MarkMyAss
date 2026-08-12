"""Top-level cleaning: dispatches to the right cleaners for a text or file input.

Mirrors ``ghostmark.inspector`` -- one dispatch point shared by the CLI and
the web UI, so "what gets cleaned for this file type" is defined once.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ghostmark.cleaners import c2pa as c2pa_cleaner
from ghostmark.cleaners import image as image_cleaner
from ghostmark.cleaners import pdf as pdf_cleaner
from ghostmark.cleaners import text as text_cleaner
from ghostmark.inspector import IMAGE_EXTENSIONS, PDF_EXTENSIONS, TEXT_EXTENSIONS
from ghostmark.models import CleanAction, CleanResult
from ghostmark.security import (
    UnsupportedFileTypeError,
    check_supported,
    cleaned_output_path,
    suffix_of,
)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_text_content(text: str, *, remove_semantic: bool = False) -> tuple[str, CleanResult]:
    result = text_cleaner.clean_text(text, remove_semantic=remove_semantic)
    clean_result = CleanResult(
        source="<text>",
        output="<text>",
        actions=[result.action],
        before_hash=_hash(text.encode("utf-8")),
        after_hash=_hash(result.cleaned.encode("utf-8")),
    )
    return result.cleaned, clean_result


def clean_file(path: Path, *, output_path: Path | None = None) -> CleanResult:
    check_supported(path.name)
    ext = suffix_of(path.name)
    original_bytes = path.read_bytes()
    output_path = output_path or cleaned_output_path(path)
    actions: list[CleanAction] = []

    if ext in TEXT_EXTENSIONS:
        text = original_bytes.decode("utf-8", errors="replace")
        result = text_cleaner.clean_text(text)
        cleaned_bytes = result.cleaned.encode("utf-8")
        actions = [result.action]
        output_path.write_bytes(cleaned_bytes)

    elif ext in PDF_EXTENSIONS:
        actions = pdf_cleaner.clean_pdf_file(path, output_path)
        actions.append(
            CleanAction(
                "c2pa",
                "C2PA / provenance",
                False,
                False,
                True,
                False,
                "C2PA cleaning is not implemented for PDF in this version (unsupported).",
            )
        )
        cleaned_bytes = output_path.read_bytes()

    elif ext in IMAGE_EXTENSIONS:
        cleaned_bytes, actions = image_cleaner.clean_image_bytes(original_bytes, ext)
        cleaned_bytes, c2pa_action = c2pa_cleaner.clean_c2pa_bytes(cleaned_bytes, ext)
        actions.append(c2pa_action)
        output_path.write_bytes(cleaned_bytes)

    else:
        raise UnsupportedFileTypeError(f"No cleaner registered for '{ext}'")

    return CleanResult(
        source=str(path),
        output=str(output_path),
        actions=actions,
        before_hash=_hash(original_bytes),
        after_hash=_hash(cleaned_bytes),
    )
