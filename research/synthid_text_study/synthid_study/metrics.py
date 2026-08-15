"""Pure-python text/token metrics.

No third-party dependencies, so these run even when the ML stack
(torch/transformers) is unavailable. All functions operate on plain
sequences (token-id lists or strings) and return plain floats/ints.
"""

from __future__ import annotations

from collections.abc import Sequence


def token_edit_distance(a: Sequence, b: Sequence) -> int:
    """Levenshtein edit distance between two token sequences."""
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ai = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ai == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]


def lcs_length(a: Sequence, b: Sequence) -> int:
    """Length of the longest common subsequence of two sequences."""
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0
    prev = [0] * (lb + 1)
    for i in range(1, la + 1):
        cur = [0] * (lb + 1)
        ai = a[i - 1]
        for j in range(1, lb + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = prev[j] if prev[j] >= cur[j - 1] else cur[j - 1]
        prev = cur
    return prev[lb]


def retained_fraction(reference: Sequence, candidate: Sequence) -> float:
    """Fraction of `reference` tokens preserved in `candidate` (LCS / len(ref)).

    Read as "how much of the original human wording survives in the output".
    """
    if len(reference) == 0:
        return 0.0
    return lcs_length(reference, candidate) / len(reference)


def token_jaccard(a: Sequence, b: Sequence) -> float:
    """Jaccard similarity of the token *sets* of two sequences."""
    sa, sb = set(a), set(b)
    union = sa | sb
    if not union:
        return 1.0
    return len(sa & sb) / len(union)


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length numeric vectors."""
    if len(a) != len(b):
        raise ValueError("vectors must have equal length")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
