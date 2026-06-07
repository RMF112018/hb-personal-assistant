#!/usr/bin/env bash
set -euo pipefail

# Prompt 23 thin wrapper for "one command" scripted smoke.
# Runs the Python harness (TestClient contract checks for all UI surfaces +
# frontend build + vitest) and exits non-zero on any failure.
# Evidence-friendly: full output goes to stdout/stderr.

cd "$(dirname "$0")/.."

echo "=== Prompt 23 scripted smoke (via scripts/smoke_local.py) ==="
python -m scripts.smoke_local

echo "=== scripted smoke complete ==="
