"""Replication / robustness study for Study 2 (isolated R&D).

Tests whether the ~20-30% "mostly-undetected -> commonly-detected" transition
observed in Study 2 is robust across independent local keys, generation seeds,
and document lengths, or an artifact of one configuration.

Reuses (does not modify) Study 1's SynthID Engine/detector/metrics and Study 2's
contamination framework. Both prior studies are left untouched. Detector
methodology is unchanged (tuning-free Weighted-Mean, per-key 1% FPR threshold) —
deliberately NOT tuned to improve results.

Uses OUR OWN local keys; says nothing about Google's production secret key.
"""

import pathlib
import sys

_RESEARCH = pathlib.Path(__file__).resolve().parents[2]
for _pkg in ("synthid_text_study", "synthid_text_inverse_study"):
    _p = _RESEARCH / _pkg
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

__all__ = ["corpus_lengths", "experiment", "report"]
