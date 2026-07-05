#!/bin/sh
# Install an hourly Synology cron entry that refreshes the NAS MCP DB snapshot.
#
# Synology /etc/crontab is TAB-separated with a 6th "user" field. Manual entries survive
# reboots (crond reads /etc/crontab on boot). This installer is idempotent, backs up the
# crontab first, and reloads crond.
#
# ALTERNATIVE (safer / DSM-canonical): DSM > Control Panel > Task Scheduler > Create >
# Scheduled Task > User-defined script, run as root, hourly, command:
#   sh /volume2/personal-assistant/deploy/nas/scripts/snapshot-mcp-db.sh
#
# RUN (operator, needs root): sudo sh deploy/nas/scripts/install-snapshot-cron.sh
set -eu

CRON=/etc/crontab
SCRIPT=/volume2/personal-assistant/deploy/nas/scripts/snapshot-mcp-db.sh
LOGDIR=/volume2/personal-assistant/app-support/mcp-snapshot
LOG="$LOGDIR/snapshot.log"
TAG="# hb-mcp-snapshot (hourly DB snapshot for NAS MCP)"

[ -f "$SCRIPT" ] || { echo "FAIL: $SCRIPT not found" >&2; exit 1; }
[ -f "$CRON" ]   || { echo "FAIL: $CRON not found (unexpected on DSM)" >&2; exit 1; }
mkdir -p "$LOGDIR"

if grep -qF "hb-mcp-snapshot" "$CRON"; then
    echo "already installed:"; grep -A1 -F "hb-mcp-snapshot" "$CRON"; exit 0
fi

BAK="$CRON.bak.hb-$(date +%Y%m%d%H%M%S)"
cp -a "$CRON" "$BAK"
echo "backed up $CRON -> $BAK"

# top of every hour; fields TAB-separated (Synology requirement); user=root
{ printf '%s\n' "$TAG"; printf '0\t*\t*\t*\t*\troot\t%s >> %s 2>&1\n' "$SCRIPT" "$LOG"; } >> "$CRON"

# reload crond (DSM7 then DSM6 fallbacks)
synoservicectl --restart crond 2>/dev/null \
  || synosystemctl restart crond 2>/dev/null \
  || synoservice --restart crond 2>/dev/null \
  || { echo "WARN: could not auto-reload crond; reboot or restart crond manually" >&2; }

echo "installed hourly snapshot cron:"; grep -A1 -F "hb-mcp-snapshot" "$CRON"
echo "log -> $LOG"
