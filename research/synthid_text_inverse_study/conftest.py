"""Make `inverse_study` (and, via its bootstrap, Study 1's `synthid_study`) importable."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
