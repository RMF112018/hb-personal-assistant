#!/bin/sh
# health.sh — query HB viewer backend health endpoints (metadata only).
#
# /health may read schema version from SQLite (read-only when schema == head under PR A).
# For production viewer validation, set HB_VIEWER_HEALTH_OK=1.
# For admin DB posture, set HB_ADMIN_DB_STATUS=1 (requires local admin access to loopback backend).
#
# Does NOT call source/ingestion endpoints.
set -eu

URL="${HB_HEALTH_URL:-http://127.0.0.1:8000/health}"
ADMIN_URL="${HB_ADMIN_DB_STATUS_URL:-http://127.0.0.1:8000/api/admin/db/status}"

if [ "${HB_VIEWER_HEALTH_OK:-}" != "1" ] && [ "${HB_SMOKE_OK:-}" != "1" ]; then
  echo "refusing to run: set HB_VIEWER_HEALTH_OK=1 (viewer) or HB_SMOKE_OK=1 (scratch smoke)." >&2
  exit 3
fi

_fetch() {
  _url="$1"
  _role="${2:-}"
  if [ -n "$_role" ]; then
    echo "GET $_url (X-HB-UI-Role: $_role)"
  else
    echo "GET $_url"
  fi
  if command -v curl >/dev/null 2>&1; then
    if [ -n "$_role" ]; then
      # Pass the header as ONE argument so the value is never word-split.
      curl -sS -i --max-time 10 -H "X-HB-UI-Role: $_role" "$_url"
    else
      curl -sS -i --max-time 10 "$_url"
    fi
  else
    python3 - "$_url" "$_role" <<'PY'
import sys, urllib.request
url, role = sys.argv[1], sys.argv[2]
req = urllib.request.Request(url)
if role.strip():
    req.add_header("X-HB-UI-Role", role.strip())
r = urllib.request.urlopen(req, timeout=10)
print(r.status)
print(r.read().decode(errors="replace"))
PY
  fi
  echo
}

_fetch "$URL"
if [ "${HB_ADMIN_DB_STATUS:-}" = "1" ]; then
  _fetch "$ADMIN_URL" "admin"
fi
