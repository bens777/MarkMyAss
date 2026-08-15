"""Inverse SynthID-Text study: AI-assisted human text (isolated R&D).

Study 1 measured: 100% watermarked text -> progressively restored to original.
This study measures the INVERSE: genuinely human, public-domain prose ->
progressively contaminated with SynthID-watermarked AI-generated spans, to
characterise how detectability grows with AI-generated fraction and geometry.

It REUSES (does not modify) Study 1's validated components: the SynthID-Text
Engine, the Weighted-Mean detector, the metrics, and the threshold-calibration
methodology. To import them, Study 1's package root is added to sys.path here.

This is contamination/detectability characterisation, NOT detector-evasion
optimisation. It uses OUR OWN local key and says nothing about Google's
production secret key.
"""

import pathlib
import sys

# Reuse Study 1 (research/synthid_text_study) without copying its code.
_STUDY1 = pathlib.Path(__file__).resolve().parents[2] / "synthid_text_study"
if _STUDY1.is_dir() and str(_STUDY1) not in sys.path:
    sys.path.insert(0, str(_STUDY1))

__all__ = ["corpus", "contaminate", "experiment", "report"]
