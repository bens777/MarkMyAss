#!/usr/bin/env python3
"""Generate GhostMark's public, reproducible test corpus (src/ghostmark/corpus/).

Every fixture here is synthetic -- built entirely by
``ghostmark.fixtures.generate`` (the same generator used by
``ghostmark demo``), never copied from a real document or image. There is
no copyrighted or private content in this corpus.

The corpus lives inside the installed package (not under tests/) so it
ships with every install mode, including the production Docker image --
see ``ghostmark.corpus_data`` for why.

Run this to regenerate the corpus after a fixture generator changes:

    python scripts/generate_corpus.py

The output is deterministic given the same GhostMark version, so
regenerating should normally produce byte-identical files -- if it
doesn't, that's worth investigating before committing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from ghostmark.corpus_data import CORPUS_DIR  # noqa: E402
from ghostmark.fixtures.generate import (  # noqa: E402
    demo_text,
    make_jpeg_fixture,
    make_pdf_fixture,
    make_png_fixture,
)

MANIFEST: list[dict] = [
    {
        "path": "text/hidden-unicode.txt",
        "kind": "text",
        "description": (
            "Multilingual text containing a zero-width space, a word joiner, and Unicode "
            "'tag' steganography characters, alongside legitimate French/German/emoji/code content."
        ),
        "expected_before": ["unicode"],
        "expected_after": [],
    },
    {
        "path": "jpeg/exif-xmp-iptc-comment.jpg",
        "kind": "jpeg",
        "description": "JPEG with synthetic EXIF, XMP, IPTC (Photoshop IRB), and comment segments.",
        "expected_before": ["exif", "xmp", "iptc", "comment"],
        "expected_after": [],
    },
    {
        "path": "png/exif-xmp-text.png",
        "kind": "png",
        "description": "PNG with a synthetic eXIf chunk, an XMP iTXt chunk, and a plain tEXt comment chunk.",
        "expected_before": ["exif", "xmp", "png_text"],
        "expected_after": [],
    },
    {
        "path": "pdf/docinfo-xmp.pdf",
        "kind": "pdf",
        "description": "Single-page PDF with DocInfo (Title/Author/Producer) and XMP metadata.",
        "expected_before": ["pdf_info", "pdf_xmp"],
        "expected_after": [],
    },
]


def main() -> None:
    for entry in MANIFEST:
        target = CORPUS_DIR / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if entry["kind"] == "text":
            target.write_text(demo_text(), encoding="utf-8")
        elif entry["kind"] == "jpeg":
            make_jpeg_fixture(target)
        elif entry["kind"] == "png":
            make_png_fixture(target)
        elif entry["kind"] == "pdf":
            make_pdf_fixture(target)
        else:
            raise ValueError(f"Unknown fixture kind: {entry['kind']}")
        print(f"wrote {target.relative_to(REPO_ROOT)} ({target.stat().st_size} bytes)")

    manifest_path = CORPUS_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps({"ghostmark_corpus_version": 1, "fixtures": MANIFEST}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {manifest_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
