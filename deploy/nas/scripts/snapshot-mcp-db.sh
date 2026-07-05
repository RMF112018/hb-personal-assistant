#!/bin/sh
# Refresh the read-only DB snapshot that the NAS MCP reads.
#
# WHY: the internet-facing MCP must never touch the live 4GB production DB. Instead it reads
# a consistent, checkpointed SNAPSHOT copy (opened mode=ro&immutable=1 on a :ro mount). This
# job produces that snapshot in a SHORT-LIVED, NON-exposed container using SQLite's online
# backup API, then atomically renames it into place so an MCP descriptor already open on the
# old snapshot keeps reading a stable inode.
#
# SAFETY:
#   * The live DB is mounted here :rw ONLY so SQLite can take the SHARED locks an online
#     backup needs (a :ro mount cannot open it; `immutable` on a live-written DB risks a
#     torn copy). The SQL connection is mode=ro, so no writes occur. This job is local/
#     operator-run and never internet-exposed — unlike the MCP, which never mounts the live DB.
#   * Snapshot is written to a temp file and os.replace()'d (atomic) — never edited in place.
#
# RUN (operator, needs docker => sudo):
#   sudo sh deploy/nas/scripts/snapshot-mcp-db.sh
# SCHEDULE hourly via Synology Task Scheduler (or cron) for fresh freshness/queue/status
# data; snapshot staleness == time since last run.
set -eu

APP_SUPPORT="${HB_APP_SUPPORT_DIR:-/volume2/personal-assistant/app-support}"
LIVE_DIR="$APP_SUPPORT/db"
SNAP_DIR="$APP_SUPPORT/mcp-snapshot/db"
IMAGE="${HB_MCP_IMAGE:-hb-personal-assistant:nas}"
UIDGID="1028:100"   # personal-assistant-svc:users — owner of the managed DB + MCP runtime user

[ -f "$LIVE_DIR/hb-personal-assistant.sqlite" ] || { echo "FAIL: live DB not found at $LIVE_DIR" >&2; exit 1; }
mkdir -p "$SNAP_DIR"
chown "$UIDGID" "$SNAP_DIR" "$(dirname "$SNAP_DIR")" 2>/dev/null || true

docker run --rm -i --user "$UIDGID" \
  -v "$LIVE_DIR:/live/db:rw" \
  -v "$SNAP_DIR:/snap/db:rw" \
  --entrypoint python3 "$IMAGE" - <<'PY'
import os, sqlite3, time
live  = "/live/db/hb-personal-assistant.sqlite"
final = "/snap/db/hb-personal-assistant.sqlite"
tmp   = "/snap/db/.hb-personal-assistant.sqlite.tmp"
try:
    os.remove(tmp)
except FileNotFoundError:
    pass
t0 = time.time()
src = sqlite3.connect(f"file:{live}?mode=ro", uri=True, timeout=60)   # read-only, proper SHARED locks
dst = sqlite3.connect(tmp)
try:
    with dst:
        src.backup(dst)          # online backup: consistent even under concurrent writes
finally:
    dst.close(); src.close()
os.replace(tmp, final)           # atomic publish
os.chmod(final, 0o640)
print(f"snapshot ok: {final} {os.path.getsize(final)} bytes in {time.time()-t0:.1f}s")
PY
echo "snapshot refresh complete: $SNAP_DIR/hb-personal-assistant.sqlite"
