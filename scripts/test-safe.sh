#!/usr/bin/env bash
# Canonical merge-safe repository test suite.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

usage() {
  cat <<'USAGE'
Usage: bash scripts/test-safe.sh [--collect-only] [--python-only] [--frontend-only]

Runs the complete repository-safe test gate without integration, manual, or live
pytest markers. No test paths, node IDs, marker overrides, or arbitrary pytest
arguments are accepted because those would no longer represent the canonical
merge-safe suite.

Interpreter contract:
- Set PYTHON to one executable name or path; or
- create the active worktree interpreter at .venv/bin/python.

The selected interpreter must be executable and Python 3.12 or newer. The script
fails closed rather than falling back to a generic or operator-specific Python.

Python gate prerequisites:
  python -m pip install -e '.[dev,mcp,analytics-ui]' \
    -e 'subrepos/construction-financial-review[dev]'
USAGE
}

collect_only=false
run_python=true
run_frontend=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --collect-only)
      collect_only=true
      ;;
    --python-only)
      run_frontend=false
      ;;
    --frontend-only)
      run_python=false
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unsupported argument for canonical safe suite: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ "$run_python" == false && "$run_frontend" == false ]]; then
  echo "ERROR: no suite component selected" >&2
  exit 2
fi

if [[ "$collect_only" == true && "$run_python" == false ]]; then
  echo "ERROR: --collect-only is a Python collection mode and cannot be combined with --frontend-only" >&2
  exit 2
fi

resolve_python() {
  local requested="${PYTHON:-}"
  local candidate=""

  if [[ -n "$requested" ]]; then
    if [[ "$requested" =~ [[:space:]] ]]; then
      echo "ERROR: PYTHON must name exactly one executable without arguments" >&2
      exit 3
    fi
    if [[ "$requested" == */* ]]; then
      candidate="$requested"
    else
      candidate="$(command -v -- "$requested" 2>/dev/null || true)"
    fi
  else
    candidate="$ROOT/.venv/bin/python"
  fi

  if [[ -z "$candidate" || ! -x "$candidate" ]]; then
    echo "ERROR: no compliant Python interpreter is executable; set PYTHON or create $ROOT/.venv/bin/python" >&2
    exit 3
  fi

  if ! "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
    echo "ERROR: canonical safe suite requires Python 3.12 or newer" >&2
    exit 3
  fi

  printf '%s\n' "$candidate"
}

PYTHON_BIN="$(resolve_python)"
export PYTHONPATH="$ROOT/src:$ROOT/subrepos/construction-financial-review/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ "$run_python" == true ]]; then
  if ! "$PYTHON_BIN" -c 'import pytest, mcp, fastapi, numpy, scipy' >/dev/null 2>&1; then
    echo "ERROR: canonical safe-suite Python dependencies are unavailable" >&2
    echo "Install with: python -m pip install -e '.[dev,mcp,analytics-ui]' -e 'subrepos/construction-financial-review[dev]'" >&2
    exit 3
  fi

  python_args=(
    -m pytest
    -m "not integration and not manual and not live"
    tests
  )
  if [[ "$collect_only" == true ]]; then
    python_args+=(--collect-only)
  fi
  echo "=== Canonical safe Python suite ==="
  "$PYTHON_BIN" "${python_args[@]}"
fi

if [[ "$run_frontend" == true ]]; then
  if [[ "$collect_only" == true ]]; then
    echo "=== Frontend suite skipped in --collect-only mode ==="
  else
    if [[ ! -f "$ROOT/frontend/package.json" ]]; then
      echo "ERROR: frontend/package.json is missing" >&2
      exit 3
    fi
    if ! command -v npm >/dev/null 2>&1; then
      echo "ERROR: npm is unavailable" >&2
      exit 3
    fi
    if [[ ! -x "$ROOT/frontend/node_modules/.bin/vitest" ]]; then
      echo "ERROR: frontend dependencies are unavailable; run npm ci in frontend before the merge-safe gate" >&2
      exit 3
    fi
    echo "=== Canonical safe frontend suite ==="
    (
      cd "$ROOT/frontend"
      npm test
    )
  fi
fi
