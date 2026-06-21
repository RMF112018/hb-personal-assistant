#!/usr/bin/env bash
# Create the isolated Python 3.12 model-engine runtime venv (statsforecast stack).
# This venv is machine-local and NOT committed. The 3.14 core never imports statsforecast;
# it calls runner.py through this interpreter via a subprocess boundary.
#
# Usage:
#   bash model_engine_runtime/setup_venv.sh
# Then export the printed path:
#   export CFR_MODEL_ENGINE_PYTHON=<printed path>
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYBIN="${CFR_MODEL_ENGINE_PYTHON_BASE:-python3.12}"
HOME_DIR="${CFR_MODEL_ENGINE_HOME:-$HOME/Library/Application Support/HB Model Engine}"
VENV_DIR="$HOME_DIR/.venv-3.12"

if ! command -v "$PYBIN" >/dev/null 2>&1; then
  echo "ERROR: $PYBIN not found. Install Python 3.12 (e.g. 'brew install python@3.12')." >&2
  exit 2
fi

mkdir -p "$HOME_DIR"
"$PYBIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/python" -m pip install -r "$HERE/requirements.txt"

# Smoke check: the runner imports cleanly in the isolated interpreter.
"$VENV_DIR/bin/python" -c "import statsforecast, scipy, numba, pandas; print('statsforecast', statsforecast.__version__)"

echo ""
echo "Model-engine runtime ready. Export this to enable it:"
echo "  export CFR_MODEL_ENGINE_PYTHON=\"$VENV_DIR/bin/python\""
