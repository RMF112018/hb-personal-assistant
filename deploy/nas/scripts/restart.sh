#!/bin/sh
# restart.sh — restart NAS viewer backend without rebuild.
#
# Usage:
#   deploy/nas/scripts/restart.sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "== HB viewer restart (stop then start; no build) =="
"$SCRIPT_DIR/stop.sh" --down
"$SCRIPT_DIR/start.sh"
