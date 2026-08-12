"""PDF metadata cleaning: strip DocInfo + XMP, preserve pages/text/fonts/links.

pikepdf edits the PDF object graph directly (it does not rasterize or
re-render pages), so page content, fonts, images and links are byte-for-byte
untouched other than the metadata objects themselves.
"""

from __future__ import annotations

from pathlib import Path

import pikepdf

from ghostmark.models import CleanAction


def clean_pdf_file(path: Path, output_path: Path) -> list[CleanAction]:
    actions: list[CleanAction] = []
    with pikepdf.open(str(path)) as pdf:
        docinfo = pdf.docinfo
        had_info = docinfo is not None and len(docinfo.keys()) > 0
        if had_info:
            del pdf.trailer["/Info"]
        actions.append(
            CleanAction(
                "pdf_info",
                "Document metadata",
                True,
                had_info,
                not had_info,
                False,
                "Removed." if had_info else "Not present.",
            )
        )

        had_xmp = "/Metadata" in pdf.Root
        if had_xmp:
            del pdf.Root["/Metadata"]
        actions.append(
            CleanAction(
                "pdf_xmp",
                "XMP metadata",
                True,
                had_xmp,
                not had_xmp,
                False,
                "Removed." if had_xmp else "Not present.",
            )
        )

        pdf.save(str(output_path))

    # Reopen and verify the produced file is structurally readable before
    # we hand it back to the caller.
    verify_pdf_readable(output_path)
    return actions


def verify_pdf_readable(path: Path) -> int:
    """Reopen the PDF and confirm it parses and its pages are enumerable.

    Returns the page count. Raises ``pikepdf.PdfError`` (or similar) if the
    file is not structurally valid -- callers should treat that as a clean
    failure, not silently ship a broken file.
    """

    with pikepdf.open(str(path)) as pdf:
        return len(pdf.pages)
