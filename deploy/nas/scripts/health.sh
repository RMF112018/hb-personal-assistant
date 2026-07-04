#!/bin/sh
# health.sh — query the HB /health endpoint.
#
# WARNING: /health may OPEN THE SQLITE DB (schema-version read) and, on first open under a given
# app-support root, trigger schema migration (a WRITE). Therefore this MUST only ever be pointed at a
# DISPOSABLE SCRATCH app-support root — never the live DB. As a guard, this script refuses to run
# unless HB_SMOKE_OK=1 is exported (an explicit operator acknowledgement for the N1C scratch smoke).
set -eu
URL="${HB_HEALTH_URL:-http://127.0.0.1:8000/health}"
if [ "${HB_SMOKE_OK:-}" != "1" ]; then
  echo "refusing to run: set HB_SMOKE_OK=1 to confirm this targets a DISPOSABLE scratch backend."
  echo "(/health can touch/migrate the DB; never run against the live DB.)"
  exit 3
fi
echo "GET $URL"
if command -v curl >/dev/null 2>&1; then
  curl -sS -i --max-time 5 "$URL"
else
  python3 - "$URL" <<'PY'
import sys,urllib.request
r=urllib.request.urlopen(sys.argv[1],timeout=5); print(r.status); print(r.read().decode(errors="replace"))
PY
fi
