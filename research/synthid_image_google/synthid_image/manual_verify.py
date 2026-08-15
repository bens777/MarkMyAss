"""Manually record EXTERNAL SynthID verification results (research only).

Because no public API currently verifies Gemini-generated SynthID (see
docs/google-synthid-research.md), external checks (e.g. pasting an image into the
Gemini app and reading its answer) are done by hand. This module stores those
manual results as append-only research data.

IMPORTANT: this is research bookkeeping ONLY. Production MarkMyAss must never
depend on Gemini/external verification, and nothing here selects or optimises a
transform based on an external "detected / not detected" answer.
"""

from __future__ import annotations

import json
import pathlib
import time
from dataclasses import asdict, dataclass, field


@dataclass
class ManualExternalRecord:
    source_image: str          # filename / id of the image checked
    transform_profile: str     # "none" | "light" | "medium" | "strong" | free text
    external_verifier: str     # e.g. "gemini-app"
    result_text: str           # verbatim answer from the external verifier
    timestamp: str = ""        # ISO-ish; auto-filled if empty
    manual: bool = True        # always true -- a human performed this check
    notes: str = ""
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")


def records_path(results_dir: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(results_dir) / "manual_external.jsonl"


def append_record(results_dir: pathlib.Path, record: ManualExternalRecord) -> pathlib.Path:
    results_dir = pathlib.Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    path = records_path(results_dir)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(record)) + "\n")
    return path


def load_records(results_dir: pathlib.Path) -> list[dict]:
    path = records_path(results_dir)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out
