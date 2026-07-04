#!/bin/sh
# emergency-shutdown.sh — stop HB viewer backend and verify host is not listening on 8000.
#
# Default: compose down only — no WAL checkpoint, no DB mutation.
# Optional: --passive-checkpoint documents operator intent only (PR B deferred; no-op here).
#
# Usage:
#   deploy/nas/scripts/emergency-shutdown.sh
#   deploy/nas/scripts/emergency-shutdown.sh --passive-checkpoint   # no-op until PR B; logged only
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=viewer-common.sh
. "$SCRIPT_DIR/viewer-common.sh"

_passive=0
for _arg in "$@"; do
  case "$_arg" in
    --passive-checkpoint) _passive=1 ;;
    *) echo "unknown arg: $_arg" >&2; exit 2 ;;
  esac
done

echo "== HB viewer emergency shutdown =="
viewer_compose down 2>/dev/null || true

if [ "$_passive" -eq 1 ]; then
  echo "NOTE: --passive-checkpoint requested; WAL checkpoint deferred to PR B (no DB mutation performed)."
fi

echo "-- container check --"
_running="$("$DOCKER" ps -a --filter "name=^${VIEWER_CONTAINER}$" --format '{{.Names}} {{.Status}}' 2>/dev/null || true)"
if [ -n "$_running" ]; then
  echo "WARN: container still present: $_running"
else
  echo "container_absent=yes"
fi

echo "-- LISTEN check (port 8000) --"
if netstat -an 2>/dev/null | grep -E '\.8000[[:space:]].*LISTEN' >/dev/null; then
  netstat -an 2>/dev/null | grep -E '\.8000[[:space:]].*LISTEN' || true
  echo "FAIL: port 8000 still LISTEN" >&2
  exit 1
fi
echo "port_8000_listen=no"

echo "emergency shutdown complete"
