"""Single source of truth for the AI Watermark Lab's capability matrix.

This is Python data, not prose someone edited once and forgot -- the
``/lab`` page, the individual signal pages' status lines, and the
``/api/lab/status`` JSON endpoint are ALL generated from this list, so
they can never drift out of sync with each other. When GhostMark's actual
capability for a signal changes, update it here and every surface that
reports it updates together.

USE ACTUAL CAPABILITIES. Never mark something "Yes" that GhostMark cannot
actually do -- see CONTRIBUTING.md for how to propose a correction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LAST_REVIEWED = "2026-08-13"


@dataclass(frozen=True)
class LabSignal:
    key: str
    label: str
    detect: str
    remove: str
    independent_verification: str
    status: str  # "Verified" | "Partial" | "Unknown"
    last_tested: str
    page: str | None = None  # slug under /lab/<page>, or None if no dedicated page yet

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "detect": self.detect,
            "remove": self.remove,
            "independent_verification": self.independent_verification,
            "status": self.status,
            "last_tested": self.last_tested,
            "page": f"/lab/{self.page}" if self.page else None,
        }

    @property
    def relative_link(self) -> str:
        """Link target relative to the site root (matches the <base href> every
        page shares) -- NOT relative to whatever page happens to render it."""

        return f"lab/{self.page}" if self.page else ""


LAB_SIGNALS: list[LabSignal] = [
    LabSignal(
        key="hidden_unicode",
        label="Hidden Unicode",
        detect="Yes",
        remove="Yes",
        independent_verification="Deterministic (re-inspection with the same open-source detector)",
        status="Verified",
        last_tested=LAST_REVIEWED,
        page="hidden-unicode",
    ),
    LabSignal(
        key="pdf_metadata",
        label="PDF metadata (DocInfo + XMP)",
        detect="Yes",
        remove="Yes",
        independent_verification="ExifTool",
        status="Verified",
        last_tested=LAST_REVIEWED,
        page="pdf-metadata",
    ),
    LabSignal(
        key="exif",
        label="EXIF (JPEG/PNG/WebP)",
        detect="Yes",
        remove="Yes",
        independent_verification="ExifTool",
        status="Verified",
        last_tested=LAST_REVIEWED,
    ),
    LabSignal(
        key="xmp",
        label="XMP (JPEG/PNG/WebP)",
        detect="Yes",
        remove="Yes",
        independent_verification="ExifTool",
        status="Verified",
        last_tested=LAST_REVIEWED,
    ),
    LabSignal(
        key="iptc",
        label="IPTC (JPEG)",
        detect="Yes",
        remove="Yes",
        independent_verification="ExifTool",
        status="Verified",
        last_tested=LAST_REVIEWED,
    ),
    LabSignal(
        key="c2pa",
        label="C2PA / Content Credentials",
        detect="Partial",
        remove="Partial",
        independent_verification="c2patool, where installed and the file format is supported",
        status="Partial",
        last_tested=LAST_REVIEWED,
        page="c2pa",
    ),
    LabSignal(
        key="claude_statistical_watermark",
        label="Claude statistical text watermark",
        detect="Unknown",
        remove="Unknown",
        independent_verification="No public verifier exists",
        status="Unknown",
        last_tested=LAST_REVIEWED,
        page="claude-watermark",
    ),
    LabSignal(
        key="gemini_statistical_watermark",
        label="Gemini statistical text watermark",
        detect="Unknown",
        remove="Unknown",
        independent_verification="No public verifier exists; provider-dependent by design",
        status="Unknown",
        last_tested=LAST_REVIEWED,
    ),
    LabSignal(
        key="gpt_statistical_watermark",
        label="GPT statistical text watermark",
        detect="Unknown",
        remove="Unknown",
        independent_verification="No public verifier exists",
        status="Unknown",
        last_tested=LAST_REVIEWED,
    ),
    LabSignal(
        key="visible_image_watermark",
        label="Visible image watermark (logo/text baked into pixels)",
        detect="No",
        remove="No",
        independent_verification="Not applicable -- not implemented",
        status="Unknown",
        last_tested=LAST_REVIEWED,
    ),
]


def signal_by_key(key: str) -> LabSignal | None:
    return next((s for s in LAB_SIGNALS if s.key == key), None)


def to_markdown_table() -> str:
    header = "| Provider / Signal | Detect | Remove | Independent verification | Status | Last tested |"
    sep = "| --- | --- | --- | --- | --- | --- |"
    rows = []
    for s in LAB_SIGNALS:
        label = f"[{s.label}]({s.relative_link})" if s.page else s.label
        rows.append(f"| {label} | {s.detect} | {s.remove} | {s.independent_verification} | {s.status} | {s.last_tested} |")
    return "\n".join([header, sep, *rows])


def to_status_line(key: str) -> str:
    s = signal_by_key(key)
    if s is None:
        return ""
    return f"**Current status: {s.status}** &middot; Detect: {s.detect} &middot; Remove: {s.remove} &middot; Last tested: {s.last_tested}"
