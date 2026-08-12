# Third-party dependency licenses

GhostMark is MIT-licensed. Its runtime dependencies use permissive
licenses, with one deliberate exception noted below. This list covers
direct runtime dependencies (see `pyproject.toml` for exact version
constraints; generated with `pip-licenses`).

| Package            | License        | Notes |
| ------------------- | --------------- | ----- |
| `typer`              | MIT             | CLI framework |
| `fastapi`            | MIT             | Local web UI server |
| `starlette`          | BSD-3-Clause    | FastAPI's ASGI toolkit |
| `uvicorn`            | BSD-3-Clause    | ASGI server |
| `pydantic`           | MIT             | Request validation for the web UI |
| `pillow`             | MIT-CMU (HPND)  | Used only for fixture generation and WebP/pixel decoding in tests; GhostMark's own metadata stripping does not depend on Pillow re-encoding |
| `python-multipart`   | Apache-2.0      | File upload parsing in the web UI |
| `pikepdf`            | **MPL-2.0**     | PDF object-graph editing (see below) |

Development-only dependencies (`pytest`, `pytest-cov`, `httpx`, `ruff`) are
not distributed with GhostMark and do not affect end users.

## About `pikepdf` (MPL-2.0)

`pikepdf` is licensed under the Mozilla Public License 2.0, a **file-level**
weak-copyleft license. Used as an unmodified external dependency (as
GhostMark does -- it is installed from PyPI, not vendored or modified),
MPL-2.0 does not require GhostMark's own source to be relicensed or
disclosed; it only applies to modifications made to pikepdf's own files.
This is standard, well-understood practice and does not change GhostMark's
MIT licensing for its own code.

If this ever becomes a concern for a downstream user, `pikepdf`'s PDF
functionality is isolated to `src/ghostmark/cleaners/pdf.py` and
`inspect_pdf_metadata` in `src/ghostmark/detectors/metadata.py`, so PDF
support could be made optional without touching the rest of GhostMark.
