"""Example: using GhostMark as a library instead of the CLI/web UI.

Run with: python examples/basic_usage.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ghostmark.cleaner import clean_text_content
from ghostmark.inspector import inspect_text
from ghostmark.verifier import verify_text

ZERO_WIDTH_SPACE = chr(0x200B)


def main() -> None:
    original = f"This text{ZERO_WIDTH_SPACE}has a hidden character in it."

    report = inspect_text(original)
    print("Inspection:")
    for detection in report.detections:
        print(f"  {detection.label}: {detection.status.value}")

    cleaned, _clean_result = clean_text_content(original)
    print(f"\nCleaned text: {cleaned!r}")

    verify_result = verify_text(original, cleaned)
    print(f"\n{verify_result.summary()}")

    # The same functions work on files -- clean_file()/inspect_file() write
    # a NAME.ghostmark.EXT copy and never touch the original.
    with tempfile.TemporaryDirectory() as tmp:
        sample = Path(tmp) / "sample.txt"
        sample.write_text(original, encoding="utf-8")
        print(f"\n(See ghostmark.cleaner.clean_file for the file-based equivalent, e.g. on {sample})")


if __name__ == "__main__":
    main()
