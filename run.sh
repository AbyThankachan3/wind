#!/usr/bin/env bash
# ============================================================
#  Wind pipeline launcher (macOS / Linux / Git Bash on Windows)
#  Same purpose as run.bat. Sets everything up on first run.
#
#  Usage:  ./run.sh            (from a terminal, in this folder)
#  If you get "permission denied", run:  chmod +x run.sh   first.
# ============================================================
set -euo pipefail

# Move to the folder this script lives in, so relative paths work.
cd "$(dirname "$0")"

echo
echo "=== Wind pipeline ==="
echo

# ---- 1. Find a Python 3 interpreter ----
if command -v python3 >/dev/null 2>&1; then
    PYBOOT="python3"
elif command -v python >/dev/null 2>&1; then
    PYBOOT="python"
else
    echo "[ERROR] Python is not installed or not on PATH."
    echo "Install Python 3.10 or newer from https://www.python.org/downloads/"
    echo "(on macOS you can also use: brew install python)"
    exit 1
fi

# ---- 2. Create a local virtual environment on first run ----
# The venv puts its python in .venv/bin (Unix) or .venv/Scripts (Git Bash).
if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
    PY=".venv/Scripts/python.exe"
else
    echo "Creating a local Python environment (.venv)..."
    "$PYBOOT" -m venv .venv
    if [ -x ".venv/bin/python" ]; then
        PY=".venv/bin/python"
    else
        PY=".venv/Scripts/python.exe"
    fi
fi

# ---- 3. Install / update dependencies ----
echo "Installing dependencies (first run can take several minutes)..."
"$PY" -m pip install --upgrade pip >/dev/null
if ! "$PY" -m pip install -r requirements.txt; then
    echo
    echo "[ERROR] Some dependencies failed to install. See the messages above."
    exit 1
fi

# ---- 4. Run the pipeline ----
echo
"$PY" run_all.py "$@"
