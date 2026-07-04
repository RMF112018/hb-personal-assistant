#!/bin/sh
# PR C viewer lifecycle validation — operator-run with sudo on NAS.
# Usage:
#   sudo bash /volume2/personal-assistant/runtime/pr-c-viewer-lifecycle-<TS>/pr-c-viewer-lifecycle-run.sh
set -eu

TS="${PR_C_TS:-20260704T095243Z}"
RUNTIME="/volume2/personal-assistant/runtime/pr-c-viewer-lifecycle-${TS}"
REPO="${RUNTIME}/repo"
EVID="${RUNTIME}/evidence"
LOG="/volume2/personal-assistant/app-support/logs/pr-c-viewer-lifecycle-${TS}.log"
DOCKER="${DOCKER:-/usr/local/bin/docker}"

export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HB_PUBLISH_ADDR=127.0.0.1
export HB_CONFIG_FILE=/volume2/personal-assistant/config/hb-pa-config.yml
export HB_APP_SUPPORT_DIR=/volume2/personal-assistant/app-support

mkdir -p "${EVID}"
exec > >(tee -a "${LOG}") 2>&1

echo "== PR C viewer lifecycle validation ${TS} =="
echo "commit=$(cat "${REPO}/.commit-sha" 2>/dev/null || echo unknown)"
cd "${REPO}/deploy/nas"

echo "== preflight: image =="
"${DOCKER}" images | grep -E 'hb-personal-assistant|REPOSITORY' || true

echo "== preflight: port 8000 LISTEN =="
netstat -an 2>/dev/null | grep -E '[:.]8000[[:space:]].*LISTEN' || echo 'port 8000 not listening'

echo "== preflight: check-runtime-safety =="
sh scripts/check-runtime-safety.sh "${HB_CONFIG_FILE}" | tee "${EVID}/check-runtime-safety.txt"

echo "== start.sh =="
sh scripts/start.sh | tee "${EVID}/start.txt"

echo "== status.sh (during runtime) =="
sh scripts/status.sh | tee "${EVID}/status-during.txt"

echo "== health.sh =="
HB_VIEWER_HEALTH_OK=1 sh scripts/health.sh | tee "${EVID}/health.txt"

echo "== health.sh admin db status =="
HB_VIEWER_HEALTH_OK=1 HB_ADMIN_DB_STATUS=1 sh scripts/health.sh | tee "${EVID}/health-admin-db.txt"

echo "== validate-db.sh =="
sh scripts/validate-db.sh | tee "${EVID}/validate-db.txt"

echo "== stop.sh --down =="
sh scripts/stop.sh --down | tee "${EVID}/stop.txt"

echo "== status.sh (post-stop) =="
sh scripts/status.sh | tee "${EVID}/status-post-stop.txt"

echo "== post-stop port 8000 =="
netstat -an 2>/dev/null | grep -E '[:.]8000[[:space:]].*LISTEN' || echo 'port 8000 not listening'

echo "== emergency-shutdown.sh (default) =="
sh scripts/emergency-shutdown.sh | tee "${EVID}/emergency-shutdown.txt"

echo "== final port 8000 =="
netstat -an 2>/dev/null | grep -E '[:.]8000[[:space:]].*LISTEN' || echo 'port 8000 not listening'

echo "== unrelated containers spot-check =="
"${DOCKER}" ps --format '{{.Names}}' | grep -v '^hb-personal-assistant-backend$' | head -20 || true

echo "PR C validation complete. Evidence: ${EVID} Log: ${LOG}"
