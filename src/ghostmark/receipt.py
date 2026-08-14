"""Verification Receipt: proof, not promises.

A structured, downloadable record of exactly what GhostMark found in a
file, what it removed, what an independent tool confirmed, and what it
could not verify at all. This is GhostMark's core differentiator -- it
never claims more than what was actually tested, and the receipt is the
artifact a user can keep, share, or re-check later.

Deliberately NOT called a "certificate of authorship" or similar -- it
proves only what GhostMark (and whichever independent verifiers were
available) actually tested, nothing about who created the content.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from typing import Any

from ghostmark import __version__
from ghostmark.models import Status, VerifyResult

_STATUS_WORD = {Status.FOUND: "FOUND", Status.NOT_FOUND: "NOT FOUND", Status.UNKNOWN: "N/A"}

# Human wording for the headline verdict -- kept in lockstep with the web
# UI's VERDICT_TEXT map (app.js): the strongest claim is only ever made
# when an independent tool corroborated, and a native-only pass says so.
_VERDICT_WORDS = {
    "verified_clean": "INDEPENDENTLY VERIFIED CLEAN",
    "partial": "PARTIAL — VERIFIER DISAGREEMENT",
    "unverified": "NATIVE CLEAN — NOT INDEPENDENTLY VERIFIED",
    "not_applicable": "NOT APPLICABLE",
    "failed": "FAILED",
}


def _detection_fields(detections) -> list[tuple[str, dict]]:
    """(detector label, field dict) pairs for every native tag-level field."""

    out: list[tuple[str, dict]] = []
    for d in detections:
        for f in d.details.get("fields", []):
            out.append((d.label, f))
    return out

STATISTICAL_WATERMARK_LABELS = (
    "Claude statistical watermark",
    "Gemini statistical watermark",
    "GPT statistical watermark",
)


@dataclass
class VerificationReceipt:
    file_name: str
    before_hash: str
    after_hash: str
    verify_result: VerifyResult
    ghostmark_version: str
    generated_at: str  # ISO-8601 UTC, second precision

    # --- JSON -------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        vr = self.verify_result.to_dict()
        summary = vr["verification_summary"]
        return {
            "ghostmark_verification_receipt": True,
            "receipt_version": 1,
            "file": self.file_name,
            "ghostmark_version": self.ghostmark_version,
            "generated_at": self.generated_at,
            "sha256_original": self.before_hash,
            "sha256_cleaned": self.after_hash,
            "before": vr["before"]["detections"],
            "after": vr["after"]["detections"],
            "resolved": vr["resolved"],
            "remaining": vr["remaining"],
            "unknown": vr["unknown"],
            "independent_verification": summary["external_verifiers"] if summary else [],
            "supported_signals_removed": {
                "resolved": len(vr["resolved"]),
                "total_found": self.verify_result.supported_found_before,
            },
            "verdict": summary["verdict"] if summary else None,
            "verdict_label": _VERDICT_WORDS.get(summary["verdict"], "") if summary else None,
            "c2pa_status": summary["c2pa_status"] if summary else "not_applicable",
            "statistical_watermark_status": dict.fromkeys(STATISTICAL_WATERMARK_LABELS, "unverified"),
            "summary": vr["summary"],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    # --- Plain text --------------------------------------------------------------------

    def to_text(self) -> str:
        lines: list[str] = []
        add = lines.append

        add("GHOSTMARK VERIFICATION RECEIPT")
        add("")
        add("File:")
        add(self.file_name)
        add("")
        add("BEFORE")
        for d in self.verify_result.before.detections:
            add(f"{d.label:<26} {_STATUS_WORD[d.status]}")
        before_fields = _detection_fields(self.verify_result.before.detections)
        if before_fields:
            add("")
            add("DETECTED METADATA FIELDS (BEFORE CLEANING)")
            for _label, f in before_fields:
                add(f"  [{f['category']}] {f['container']} {f['tag']}: {f['preview']}")
        add("")
        add("AFTER")
        for d in self.verify_result.after.detections:
            add(f"{d.label:<26} {_STATUS_WORD[d.status]}")
        add("")
        add("INDEPENDENT VERIFICATION")
        summary = self.verify_result.summary_v2
        if summary is not None:
            add(f"{'GhostMark':<26} {'PASS' if summary.ghostmark_pass else 'FAIL'}")
            for v in summary.external_verifiers:
                label = f"{v.label} {v.version}" if v.version else v.label
                word = "N/A" if v.passed is None else ("PASS" if v.passed else "FAIL")
                add(f"{label:<26} {word}")
        add("")
        add("SUPPORTED SIGNALS REMOVED")
        add(f"{len(self.verify_result.resolved)} / {self.verify_result.supported_found_before}")
        add("")
        add("UNVERIFIED")
        for label in STATISTICAL_WATERMARK_LABELS:
            add(label)
        add("")
        add("SHA-256 original:")
        add(self.before_hash)
        add("")
        add("SHA-256 cleaned:")
        add(self.after_hash)
        add("")
        add("GhostMark version:")
        add(self.ghostmark_version)
        add("")
        add("Verification timestamp:")
        add(self.generated_at)
        add("")
        if summary is not None:
            word = _VERDICT_WORDS.get(summary.verdict.value,
                                      summary.verdict.value.replace("_", " ").upper())
            add(f"Overall verdict: {word}")

        return "\n".join(lines) + "\n"

    # --- HTML (self-contained, safe to open outside GhostMark) -------------------------

    def to_html(self) -> str:
        summary = self.verify_result.summary_v2

        def status_row(label: str, status: Status) -> str:
            word = _STATUS_WORD[status]
            cls = {"FOUND": "found", "NOT FOUND": "clean", "N/A": "na"}[word]
            return f'<tr><td>{escape(label)}</td><td class="{cls}">{word}</td></tr>'

        before_rows = "\n".join(status_row(d.label, d.status) for d in self.verify_result.before.detections)
        after_rows = "\n".join(status_row(d.label, d.status) for d in self.verify_result.after.detections)

        before_fields = _detection_fields(self.verify_result.before.detections)
        fields_section = ""
        if before_fields:
            field_rows = "\n".join(
                f'<tr><td>{escape(f["container"])} · {escape(f["tag"])}'
                f' <span class="na">[{escape(f["category"])}]</span></td>'
                f"<td>{escape(f['preview'])}</td></tr>"
                for _label, f in before_fields
            )
            fields_section = (
                "<h2>Detected metadata fields (before cleaning)</h2>"
                f"<table>{field_rows}</table>"
            )

        verifier_rows = ""
        verdict_word = "UNVERIFIED"
        verdict_class = "na"
        if summary is not None:
            ghostmark_word = "PASS" if summary.ghostmark_pass else "FAIL"
            rows = [f'<tr><td>GhostMark</td><td class="{"clean" if summary.ghostmark_pass else "found"}">{ghostmark_word}</td></tr>']
            for v in summary.external_verifiers:
                label = f"{escape(v.label)} {escape(v.version)}" if v.version else escape(v.label)
                if v.passed is None:
                    rows.append(f'<tr><td>{label}</td><td class="na">N/A</td></tr>')
                else:
                    word = "PASS" if v.passed else "FAIL"
                    rows.append(f'<tr><td>{label}</td><td class="{"clean" if v.passed else "found"}">{word}</td></tr>')
            verifier_rows = "\n".join(rows)
            verdict_word = _VERDICT_WORDS.get(summary.verdict.value,
                                              summary.verdict.value.replace("_", " ").upper())
            verdict_class = {
                "verified_clean": "clean",
                "partial": "found",
                "unverified": "na",
                "not_applicable": "na",
                "failed": "found",
            }[summary.verdict.value]

        unverified_rows = "\n".join(f"<li>{escape(label)}</li>" for label in STATISTICAL_WATERMARK_LABELS)

        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>GhostMark Verification Receipt -- {escape(self.file_name)}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; color: #f5ecd8; background: #0b1d33; }}
  h1 {{ font-family: Georgia, "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif; font-size: 1.5rem; margin-bottom: 0.1rem; }}
  .subtitle {{ color: #dcac52; font-style: italic; margin: 0 0 1.25rem; font-size: 0.95rem; }}
  h2 {{ font-size: 1rem; text-transform: uppercase; letter-spacing: .04em; color: #aebcd1; margin-top: 2rem; border-top: 2px solid #dcac52; padding-top: .5rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: .5rem; }}
  td {{ padding: .4rem .6rem; border: 1px solid #2f5074; }}
  td.found {{ color: #f0ab5d; font-weight: 700; }}
  td.clean {{ color: #6fcf8e; font-weight: 700; }}
  td.na {{ color: #aebcd1; font-weight: 700; }}
  .verdict {{ display: inline-block; padding: .4rem 1rem; border-radius: 999px; font-weight: 800; margin-top: .5rem; }}
  .verdict.clean {{ background: rgba(111,207,142,.18); color: #6fcf8e; }}
  .verdict.found {{ background: rgba(240,171,93,.18); color: #f0ab5d; }}
  .verdict.na {{ background: rgba(174,188,209,.18); color: #aebcd1; }}
  code {{ background: #122a48; border: 1px solid #2f5074; padding: .1rem .3rem; border-radius: 4px; font-size: .85em; word-break: break-all; font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", monospace; }}
  footer {{ margin-top: 2rem; color: #aebcd1; font-size: .85rem; }}
  footer a {{ color: #e2664f; }}
</style>
</head>
<body>
<h1>👻 GhostMark Verification Receipt</h1>
<p class="subtitle">Captain's manifest</p>
<p><strong>File:</strong> {escape(self.file_name)}</p>

<h2>Before</h2>
<table>{before_rows}</table>
{fields_section}

<h2>After</h2>
<table>{after_rows}</table>

<h2>Independent verification</h2>
<table>{verifier_rows}</table>
<p class="verdict {verdict_class}">{escape(verdict_word)}</p>

<h2>Supported signals removed</h2>
<p>{len(self.verify_result.resolved)} / {self.verify_result.supported_found_before}</p>

<h2>Unverified (not currently provable by GhostMark or any public tool)</h2>
<ul>{unverified_rows}</ul>

<h2>Integrity</h2>
<p>SHA-256 original: <code>{escape(self.before_hash)}</code></p>
<p>SHA-256 cleaned: <code>{escape(self.after_hash)}</code></p>

<footer>
  GhostMark {escape(self.ghostmark_version)} &middot; generated {escape(self.generated_at)}<br>
  This receipt proves only what GhostMark and the independent tools listed above actually tested.
  It is not a certificate of authorship or a claim that no other signal could exist.
  <a href="https://github.com/bens777/MarkMyAss">github.com/bens777/MarkMyAss</a>
</footer>
</body>
</html>
"""


def build_receipt(*, file_name: str, before_hash: str, after_hash: str, verify_result: VerifyResult) -> VerificationReceipt:
    return VerificationReceipt(
        file_name=file_name,
        before_hash=before_hash,
        after_hash=after_hash,
        verify_result=verify_result,
        ghostmark_version=__version__,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
