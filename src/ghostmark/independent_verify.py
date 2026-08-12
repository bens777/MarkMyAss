"""Independent cross-check of a file using ExifTool, if installed.

GhostMark's own detectors (``ghostmark.detectors.metadata``) are pure
Python and always run. This module adds an optional *independent* second
opinion using ExifTool (https://exiftool.org/) -- a long-established,
widely trusted third-party tool -- so a user doesn't have to take
GhostMark's own word for it that a file is clean.

ExifTool is GPL-licensed and is treated strictly as an external runtime
dependency: GhostMark never vendors its source or binary, only shells out
to whatever ``exiftool`` it finds on PATH (see THIRD_PARTY_LICENSES.md).
This keeps GhostMark itself MIT-licensed.

This is opt-in in the sense that it only activates when ExifTool is
present on PATH; GhostMark never requires it to run, and never fabricates
a result when it's absent -- it reports ``unknown``/unavailable honestly
instead.

## Categorization

ExifTool reports many properties for any file that are not embedded,
removable metadata: file size, MIME type, image dimensions, filesystem
timestamps, and other values it computes itself (see ``categorize_tag``).
Treating those as "metadata GhostMark failed to remove" would be wrong,
so every tag ExifTool reports is bucketed into one of:

- ``embedded_metadata``: what GhostMark's cleaners target (EXIF, GPS,
  IPTC, XMP, Photoshop IRB, PDF document-info/XMP fields, comments).
- ``structural``: needed for the file to render/open correctly (ICC
  color profile, PDF page count, PNG bit depth, ...). Never "removed".
- ``filesystem``: facts about the file on disk (name, size, path).
- ``computed``: values ExifTool derives itself, not stored in the file
  (e.g. the ``Composite`` group, ExifTool's own version).
- ``unknown``: anything not confidently classified either way. Shown for
  transparency but never counted toward pass/fail.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ghostmark.models import ExternalVerificationResult, MetadataOrigin

TOOL_NAME = "exiftool"
SUBPROCESS_TIMEOUT_SECONDS = 15

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}

# --- Tag categorization ---------------------------------------------------------------

_FILESYSTEM_GROUPS = {"file", "sourcefile"}
_COMPUTED_GROUPS = {"exiftool", "composite"}
_STRUCTURAL_GROUPS = {"icc-header", "icc_profile", "iccprofile", "jfif"}

# Any group1 name starting with one of these is treated as embedded metadata.
_METADATA_GROUP_PREFIXES = (
    "exif", "gps", "iptc", "xmp", "photoshop", "makernotes", "interopifd", "ifd0", "ifd1",
)

# PDF and PNG tags all share one group1 name regardless of whether they're
# metadata or structural facts, so those two need tag-name-level rules.
_PDF_STRUCTURAL_TAGS = {
    "pdfversion", "linearized", "pagecount", "encryption", "taggedpdf",
    "pageid", "pagelayout", "pagemode", "language",
}
_PNG_STRUCTURAL_TAGS = {
    "imagewidth", "imageheight", "bitdepth", "colortype", "compression",
    "filter", "interlace", "pixelsperunitx", "pixelsperunity", "pixelunits",
    "srgbrendering", "gamma", "palette", "transparency", "backgroundcolor",
}


def categorize_tag(key: str) -> MetadataOrigin:
    """Classify one ``Group:Tag`` key from ExifTool's ``-G1 -j`` output."""

    if ":" not in key:
        return MetadataOrigin.FILESYSTEM if key.lower() == "sourcefile" else MetadataOrigin.UNKNOWN

    group, tag = key.split(":", 1)
    g, t = group.lower(), tag.lower()

    if g in _FILESYSTEM_GROUPS:
        return MetadataOrigin.FILESYSTEM
    if g in _COMPUTED_GROUPS:
        return MetadataOrigin.COMPUTED
    if g in _STRUCTURAL_GROUPS:
        return MetadataOrigin.STRUCTURAL
    if g == "pdf":
        return MetadataOrigin.STRUCTURAL if t in _PDF_STRUCTURAL_TAGS else MetadataOrigin.EMBEDDED_METADATA
    if g == "png":
        return MetadataOrigin.STRUCTURAL if t in _PNG_STRUCTURAL_TAGS else MetadataOrigin.EMBEDDED_METADATA
    if any(g.startswith(p) for p in _METADATA_GROUP_PREFIXES):
        return MetadataOrigin.EMBEDDED_METADATA
    return MetadataOrigin.UNKNOWN


@dataclass
class _RunResult:
    ok: bool
    stdout: bytes = b""
    stderr: bytes = b""
    note: str = ""


def _run_exiftool(args: list[str]) -> _RunResult:
    """Run exiftool with a fixed, non-shell argv and a strict timeout.

    Never interpolates a filename into a shell string -- ``args`` is passed
    straight to the OS as an argv array with ``shell=False``.
    """

    exe = shutil.which(TOOL_NAME)
    if exe is None:
        return _RunResult(ok=False, note="ExifTool is not installed.")
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv resolved via shutil.which, shell=False
            [exe, *args],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _RunResult(ok=False, note=f"ExifTool timed out after {SUBPROCESS_TIMEOUT_SECONDS}s.")
    except OSError as exc:
        return _RunResult(ok=False, note=f"ExifTool could not be run: {exc}")

    if proc.returncode != 0:
        return _RunResult(ok=False, stderr=proc.stderr, note="ExifTool exited with an error.")
    return _RunResult(ok=True, stdout=proc.stdout, stderr=proc.stderr)


class ExifToolVerifier:
    """Adapter around the external ``exiftool`` binary."""

    def available(self) -> bool:
        return shutil.which(TOOL_NAME) is not None

    def version(self) -> str | None:
        if not self.available():
            return None
        result = _run_exiftool(["-ver"])
        if not result.ok:
            return None
        return result.stdout.decode("utf-8", errors="replace").strip() or None

    def inspect(self, path: Path) -> ExternalVerificationResult:
        """Run ``exiftool -j -G1 -a -s FILE`` and categorize every tag it reports.

        Always returns a result -- never raises, never silently omits a
        result. Absence/unavailability is reported explicitly via
        ``available``/``applicable``/``note`` rather than an exception.
        """

        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            return ExternalVerificationResult(
                tool=TOOL_NAME,
                available=self.available(),
                applicable=False,
                version=self.version(),
                note=f"ExifTool cross-check is not applicable to {suffix or 'this file type'}.",
            )

        if not self.available():
            return ExternalVerificationResult(
                tool=TOOL_NAME,
                available=False,
                applicable=True,
                note="ExifTool is not installed. Install it from https://exiftool.org/ for independent verification.",
            )

        result = _run_exiftool(["-j", "-G1", "-a", "-s", str(path)])
        version = self.version()
        if not result.ok:
            note = result.note
            if result.stderr:
                note += " " + result.stderr.decode("utf-8", errors="replace")[:200]
            return ExternalVerificationResult(
                tool=TOOL_NAME, available=True, applicable=True, version=version, note=note.strip()
            )

        try:
            records = json.loads(result.stdout.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return ExternalVerificationResult(
                tool=TOOL_NAME,
                available=True,
                applicable=True,
                version=version,
                note="ExifTool returned output GhostMark could not parse.",
            )

        if not records:
            return ExternalVerificationResult(
                tool=TOOL_NAME,
                available=True,
                applicable=True,
                version=version,
                note="ExifTool returned no data for this file.",
            )

        record = records[0]
        tags_by_origin: dict[str, dict[str, str]] = {}
        for key, value in record.items():
            origin = categorize_tag(key)
            tags_by_origin.setdefault(origin.value, {})[key] = str(value)

        return ExternalVerificationResult(
            tool=TOOL_NAME,
            available=True,
            applicable=True,
            version=version,
            tags_by_origin=tags_by_origin,
        )


_DEFAULT_VERIFIER = ExifToolVerifier()


def exiftool_available() -> bool:
    return _DEFAULT_VERIFIER.available()


def exiftool_inspect(path: Path) -> ExternalVerificationResult:
    return _DEFAULT_VERIFIER.inspect(path)
