"""Splice SynthID-watermarked AI spans into human token sequences.

The AI content is a genuine SynthID-watermarked generation (`a_ids`), produced
by Study 1's Engine conditioned on the human sample's opening. A contamination
condition selects a set of token positions and fills them from `a_ids` at the
SAME indices, so within a contiguous block each watermarked token keeps its
generation-time predecessor (preserving the watermark); only block boundaries
sit in human context (the same "blast radius" measured in Study 1).

Geometries: one contiguous block, several scattered blocks, whole sentences,
whole paragraphs. This mirrors Study 1's mixture construction in reverse, so
the two studies are directly comparable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Contaminated:
    token_ids: list[int]
    ai_mask: list[bool]  # True where the token is AI-generated/watermarked

    @property
    def n_ai(self) -> int:
        return sum(self.ai_mask)

    @property
    def ai_fraction(self) -> float:
        return self.n_ai / len(self.ai_mask) if self.ai_mask else 0.0


def _fill(h_ids: list[int], a_ids: list[int], positions: set[int]) -> Contaminated:
    ids = list(h_ids)
    mask = [False] * len(h_ids)
    for i in positions:
        ids[i] = a_ids[i]
        mask[i] = True
    return Contaminated(token_ids=ids, ai_mask=mask)


def contiguous_positions(n: int, length: int) -> set[int]:
    if length <= 0:
        return set()
    length = min(length, n)
    p0 = min(max(0, round(0.15 * n)), n - length)
    return set(range(p0, p0 + length))


def scattered_positions(n: int, length: int, k: int = 5) -> set[int]:
    if length <= 0:
        return set()
    length = min(length, n)
    k = min(k, length)
    block = length // k
    rem = length - block * k
    positions: set[int] = set()
    for j in range(k):
        blen = block + (1 if j < rem else 0)
        anchor = round(j * (n - blen) / max(1, k - 1)) if k > 1 else (n - blen) // 2
        anchor = min(max(0, anchor), n - blen)
        positions.update(range(anchor, anchor + blen))
    return positions


def unit_positions(unit_spans: list[tuple[int, int]], n: int, length: int) -> set[int]:
    """Take whole units (sentences/paragraphs) in order until >= length tokens."""
    if length <= 0:
        return set()
    positions: set[int] = set()
    for s, e in unit_spans:
        if len(positions) >= length:
            break
        positions.update(range(s, e))
    return {i for i in positions if i < n}


def contaminate(
    h_ids: list[int],
    a_ids: list[int],
    fraction: float,
    geometry: str,
    unit_spans: list[tuple[int, int]] | None = None,
    k_scatter: int = 5,
) -> Contaminated:
    n = len(h_ids)
    length = round(fraction * n)
    if geometry == "contiguous":
        pos = contiguous_positions(n, length)
    elif geometry == "scattered":
        pos = scattered_positions(n, length, k_scatter)
    elif geometry in ("sentence", "paragraph"):
        if unit_spans is None:
            raise ValueError(f"geometry {geometry!r} requires unit_spans")
        pos = unit_positions(unit_spans, n, length)
    else:
        raise ValueError(f"unknown geometry: {geometry!r}")
    return _fill(h_ids, a_ids, pos)


def append_ai(h_ids: list[int], b_ids: list[int], n_ai: int) -> Contaminated:
    """Append n_ai watermarked tokens after the human text (added paragraph/conclusion)."""
    add = b_ids[:n_ai]
    ids = list(h_ids) + list(add)
    mask = [False] * len(h_ids) + [True] * len(add)
    return Contaminated(token_ids=ids, ai_mask=mask)


def prepend_ai(h_ids: list[int], a_ids: list[int], n_ai: int) -> Contaminated:
    """Prepend n_ai watermarked tokens before the human text (AI intro)."""
    add = a_ids[:n_ai]
    ids = list(add) + list(h_ids)
    mask = [True] * len(add) + [False] * len(h_ids)
    return Contaminated(token_ids=ids, ai_mask=mask)


def wrap_ai(h_ids: list[int], a_ids: list[int], b_ids: list[int], intro: int, concl: int) -> Contaminated:
    """AI intro + human body + AI conclusion."""
    pre, post = a_ids[:intro], b_ids[:concl]
    ids = list(pre) + list(h_ids) + list(post)
    mask = [True] * len(pre) + [False] * len(h_ids) + [True] * len(post)
    return Contaminated(token_ids=ids, ai_mask=mask)
