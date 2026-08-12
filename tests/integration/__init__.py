"""Integration tests that exercise the REAL ExifTool binary (not mocked).

These are separated from the main unit test suite because they require
ExifTool to actually be installed. They skip cleanly when it isn't
(local dev machines), but CI runs a dedicated job -- "Independent
ExifTool Verification" -- that installs ExifTool and requires this suite
to pass; see .github/workflows/ci.yml.
"""
