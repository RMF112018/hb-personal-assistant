#!/bin/sh
# Manual client-tool manifest refresh — stage → promote → verify.
# RUN ON THE NAS: sudo sh /tmp/hb-manifest-refresh.sh
set -eu

DOCKER=/usr/local/bin/docker
CONTAINER=hb-personal-assistant-mcp
EXPECT_PUBLISHED=15

say() { printf '\n=== %s ===\n' "$1"; }
die() { printf '\nFATAL: %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "must run as root (sudo)"
[ -x "$DOCKER" ] || die "docker not found"

say "0. Preconditions"
"$DOCKER" inspect "$CONTAINER" >/dev/null 2>&1 || die "container $CONTAINER not running"
echo "container ok"

say "1. Freshness + review plan (pre)"
"$DOCKER" exec "$CONTAINER" python3 -c \
  'import json; from hb_assistant.nas_mcp.broker import NasMcpBroker; from hb_assistant.nas_mcp.config import NasMcpConfig; b=NasMcpBroker(NasMcpConfig.from_env());
for t in ("pa_tool_surface_freshness_check","pa_tool_manifest_freshness_check","pa_tool_manifest_review_plan"):
 r=b.dispatch(t,{}); print(t, json.dumps(r.get("result") or r, sort_keys=True))'

say "2. Stage manifest refresh"
STAGE_OUT=$("$DOCKER" exec "$CONTAINER" python3 -c \
  'import json; from hb_assistant.nas_mcp.broker import NasMcpBroker; from hb_assistant.nas_mcp.config import NasMcpConfig; b=NasMcpBroker(NasMcpConfig.from_env()); r=b.dispatch("pa_tool_manifest_refresh_stage",{}); print(json.dumps(r))')
echo "$STAGE_OUT"
echo "$STAGE_OUT" | grep -q '"ok": true' || die "stage failed"
REFRESH_ID=$(echo "$STAGE_OUT" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["result"]["refresh_proposal_id"])')
APPROVAL_ID=$(echo "$STAGE_OUT" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["result"]["operator_approval_id"])')
printf 'refresh_proposal_id=%s\noperator_approval_id=%s\n' "$REFRESH_ID" "$APPROVAL_ID"

say "3. Promote (server-minted approval)"
PROMOTE_OUT=$("$DOCKER" exec "$CONTAINER" python3 -c \
  "import json; from hb_assistant.nas_mcp.broker import NasMcpBroker; from hb_assistant.nas_mcp.config import NasMcpConfig; b=NasMcpBroker(NasMcpConfig.from_env()); r=b.dispatch('pa_tool_manifest_refresh_promote', {'refresh_proposal_id': '$REFRESH_ID', 'operator_approval_id': '$APPROVAL_ID'}); print(json.dumps(r))")
echo "$PROMOTE_OUT"
echo "$PROMOTE_OUT" | grep -q '"ok": true' || die "promote failed"

say "4. Verify active manifest"
"$DOCKER" exec "$CONTAINER" python3 -c \
  "import json; from hb_assistant.nas_mcp.broker import NasMcpBroker; from hb_assistant.nas_mcp.config import NasMcpConfig; b=NasMcpBroker(NasMcpConfig.from_env());
from hb_assistant.obsidian_mcp.client_tool_manifest import WORKFLOW_RECIPES
r=b.dispatch('pa_tool_manifest_get',{})['result']; fr=b.dispatch('pa_tool_manifest_freshness_check',{})['result'];
print('manifest_status', r.get('manifest_status'), 'persisted', r.get('persisted'));
print('manifest_schema_version', r.get('manifest_schema_version'));
print('workflow_count', r.get('workflow_count'), 'published_recipes', len(WORKFLOW_RECIPES));
print('staleness', fr.get('staleness_state'), 'stale', fr.get('tool_manifest_stale'), 'review_required', fr.get('tool_manifest_review_required'));
assert r.get('persisted') is True, r
assert r.get('manifest_schema_version') == 1, r
assert len(WORKFLOW_RECIPES) >= $EXPECT_PUBLISHED, len(WORKFLOW_RECIPES)
assert fr.get('tool_manifest_stale') is False, fr
print('manifest refresh verified')"

say "5. Routing spot-check (document_session should not be surface_stale)"
"$DOCKER" exec "$CONTAINER" python3 -c \
  'from hb_assistant.nas_mcp.broker import NasMcpBroker; from hb_assistant.nas_mcp.config import NasMcpConfig; b=NasMcpBroker(NasMcpConfig.from_env()); r=b.dispatch("pa_prompt_route",{"prompt":"Document this session as decisions and open loops"})["result"]; a=r.get("authorization") or {}; print("workflow", r.get("recommended_workflow"), "executable", a.get("currently_executable"), "blocked", a.get("execution_blocked_reason"))'

say "DONE"
cat <<EOF
SUMMARY
  refresh_proposal_id : $REFRESH_ID
  operator_approval_id: $APPROVAL_ID
  expected_published  : $EXPECT_PUBLISHED workflows
EOF