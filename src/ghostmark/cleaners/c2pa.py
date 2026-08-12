"""C2PA / Content Credentials removal.

This strips the JUMBF container segment/chunk found by
``ghostmark.detectors.c2pa`` (JPEG APP11, PNG caBX). That reliably removes
the C2PA manifest *when GhostMark's heuristic scan found it in the expected
container*, but it is not a guarantee against every possible embedding
technique a future C2PA implementation might use. Cleaning results are
always reported as ``partial`` for this reason -- never as a flat
"removed".
"""

from __future__ import annotations

from pathlib import Path

from ghostmark.formats import jpeg, png
from ghostmark.models import CleanAction

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png"}


def clean_c2pa_bytes(data: bytes, suffix: str) -> tuple[bytes, CleanAction]:
    suffix = suffix.lower()

    if suffix in (".jpg", ".jpeg"):
        try:
            cleaned, removed = jpeg.strip_c2pa(data)
        except jpeg.NotAJpegError as exc:
            return data, CleanAction("c2pa", "C2PA / provenance", False, False, False, True, str(exc))
    elif suffix == ".png":
        try:
            cleaned, removed = png.strip_c2pa(data)
        except png.NotAPngError as exc:
            return data, CleanAction("c2pa", "C2PA / provenance", False, False, False, True, str(exc))
    else:
        return data, CleanAction(
            "c2pa", "C2PA / provenance", False, False, True, False,
            f"C2PA cleaning is not implemented for {suffix or 'this file type'} (unsupported).",
        )

    note = (
        "Removed JUMBF/C2PA container (partial: structural removal only, not a full manifest audit)."
        if removed
        else "No C2PA/JUMBF container detected by the heuristic scan."
    )
    return cleaned, CleanAction("c2pa", "C2PA / provenance", True, removed, not removed, False, note)


def clean_c2pa_file(path: Path) -> tuple[bytes, CleanAction]:
    return clean_c2pa_bytes(path.read_bytes(), path.suffix)
