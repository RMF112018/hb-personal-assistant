#!/bin/bash
# HB Assistant — Dev launcher shortcut (Automator / Dock / double-click).
#
# Starts the Dev launcher in the background and exits quickly. The launcher itself
# owns `--open`: it starts the managed processes, waits for the Dev frontend to
# become reachable, and opens it in the default browser. This script must NOT
# launch the dev/backend servers or a browser directly.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"
HB="$REPO/.venv/bin/hb-assistant"
[ -x "$HB" ] || HB="hb-assistant"
nohup "$HB" launcher dev --open --json >/dev/null 2>&1 &
exit 0
