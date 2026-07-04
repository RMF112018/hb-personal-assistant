#!/bin/sh
# N4C bounded backend smoke — operator-run with sudo when Docker requires it.
# Usage on NAS (as bfetting):
#   sudo sh /volume2/personal-assistant/runtime/n4c-backend-smoke-<TS>/n4c-smoke-run.sh
set -eu

TS="${N4C_TS:-20260704T075948Z}"
RUNTIME="/volume2/personal-assistant/runtime/n4c-backend-smoke-${TS}"
REPO="${RUNTIME}/repo"
LOG="/volume2/personal-assistant/app-support/logs/n4c-backend-smoke-${TS}.log"
DOCKER="${DOCKER:-/usr/local/bin/docker}"

export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HB_PUBLISH_ADDR=127.0.0.1
export HB_CONFIG_FILE=/volume2/personal-assistant/config/hb-pa-config.yml
export HB_APP_SUPPORT_DIR=/volume2/personal-assistant/app-support

cd "${REPO}/deploy/nas"

echo "== N4C compose up (loopback only) =="
"${DOCKER}" compose down 2>/dev/null || true
"${DOCKER}" compose up -d --build 2>&1 | tee -a "${LOG}"

echo "== waiting for startup =="
sleep 15

echo "== port bindings =="
netstat -an 2>/dev/null | grep -E '[:.]8000[[:space:]]' || true
"${DOCKER}" inspect hb-personal-assistant-backend --format '{{json .HostConfig.PortBindings}}' 2>/dev/null || true

echo "== health =="
curl -fsS http://127.0.0.1:8000/health || true
echo
curl -fsS -H 'X-HB-UI-Role: admin' http://127.0.0.1:8000/api/admin/schema/status || true
echo
curl -fsS http://127.0.0.1:8000/api/environment || true
echo
curl -fsS http://127.0.0.1:8000/api/onboarding/readiness || true
echo

echo "== logs tail =="
"${DOCKER}" compose logs --tail=80 2>&1 | tee -a "${LOG}"

echo "== compose down =="
"${DOCKER}" compose down 2>&1 | tee -a "${LOG}"

echo "== port after shutdown =="
netstat -an 2>/dev/null | grep -E '[:.]8000[[:space:]]' || echo 'port 8000 not listening'

echo "N4C smoke script complete. Log: ${LOG}"
