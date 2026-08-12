"""Independent cross-check of a cleaned file using ExifTool, if installed.

GhostMark's own detectors (``ghostmark.detectors.metadata``) are pure
Python and always run. This module adds an optional *independent* second
opinion using ExifTool (https://exiftool.org/) -- a long-established,
widely trusted third-party tool -- so a user doesn't have to take
GhostMark's own word for it that a file is clean.

This is opt-in in the sense that it only activates when ExifTool is
present on PATH; GhostMark never requires it to run, and never fabricates
a result when it's absent -- it reports ``unknown`` honestly instead.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ghostmark.models import Category, Confidence, DetectionResult, Status

DETECTOR_KEY = "exiftool_independent"
LABEL = "Independent verification (ExifTool)"

# ExifTool always reports these groups even for a file with zero embedded
# metadata (file size, MIME type, derived/computed values) -- they are not
# "metadata" in the sense GhostMark cleans, so they're excluded when
# deciding whether anything remains.
_IGNORED_GROUPS = {"SourceFile", "ExifTool", "File", "Composite"}

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


def exiftool_available() -> bool:
    return shutil.which("exiftool") is not None


def _unavailable(note: str) -> DetectionResult:
    return DetectionResult(
        detector=DETECTOR_KEY,
        label=LABEL,
        status=Status.UNKNOWN,
        category=Category.METADATA,
        confidence=Confidence.UNKNOWN,
        removable=False,
        details={"note": note},
    )


def exiftool_check(path: Path) -> DetectionResult:
    """Run `exiftool -j -G` on ``path`` and report whether any real metadata remains.

    Always returns a DetectionResult -- never raises, never silently omits
    a result. If ExifTool isn't installed, isn't applicable to this file
    type, or fails for any reason, that is reported as ``unknown`` with an
    explanatory note rather than pretending the check ran.
    """

    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        return _unavailable(f"ExifTool cross-check is not applicable to {path.suffix or 'this file type'}.")

    if not exiftool_available():
        return _unavailable("ExifTool is not installed. Install it from https://exiftool.org/ for independent verification.")

    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, path is our own generated file
            ["exiftool", "-j", "-G", str(path)],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _unavailable(f"ExifTool could not be run: {exc}")

    if proc.returncode != 0:
        return _unavailable(f"ExifTool exited with an error: {proc.stderr.decode('utf-8', errors='replace')[:200]}")

    try:
        records = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return _unavailable("ExifTool returned output GhostMark could not parse.")

    if not records:
        return _unavailable("ExifTool returned no data for this file.")

    record = records[0]
    remaining_tags = {
        key: value
        for key, value in record.items()
        if ":" in key and key.split(":", 1)[0] not in _IGNORED_GROUPS
    }

    found = bool(remaining_tags)
    return DetectionResult(
        detector=DETECTOR_KEY,
        label=LABEL,
        status=Status.FOUND if found else Status.NOT_FOUND,
        category=Category.METADATA,
        confidence=Confidence.HIGH,
        removable=False,
        details={
            "tool": "exiftool",
            "remaining_tag_count": len(remaining_tags),
            "remaining_tags": list(remaining_tags.keys())[:25],
        },
    )
