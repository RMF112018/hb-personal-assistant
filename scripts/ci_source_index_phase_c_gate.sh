#!/usr/bin/env bash
# Source-Index Phase C CI gate (PC-WI-05 / PC-AC-047).
#
# Deterministic and CI-safe: scratch SQLite databases under temporary rehearsal roots, a
# fresh-interpreter subprocess for the kill-mid-apply() atomicity proof, and a read-only historical
# `git worktree` for the executable-compatibility proof. No live NAS, production database, network,
# watcher activation, or MCP snapshot is required.
#
# Runs SEPARATELY from scripts/ci_source_index_gate.sh (Phase A/B), so that gate stays green (PC-AC-046).
#
# Requires FULL git history: the executable-compatibility proof checks out the pinned prior-executable
# SHA (6b57a406) via `git worktree`. On a shallow clone lacking that commit, those tests fail closed
# with an INSUFFICIENT-EVIDENCE error (never a false pass) — run with a complete clone in CI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Deterministic interpreter selection — never rely on a bare `pytest`/`python` from an ambient shell,
# which can resolve to a system interpreter with the wrong dependency set.
PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi
export PYTHONPATH="$ROOT/src:$ROOT/subrepos/construction-financial-review/src${PYTHONPATH:+:$PYTHONPATH}"

PHASE_C_SRC=(
  src/hb_assistant/store/source_index_migration_assurance.py
  src/hb_assistant/store/sqlite_backup.py
)
PHASE_C_TESTS=(
  tests/source_index/test_phase_c_migration_matrix.py
  tests/source_index/test_phase_c_parity.py
  tests/source_index/test_phase_c_idempotency.py
  tests/source_index/test_phase_c_query_plans.py
  tests/source_index/test_phase_c_backup_restore.py
  tests/source_index/test_phase_c_atomicity_recovery.py
  tests/source_index/test_phase_c_executable_compatibility.py
)
PHASE_C_SUPPORT=(
  tests/support/source_index_migration_fixture.py
  tests/support/source_index_atomicity_child.py
  tests/support/source_index_compat_probe.py
)

echo "[phase-c-gate] pytest — Phase C source-index suite"
"$PYTHON_BIN" -m pytest -p no:cacheprovider -q tests/source_index/

echo "[phase-c-gate] ruff — Phase C source + tests"
"$PYTHON_BIN" -m ruff check --no-force-exclude \
  "${PHASE_C_SRC[@]}" "${PHASE_C_TESTS[@]}" "${PHASE_C_SUPPORT[@]}"

# Strict type-check the Phase C SOURCE modules — these are in the pyproject `[[tool.mypy.overrides]]`
# strict scope, so `mypy src` (and this gate) enforce them. The Phase C test modules are linted (ruff)
# and run (pytest) above; they are not held to `mypy --strict` here (the earlier work items' test files
# predate strict typing and are out of PC-WI-05's create-only scope to modify).
echo "[phase-c-gate] mypy --strict — Phase C source modules (pyproject strict override)"
"$PYTHON_BIN" -m mypy --strict "${PHASE_C_SRC[@]}"

echo "[phase-c-gate] OK"
