#!/usr/bin/env bash
# Run the FORECAST-ACCURACY generator for project tropical.
# Config-driven: independent EAC models + backtest-calibrated confidence + adequacy flags + optional
# advisory local-Ollama narratives. Writes only to a new timestamped output package under the data
# root. Does not mutate source data and does not commit.
#
# Pass --with-llm to engage the local Ollama advisory layer (default: deterministic mock templates).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUBPROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_ROOT="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['default_data_root'])" "${SUBPROJECT_ROOT}/config/projects/tropical.json")"

echo "[cfr] START run_tropical_forecast_accuracy"
echo "[cfr] subproject_root: ${SUBPROJECT_ROOT}"
echo "[cfr] data_root:       ${DATA_ROOT}"

cd "${SUBPROJECT_ROOT}"
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-accuracy --project tropical "$@"

echo "[cfr] END run_tropical_forecast_accuracy"
