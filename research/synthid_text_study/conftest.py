"""Make the `synthid_study` package importable when running tests from anywhere."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
