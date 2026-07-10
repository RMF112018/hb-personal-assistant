#!/bin/sh
# Live 40-prompt audit regression probe — run ON THE NAS after deploy.
# Usage: sudo sh /tmp/hb-live-40-prompt-probe.sh
set -eu

DOCKER=/usr/local/bin/docker
CONTAINER=hb-personal-assistant-mcp

say() { printf '\n=== %s ===\n' "$1"; }
die() { printf '\nFATAL: %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "must run as root (sudo)"
[ -x "$DOCKER" ] || die "docker not found"

say "Runtime identity"
"$DOCKER" exec "$CONTAINER" python3 - <<'PY'
from hb_assistant.nas_mcp.broker import runtime_commit, runtime_identity
print("runtime_commit=", runtime_commit())
print("runtime_identity=", runtime_identity())
PY

say "40-case audit matrix (in-container broker)"
set +e
"$DOCKER" exec "$CONTAINER" python3 - <<'PY'
import json
from pathlib import Path

from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.config import NasMcpConfig

# Matrix is baked into the image via COPY . /app in deploy/nas/Dockerfile
matrix_path = Path("/app/scripts/audit-route-regression-matrix.json")
if not matrix_path.is_file():
    raise SystemExit(f"matrix not found: {matrix_path}")

import sys
sys.path.insert(0, str(matrix_path.parent))
from route_proof_lib import evaluate_route_expectations, route_actual

cases = json.loads(matrix_path.read_text(encoding="utf-8"))
broker = NasMcpBroker(NasMcpConfig.from_env())
failures = []
for case in cases:
    payload = broker.dispatch("pa_prompt_route", {"prompt": case["prompt"]})
    if not payload.get("ok"):
        failures.append((case["id"], "dispatch_failed", payload.get("error") or payload.get("safe_message")))
        continue
    actual = route_actual(payload["result"])
    mismatches = evaluate_route_expectations(case.get("expected") or {}, actual)
    if mismatches:
        failures.append((case["id"], mismatches, actual.get("workflow")))
    else:
        print("PASS", case["id"], "->", actual.get("workflow"))

print()
print(f"total={len(cases)} pass={len(cases)-len(failures)} fail={len(failures)}")
if failures:
    print("FAILURES:")
    for f in failures:
        print(" ", f)
    raise SystemExit(1)
print("LIVE 40-PROMPT PROBE PASSED")
PY
RC=$?
set -e
[ "$RC" = "0" ] || die "live 40-prompt probe failed (exit $RC)"

say "Failure envelope mapping spot-check (R5)"
"$DOCKER" exec "$CONTAINER" python3 - <<'PY'
from hb_assistant.nas_mcp.failure_envelope import gateway_plugin_failure, map_deny_reason
from hb_assistant.obsidian_mcp.tool_metadata_types import PluginFailureStage

stage, code, _ = map_deny_reason("not_an_allowlisted_assistant_tool:raw_sql")
assert stage == PluginFailureStage.GATEWAY_ALLOWLIST and code == "gateway_denied"
stage, code, _ = map_deny_reason("tool_not_registered: assistant_output_stage")
assert stage == PluginFailureStage.BROKER_DISPATCH and code == "tool_not_registered"
env = gateway_plugin_failure(tool="raw_sql", reason="not_an_allowlisted_assistant_tool:raw_sql",
                             gateway_tool="hb_assistant_tool_query")
assert env["ok"] is False and env["reached_broker"] is False
print("failure envelope R5 ok")
PY

say "DONE"