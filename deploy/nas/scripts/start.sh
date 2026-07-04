#!/bin/sh
# start.sh — start NAS read-only viewer backend (no implicit build).
#
# Requires: prebuilt hb-personal-assistant:nas image, loopback publish, viewer compose invariants.
# Does NOT enable workers, source ingestion, schedulers, or secrets mounts.
#
# Usage (on NAS, typically via operator sudo for Docker):
#   deploy/nas/scripts/start.sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=viewer-common.sh
. "$SCRIPT_DIR/viewer-common.sh"

viewer_require_config
viewer_require_compose_invariants
viewer_require_image

echo "== HB viewer start (compose up --no-build, loopback only) =="
echo "image=$VIEWER_IMAGE publish=$HB_PUBLISH_ADDR config=$HB_CONFIG_FILE app_support=$HB_APP_SUPPORT_DIR"

viewer_compose down 2>/dev/null || true
viewer_compose up --no-build -d

echo "-- compose ps --"
viewer_compose ps

echo "start complete (viewer mode; workers disabled by compose)"
