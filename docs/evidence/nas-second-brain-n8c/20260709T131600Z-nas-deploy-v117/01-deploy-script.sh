#!/bin/sh
# =============================================================================
# hb-deploy-v117.sh — Controlled NAS deploy of merged main @ bf2f30cc
# =============================================================================
# RUN ON THE NAS as:   sudo sh /tmp/hb-deploy-v117.sh
#
# Authorized scope (Bobby, deploy gate id=u84c2g):
#   * Deploy code only (load new image, restart MCP service).
#   * Migrate the live DB additively to schema head 117.
#   * Do NOT enable the long-running watcher (never calls `source-watch run --start`).
#   * Do NOT run `bootstrap ... apply` — only `--dry-run` (read-only) is executed here.
#   * Do NOT install launchd/cron/scheduled jobs.
#
# Safety design:
#   * Aborts on ANY error (set -eu) — a failed step never cascades into the next.
#   * FULL DB BACKUP is taken and verified BEFORE the migration runs.
#   * Migration is additive-only (v115/116/117 are CREATE ... IF NOT EXISTS; verified off-NAS).
#   * The internet-facing MCP never touches the live DB — it reads a refreshed RO snapshot.
#   * Read-only validation (status, tool count, source-watch dry-run) runs AFTER restart.
#
# Rollback anchors (see end of script output):
#   * Pre-migration DB backup path is printed and verified.
#   * The prior image is retagged as :prev before load, so `docker tag` + runner restart reverts.
# =============================================================================
set -eu

# ---- fixed paths / identity (repo-truth) ------------------------------------
DOCKER=/usr/local/bin/docker
IMAGE=hb-personal-assistant:nas
TARBALL=/tmp/hb-nas-bf2f30cc.tar.gz
UIDGID=1028:100

BASE=/volume2/personal-assistant
DB_DIR=$BASE/app-support/db
DB=$DB_DIR/hb-personal-assistant.sqlite
BACKUP_DIR=$BASE/app-support/db-backups
SNAP_DIR=$BASE/app-support/mcp-snapshot/db
RUNNER=$BASE/bin/hb-mcp-runner
COMPOSE=$BASE/deploy/nas/mcp/compose-mcp.yaml
CONTAINER=hb-personal-assistant-mcp

# ---- expected posture at head 117 (computed off-NAS from a fresh migrate) ----
EXPECT_HEAD=117
EXPECT_TABLES=581
EXPECT_VIEWS=2
EXPECT_OBJECTS=583

TS=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=$BACKUP_DIR/hb-personal-assistant.pre-v117.$TS.sqlite

say() { printf '\n=== %s ===\n' "$1"; }
die() { printf '\nFATAL: %s\n' "$1" >&2; exit 1; }

# Run a short-lived, network-isolated python off the deployed image, mounting the live DB
# dir at its canonical path (HB_NAS_RUNTIME storage guard requires /volume2 paths).
img_py() {  # img_py <<'PY' ... PY
  "$DOCKER" run --rm -i --network none --user "$UIDGID" \
    -e HB_NAS_RUNTIME=1 \
    -v "$DB_DIR:$DB_DIR:rw" \
    --entrypoint python3 "$IMAGE" -
}

# -----------------------------------------------------------------------------
say "0. Preconditions"
[ "$(id -u)" = "0" ] || die "must run as root (sudo)"
[ -x "$DOCKER" ] || die "docker not found at $DOCKER"
[ -f "$TARBALL" ] || die "image tarball not found at $TARBALL (ship it first)"
[ -f "$DB" ] || die "live DB not found at $DB"
[ -x "$RUNNER" ] || die "hb-mcp-runner not found/executable at $RUNNER"
[ -f "$COMPOSE" ] || die "compose file not found at $COMPOSE"
mkdir -p "$BACKUP_DIR" "$SNAP_DIR"
# free space must exceed live DB size (for the backup copy)
DBSZ=$(wc -c < "$DB")
AVAIL=$(df -k "$BACKUP_DIR" | awk 'NR==2{print $4*1024}')
printf 'live_db_bytes=%s  backup_fs_avail_bytes=%s\n' "$DBSZ" "$AVAIL"
[ "$AVAIL" -gt "$DBSZ" ] || die "insufficient free space for backup"
echo "preconditions ok"

# -----------------------------------------------------------------------------
say "1. Retag current image as :prev (rollback anchor)"
# Guard: never overwrite an existing :prev — on a re-run :nas is already the NEW image, and
# clobbering :prev would destroy the real rollback anchor captured on the first run.
if "$DOCKER" image inspect hb-personal-assistant:prev >/dev/null 2>&1; then
  echo "rollback anchor hb-personal-assistant:prev already exists — preserving it (not overwriting)"
elif "$DOCKER" image inspect "$IMAGE" >/dev/null 2>&1; then
  "$DOCKER" tag "$IMAGE" hb-personal-assistant:prev
  echo "tagged current $IMAGE -> hb-personal-assistant:prev"
else
  echo "no existing $IMAGE image to retag (first load) — continuing"
fi

# -----------------------------------------------------------------------------
say "2. Load new image from tarball (code deploy)"
gzip -t "$TARBALL" || die "tarball failed gzip integrity check"
"$DOCKER" load < "$TARBALL"
"$DOCKER" image inspect "$IMAGE" --format 'loaded image id={{.Id}}' || die "image not present after load"

# -----------------------------------------------------------------------------
say "3. Pre-migration backup + 4. additive migration -> head $EXPECT_HEAD"
BEFORE_HEAD=$(img_py <<PY
import sqlite3
print(sqlite3.connect("file:$DB?mode=ro", uri=True).execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0])
PY
)
printf 'live DB current schema head = %s\n' "$BEFORE_HEAD"
[ "$BEFORE_HEAD" -le "$EXPECT_HEAD" ] || die "live head $BEFORE_HEAD > target $EXPECT_HEAD (image older than DB — refusing to downgrade)"

if [ "$BEFORE_HEAD" = "$EXPECT_HEAD" ]; then
  echo "live DB already at head $EXPECT_HEAD — skipping backup+migrate (idempotent re-run)."
  echo "existing pre-migration backups:"
  ls -1 "$BACKUP_DIR"/hb-personal-assistant.pre-v117.*.sqlite 2>/dev/null || echo "  (none listed)"
else
  # ---- full DB backup BEFORE any mutation ----
  cp -p "$DB" "$BACKUP"
  chown "$UIDGID" "$BACKUP" 2>/dev/null || true
  BSZ=$(wc -c < "$BACKUP")
  printf 'backup written: %s (%s bytes)\n' "$BACKUP" "$BSZ"
  [ "$BSZ" = "$DBSZ" ] || die "backup size mismatch (src=$DBSZ backup=$BSZ)"
  # immutable=1: production DB is WAL-mode; a read-only open on a :ro mount otherwise needs the
  # -shm/-wal sidecars (not copied) and fails. immutable is correct/safe for a static backup.
  BQC=$("$DOCKER" run --rm -i --network none --user "$UIDGID" \
    -v "$BACKUP_DIR:$BACKUP_DIR:ro" --entrypoint python3 "$IMAGE" - <<PY
import sqlite3
print(sqlite3.connect("file:$BACKUP?mode=ro&immutable=1", uri=True).execute("PRAGMA quick_check").fetchone()[0])
PY
)
  printf 'backup quick_check = %s\n' "$BQC"
  [ "$BQC" = "ok" ] || die "backup quick_check != ok — aborting BEFORE migration"
  # ---- additive migration ----
  img_py <<PY
from hb_assistant.store.migrator import SQLiteMigrator, LATEST_SCHEMA_VERSION
head = SQLiteMigrator(db_path="$DB").apply()
print("migrated ->", head, "code_head", LATEST_SCHEMA_VERSION)
assert head == LATEST_SCHEMA_VERSION == $EXPECT_HEAD, "unexpected head after migrate"
PY
fi

# ---- post-state verification (always runs) ----
# Production carries runtime-created tables beyond the fresh-migrate schema (e.g. FTS5 shadow
# tables), so an EXACT object count is the wrong check. Verify the REAL success criteria: schema
# head, integrity, and that BOTH v117 tables now exist. Table count must be >= the fresh baseline
# (fewer would mean MISSING tables); extra tables are reported, not fatal.
AFTER=$(img_py <<PY
import sqlite3
c=sqlite3.connect("file:$DB?mode=ro", uri=True)
h=c.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
qc=c.execute("PRAGMA quick_check").fetchone()[0]
t=c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
v=c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
n=c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('source_index_bootstrap_state','source_index_reconciliation_runs')").fetchone()[0]
print(f"{h} {qc} {t} {v} {n}")
PY
)
set -- $AFTER
A_HEAD=$1; A_QC=$2; A_TABLES=$3; A_VIEWS=$4; A_V117=$5; A_OBJ=$((A_TABLES + A_VIEWS))
printf 'post-migrate: head=%s quick_check=%s tables=%s views=%s objects=%s v117_tables_present=%s/2\n' \
  "$A_HEAD" "$A_QC" "$A_TABLES" "$A_VIEWS" "$A_OBJ" "$A_V117"
[ "$A_HEAD" = "$EXPECT_HEAD" ]       || die "head $A_HEAD != $EXPECT_HEAD"
[ "$A_QC" = "ok" ]                   || die "quick_check != ok after migrate"
[ "$A_V117" = "2" ]                  || die "expected both v117 tables present, found $A_V117/2"
[ "$A_TABLES" -ge "$EXPECT_TABLES" ] || die "table_count $A_TABLES < fresh baseline $EXPECT_TABLES (missing tables)"
[ "$A_VIEWS" -ge "$EXPECT_VIEWS" ]   || die "view_count $A_VIEWS < $EXPECT_VIEWS"
if [ "$A_TABLES" -ne "$EXPECT_TABLES" ]; then
  echo "note: $((A_TABLES - EXPECT_TABLES)) production table(s) beyond the fresh-migrate baseline (runtime-created, e.g. FTS5 shadow tables) — benign; additive migration unaffected"
fi
echo "migration verified"

# -----------------------------------------------------------------------------
say "5. Refresh read-only MCP snapshot from migrated live DB"
chown "$UIDGID" "$SNAP_DIR" "$(dirname "$SNAP_DIR")" 2>/dev/null || true
"$DOCKER" run --rm -i --user "$UIDGID" \
  -v "$DB_DIR:/live/db:rw" -v "$SNAP_DIR:/snap/db:rw" \
  --entrypoint python3 "$IMAGE" - <<'PY'
import os, sqlite3, time
live="/live/db/hb-personal-assistant.sqlite"; final="/snap/db/hb-personal-assistant.sqlite"
tmp="/snap/db/.hb-personal-assistant.sqlite.tmp"
try: os.remove(tmp)
except FileNotFoundError: pass
t0=time.time()
src=sqlite3.connect(f"file:{live}?mode=ro", uri=True, timeout=60); dst=sqlite3.connect(tmp)
try:
    with dst: src.backup(dst)
finally:
    dst.close(); src.close()
os.replace(tmp, final); os.chmod(final, 0o640)
print(f"snapshot ok: {final} {os.path.getsize(final)} bytes in {time.time()-t0:.1f}s")
PY
SNAP_HEAD=$("$DOCKER" run --rm -i --network none --user "$UIDGID" \
  -v "$SNAP_DIR:/snap/db:ro" --entrypoint python3 "$IMAGE" - <<'PY'
import sqlite3
c=sqlite3.connect("file:/snap/db/hb-personal-assistant.sqlite?mode=ro&immutable=1", uri=True)
print(c.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], c.execute("PRAGMA quick_check").fetchone()[0])
PY
)
printf 'snapshot head/quick_check = %s\n' "$SNAP_HEAD"
echo "$SNAP_HEAD" | grep -q "^$EXPECT_HEAD ok$" || die "snapshot not at head $EXPECT_HEAD / not ok"

# -----------------------------------------------------------------------------
say "6. Restart MCP service on the new image"
sh "$BASE/deploy/nas/mcp/check-mcp-compose.sh" || die "compose static guard failed"
"$RUNNER" stop  || die "runner stop failed"
"$RUNNER" start || die "runner start failed"
sleep 3
"$RUNNER" status
echo "--- health ---"
"$RUNNER" health || die "health check failed"
echo "--- running image id (must equal loaded id) ---"
"$DOCKER" inspect "$CONTAINER" --format 'container image={{.Image}}'

# -----------------------------------------------------------------------------
say "7. Origin-auth still enforced (unauth POST /mcp must be 401)"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8765/mcp || echo "000")
printf 'unauth POST /mcp -> HTTP %s (expect 401)\n' "$CODE"
[ "$CODE" = "401" ] || echo "WARN: expected 401 from unauth /mcp (got $CODE) — review before exposing"

# -----------------------------------------------------------------------------
say "8. MCP tool-surface count (expect 87 tools / 14 groups) — best-effort, read-only"
set +e
"$DOCKER" exec "$CONTAINER" python3 - <<'PY'
try:
    from hb_assistant.nas_mcp.broker import ALL_ASSISTANT_TOOLS, ASSISTANT_TOOL_GROUPS
    print("assistant_tool_count =", len(ALL_ASSISTANT_TOOLS))
    print("assistant_group_count =", len(ASSISTANT_TOOL_GROUPS))
except Exception as e:
    print("tool-count probe error:", e)
PY
set -e

# -----------------------------------------------------------------------------
say "9. source-watch STATUS (read-only) — runs in the live container"
set +e
"$DOCKER" exec "$CONTAINER" hb-assistant source-watch status --json 2>&1 | head -80
echo ""
say "10. source-watch BOOTSTRAP DRY-RUN --all-roots (read-only; NO apply)"
"$DOCKER" exec "$CONTAINER" hb-assistant source-watch bootstrap --dry-run --all-roots --json 2>&1 | head -200
RC=$?
set -e
[ "$RC" = "0" ] || echo "NOTE: source-watch dry-run returned rc=$RC — capture output above; core deploy already succeeded."

# -----------------------------------------------------------------------------
say "DONE — deploy complete, watcher NOT enabled, NO bootstrap apply performed"
cat <<EOF

SUMMARY
  image tarball     : $TARBALL
  live DB head      : $BEFORE_HEAD -> $A_HEAD (verified, quick_check=$A_QC)
  schema objects    : $A_OBJ ($A_TABLES tables / $A_VIEWS views); v117 tables present=$A_V117/2
  pre-migration bak : $(ls -1 "$BACKUP_DIR"/hb-personal-assistant.pre-v117.*.sqlite 2>/dev/null | tail -1)
  snapshot          : refreshed to head $EXPECT_HEAD
  service           : hb-personal-assistant-mcp restarted on new image (127.0.0.1:8765)

NEXT (requires SEPARATE authorization — do NOT run now):
  hb-assistant source-watch bootstrap --all-roots         # apply, after dry-run review
  (watcher enable + scheduled snapshot cron are also deferred)

ROLLBACK if needed:
  $DOCKER tag hb-personal-assistant:prev $IMAGE && sudo $RUNNER stop && sudo $RUNNER start
  # and restore DB from: $BACKUP
EOF
