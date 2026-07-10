#!/bin/sh
# =============================================================================
# hb-deploy-routing-remediation.sh — Controlled NAS code-only deploy (schema 119)
# =============================================================================
# RUN ON THE NAS as:   sudo sh /tmp/hb-deploy-routing-remediation.sh
#
# Prerequisite: set DEPLOY_SHA below to the landed remediation commit SHA.
# Authorized scope:
#   * Deploy code only (load new image, restart MCP service).
#   * Inject HB_RUNTIME_COMMIT for exact deploy SHA provenance.
#   * Refresh RO MCP snapshot (no live-DB migration — already at head 119).
#   * Do NOT enable watcher, bootstrap apply, or manifest auto-promote/auto-stage.
# =============================================================================
set -eu

DOCKER=/usr/local/bin/docker
IMAGE=hb-personal-assistant:nas
# >>> OPERATOR: replace with landed remediation SHA after commit <<<
DEPLOY_SHA=REPLACE_WITH_LANDED_SHA
TARBALL=/tmp/hb-nas-${DEPLOY_SHA%%????????????????????????????????}.tar.gz
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

[ "$DEPLOY_SHA" != "REPLACE_WITH_LANDED_SHA" ] || die "set DEPLOY_SHA to the landed remediation commit"

img_py() {
  "$DOCKER" run --rm -i --network none --user "$UIDGID" \
    -e HB_NAS_RUNTIME=1 \
    -v "$DB_DIR:$DB_DIR:ro" \
    --entrypoint python3 "$IMAGE" -
}

say "0. Preconditions"
[ "$(id -u)" = "0" ] || die "must run as root (sudo)"
[ -x "$DOCKER" ] || die "docker not found at $DOCKER"
[ -f "$TARBALL" ] || die "image tarball not found at $TARBALL (expected $TARBALL)"
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

say "3. Verify live DB at schema head (no migration this deploy)"
BEFORE_HEAD=$(img_py <<PY
import sqlite3
print(sqlite3.connect("file:$DB?mode=ro", uri=True).execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0])
PY
)
printf 'live DB head=%s (expect %s)\n' "$BEFORE_HEAD" "$EXPECT_HEAD"
[ "$BEFORE_HEAD" = "$EXPECT_HEAD" ] || die "unexpected schema head — stop and review before deploy"

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
SNAP_HEAD=$("$DOCKER" run --rm -i --network none --user "$UIDGID" \
  -v "$SNAP_DIR:/snap/db:ro" --entrypoint python3 "$IMAGE" - <<'PY'
import sqlite3
c=sqlite3.connect("file:/snap/db/hb-personal-assistant.sqlite?mode=ro&immutable=1", uri=True)
print(c.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], c.execute("PRAGMA quick_check").fetchone()[0])
PY
)
printf 'snapshot head/qc=%s\n' "$SNAP_HEAD"
echo "$SNAP_HEAD" | grep -q "^$EXPECT_HEAD ok$" || die "snapshot not at head"

say "5. Restart MCP service"
sh "$BASE/deploy/nas/mcp/check-mcp-compose.sh" || die "compose guard failed"
"$RUNNER" stop || die "runner stop failed"
"$RUNNER" start || die "runner start failed"
sleep 60
"$RUNNER" status || true
"$RUNNER" health || die "health check failed"
"$DOCKER" inspect "$CONTAINER" --format 'container={{.Id}} image={{.Image}}'

say "6. Runtime identity"
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

say "7. Routing smoke (in-container)"
set +e
"$DOCKER" exec "$CONTAINER" python3 - <<'PY'
from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.config import NasMcpConfig
b = NasMcpBroker(NasMcpConfig.from_env())
checks = [
    ("Search my work files.", "source_file_search", True),
    ("Search the vault for meeting notes.", "vault_note_search", True),
    ("Do not promote anything.", "apply_canonical_promotion", False),
]
for prompt, bad_wf, expect_exec in checks:
    r = b.dispatch("pa_prompt_route", {"prompt": prompt})["result"]
    wf = r.get("recommended_workflow")
    a = r.get("authorization") or {}
    ok = (wf != bad_wf) if not expect_exec else (wf in ("source_file_search", "vault_note_search"))
    if expect_exec:
        ok = ok and a.get("currently_executable") is True
    print(("PASS" if ok else "FAIL"), prompt, "->", wf, a.get("currently_executable"))
    assert ok, (prompt, wf, a)
print("routing smoke ok")
PY
set -e

say "8. Origin-auth (unauth POST /mcp -> 401)"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8765/mcp || echo "000")
printf 'unauth POST /mcp -> HTTP %s\n' "$CODE"
[ "$CODE" = "401" ] || echo "WARN: expected 401"

say "DONE"
cat <<EOF
SUMMARY
  deploy_sha        : $DEPLOY_SHA
  image tarball     : $TARBALL
  loaded_image_id   : $LOADED_ID
  live DB head      : $BEFORE_HEAD (unchanged)
  compose backup    : $COMPOSE_BAK
NEXT
  run 09-live-40-prompt-probe.sh on NAS
  manual manifest refresh per 08-operator-manifest-refresh.md
ROLLBACK
  docker tag hb-personal-assistant:prev hb-personal-assistant:nas + runner stop/start
EOF