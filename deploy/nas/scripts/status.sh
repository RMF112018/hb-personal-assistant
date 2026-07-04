#!/bin/sh
# status.sh — report HB viewer backend compose and loopback bind posture (metadata only).
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=viewer-common.sh
. "$SCRIPT_DIR/viewer-common.sh"

echo "== HB viewer status =="
echo "publish_addr=$HB_PUBLISH_ADDR (required: loopback)"
echo "config=$HB_CONFIG_FILE"
echo "app_support=$HB_APP_SUPPORT_DIR"
echo "image=$VIEWER_IMAGE"

echo "-- compose ps --"
viewer_compose ps || true

_running="$("$DOCKER" ps --filter "name=^${VIEWER_CONTAINER}$" --format '{{.Names}} {{.Status}}' 2>/dev/null || true)"
if [ -n "$_running" ]; then
  echo "container_running=yes ($_running)"
else
  echo "container_running=no"
fi

echo "-- port bindings (docker inspect) --"
if "$DOCKER" inspect "$VIEWER_CONTAINER" >/dev/null 2>&1; then
  "$DOCKER" inspect "$VIEWER_CONTAINER" --format \
    'HostIp={{(index (index .NetworkSettings.Ports "8000/tcp") 0).HostIp}} HostPort={{(index (index .NetworkSettings.Ports "8000/tcp") 0).HostPort}}' \
    2>/dev/null || echo "inspect: port 8000/tcp not published"
else
  echo "inspect: container not present"
fi

echo "-- LISTEN check (host port 8000) --"
if netstat -an 2>/dev/null | grep -E '\.8000[[:space:]].*LISTEN' >/dev/null; then
  _listen="$(netstat -an 2>/dev/null | grep -E '\.8000[[:space:]].*LISTEN' || true)"
  echo "$_listen"
  if echo "$_listen" | grep -qv '127.0.0.1\.8000'; then
    echo "WARN: port 8000 LISTEN is not loopback-only"
    loopback_only=no
  else
    echo "loopback_only=yes"
    loopback_only=yes
  fi
else
  echo "port_8000_listen=no"
  loopback_only=n/a
fi

echo "status complete"
