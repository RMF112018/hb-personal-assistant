#!/bin/sh
# Live 50-prompt audit corpus replay — run ON THE NAS after deploy + manifest refresh.
# Usage: sudo sh /tmp/04-live-50-prompt-corpus.sh
set -eu

DOCKER=/usr/local/bin/docker
CONTAINER=hb-personal-assistant-mcp
DEPLOY_SHA=542307fc6fc87b7a5713b8917e861a576a03c96c
CORPUS=/app/tests/fixtures/prompt_routing_audit_corpus_v1.json
REPORT=/tmp/live-corpus-v1-report.json
REPORT_REQUIRED=/tmp/live-corpus-v1-required-report.json

say() { printf '\n=== %s ===\n' "$1"; }
die() { printf '\nFATAL: %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "must run as root (sudo)"
[ -x "$DOCKER" ] || die "docker not found"

say "Runtime identity (RT-01 Tier B)"
"$DOCKER" exec "$CONTAINER" python3 -c \
  'from hb_assistant.nas_mcp.broker import runtime_commit, runtime_identity; from hb_assistant.obsidian_mcp.tool_metadata_types import RuntimeIdentityKind; ri=runtime_identity(); print("runtime_commit=", runtime_commit()); print("runtime_identity=", ri); assert ri.runtime_identity_kind == RuntimeIdentityKind.EXACT_UNVERIFIED_STAMP; assert ri.runtime_identity_verified is False; assert ri.runtime_image_digest and ri.runtime_image_digest.startswith("sha256:")'
RC=$("$DOCKER" exec "$CONTAINER" python3 -c \
  "from hb_assistant.nas_mcp.broker import runtime_commit; rc=runtime_commit(); print(rc); assert rc == '$DEPLOY_SHA', rc" 2>&1) || die "runtime commit mismatch: $RC"
echo "runtime commit ok: $RC"
"$DOCKER" exec "$CONTAINER" test ! -e /app/.claude
echo "forbidden-path scan ok"

say "Required corpus rows (47) — must pass"
set +e
"$DOCKER" exec "$CONTAINER" python3 /app/scripts/run-audit-route-regression-matrix.py \
  --matrix "$CORPUS" --from-env --enforcement required --out "$REPORT_REQUIRED"
RC=$?
set -e
"$DOCKER" exec "$CONTAINER" cat "$REPORT_REQUIRED" || true
[ "$RC" = "0" ] || die "live required-corpus probe failed (exit $RC)"

say "Full 50-case corpus (informational; accepted_partial may differ)"
set +e
"$DOCKER" exec "$CONTAINER" python3 /app/scripts/run-audit-route-regression-matrix.py \
  --matrix "$CORPUS" --from-env --out "$REPORT"
RC=$?
set -e
"$DOCKER" exec "$CONTAINER" cat "$REPORT" || true
[ "$RC" = "0" ] || echo "WARN: full corpus had failures — review accepted_partial rows" >&2

say "HIGH-row spot checks"
"$DOCKER" exec "$CONTAINER" python3 -c \
  'from hb_assistant.nas_mcp.broker import NasMcpBroker; from hb_assistant.nas_mcp.config import NasMcpConfig; b=NasMcpBroker(NasMcpConfig.from_env());
checks=[
 ("row25", {"prompt": "Show me decision `DEC-20260708-7847F4`."}, "assistant_get_decision"),
 ("row36", {"prompt": "Find files and notes related to `23-435-01`."}, "assistant_source_file_search"),
 ("row01", {"prompt": "Attached read-only audit objective"}, "hb_mcp_status"),
]
for label, args, tool in checks:
 r=b.dispatch("pa_prompt_route", args)["result"]; ns=(r.get("next_step") or {}).get("tool"); a=r.get("authorization") or {}; print(label, r.get("recommended_workflow"), ns, a.get("currently_executable"), a.get("execution_blocked_reason"));
 assert ns == tool, (label, ns, tool)'

say "DONE"