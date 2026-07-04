#!/bin/sh
# logs.sh — show ONLY the HB backend service logs. No other containers.
# Default: follow (-f). Pass args (e.g. --tail 100) to override.
set -eu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$NAS_DIR"
if [ "$#" -eq 0 ]; then
  set -- -f
fi
exec docker compose -f compose.yaml logs "$@" hb-personal-assistant-backend
