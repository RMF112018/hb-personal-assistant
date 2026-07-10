#!/bin/sh
# Live 40-prompt audit regression probe — run ON THE NAS after deploy.
# Usage: sudo sh /tmp/hb-live-40-prompt-probe.sh
# Note: Synology docker exec drops heredoc stdin — use python -c / baked scripts only.
set -eu

DOCKER=/usr/local/bin/docker
CONTAINER=hb-personal-assistant-mcp
DEPLOY_SHA=f53cba1c7b4bcba0c5d7bb82aa63694c3041f0e3

say() { printf '\n=== %s ===\n' "$1"; }
die() { printf '\nFATAL: %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "must run as root (sudo)"
[ -x "$DOCKER" ] || die "docker not found"

say "Runtime identity"
"$DOCKER" exec "$CONTAINER" python3 -c \
  'from hb_assistant.nas_mcp.broker import runtime_commit, runtime_identity; print("runtime_commit=", runtime_commit()); print("runtime_identity=", runtime_identity())'
RC=$("$DOCKER" exec "$CONTAINER" python3 -c \
  "from hb_assistant.nas_mcp.broker import runtime_commit; rc=runtime_commit(); print(rc); assert rc == '$DEPLOY_SHA', rc" 2>&1) || die "runtime commit mismatch: $RC"
echo "runtime commit ok: $RC"

say "40-case audit matrix (in-container broker)"
set +e
"$DOCKER" exec "$CONTAINER" python3 /app/scripts/run-audit-route-regression-matrix.py --from-env
RC=$?
set -e
[ "$RC" = "0" ] || die "live 40-prompt probe failed (exit $RC)"

say "Failure envelope mapping spot-check (R5)"
"$DOCKER" exec "$CONTAINER" python3 -c \
  'from hb_assistant.nas_mcp.failure_envelope import gateway_plugin_failure, map_deny_reason; from hb_assistant.obsidian_mcp.tool_metadata_types import PluginFailureStage; stage, code, _ = map_deny_reason("not_an_allowlisted_assistant_tool:raw_sql"); assert stage == PluginFailureStage.GATEWAY_ALLOWLIST and code == "gateway_denied"; stage, code, _ = map_deny_reason("tool_not_registered: assistant_output_stage"); assert stage == PluginFailureStage.BROKER_DISPATCH and code == "tool_not_registered"; env = gateway_plugin_failure(tool="raw_sql", reason="not_an_allowlisted_assistant_tool:raw_sql", gateway_tool="hb_assistant_tool_query"); assert env["ok"] is False and env["reached_broker"] is False; print("failure envelope R5 ok")'

say "DONE"