"""Independent cross-checks of a file using external, third-party tools.

GhostMark's own detectors (``ghostmark.detectors.metadata``,
``ghostmark.detectors.c2pa``) are pure Python and always run. This module
adds optional *independent* second opinions from separate, independently
trusted tools, so a user doesn't have to take GhostMark's own word for it
that a file is clean:

- **ExifTool** (https://exiftool.org/) for EXIF/XMP/IPTC/PDF metadata.
- **c2patool** (https://github.com/contentauth/c2pa-rs, the official
  Content Authenticity Initiative CLI) for C2PA manifest presence.

Both are treated strictly as external runtime dependencies: GhostMark
never vendors their source or binary, only shells out to whatever it
finds on PATH (see THIRD_PARTY_LICENSES.md for each tool's license --
ExifTool is GPL, c2patool is Apache-2.0/MIT). This keeps GhostMark itself
MIT-licensed.

Both are opt-in in the sense that they only activate when the
corresponding binary is present on PATH; GhostMark never requires either
to run, and never fabricates a result when one is absent -- it reports
``unknown``/unavailable honestly instead.

c2patool can *read* a C2PA manifest, but GhostMark only uses that to
confirm presence/absence of a manifest -- this is NOT a claim of
cryptographic signature/trust-chain validation. Do not conflate "c2patool
found no manifest" with "this content is unmodified since signing"; those
are different questions.

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

from ghostmark.models import C2paVerificationResult, ExternalVerificationResult, MetadataOrigin

EXIFTOOL_NAME = "exiftool"
C2PATOOL_NAME = "c2patool"
SUBPROCESS_TIMEOUT_SECONDS = 15

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
C2PA_SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".pdf"}

# c2patool's read-only output (or its error message) when no manifest is
# present isn't guaranteed to be identical across versions, so this checks
# for the substrings its documented behavior is known to use rather than
# matching one exact string.
_NO_MANIFEST_MARKERS = ("no claim", "no manifest", "not found", "no embed")

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


def _run_process(display_name: str, exe_name: str, args: list[str]) -> _RunResult:
    """Run an external verifier binary with a fixed, non-shell argv and a strict timeout.

    Never interpolates a filename into a shell string -- ``args`` is passed
    straight to the OS as an argv array with ``shell=False``. Shared by
    every external verifier (ExifTool, c2patool, ...) so process-launch
    safety is enforced in exactly one place.
    """

    exe = shutil.which(exe_name)
    if exe is None:
        return _RunResult(ok=False, note=f"{display_name} is not installed.")
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv resolved via shutil.which, shell=False
            [exe, *args],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _RunResult(ok=False, note=f"{display_name} timed out after {SUBPROCESS_TIMEOUT_SECONDS}s.")
    except OSError as exc:
        return _RunResult(ok=False, note=f"{display_name} could not be run: {exc}")

    if proc.returncode != 0:
        return _RunResult(
            ok=False, stdout=proc.stdout, stderr=proc.stderr,
            note=f"{display_name} exited with code {proc.returncode}.",
        )
    return _RunResult(ok=True, stdout=proc.stdout, stderr=proc.stderr)


class ExifToolVerifier:
    """Adapter around the external ``exiftool`` binary."""

    def available(self) -> bool:
        return shutil.which(EXIFTOOL_NAME) is not None

    def version(self) -> str | None:
        if not self.available():
            return None
        result = _run_process("ExifTool", EXIFTOOL_NAME, ["-ver"])
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
                tool=EXIFTOOL_NAME,
                available=self.available(),
                applicable=False,
                version=self.version(),
                note=f"ExifTool cross-check is not applicable to {suffix or 'this file type'}.",
            )

        if not self.available():
            return ExternalVerificationResult(
                tool=EXIFTOOL_NAME,
                available=False,
                applicable=True,
                note="ExifTool is not installed. Install it from https://exiftool.org/ for independent verification.",
            )

        result = _run_process("ExifTool", EXIFTOOL_NAME, ["-j", "-G1", "-a", "-s", str(path)])
        version = self.version()
        if not result.ok:
            note = result.note
            if result.stderr:
                note += " " + result.stderr.decode("utf-8", errors="replace")[:200]
            return ExternalVerificationResult(
                tool=EXIFTOOL_NAME, available=True, applicable=True, version=version, note=note.strip()
            )

        try:
            records = json.loads(result.stdout.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return ExternalVerificationResult(
                tool=EXIFTOOL_NAME,
                available=True,
                applicable=True,
                version=version,
                note="ExifTool returned output GhostMark could not parse.",
            )

        if not records:
            return ExternalVerificationResult(
                tool=EXIFTOOL_NAME,
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
            tool=EXIFTOOL_NAME,
            available=True,
            applicable=True,
            version=version,
            tags_by_origin=tags_by_origin,
            ran_successfully=True,
        )


class C2paToolVerifier:
    """Adapter around the external ``c2patool`` binary (read-only manifest check).

    c2patool is only invoked in its default read-only mode (no ``-m``
    flag, so it never signs or modifies anything) -- it simply reads
    whatever C2PA manifest is embedded and prints it as JSON, or reports
    that none was found.
    """

    def available(self) -> bool:
        return shutil.which(C2PATOOL_NAME) is not None

    def version(self) -> str | None:
        if not self.available():
            return None
        result = _run_process("c2patool", C2PATOOL_NAME, ["--version"])
        if not result.ok:
            return None
        # Typical output: "c2patool 0.27.12"
        text = result.stdout.decode("utf-8", errors="replace").strip()
        parts = text.split()
        return parts[-1] if parts else (text or None)

    def inspect(self, path: Path) -> C2paVerificationResult:
        """Run ``c2patool FILE`` (read-only) and report manifest presence/absence.

        Always returns a result -- never raises. A non-zero exit with a
        message matching a known "no manifest" pattern is reported as
        ``found=False``; any other failure is reported via ``note`` with
        ``found`` left at its default (unknown, not asserted either way).
        """

        suffix = path.suffix.lower()
        if suffix not in C2PA_SUPPORTED_SUFFIXES:
            return C2paVerificationResult(
                tool=C2PATOOL_NAME,
                available=self.available(),
                applicable=False,
                version=self.version(),
                note=f"c2patool cross-check is not applicable to {suffix or 'this file type'}.",
            )

        if not self.available():
            return C2paVerificationResult(
                tool=C2PATOOL_NAME,
                available=False,
                applicable=True,
                note=(
                    "c2patool is not installed. See "
                    "https://github.com/contentauth/c2pa-rs/tree/main/cli for install options."
                ),
            )

        result = _run_process("c2patool", C2PATOOL_NAME, [str(path)])
        version = self.version()

        if result.ok:
            try:
                manifest = json.loads(result.stdout.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                return C2paVerificationResult(
                    tool=C2PATOOL_NAME,
                    available=True,
                    applicable=True,
                    version=version,
                    note="c2patool returned output GhostMark could not parse.",
                )
            found = bool(manifest)
            return C2paVerificationResult(
                tool=C2PATOOL_NAME,
                available=True,
                applicable=True,
                version=version,
                found=found,
                ran_successfully=True,
                note="" if found else "c2patool ran successfully and found no manifest.",
            )

        combined_output = (result.stdout + result.stderr).decode("utf-8", errors="replace").lower()
        if any(marker in combined_output for marker in _NO_MANIFEST_MARKERS):
            return C2paVerificationResult(
                tool=C2PATOOL_NAME,
                available=True,
                applicable=True,
                version=version,
                found=False,
                ran_successfully=True,
                note="c2patool reported no C2PA manifest present.",
            )

        # A real tool failure (crash, unsupported format, etc.) -- do not
        # guess found=True or found=False, report it as genuinely unknown.
        note = result.note
        if result.stderr:
            note += " " + result.stderr.decode("utf-8", errors="replace")[:200]
        return C2paVerificationResult(
            tool=C2PATOOL_NAME, available=True, applicable=True, version=version, note=note.strip()
        )


_DEFAULT_EXIFTOOL_VERIFIER = ExifToolVerifier()
_DEFAULT_C2PATOOL_VERIFIER = C2paToolVerifier()


def exiftool_available() -> bool:
    return _DEFAULT_EXIFTOOL_VERIFIER.available()


def exiftool_inspect(path: Path) -> ExternalVerificationResult:
    return _DEFAULT_EXIFTOOL_VERIFIER.inspect(path)


def c2patool_available() -> bool:
    return _DEFAULT_C2PATOOL_VERIFIER.available()


def c2patool_inspect(path: Path) -> C2paVerificationResult:
    return _DEFAULT_C2PATOOL_VERIFIER.inspect(path)
