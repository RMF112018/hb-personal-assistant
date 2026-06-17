#!/usr/bin/env bash
set -euo pipefail

# repo-relative: scripts/ sits directly under the subproject root
cd "$(dirname "$0")/.."

PY="../../.venv/bin/python"
export PYTHONPATH=src

echo "== Preflight =="
$PY -m compileall -q src
$PY -m construction_financial_review.cli validate-crosswalk --project tropical

echo "== Core packages =="
$PY -m construction_financial_review.cli run-context --project tropical

# Derive the EXACT context package stamp this fresh run just generated, and pin every downstream
# context-consuming stage to it (fail closed) so the run is lineage-consistent.
DATA_ROOT=$($PY - <<'PYEOF'
import json, pathlib
print(json.load(open(pathlib.Path("config/projects/tropical.json")))["default_data_root"])
PYEOF
)
CTX_DIR=$(ls -td "$DATA_ROOT"/forecast_context_package_tropical_* | head -1)
CTX_STAMP=$(basename "$CTX_DIR" | sed -E 's/^forecast_context_package_tropical_//')
if [ -z "$CTX_STAMP" ]; then
  echo "ERROR: could not resolve the freshly generated context package stamp" >&2
  exit 1
fi
echo "Pinned context stamp for this fresh run: $CTX_STAMP"
PIN="--context-stamp $CTX_STAMP"

$PY -m construction_financial_review.cli actuals-erp-crosscheck --project tropical || \
  echo "WARN: actuals-erp-crosscheck advisory package reported validation warnings; continuing full run"
$PY -m construction_financial_review.cli run-analysis --project tropical
$PY -m construction_financial_review.cli run-mapping-workpaper --project tropical
$PY -m construction_financial_review.cli run-crosswalk-v2 --project tropical

echo "== Schedule / intelligence =="
$PY -m construction_financial_review.cli schedule-integrate-forecast --project tropical
$PY -m construction_financial_review.cli forecast-accuracy --project tropical
$PY -m construction_financial_review.cli forecast-intelligence --project tropical $PIN

echo "== Advisory / operator evidence =="
$PY -m construction_financial_review.cli forecast-history-informed --project tropical
$PY -m construction_financial_review.cli forecast-controls --project tropical
$PY -m construction_financial_review.cli forecast-model-controls --project tropical
$PY -m construction_financial_review.cli forecast-staffing-plan --project tropical $PIN
$PY -m construction_financial_review.cli forecast-cost-frequency --project tropical $PIN

echo "== Forecast outputs =="
$PY -m construction_financial_review.cli forecast-monthly --project tropical $PIN
$PY -m construction_financial_review.cli forecast-probability --project tropical $PIN
$PY -m construction_financial_review.cli forecast-comprehensive --project tropical $PIN

echo "== Full fresh Tropical forecast run complete (pinned context $CTX_STAMP) =="
