"""GhostMark command-line interface."""

from __future__ import annotations

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
from ghostmark.security import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    check_size,
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
def verify(
    file: Path = typer.Argument(..., exists=True, readable=True, help="Cleaned file to verify."),
    original: Path | None = typer.Option(
        None, "--original", help="Original file to compare against (auto-detected for *.ghostmark.* files)."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON instead of text."),
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
        else:
            report = inspect_file(file)
            if json_output:
                typer.echo(json.dumps(report.to_dict(), indent=2))
            else:
                typer.echo("No original file found for comparison -- showing current inspection only.\n")
                _print_report_human(report)
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
