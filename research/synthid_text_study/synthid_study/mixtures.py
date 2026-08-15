"""Construct controlled watermarked/original token mixtures.

Given a fully watermarked token sequence and an aligned un-watermarked
("human original") reference of the same length, build a sequence that
retains a chosen fraction of watermarked tokens and takes the rest from the
reference. This isolates the core relationship under study:

    fraction of watermarked tokens retained  ->  detector score

Three geometries are provided because the SynthID-Text g-value at each
position depends on a sliding window of *preceding* tokens. Replacing tokens
therefore has a "blast radius": it disturbs not only the replaced position
but the scored positions whose context window overlaps it. Contiguous vs
scattered replacement expose that effect.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

GEOMETRIES = ("keep_prefix", "keep_suffix", "scattered")


@dataclass
class Mixture:
    """A spliced sequence plus a mask marking original-watermarked positions."""

    token_ids: list[int]
    watermarked_mask: list[bool]  # True where the token is original-watermarked

    @property
    def retained_fraction(self) -> float:
        if not self.watermarked_mask:
            return 0.0
        return sum(self.watermarked_mask) / len(self.watermarked_mask)

    @property
    def n_watermarked(self) -> int:
        return sum(self.watermarked_mask)


def make_mixture(
    watermarked_ids: list[int],
    reference_ids: list[int],
    retained_fraction: float,
    geometry: str = "keep_prefix",
    seed: int = 0,
) -> Mixture:
    """Retain `retained_fraction` of watermarked tokens; fill the rest from reference.

    * keep_prefix  -- the leading run stays watermarked (edits at the tail)
    * keep_suffix  -- the trailing run stays watermarked (edits at the head)
    * scattered    -- watermarked positions are chosen at random (seeded)
    """
    if len(watermarked_ids) != len(reference_ids):
        raise ValueError("watermarked and reference sequences must be equal length")
    if not 0.0 <= retained_fraction <= 1.0:
        raise ValueError("retained_fraction must be in [0, 1]")
    if geometry not in GEOMETRIES:
        raise ValueError(f"unknown geometry: {geometry!r} (expected one of {GEOMETRIES})")

    n = len(watermarked_ids)
    keep = round(retained_fraction * n)

    if geometry == "keep_prefix":
        keep_positions = set(range(keep))
    elif geometry == "keep_suffix":
        keep_positions = set(range(n - keep, n))
    else:  # scattered
        rng = random.Random(seed)
        keep_positions = set(rng.sample(range(n), keep)) if keep else set()

    ids: list[int] = []
    mask: list[bool] = []
    for i in range(n):
        if i in keep_positions:
            ids.append(watermarked_ids[i])
            mask.append(True)
        else:
            ids.append(reference_ids[i])
            mask.append(False)
    return Mixture(token_ids=ids, watermarked_mask=mask)
