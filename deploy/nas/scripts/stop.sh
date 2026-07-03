#!/bin/sh
# stop.sh — stop ONLY the HB backend compose project/service. Never touches other containers.
# Uses `stop` (not `down`) by default to preserve the network/volumes; pass --down to remove them.
set -eu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SVC="hb-personal-assistant-backend"

cd "$NAS_DIR"
if [ "${1:-}" = "--down" ]; then
  echo "docker compose down (this HB project only; keeps images/volumes)"
  docker compose -f compose.yaml down
else
  echo "docker compose stop $SVC (HB service only)"
  docker compose -f compose.yaml stop "$SVC"
fi
echo "-- HB service state --"
docker compose -f compose.yaml ps
