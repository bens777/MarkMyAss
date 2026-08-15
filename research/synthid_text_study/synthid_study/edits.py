"""Realistic edit-category transforms over token sequences.

Each category is modelled as a token-level perturbation characterised by
three parameters:

  * density      -- fraction of tokens altered
  * locality     -- "scattered" (spread out) or "contiguous" (one span)
  * replacement  -- where the new token comes from:
                      "reference" -> the aligned original human token
                                     (i.e. reverting toward the human draft)
                      "alt"       -> a different, un-watermarked vocab token
                                     (i.e. an AI editor's substitution)

IMPORTANT modelling note (also in README.md): the SynthID-Text statistic does
NOT depend on the *linguistic* nature of an edit (whether it "fixes spelling"
or "rewrites a sentence"). It depends only on how many scored positions are
altered and how the context window is disturbed. These categories therefore
differ by (density, locality, replacement source) -- NOT by performing real
linguistic edits. Treat the category labels as shorthand for perturbation
profiles, and read results accordingly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class EditSpec:
    density: float
    locality: str  # "scattered" | "contiguous"
    replacement: str  # "reference" | "alt"


# Ordered from lightest to heaviest perturbation. `restoration` is the special
# case: full revert to the original human tokens.
CATEGORIES: dict[str, EditSpec] = {
    "spelling": EditSpec(0.03, "scattered", "alt"),
    "grammar": EditSpec(0.06, "scattered", "alt"),
    "punctuation": EditSpec(0.04, "scattered", "alt"),
    "light_copyedit": EditSpec(0.10, "scattered", "alt"),
    "word_substitution": EditSpec(0.15, "scattered", "alt"),
    "sentence_rewrite": EditSpec(0.20, "contiguous", "alt"),
    "paragraph_rewrite": EditSpec(0.50, "contiguous", "alt"),
    "restoration": EditSpec(1.00, "contiguous", "reference"),
}


@dataclass
class EditResult:
    token_ids: list[int]
    n_changed: int
    changed_positions: list[int]


def _alt_token(original: int, vocab_size: int, rng: random.Random) -> int:
    """Pick an un-watermarked replacement token id different from `original`."""
    if vocab_size <= 1:
        return original
    tok = rng.randrange(vocab_size)
    if tok == original:
        tok = (tok + 1) % vocab_size
    return tok


def apply_edit(
    watermarked_ids: list[int],
    reference_ids: list[int],
    category: str,
    vocab_size: int,
    seed: int = 0,
) -> EditResult:
    """Apply an edit-category perturbation to a watermarked token sequence.

    `reference_ids` (same length) supplies the original human tokens used by
    the "reference" replacement source.
    """
    if category not in CATEGORIES:
        raise ValueError(f"unknown edit category: {category!r}")
    if len(watermarked_ids) != len(reference_ids):
        raise ValueError("watermarked and reference sequences must be equal length")

    spec = CATEGORIES[category]
    n = len(watermarked_ids)
    rng = random.Random(seed)
    k = round(spec.density * n)
    k = max(0, min(k, n))

    if spec.locality == "contiguous":
        start = 0 if k >= n else rng.randrange(0, n - k + 1)
        positions = list(range(start, start + k))
    elif spec.locality == "scattered":
        positions = sorted(rng.sample(range(n), k)) if k else []
    else:  # pragma: no cover - guarded by EditSpec construction
        raise ValueError(f"unknown locality: {spec.locality!r}")

    out = list(watermarked_ids)
    changed: list[int] = []
    for i in positions:
        if spec.replacement == "reference":
            new = reference_ids[i]
        else:  # "alt"
            new = _alt_token(watermarked_ids[i], vocab_size, rng)
        if new != out[i]:
            out[i] = new
            changed.append(i)
    return EditResult(token_ids=out, n_changed=len(changed), changed_positions=changed)
