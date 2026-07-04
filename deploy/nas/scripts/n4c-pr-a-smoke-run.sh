#!/bin/sh
# N4C-PR-A bounded backend re-smoke — operator-run with sudo (Docker requires it on NAS).
# Usage on NAS:
#   sudo sh /volume2/personal-assistant/runtime/n4c-pr-a-backend-smoke-<TS>/n4c-pr-a-smoke-run.sh
set -eu

TS="${N4C_PR_A_TS:-20260704T092127Z}"
RUNTIME="/volume2/personal-assistant/runtime/n4c-pr-a-backend-smoke-${TS}"
REPO="${RUNTIME}/repo"
EVID="${RUNTIME}/evidence"
LOG="/volume2/personal-assistant/app-support/logs/n4c-pr-a-backend-smoke-${TS}.log"
DOCKER="${DOCKER:-/usr/local/bin/docker}"
DB="/volume2/personal-assistant/app-support/db/hb-personal-assistant.sqlite"

export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HB_PUBLISH_ADDR=127.0.0.1
export HB_CONFIG_FILE=/volume2/personal-assistant/config/hb-pa-config.yml
export HB_APP_SUPPORT_DIR=/volume2/personal-assistant/app-support

mkdir -p "${EVID}" "$(dirname "${LOG}")"

exec > >(tee -a "${LOG}") 2>&1

echo "== N4C-PR-A smoke ${TS} =="
echo "repo=${REPO}"
echo "commit=$(cat "${REPO}/.commit-sha" 2>/dev/null || echo unknown)"

echo "== preflight config =="
grep -E 'application_support_root|HB_NAS_RUNTIME|HB_EVIDENCE_DISABLE' \
  "${HB_CONFIG_FILE}" /etc/passwd 2>/dev/null || true
sh "${REPO}/deploy/nas/scripts/check-runtime-safety.sh" "${HB_CONFIG_FILE}" || true

echo "== pre-smoke DB (svc RO) =="
sudo -u personal-assistant-svc sqlite3 "file:${DB}?mode=ro" \
  "PRAGMA quick_check; SELECT MAX(version) FROM schema_migrations; SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
sudo -u personal-assistant-svc ls -la "${DB}"

echo "== build image (host network) =="
cd "${REPO}"
"${DOCKER}" build --network host -f deploy/nas/Dockerfile -t hb-personal-assistant:nas .
IMAGE_ID="$("${DOCKER}" images -q hb-personal-assistant:nas | head -1)"
echo "image_id=${IMAGE_ID}"

echo "== compose up (no-build, loopback) =="
cd "${REPO}/deploy/nas"
"${DOCKER}" compose down 2>/dev/null || true
"${DOCKER}" compose up --no-build -d

echo "== waiting for startup =="
sleep 20

echo "== port bindings =="
netstat -an 2>/dev/null | grep -E '[:.]8000[[:space:]]' || true
"${DOCKER}" inspect hb-personal-assistant-backend --format 'HostIp={{(index (index .NetworkSettings.Ports "8000/tcp") 0).HostIp}} HostPort={{(index (index .NetworkSettings.Ports "8000/tcp") 0).HostPort}}' 2>/dev/null || true

echo "== endpoints =="
curl -fsS http://127.0.0.1:8000/health | tee "${EVID}/health.json"
echo
curl -fsS -H 'X-HB-UI-Role: admin' http://127.0.0.1:8000/api/admin/schema/status | tee "${EVID}/admin-schema-status.json"
echo
curl -fsS -H 'X-HB-UI-Role: admin' http://127.0.0.1:8000/api/admin/db/status | tee "${EVID}/admin-db-status.json"
echo
curl -fsS http://127.0.0.1:8000/api/environment | tee "${EVID}/environment.json"
echo
curl -fsS http://127.0.0.1:8000/api/onboarding/readiness | tee "${EVID}/onboarding-readiness.json"
echo

echo "== logs review =="
"${DOCKER}" compose logs --tail=200 2>&1 | tee "${EVID}/compose-logs-tail.txt"
grep -Ei 'db_posture_at_startup|migration_performed|DbStorageGuard|StartupSchemaPolicy|SQLITE_BUSY|database locked|source.?watch|scheduler' \
  "${EVID}/compose-logs-tail.txt" || true

echo "== compose down =="
"${DOCKER}" compose down 2>&1 | tee "${EVID}/compose-down.txt"

echo "== port after shutdown =="
netstat -an 2>/dev/null | grep -E '[:.]8000[[:space:]]' || echo 'port 8000 not listening'
"${DOCKER}" ps --filter name=hb-personal-assistant-backend --format '{{.Names}} {{.Status}}' || true

echo "== post-smoke DB (svc RO) =="
sudo -u personal-assistant-svc sqlite3 "file:${DB}?mode=ro" \
  "PRAGMA quick_check; SELECT MAX(version) FROM schema_migrations; SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'; SELECT COUNT(*) FROM sqlite_master WHERE type='view' AND name NOT LIKE 'sqlite_%';"
sudo -u personal-assistant-svc ls -la "${DB}"

echo "N4C-PR-A smoke complete. Log: ${LOG} Evidence: ${EVID}"
