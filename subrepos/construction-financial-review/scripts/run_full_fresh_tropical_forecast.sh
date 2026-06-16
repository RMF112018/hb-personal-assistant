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
$PY -m construction_financial_review.cli run-analysis --project tropical
$PY -m construction_financial_review.cli run-mapping-workpaper --project tropical
$PY -m construction_financial_review.cli run-crosswalk-v2 --project tropical

echo "== Schedule / intelligence =="
$PY -m construction_financial_review.cli schedule-integrate-forecast --project tropical
$PY -m construction_financial_review.cli forecast-accuracy --project tropical
$PY -m construction_financial_review.cli forecast-intelligence --project tropical

echo "== Advisory / operator evidence =="
$PY -m construction_financial_review.cli forecast-history-informed --project tropical
$PY -m construction_financial_review.cli forecast-controls --project tropical
$PY -m construction_financial_review.cli forecast-model-controls --project tropical
$PY -m construction_financial_review.cli forecast-staffing-plan --project tropical
$PY -m construction_financial_review.cli forecast-cost-frequency --project tropical

echo "== Forecast outputs =="
$PY -m construction_financial_review.cli forecast-monthly --project tropical
$PY -m construction_financial_review.cli forecast-probability --project tropical
$PY -m construction_financial_review.cli forecast-comprehensive --project tropical

echo "== Full fresh Tropical forecast run complete =="
