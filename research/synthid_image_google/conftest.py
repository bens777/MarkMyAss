"""Make the `synthid_image` package importable when running tests."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
