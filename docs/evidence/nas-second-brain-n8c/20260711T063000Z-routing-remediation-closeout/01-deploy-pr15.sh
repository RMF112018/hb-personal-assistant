#!/bin/sh
# NAS deploy — routing audit remediation (PR-16..PR-20 wave, code-only schema 119)
# RUN ON THE NAS: sudo sh /tmp/01-deploy-pr15.sh
set -eu

DOCKER=/usr/local/bin/docker
IMAGE=hb-personal-assistant:nas
DEPLOY_SHA=931f69f04c697c4082f65fbf90ab2b6ae6c81af9
TARBALL=/tmp/hb-nas-931f69f0.tar.gz
UIDGID=1028:100

BASE=/volume2/personal-assistant
DB_DIR=$BASE/app-support/db
DB=$DB_DIR/hb-personal-assistant.sqlite
SNAP_DIR=$BASE/app-support/mcp-snapshot/db
RUNNER=$BASE/bin/hb-mcp-runner
COMPOSE=$BASE/deploy/nas/mcp/compose-mcp.yaml
CONTAINER=hb-personal-assistant-mcp

EXPECT_HEAD=119

say() { printf '\n=== %s ===\n' "$1"; }
die() { printf '\nFATAL: %s\n' "$1" >&2; exit 1; }

img_py() {
  "$DOCKER" run --rm -i --network none --user "$UIDGID" \
    -e HB_NAS_RUNTIME=1 \
    -v "$DB_DIR:$DB_DIR:ro" \
    --entrypoint python3 "$IMAGE" -
}

say "0. Preconditions"
[ "$(id -u)" = "0" ] || die "must run as root (sudo)"
[ -x "$DOCKER" ] || die "docker not found at $DOCKER"
[ -f "$TARBALL" ] || die "image tarball not found at $TARBALL"
[ -f "$DB" ] || die "live DB not found at $DB"
[ -x "$RUNNER" ] || die "hb-mcp-runner not found at $RUNNER"
[ -f "$COMPOSE" ] || die "compose file not found at $COMPOSE"
mkdir -p "$SNAP_DIR"
echo "preconditions ok"

say "0b. Backup compose + inject HB_RUNTIME_COMMIT"
TS=$(date -u +%Y%m%dT%H%M%SZ)
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

say "3. Verify live DB at schema head (no migration)"
BEFORE_HEAD=$(img_py <<PY
import sqlite3
print(sqlite3.connect("file:$DB?mode=ro", uri=True).execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0])
PY
)
printf 'live DB head=%s (expect %s)\n' "$BEFORE_HEAD" "$EXPECT_HEAD"
[ "$BEFORE_HEAD" = "$EXPECT_HEAD" ] || die "unexpected schema head"

say "3b. Schema lineage (RO snapshot vs RW workspace)"
WORKSPACE_DB=$BASE/app-support/mcp-workspace/db/hb-personal-assistant.sqlite
LATEST_HEAD=$(img_py <<PY
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION
print(LATEST_SCHEMA_VERSION)
PY
)
# Host-side read: img_py only mounts the live DB dir, not mcp-workspace.
if [ -f "$WORKSPACE_DB" ]; then
  WORKSPACE_HEAD=$(sqlite3 "$WORKSPACE_DB" "SELECT MAX(version) FROM schema_migrations;")
else
  WORKSPACE_HEAD="(absent — will auto-migrate to $LATEST_HEAD on first start)"
fi
printf 'RO snapshot/live head=%s (deploy expect %s)\n' "$BEFORE_HEAD" "$EXPECT_HEAD"
printf 'RW workspace head=%s (repo LATEST_SCHEMA_VERSION=%s)\n' "$WORKSPACE_HEAD" "$LATEST_HEAD"

say "4. Refresh RO MCP snapshot"
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

say "5. Restart MCP service"
sh "$BASE/deploy/nas/mcp/check-mcp-compose.sh" || die "compose guard failed"
"$RUNNER" stop || die "runner stop failed"
"$RUNNER" start || die "runner start failed"
sleep 60
"$RUNNER" health || die "health check failed"

say "6. Runtime identity"
"$DOCKER" exec "$CONTAINER" python3 -c \
  "from hb_assistant.nas_mcp.broker import runtime_commit; rc=runtime_commit(); assert rc == '$DEPLOY_SHA', f'mismatch: {rc}'; print('runtime commit ok:', rc)"

say "7. Freshness parity smoke (expected stale until manifest refresh)"
"$DOCKER" exec "$CONTAINER" python3 -c \
  'from hb_assistant.nas_mcp.broker import NasMcpBroker; from hb_assistant.nas_mcp.config import NasMcpConfig; b=NasMcpBroker(NasMcpConfig.from_env()); fr=b.dispatch("pa_tool_surface_freshness_check",{})["result"]; print("stale", fr.get("stale"), "family_changed", len(fr.get("family_changed_tools") or []), "class_changed", len(fr.get("class_changed_tools") or [])); stale=fr.get("stale");
import sys
if stale:
    print("NOTE: surface stale before manifest refresh — proceed to 02-manifest-refresh-pr15.sh", file=sys.stderr)
else:
    print("surface fresh")'

say "DONE — next: sudo sh /tmp/02-manifest-refresh-pr15.sh then /tmp/03-manifest-verify-pr15.sh and /tmp/04-live-50-prompt-corpus.sh"
cat <<EOF
SUMMARY
  deploy_sha      : $DEPLOY_SHA
  tarball         : $TARBALL
  loaded_image_id : $LOADED_ID
EOF