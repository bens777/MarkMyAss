"""Text cleaning: remove/normalize the Unicode signals detectors flagged.

Only ``safe_to_remove`` and ``safe_to_normalize`` characters are ever
touched automatically. ``potentially_semantic`` characters (bidi marks,
ZWJ/ZWNJ, NBSP) are always preserved unless the caller explicitly opts in
via ``remove_semantic=True`` -- GhostMark must never silently destroy text
that could carry meaning in Arabic, Persian, Hebrew, Indic scripts, or
emoji sequences.
"""

from __future__ import annotations

from dataclasses import dataclass

from ghostmark.detectors.unicode import (
    SAFE_NORMALIZE,
    SAFE_REMOVE,
    SEMANTIC,
    scan_text,
)
from ghostmark.models import CleanAction


@dataclass
class TextCleanResult:
    cleaned: str
    action: CleanAction
    stats: dict[str, int]


def clean_text(text: str, *, remove_semantic: bool = False) -> TextCleanResult:
    """Remove safe-to-remove characters and normalize safe-to-normalize ones.

    Returns the cleaned text plus a :class:`CleanAction` describing what was
    done, suitable for inclusion in a :class:`~ghostmark.models.CleanResult`.
    """

    hits = scan_text(text)
    if not hits:
        action = CleanAction(
            detector="unicode",
            label="Hidden Unicode",
            attempted=True,
            removed=False,
            preserved=True,
            failed=False,
            note="No suspicious Unicode characters found.",
        )
        return TextCleanResult(
            cleaned=text,
            action=action,
            stats={"total_characters": len(text), "suspicious_characters": 0, "removed": 0, "normalized": 0},
        )

    removed = 0
    normalized = 0
    preserved_semantic = 0
    out_chars: list[str] = []

    for i, ch in enumerate(text):
        hit = next((h for h in hits if h.position == i), None)
        if hit is None:
            out_chars.append(ch)
            continue
        if hit.classification is SAFE_REMOVE:
            removed += 1
            continue
        if hit.classification is SAFE_NORMALIZE:
            out_chars.append(" ")
            normalized += 1
            continue
        if hit.classification is SEMANTIC:
            if remove_semantic:
                removed += 1
                continue
            preserved_semantic += 1
            out_chars.append(ch)
            continue
        # INFO: always preserved
        out_chars.append(ch)

    cleaned = "".join(out_chars)
    actionable = removed + normalized

    note = f"Removed {removed} character(s), normalized {normalized} character(s)."
    if preserved_semantic and not remove_semantic:
        note += f" Preserved {preserved_semantic} potentially-semantic character(s) (bidi marks, ZWJ/ZWNJ, NBSP)."

    action = CleanAction(
        detector="unicode",
        label="Hidden Unicode",
        attempted=True,
        removed=actionable > 0,
        preserved=preserved_semantic > 0 or actionable == 0,
        failed=False,
        note=note,
    )

    stats = {
        "total_characters": len(text),
        "suspicious_characters": len(hits),
        "removed": removed,
        "normalized": normalized,
        "preserved_semantic": preserved_semantic,
    }

    return TextCleanResult(cleaned=cleaned, action=action, stats=stats)
