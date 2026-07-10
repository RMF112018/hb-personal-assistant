#!/bin/sh
# =============================================================================
# hb-deploy-v119.sh — Controlled NAS deploy of merged main @ 14dfc3a0
# =============================================================================
# RUN ON THE NAS as:   sudo sh /tmp/hb-deploy-v119.sh
#
# Authorized scope:
#   * Deploy code only (load new image, restart MCP service).
#   * Migrate the live DB additively to schema head 119 (V118 manifest + V119 bootstrap runs).
#   * Inject HB_RUNTIME_COMMIT for exact deploy SHA provenance.
#   * Do NOT enable watcher, bootstrap apply, or manifest auto-promote/auto-stage.
# =============================================================================
set -eu

DOCKER=/usr/local/bin/docker
IMAGE=hb-personal-assistant:nas
TARBALL=/tmp/hb-nas-14dfc3a0.tar.gz
DEPLOY_SHA=14dfc3a0e007475543e19f1d8efd999b23f3e28b
UIDGID=1028:100

BASE=/volume2/personal-assistant
DB_DIR=$BASE/app-support/db
DB=$DB_DIR/hb-personal-assistant.sqlite
BACKUP_DIR=$BASE/app-support/db-backups
SNAP_DIR=$BASE/app-support/mcp-snapshot/db
RUNNER=$BASE/bin/hb-mcp-runner
COMPOSE=$BASE/deploy/nas/mcp/compose-mcp.yaml
CONTAINER=hb-personal-assistant-mcp

EXPECT_HEAD=119
EXPECT_TABLES=582
EXPECT_VIEWS=2

TS=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=$BACKUP_DIR/hb-personal-assistant.pre-v119.$TS.sqlite

say() { printf '\n=== %s ===\n' "$1"; }
die() { printf '\nFATAL: %s\n' "$1" >&2; exit 1; }

img_py() {
  "$DOCKER" run --rm -i --network none --user "$UIDGID" \
    -e HB_NAS_RUNTIME=1 \
    -v "$DB_DIR:$DB_DIR:rw" \
    --entrypoint python3 "$IMAGE" -
}

say "0. Preconditions"
[ "$(id -u)" = "0" ] || die "must run as root (sudo)"
[ -x "$DOCKER" ] || die "docker not found at $DOCKER"
[ -f "$TARBALL" ] || die "image tarball not found at $TARBALL"
[ -f "$DB" ] || die "live DB not found at $DB"
[ -x "$RUNNER" ] || die "hb-mcp-runner not found at $RUNNER"
[ -f "$COMPOSE" ] || die "compose file not found at $COMPOSE"
mkdir -p "$BACKUP_DIR" "$SNAP_DIR"
DBSZ=$(wc -c < "$DB")
AVAIL=$(df -k "$BACKUP_DIR" | awk 'NR==2{print $4*1024}')
printf 'live_db_bytes=%s backup_fs_avail_bytes=%s\n' "$DBSZ" "$AVAIL"
[ "$AVAIL" -gt "$DBSZ" ] || die "insufficient free space for backup"
echo "preconditions ok"

say "0b. Backup compose + inject HB_RUNTIME_COMMIT"
COMPOSE_BAK=$COMPOSE.bak-$TS
cp -p "$COMPOSE" "$COMPOSE_BAK"
if grep -q 'HB_RUNTIME_COMMIT:' "$COMPOSE"; then
  sed -i "s|HB_RUNTIME_COMMIT:.*|HB_RUNTIME_COMMIT: \"$DEPLOY_SHA\"|" "$COMPOSE"
else
  sed -i "/PYTHONUNBUFFERED: \"1\"/a\\
      HB_RUNTIME_COMMIT: \"$DEPLOY_SHA\"" "$COMPOSE"
fi
grep HB_RUNTIME_COMMIT "$COMPOSE" || die "HB_RUNTIME_COMMIT not present in compose after patch"
echo "compose backup: $COMPOSE_BAK"

say "1. Retag current image as :prev (rollback anchor)"
if "$DOCKER" image inspect hb-personal-assistant:prev >/dev/null 2>&1; then
  echo "rollback anchor hb-personal-assistant:prev already exists — preserving"
elif "$DOCKER" image inspect "$IMAGE" >/dev/null 2>&1; then
  "$DOCKER" tag "$IMAGE" hb-personal-assistant:prev
  echo "tagged current $IMAGE -> hb-personal-assistant:prev"
else
  echo "no existing $IMAGE image to retag — continuing"
fi

say "2. Load new image from tarball"
gzip -t "$TARBALL" || die "tarball failed gzip integrity check"
"$DOCKER" load < "$TARBALL"
LOADED_ID=$("$DOCKER" image inspect "$IMAGE" --format '{{.Id}}')
printf 'loaded image id=%s\n' "$LOADED_ID"

say "3. Pre-migration backup + 4. additive migration -> head $EXPECT_HEAD"
BEFORE_HEAD=$(img_py <<PY
import sqlite3
print(sqlite3.connect("file:$DB?mode=ro", uri=True).execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0])
PY
)
MANIFEST_ROWS_BEFORE=$(img_py <<PY
import sqlite3
c=sqlite3.connect("file:$DB?mode=ro", uri=True)
try:
    print(c.execute("SELECT COUNT(*) FROM pa_client_tool_manifests").fetchone()[0])
except Exception:
    print(0)
PY
)
printf 'live DB head=%s manifest_rows=%s\n' "$BEFORE_HEAD" "$MANIFEST_ROWS_BEFORE"
[ "$BEFORE_HEAD" -le "$EXPECT_HEAD" ] || die "live head $BEFORE_HEAD > target $EXPECT_HEAD"

if [ "$BEFORE_HEAD" = "$EXPECT_HEAD" ]; then
  echo "live DB already at head $EXPECT_HEAD — skipping backup+migrate"
  ls -1 "$BACKUP_DIR"/hb-personal-assistant.pre-v119.*.sqlite 2>/dev/null || true
else
  cp -p "$DB" "$BACKUP"
  chown "$UIDGID" "$BACKUP" 2>/dev/null || true
  BSZ=$(wc -c < "$BACKUP")
  printf 'backup written: %s (%s bytes)\n' "$BACKUP" "$BSZ"
  [ "$BSZ" = "$DBSZ" ] || die "backup size mismatch"
  BQC=$("$DOCKER" run --rm -i --network none --user "$UIDGID" \
    -v "$BACKUP_DIR:$BACKUP_DIR:ro" --entrypoint python3 "$IMAGE" - <<PY
import sqlite3
print(sqlite3.connect("file:$BACKUP?mode=ro&immutable=1", uri=True).execute("PRAGMA quick_check").fetchone()[0])
PY
)
  printf 'backup quick_check=%s\n' "$BQC"
  [ "$BQC" = "ok" ] || die "backup quick_check != ok"
  img_py <<PY
from hb_assistant.store.migrator import SQLiteMigrator, LATEST_SCHEMA_VERSION
head = SQLiteMigrator(db_path="$DB").apply()
print("migrated ->", head, "code_head", LATEST_SCHEMA_VERSION)
assert head == LATEST_SCHEMA_VERSION == $EXPECT_HEAD
PY
fi

say "4b. Post-migrate verification"
AFTER=$(img_py <<PY
import sqlite3
c=sqlite3.connect("file:$DB?mode=ro", uri=True)
h=c.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
qc=c.execute("PRAGMA quick_check").fetchone()[0]
t=c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
v=c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
v117=c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('source_index_bootstrap_state','source_index_reconciliation_runs')").fetchone()[0]
v119=c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='source_index_bootstrap_runs'").fetchone()[0]
v118cols=c.execute("SELECT COUNT(*) FROM pragma_table_info('pa_client_tool_manifests') WHERE name IN ('manifest_schema_version','semantic_surface_checksum')").fetchone()[0]
mrows=c.execute("SELECT COUNT(*) FROM pa_client_tool_manifests").fetchone()[0]
print(f"{h} {qc} {t} {v} {v117} {v119} {v118cols} {mrows}")
PY
)
set -- $AFTER
A_HEAD=$1; A_QC=$2; A_TABLES=$3; A_VIEWS=$4; A_V117=$5; A_V119=$6; A_V118COLS=$7; A_MROWS=$8
A_OBJ=$((A_TABLES + A_VIEWS))
printf 'post-migrate: head=%s qc=%s tables=%s views=%s v117_tables=%s/2 v119_table=%s v118_cols=%s manifest_rows=%s\n' \
  "$A_HEAD" "$A_QC" "$A_TABLES" "$A_VIEWS" "$A_V117" "$A_V119" "$A_V118COLS" "$A_MROWS"
[ "$A_HEAD" = "$EXPECT_HEAD" ] || die "head mismatch"
[ "$A_QC" = "ok" ] || die "quick_check != ok"
[ "$A_V117" = "2" ] || die "v117 tables missing"
[ "$A_V119" = "1" ] || die "v119 table missing"
[ "$A_V118COLS" = "2" ] || die "v118 manifest columns missing"
[ "$A_MROWS" = "$MANIFEST_ROWS_BEFORE" ] || die "manifest row count changed $MANIFEST_ROWS_BEFORE -> $A_MROWS"
[ "$A_TABLES" -ge "$EXPECT_TABLES" ] || die "table_count below baseline"
[ "$A_VIEWS" -ge "$EXPECT_VIEWS" ] || die "view_count below baseline"
echo "migration verified"

say "5. Refresh RO MCP snapshot"
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
print(f"snapshot ok: {os.path.getsize(final)} bytes in {time.time()-t0:.1f}s")
PY
SNAP_HEAD=$("$DOCKER" run --rm -i --network none --user "$UIDGID" \
  -v "$SNAP_DIR:/snap/db:ro" --entrypoint python3 "$IMAGE" - <<'PY'
import sqlite3
c=sqlite3.connect("file:/snap/db/hb-personal-assistant.sqlite?mode=ro&immutable=1", uri=True)
print(c.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], c.execute("PRAGMA quick_check").fetchone()[0])
PY
)
printf 'snapshot head/qc=%s\n' "$SNAP_HEAD"
echo "$SNAP_HEAD" | grep -q "^$EXPECT_HEAD ok$" || die "snapshot not at head"

say "6. Restart MCP service"
sh "$BASE/deploy/nas/mcp/check-mcp-compose.sh" || die "compose guard failed"
"$RUNNER" stop || die "runner stop failed"
"$RUNNER" start || die "runner start failed"
sleep 60
"$RUNNER" status || true
"$RUNNER" health || die "health check failed"
"$DOCKER" inspect "$CONTAINER" --format 'container={{.Id}} image={{.Image}}'

say "7. Runtime identity"
set +e
"$DOCKER" exec "$CONTAINER" python3 - <<PY
from hb_assistant.nas_mcp.broker import runtime_identity, runtime_commit
ri = runtime_identity(); rc = runtime_commit()
print("runtime_identity=", ri)
print("runtime_commit=", rc)
assert rc == "$DEPLOY_SHA", f"commit mismatch: {rc}"
PY
RC_ID=$?
set -e
[ "$RC_ID" = "0" ] || die "runtime identity check failed"

say "8. Origin-auth (unauth POST /mcp -> 401)"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8765/mcp || echo "000")
printf 'unauth POST /mcp -> HTTP %s\n' "$CODE"
[ "$CODE" = "401" ] || echo "WARN: expected 401"

say "9. Tool surface count"
set +e
"$DOCKER" exec "$CONTAINER" python3 - <<'PY'
from hb_assistant.nas_mcp.broker import ALL_ASSISTANT_TOOLS, ASSISTANT_TOOL_GROUPS
print("assistant_tool_count =", len(ALL_ASSISTANT_TOOLS))
print("assistant_group_count =", len(ASSISTANT_TOOL_GROUPS))
PY
set -e

say "10. source-watch dry-run (read-only)"
set +e
"$DOCKER" exec "$CONTAINER" hb-assistant source-watch status --json 2>&1 | head -40
"$DOCKER" exec "$CONTAINER" hb-assistant source-watch bootstrap --dry-run --all-roots --json 2>&1 | head -80
set -e

say "DONE"
cat <<EOF
SUMMARY
  deploy_sha        : $DEPLOY_SHA
  image tarball     : $TARBALL
  loaded_image_id   : $LOADED_ID
  live DB head      : $BEFORE_HEAD -> $A_HEAD (qc=$A_QC)
  manifest_rows     : $MANIFEST_ROWS_BEFORE -> $A_MROWS
  pre-migration bak : $BACKUP
  compose backup    : $COMPOSE_BAK
ROLLBACK:
  restore DB from backup + docker tag :prev :nas + runner stop/start
EOF