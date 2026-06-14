#!/usr/bin/env bash
# Run the forecast ANALYSIS package generator (v1) for project tropical.
# Writes only to a new timestamped output package under the configured data root.
# Does not mutate source folders and does not commit.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUBPROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_ROOT="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['default_data_root'])" "${SUBPROJECT_ROOT}/config/projects/tropical.json")"

echo "[cfr] START run_tropical_analysis"
echo "[cfr] subproject_root: ${SUBPROJECT_ROOT}"
echo "[cfr] data_root:       ${DATA_ROOT}"

cd "${SUBPROJECT_ROOT}"
PYTHONPATH=src python3 -m construction_financial_review.cli run-analysis --project tropical

echo "[cfr] END run_tropical_analysis"
