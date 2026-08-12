#!/usr/bin/env bash
# Runs the same checks CI runs: lint + tests.
set -e
cd "$(dirname "$0")/.."
python -m ruff check .
python -m pytest -q
