# Runs the same checks CI runs: lint + tests.
$ErrorActionPreference = "Stop"
Set-Location -Path (Join-Path $PSScriptRoot "..")
python -m ruff check .
python -m pytest -q
