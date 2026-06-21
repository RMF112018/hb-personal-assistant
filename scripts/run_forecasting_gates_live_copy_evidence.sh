#!/usr/bin/env bash
# Generate safe forecasting gate evidence from a copied live SQLite DB (read-only).
# Does NOT mutate the live DB. Does NOT commit the copied DB by default.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

LIVE_DB="${LIVE_DB:-$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${OUT:-docs/evidence/forecasting-gates-live-copy-$STAMP}"
mkdir -p "$OUT"

if [[ ! -f "$LIVE_DB" ]]; then
  echo "Live DB not found: $LIVE_DB" >&2
  exit 1
fi

{
  echo "stamp=$STAMP"
  echo "live_db=$LIVE_DB"
  echo "out_dir=$OUT"
  echo "copy_method=VACUUM INTO"
  echo "repo_root=$REPO_ROOT"
  echo "branch=$(git branch --show-current 2>/dev/null || echo unknown)"
  echo "head=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
} > "$OUT/00-run-context.txt"

sqlite3 "$LIVE_DB" "VACUUM INTO '$OUT/live-copy.sqlite';"
sqlite3 "$OUT/live-copy.sqlite" "PRAGMA quick_check;" | tee "$OUT/01-sqlite-quick-check.txt"

export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
python3 - <<'PY' "$OUT/live-copy.sqlite" "$OUT"
import json
import sys
from pathlib import Path

from hb_assistant.forecasting.gates import (
    run_actuals_reconciliation_gate,
    run_all_forecasting_gates,
    run_cost_type_guard_gate,
    run_double_count_gate,
    run_projection_parity_gate,
)

db = sys.argv[1]
out = Path(sys.argv[2])

def write(name, report):
    path = out / name
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    json.loads(path.read_text(encoding="utf-8"))

write("02-forecast-gates-warn.json", run_all_forecasting_gates(db_path=db, mode="warn"))
write("03-forecast-gates-strict.json", run_all_forecasting_gates(db_path=db, mode="strict"))
write("04-double-count-gate.json", run_double_count_gate(db_path=db, mode="warn"))
write("05-actuals-reconciliation-gate.json", run_actuals_reconciliation_gate(db_path=db, mode="warn"))
write("06-projection-parity-gate.json", run_projection_parity_gate(db_path=db))
write("07-cost-type-guard-gate.json", run_cost_type_guard_gate(db_path=db))
PY

HB="${HB_ASSISTANT:-}"
if [[ -z "$HB" ]]; then
  if [[ -x "$REPO_ROOT/.venv/bin/hb-assistant" ]]; then
    HB="$REPO_ROOT/.venv/bin/hb-assistant"
  elif [[ -x "/Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant" ]]; then
    HB="/Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant"
  else
    HB="hb-assistant"
  fi
fi

if command -v "$HB" >/dev/null 2>&1; then
  "$HB" procore analytics no-raw-leak-scan --path "$OUT" --json \
    | tee "$OUT/98-no-raw-leak-scan.json" >/dev/null || true
else
  echo '{"ok":true,"skipped":true,"reason":"hb-assistant not found"}' > "$OUT/98-no-raw-leak-scan.json"
fi
python3 -m json.tool "$OUT/98-no-raw-leak-scan.json" >/dev/null

find "$OUT" -type f -size 0 | sort > "$OUT/99-zero-byte-files.txt" || true

echo "$OUT"