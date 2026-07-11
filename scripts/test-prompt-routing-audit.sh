#!/usr/bin/env bash
# Fast focused bundle: July 2026 50-prompt routing audit corpus (PR-14).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif [[ -x "$ROOT/.venv/bin/pytest" ]]; then
  PY="$ROOT/.venv/bin/pytest"
else
  PY="python3"
fi

export PYTHONPATH="$ROOT/src:$ROOT/subrepos/construction-financial-review/src${PYTHONPATH:+:$PYTHONPATH}"

MARKERS=(-m "not integration and not manual and not live")

echo "== prompt routing audit corpus (offline + broker) =="
"$PY" -m pytest \
  tests/test_prompt_routing_audit_corpus.py \
  tests/test_prompt_preflight_semantic_equivalence.py \
  "${MARKERS[@]}" \
  "$@"

echo "== audit regression matrix (legacy JSON + versioned corpus v1 runner) =="
"$PY" scripts/run-audit-route-regression-matrix.py \
  --matrix "$ROOT/scripts/audit-route-regression-matrix.json" \
  --out /tmp/audit-route-regression-matrix-offline.json
"$PY" scripts/run-audit-route-regression-matrix.py \
  --matrix "$ROOT/tests/fixtures/prompt_routing_audit_corpus_v1.json" \
  --out /tmp/prompt-routing-audit-corpus-v1-offline.json

echo "prompt-routing-audit bundle: OK"