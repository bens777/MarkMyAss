"""Observational before/after provenance reporting for Reprocess.

This module answers one question and only that question: *did a supported,
observable provenance signal survive a reprocess?* It compares the LOCAL
inspection of the input against the LOCAL inspection of the reprocessed
output and pairs that with the pixel-similarity metrics.

CRITICAL BOUNDARY
-----------------
This is a read-only *observation*. It NEVER feeds its result back into
reprocessing, and there is deliberately no "transform -> test -> transform
again until undetected" loop anywhere in GhostMark. A detector's output is
never an optimisation objective. See the product boundary in the repo docs.

It also never claims a statistical/model-level watermark (e.g. SynthID) was
removed or survived -- those are not locally observable, and the report says
so explicitly rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ghostmark.models import Category, InspectionReport, Status
from ghostmark.reprocess import ReprocessResult

# Categories that reprocessing may incidentally affect and that GhostMark can
# actually observe locally. Statistical watermarks are intentionally excluded:
# they are not locally verifiable, so this report makes no claim about them.
_OBSERVABLE = (Category.METADATA, Category.PROVENANCE, Category.UNICODE)


@dataclass
class ProvenanceSnapshot:
    """The locally-observable provenance signals in one inspection."""

    c2pa_status: str  # "present" | "absent" | "unknown"
    metadata_signals: list[str] = field(default_factory=list)
    provenance_signals: list[str] = field(default_factory=list)
    other_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "c2pa_status": self.c2pa_status,
            "metadata_signals": self.metadata_signals,
            "provenance_signals": self.provenance_signals,
            "other_signals": self.other_signals,
        }


def _c2pa_status(report: InspectionReport) -> str:
    d = report.get("c2pa")
    if d is None:
        return "unknown"
    if d.status is Status.FOUND:
        return "present"
    if d.status is Status.NOT_FOUND:
        return "absent"
    return "unknown"


def snapshot(report: InspectionReport) -> ProvenanceSnapshot:
    metadata: list[str] = []
    provenance: list[str] = []
    other: list[str] = []
    for d in report.signals_found():
        if d.category is Category.METADATA:
            metadata.append(d.detector)
        elif d.category is Category.PROVENANCE:
            provenance.append(d.detector)
        elif d.category in _OBSERVABLE:
            other.append(d.detector)
    return ProvenanceSnapshot(
        c2pa_status=_c2pa_status(report),
        metadata_signals=sorted(metadata),
        provenance_signals=sorted(provenance),
        other_signals=sorted(other),
    )


def build_robustness_report(
    *,
    input_report: InspectionReport,
    output_report: InspectionReport,
    reprocess_result: ReprocessResult,
) -> dict[str, Any]:
    """Assemble the observational before/after report (see module docstring)."""

    before = snapshot(input_report)
    after = snapshot(output_report)
    m = reprocess_result.to_dict()["metrics"]

    return {
        "observational": True,
        "note": (
            "Read-only comparison of locally-observable provenance signals before and "
            "after reprocessing. Reprocess never retries based on any detector result, "
            "and this report makes no claim about statistical/model-level watermarks "
            "(e.g. SynthID), which are not locally verifiable."
        ),
        "input": before.to_dict(),
        "processing": {
            "profile": reprocess_result.profile,
            "output_format": reprocess_result.output_format,
            "normalize_colorspace": reprocess_result.normalize_colorspace,
            "operations": reprocess_result.operations,
        },
        "output": after.to_dict(),
        "image_similarity": {
            "ssim": m["ssim"],
            "psnr": m["psnr"],
            "pixel_changed_pct": m["pixel_changed_pct"],
            "input_dimensions": m["original_dimensions"],
            "output_dimensions": m["output_dimensions"],
            "input_size_bytes": m["original_size_bytes"],
            "output_size_bytes": m["output_size_bytes"],
            "output_format": reprocess_result.output_format,
        },
        "statistical_watermark": {
            "locally_verifiable": False,
            "note": "Not locally verifiable; no claim is made about removal or survival.",
        },
    }
