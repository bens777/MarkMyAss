"""GhostMark command-line interface."""

from __future__ import annotations

import hashlib
import json
import sys
import webbrowser
from pathlib import Path
from threading import Timer

import typer

from ghostmark import __version__
from ghostmark.cleaner import clean_file, clean_text_content
from ghostmark.fixtures.generate import generate_all
from ghostmark.inspector import inspect_file, inspect_text
from ghostmark.models import InspectionReport, Status, VerifyResult
from ghostmark.receipt import build_receipt
from ghostmark.reprocess import DEFAULT_PROFILE, PROFILES, reprocess_image_bytes
from ghostmark.security import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    check_size,
    check_supported,
    suffix_of,
)
from ghostmark.verifier import verify_file

app = typer.Typer(
    name="ghostmark",
    help="Open-source AI watermark & provenance cleaner. Inspect, clean, verify -- 100% local.",
    no_args_is_help=True,
    add_completion=False,
)

_STATUS_WORD = {Status.FOUND: "FOUND", Status.NOT_FOUND: "NOT FOUND", Status.UNKNOWN: "UNKNOWN"}
_STATUS_ICON = {Status.FOUND: "⚠", Status.NOT_FOUND: "✓", Status.UNKNOWN: "?"}


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"GhostMark {__version__}")
        raise typer.Exit(0)


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show the GhostMark version and exit."
    ),
) -> None:
    """GhostMark: inspect, clean and verify AI watermark & provenance signals -- entirely local."""


def _print_report_human(report: InspectionReport) -> None:
    typer.echo("GhostMark inspection\n")
    typer.echo(f"File: {report.target}")
    typer.echo("✓ File readable")
    if not report.enhanced_metadata_support and report.target_type in ("pdf", "png", "jpg", "jpeg", "webp"):
        typer.echo("Enhanced metadata support: unavailable (install ExifTool for deeper inspection)")
    for d in report.detections:
        icon = _STATUS_ICON[d.status]
        word = _STATUS_WORD[d.status]
        suffix = " (experimental)" if d.experimental else ""
        typer.echo(f"{icon} {d.label}: {word}{suffix}")
    typer.echo(f"\nRisk / provenance signals found: {report.signal_count()}")
    if report.warnings:
        typer.echo("\nWarnings:")
        for w in report.warnings:
            typer.echo(f"  - {w}")


_VERDICT_WORD = {
    "verified_clean": "VERIFIED CLEAN",
    "partial": "PARTIAL",
    "unverified": "UNVERIFIED",
    "not_applicable": "NOT APPLICABLE",
    "failed": "FAILED",
}


def _print_verify_human(result: VerifyResult) -> None:
    typer.echo("Verification report\n")
    typer.echo("Before:")
    for d in result.before.detections:
        typer.echo(f"  {d.label}: {_STATUS_WORD[d.status]}")
    typer.echo("\nAfter:")
    for d in result.after.detections:
        typer.echo(f"  {d.label}: {_STATUS_WORD[d.status]}")
    typer.echo(f"\n{result.summary()}")
    if result.unknown:
        typer.echo("\nMechanisms GhostMark cannot verify: " + ", ".join(sorted(set(result.unknown))))

    typer.echo("\nIndependent verification")
    ext = result.external_after
    if ext is not None:
        if not ext.applicable:
            typer.echo(f"ExifTool: NOT APPLICABLE -- {ext.note}")
        elif not ext.available:
            typer.echo("ExifTool: unavailable. GhostMark's internal verification above still applies, but an")
            typer.echo("independent cross-check could not be performed. Install ExifTool from https://exiftool.org/.")
        else:
            version = ext.version or "unknown version"
            typer.echo(f"Verified with ExifTool {version}")
            if ext.has_embedded_metadata:
                typer.echo(f"⚠ ExifTool still finds {len(ext.embedded_metadata_tags)} embedded metadata tag(s):")
                for key in list(ext.embedded_metadata_tags)[:10]:
                    typer.echo(f"    {key}")
            else:
                typer.echo("✓ ExifTool finds no remaining embedded metadata")

    c2pa = result.c2pa_after
    if c2pa is not None:
        if not c2pa.applicable:
            pass  # not worth a line for plain text / unsupported formats
        elif not c2pa.available:
            typer.echo("c2patool: unavailable (optional). See https://github.com/contentauth/c2pa-rs/tree/main/cli.")
        else:
            version = c2pa.version or "unknown version"
            typer.echo(f"Verified with c2patool {version}")
            typer.echo("⚠ c2patool still finds a C2PA manifest" if c2pa.found else "✓ c2patool finds no C2PA manifest")

    summary = result.summary_v2
    if summary is not None:
        typer.echo(f"\nGhostMark verification: {'PASS' if summary.ghostmark_pass else 'FAIL'}")
        for verifier in summary.external_verifiers:
            if verifier.passed is None:
                typer.echo(f"{verifier.label} verification: NOT AVAILABLE / NOT APPLICABLE")
            else:
                typer.echo(f"{verifier.label} verification: {'PASS' if verifier.passed else 'FAIL'}")
        typer.echo(f"\nOverall: {_VERDICT_WORD[summary.verdict.value]}")
        typer.echo(f"C2PA support: {summary.c2pa_status.upper()}")
        typer.echo("Statistical AI watermark: UNKNOWN / NOT CURRENTLY VERIFIABLE")


@app.command()
def inspect(
    file: Path = typer.Argument(..., exists=True, readable=True, help="File to inspect."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON instead of text."),
) -> None:
    """Inspect a file for hidden Unicode, metadata and provenance signals."""

    try:
        check_size(file.stat().st_size)
        report = inspect_file(file)
    except (UnsupportedFileTypeError, FileTooLargeError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    if json_output:
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        _print_report_human(report)
    raise typer.Exit(0)


@app.command()
def clean(
    file: Path = typer.Argument(..., exists=True, readable=True, help="File to clean."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output path (default: NAME.ghostmark.EXT)."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON instead of text."),
) -> None:
    """Clean a file, writing a new sanitized copy. The original is never modified."""

    try:
        check_size(file.stat().st_size)
        result = clean_file(file, output_path=output)
    except (UnsupportedFileTypeError, FileTooLargeError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    if json_output:
        typer.echo(json.dumps(result.to_dict(), indent=2))
    else:
        typer.echo("GhostMark clean\n")
        typer.echo(f"Source: {result.source}")
        typer.echo(f"Output: {result.output}\n")
        for a in result.actions:
            if a.removed:
                verb = "removed"
            elif a.failed:
                verb = "FAILED"
            else:
                verb = "preserved / not present"
            typer.echo(f"{a.label}: {verb}{' - ' + a.note if a.note else ''}")
        typer.echo(f"\nOriginal file untouched: {result.source}")
        typer.echo(f"Cleaned copy written to: {result.output}")
    raise typer.Exit(0)


@app.command()
def reprocess(
    file: Path = typer.Argument(..., exists=True, readable=True, help="Image file to reprocess."),
    profile: str = typer.Option(DEFAULT_PROFILE, "--profile", "-p", help="light | medium | strong."),
    fmt: str | None = typer.Option(
        None, "--format", "-f", help="Output format: png | jpeg | webp (default: keep source)."
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output path."),
    report: bool = typer.Option(
        False, "--report", help="Also emit an observational before/after provenance comparison."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON instead of text."),
) -> None:
    """Create a NEW pixel representation of an image (decode + re-encode / resample).

    Distinct from `clean`, which strips metadata without touching pixels. This
    does NOT guarantee removal of statistical watermarks such as SynthID.
    """
    try:
        check_size(file.stat().st_size)
        check_supported(file.name)
        if suffix_of(file.name) not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise UnsupportedFileTypeError("Reprocess supports images only (PNG, JPEG, WebP).")
        if profile not in PROFILES:
            raise typer.BadParameter(f"profile must be one of: {', '.join(PROFILES)}")
        result = reprocess_image_bytes(file.read_bytes(), file.suffix, profile, out_format=fmt)
    except (UnsupportedFileTypeError, FileTooLargeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    out_path = output or file.with_name(f"{file.stem}.reprocessed{result.output_suffix}")
    out_path.write_bytes(result.output_bytes)

    robustness = None
    if report:
        from ghostmark.robustness import build_robustness_report

        robustness = build_robustness_report(
            input_report=inspect_file(file),
            output_report=inspect_file(out_path),
            reprocess_result=result,
        )

    if json_output:
        payload = result.to_dict()
        payload["output"] = str(out_path)
        if robustness is not None:
            payload["robustness"] = robustness
        typer.echo(json.dumps(payload, indent=2))
    else:
        m = result.to_dict()["metrics"]
        typer.echo("GhostMark reprocess\n")
        typer.echo(f"Source: {file}")
        typer.echo(f"Output: {out_path}")
        typer.echo(f"Profile: {result.profile} ({result.output_format})")
        typer.echo("Operations: " + " -> ".join(result.operations))
        typer.echo(
            f"\nDimensions: {m['original_dimensions'][0]}x{m['original_dimensions'][1]} -> "
            f"{m['output_dimensions'][0]}x{m['output_dimensions'][1]}"
        )
        typer.echo(f"Bytes: {m['original_size_bytes']} -> {m['output_size_bytes']}")
        typer.echo(f"SSIM: {m['ssim']}  PSNR: {m['psnr']} dB  Pixels changed: {m['pixel_changed_pct']}%")
        for w in result.warnings:
            typer.echo(f"Note: {w}")
        if robustness is not None:
            typer.echo("\nObservational before/after provenance comparison:")
            typer.echo(f"  Input  C2PA: {robustness['input']['c2pa_status']}  "
                       f"metadata signals: {robustness['input']['metadata_signals'] or 'none'}")
            typer.echo(f"  Output C2PA: {robustness['output']['c2pa_status']}  "
                       f"metadata signals: {robustness['output']['metadata_signals'] or 'none'}")
            typer.echo("  (Observation only -- reprocess never retries based on any detector result.)")
        typer.echo("\nSSIM/PSNR describe pixel difference; they are not proof of visual identity.")
        typer.echo("Reprocess does not guarantee removal of statistical watermarks such as SynthID.")
    raise typer.Exit(0)


@app.command()
def verify(
    file: Path = typer.Argument(..., exists=True, readable=True, help="Cleaned file to verify."),
    original: Path | None = typer.Option(
        None, "--original", help="Original file to compare against (auto-detected for *.ghostmark.* files)."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON instead of text."),
    receipt: Path | None = typer.Option(
        None,
        "--receipt",
        help="Save a Verification Receipt to this path. Format is inferred from the extension "
        "(.json, .html, or .txt); defaults to JSON.",
    ),
) -> None:
    """Re-inspect a cleaned file and report which signals were actually removed."""

    if original is None:
        stem = file.stem
        if stem.endswith(".ghostmark"):
            candidate = file.with_name(stem[: -len(".ghostmark")] + file.suffix)
            if candidate.exists():
                original = candidate

    try:
        if original is not None:
            result = verify_file(original, file)
            if json_output:
                typer.echo(json.dumps(result.to_dict(), indent=2))
            else:
                _print_verify_human(result)

            if receipt is not None:
                receipt_obj = build_receipt(
                    file_name=file.name,
                    before_hash=hashlib.sha256(original.read_bytes()).hexdigest(),
                    after_hash=hashlib.sha256(file.read_bytes()).hexdigest(),
                    verify_result=result,
                )
                suffix = receipt.suffix.lower()
                if suffix == ".html":
                    receipt.write_text(receipt_obj.to_html(), encoding="utf-8")
                elif suffix == ".txt":
                    receipt.write_text(receipt_obj.to_text(), encoding="utf-8")
                else:
                    receipt.write_text(receipt_obj.to_json(), encoding="utf-8")
                typer.echo(f"\nVerification Receipt written to: {receipt}")
        else:
            report = inspect_file(file)
            if json_output:
                typer.echo(json.dumps(report.to_dict(), indent=2))
            else:
                typer.echo("No original file found for comparison -- showing current inspection only.\n")
                _print_report_human(report)
            if receipt is not None:
                typer.echo(
                    "\nNo Verification Receipt written: a receipt requires comparing against the "
                    "original file (--original), which was not found.",
                    err=True,
                )
    except (UnsupportedFileTypeError, FileTooLargeError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    raise typer.Exit(0)


@app.command("inspect-text")
def inspect_text_cmd(
    text: str = typer.Argument(..., help="Text to inspect."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON instead of text."),
) -> None:
    """Inspect a text string for hidden Unicode and (unverified) statistical watermark signals."""

    report = inspect_text(text)
    if json_output:
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        _print_report_human(report)
    raise typer.Exit(0)


@app.command("clean-text")
def clean_text_cmd(
    text: str = typer.Argument(..., help="Text to clean."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON instead of text."),
) -> None:
    """Clean a text string and print the result to stdout."""

    cleaned, result = clean_text_content(text)
    if json_output:
        payload = result.to_dict()
        payload["cleaned_text"] = cleaned
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(cleaned)
    raise typer.Exit(0)


@app.command()
def demo() -> None:
    """Generate synthetic fixtures, run inspect -> clean -> verify, and print PASS/FAIL."""

    import tempfile

    typer.echo("GhostMark Demo")
    typer.echo("==============\n")

    checks: list[tuple[str, bool]] = []
    with tempfile.TemporaryDirectory(prefix="ghostmark-demo-") as tmp:
        tmp_path = Path(tmp)
        fixtures = generate_all(tmp_path)

        label_map = {
            "text": "Text watermark artifacts",
            "jpeg": "JPEG metadata",
            "png": "PNG metadata",
            "webp": "WebP metadata",
            "pdf": "PDF metadata",
        }

        for key, path in fixtures.items():
            label = label_map[key]
            try:
                before = inspect_file(path)
                found_before = before.signal_count() > 0
                clean_result = clean_file(path)
                output_path = Path(clean_result.output)
                verify_result = verify_file(path, output_path)
                resolvable = [
                    d.detector
                    for d in before.detections
                    if d.status is Status.FOUND
                    and any(a.detector == d.detector and a.attempted for a in clean_result.actions)
                ]
                ok = found_before and all(r in verify_result.resolved for r in resolvable)
                checks.append((label, ok))
            except Exception as exc:  # noqa: BLE001 - a demo failure must not crash the whole run
                typer.echo(f"  ! {label} raised an error: {exc}")
                checks.append((label, False))

        checks.append(("Verification engine", all(ok for _, ok in checks)))

        for label, ok in checks:
            typer.echo(f"{label:<30} {'PASS' if ok else 'FAIL'}")

        passed = sum(1 for _, ok in checks if ok)
        typer.echo(f"\n{passed}/{len(checks)} tests successful.\n")

        if passed == len(checks):
            typer.echo("GhostMark is working.")
            raise typer.Exit(0)
        typer.echo("GhostMark demo reported failures -- see above.")
        raise typer.Exit(1)


@app.command()
def ui(
    port: int = typer.Option(8765, "--port", help="Local port to bind."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open a browser window."),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help=(
            "Bind address. Defaults to localhost-only. Only change this if you understand the "
            "exposure -- e.g. inside a container whose port mapping is itself restricted to "
            "localhost on the host machine. Never expose GhostMark's UI to an untrusted network."
        ),
    ),
) -> None:
    """Start the local web UI at http://127.0.0.1:PORT (binds to localhost only by default)."""

    import uvicorn

    from ghostmark.web.app import create_app

    display_host = "127.0.0.1" if host == "0.0.0.0" else host  # noqa: S104 - user-facing URL only
    url = f"http://{display_host}:{port}"
    typer.echo(f"GhostMark UI starting at {url}")
    if host == "0.0.0.0":  # noqa: S104
        typer.echo("WARNING: binding to 0.0.0.0 -- reachable from other devices on this network.\n")
    else:
        typer.echo("This server only listens on localhost. Your files never leave this computer.\n")

    if not no_browser:
        Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


def run() -> None:
    app()


if __name__ == "__main__":
    sys.exit(run())
