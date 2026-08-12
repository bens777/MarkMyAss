#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

fail() {
    echo ""
    echo "$1" >&2
    echo ""
    exit 1
}

PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    fail "Python 3.11+ is required but was not found. Install it from https://www.python.org/downloads/ (or your OS package manager) and run this script again."
fi

if ! "$PYTHON_BIN" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
    fail "GhostMark needs Python 3.11 or newer. Install it and run this script again."
fi

if [ ! -d ".venv" ]; then
    echo "Setting up GhostMark for the first time. This can take a minute..."
    "$PYTHON_BIN" -m venv .venv || fail "Could not create a Python virtual environment."
fi

./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -e . || fail "GhostMark could not install its dependencies. See the messages above for details."

echo ""
echo "Starting GhostMark at http://127.0.0.1:8765"
echo "Your files never leave this computer."
echo ""
exec ./.venv/bin/ghostmark ui
