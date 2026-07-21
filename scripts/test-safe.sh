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

PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
  elif [[ -x "/Users/bobbyfetting/hb-personal-assistant/.venv/bin/python" ]]; then
    PYTHON_BIN="/Users/bobbyfetting/hb-personal-assistant/.venv/bin/python"
  else
    PYTHON_BIN="python"
  fi
fi

export PYTHONPATH="$ROOT/src:$ROOT/subrepos/construction-financial-review/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ "$run_python" == true ]]; then
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
