#!/usr/bin/env bash
# Source Index Phase D scalability/resilience gate.
#
# CI executes the deterministic reduced-scale rehearsal and explicit fault cases.
# The terminal 400k/1M run is retained as committed evidence and is intentionally
# not repeated on every hosted runner.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi
export PYTHONPATH="$ROOT/src:$ROOT/subrepos/construction-financial-review/src${PYTHONPATH:+:$PYTHONPATH}"

echo "[phase-d-gate] pytest — scalability/resilience rehearsal and fault cases"
"$PYTHON_BIN" -m pytest -p no:cacheprovider -q \
  tests/source_index/test_phase_d_scalability_resilience.py \
  tests/test_source_index_metadata_first_bootstrap.py \
  tests/test_source_index_search_latency_index.py

echo "[phase-d-gate] ruff — Phase D script and tests"
"$PYTHON_BIN" -m ruff check --no-force-exclude \
  scripts/source_index_phase_d_rehearsal.py \
  tests/source_index/test_phase_d_scalability_resilience.py

echo "[phase-d-gate] OK"
