#!/usr/bin/env bash
set -euo pipefail

# repo-relative: scripts/ sits directly under the subproject root
cd "$(dirname "$0")/.."

PY="../../.venv/bin/python"
export PYTHONPATH=src

echo "== Preflight =="
$PY -m compileall -q src
$PY -m construction_financial_review.cli validate-crosswalk --project tropical

# Start a FRESH run-specific lineage state and export it; every downstream stage carries the fresh
# upstream lineage automatically (no manual stamp arguments). A fresh run_id avoids inheriting a stale
# state from a prior failed run.
CFR_RUN_LINEAGE_STATE=$($PY -m construction_financial_review.cli lineage-init --project tropical)
export CFR_RUN_LINEAGE_STATE
echo "Run lineage state: $CFR_RUN_LINEAGE_STATE"

echo "== Core packages =="
$PY -m construction_financial_review.cli run-context --project tropical
$PY -m construction_financial_review.cli lineage-record --project tropical --type context

$PY -m construction_financial_review.cli actuals-erp-crosscheck --project tropical || \
  echo "WARN: actuals-erp-crosscheck advisory package reported validation warnings; continuing full run"

# Analysis chain consumes the fresh upstream packages strictly from the run lineage state.
$PY -m construction_financial_review.cli run-analysis --project tropical
$PY -m construction_financial_review.cli lineage-record --project tropical --type analysis
$PY -m construction_financial_review.cli run-mapping-workpaper --project tropical
$PY -m construction_financial_review.cli lineage-record --project tropical --type mapping_workpaper
$PY -m construction_financial_review.cli run-crosswalk-v2 --project tropical
$PY -m construction_financial_review.cli lineage-record --project tropical --type crosswalk_v2
$PY -m construction_financial_review.cli lineage-show --project tropical

# Downstream forecast stages pin context by the stamp recorded in the run lineage state.
CTX_STAMP=$($PY -m construction_financial_review.cli lineage-show --project tropical --field context_stamp)
if [ -z "$CTX_STAMP" ]; then
  echo "ERROR: run lineage state has no recorded context stamp" >&2
  exit 1
fi
echo "Pinned context stamp for this fresh run: $CTX_STAMP"
PIN="--context-stamp $CTX_STAMP"

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
