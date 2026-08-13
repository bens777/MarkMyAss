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
| `markdown` (Python-Markdown) | BSD-3-Clause | Renders the `/run-local` developer guide from `src/ghostmark/web/content/run_local.md` |

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

## About c2patool (Apache-2.0 / MIT) -- external runtime dependency, never vendored

[c2patool](https://github.com/contentauth/c2pa-rs) is the official
Content Authenticity Initiative CLI for reading C2PA manifests, dual
licensed under Apache-2.0 and MIT (both permissive). GhostMark treats it
the same way it treats ExifTool -- as an **external, independently
installed runtime dependency**, never vendored:

- GhostMark's source tree and published Python package **never include
  c2patool's source or binary**. `pip install ghostmark` does not install
  it.
- `ghostmark/independent_verify.py`'s `C2paToolVerifier` only shells out
  to whatever `c2patool` executable it finds on `PATH` at runtime (via
  `shutil.which` + `subprocess.run` with a fixed argv, `shell=False`),
  read-only (it never writes or signs anything). If it's absent,
  GhostMark says so honestly (`c2patool_available: false`) and continues
  to work without it -- c2patool is never a hard requirement, and
  GhostMark never treats its absence, or a result it can't parse, as a
  false "no manifest" finding.
- In the production Docker image, c2patool is built from source (`cargo
  install c2patool`) in a throwaway Rust build stage; only the compiled
  binary is copied into the final image -- the Rust toolchain itself is
  not shipped. See `Dockerfile`. Anyone can rebuild the image without
  that stage and GhostMark still runs, just without this particular
  independent check.

Because both licenses are permissive and c2patool is used as a separate,
unmodified external binary (not linked into or distributed with
GhostMark's own code), this has no effect on GhostMark's MIT licensing.

## About ExifTool (GPL) -- external runtime dependency, never vendored

[ExifTool](https://exiftool.org/) is licensed under your choice of the
Perl "Artistic License" or the **GPL**. GhostMark treats it strictly as
an **external, independently-installed runtime dependency**:

- GhostMark's source tree (this repository) and its published Python
  package **never include ExifTool's source or binary** -- there is
  nothing to vendor, and `pip install ghostmark` does not install
  ExifTool.
- `ghostmark/independent_verify.py` only shells out to whatever
  `exiftool` executable it finds on `PATH` at runtime (via
  `shutil.which` + `subprocess.run` with a fixed argv, `shell=False`).
  If it's absent, GhostMark says so honestly (`exiftool_available:
  false`) and continues to work without it -- ExifTool is never a hard
  requirement.
- In the production Docker image, ExifTool is installed via the
  Debian/apt package `libimage-exiftool-perl` **during the image build**,
  as a separate, independently-licensed OS package -- see `Dockerfile`.
  Anyone can rebuild the image without that step and GhostMark still
  runs, just without independent verification.

This "shell out to a separately-installed binary" pattern is the
standard way to use a GPL tool from a permissively-licensed project
without GPL's copyleft extending to the calling program -- there is no
linking, no vendored/derived code, and no distribution of ExifTool
alongside GhostMark's own source. GhostMark's own code remains
100% MIT-licensed.
