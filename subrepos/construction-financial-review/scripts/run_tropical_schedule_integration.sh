#!/usr/bin/env bash
# Run the SCHEDULE-INTEGRATED forecast generator for project tropical.
# Config-driven: discovers the latest schedule / context / crosswalk-v2 / workpaper packages.
# Writes only to a new timestamped output package under the configured data root.
# Does not mutate source folders and does not commit.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUBPROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_ROOT="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['default_data_root'])" "${SUBPROJECT_ROOT}/config/projects/tropical.json")"

echo "[cfr] START run_tropical_schedule_integration"
echo "[cfr] subproject_root: ${SUBPROJECT_ROOT}"
echo "[cfr] data_root:       ${DATA_ROOT}"

cd "${SUBPROJECT_ROOT}"
PYTHONPATH=src python3 -m construction_financial_review.cli schedule-integrate-forecast --project tropical

echo "[cfr] END run_tropical_schedule_integration"
