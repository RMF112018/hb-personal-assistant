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
  _extra="${2:-}"
  echo "GET $_url $_extra"
  if command -v curl >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    curl -sS -i --max-time 10 $_extra "$_url"
  else
    python3 - "$_url" "$_extra" <<'PY'
import sys, urllib.request
url, extra = sys.argv[1], sys.argv[2]
req = urllib.request.Request(url)
if extra.strip():
    for part in extra.strip().split():
        if part.startswith("X-HB-UI-Role:"):
            req.add_header("X-HB-UI-Role", part.split(":", 1)[1].strip())
r = urllib.request.urlopen(req, timeout=10)
print(r.status)
print(r.read().decode(errors="replace"))
PY
  fi
  echo
}

_fetch "$URL"
if [ "${HB_ADMIN_DB_STATUS:-}" = "1" ]; then
  _fetch "$ADMIN_URL" "-H X-HB-UI-Role: admin"
fi
