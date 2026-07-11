#!/bin/sh
# Post-promote verification only (manifest + surface freshness + routing spot-check).
# RUN ON THE NAS: sudo sh /tmp/03-manifest-verify-pr15.sh
set -eu

DOCKER=/usr/local/bin/docker
CONTAINER=hb-personal-assistant-mcp
EXPECT_PUBLISHED=15

say() { printf '\n=== %s ===\n' "$1"; }
die() { printf '\nFATAL: %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "must run as root (sudo)"
[ -x "$DOCKER" ] || die "docker not found"
"$DOCKER" inspect "$CONTAINER" >/dev/null 2>&1 || die "container $CONTAINER not running"

say "3c. Schema lineage (RO snapshot vs RW workspace)"
"$DOCKER" exec "$CONTAINER" python3 -c \
  'import os, sqlite3; from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION;
ro=os.environ.get("HB_ASSISTANT_DB",""); ws=os.environ.get("HB_ASSISTANT_WORKSPACE_DB","");
def head(p):
    if not p or not os.path.isfile(p): return "(absent)"
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True).execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
print("RO_snapshot_head", head(ro)); print("RW_workspace_head", head(ws)); print("LATEST_SCHEMA_VERSION", LATEST_SCHEMA_VERSION)'

say "4. Verify active manifest"
"$DOCKER" exec "$CONTAINER" python3 -c \
  "import json; from hb_assistant.nas_mcp.broker import NasMcpBroker; from hb_assistant.nas_mcp.config import NasMcpConfig; b=NasMcpBroker(NasMcpConfig.from_env());
from hb_assistant.obsidian_mcp.client_tool_manifest import WORKFLOW_RECIPES
r=b.dispatch('pa_tool_manifest_get',{})['result']; fr=b.dispatch('pa_tool_manifest_freshness_check',{})['result'];
print('manifest_status', r.get('manifest_status'), 'persisted', r.get('persisted'));
print('manifest_schema_version', r.get('manifest_schema_version'));
print('workflow_count', r.get('workflow_count'), 'published_recipes', len(WORKFLOW_RECIPES));
print('staleness', fr.get('staleness_state'), 'stale', fr.get('tool_manifest_stale'), 'review_required', fr.get('tool_manifest_review_required'));
wc=r.get('workflow_count'); pr=len(WORKFLOW_RECIPES)
assert r.get('persisted') is True, r
assert r.get('manifest_schema_version') == 1, r
assert wc == pr == $EXPECT_PUBLISHED, (wc, pr)
assert fr.get('tool_manifest_stale') is False, fr
print('manifest refresh verified')"

say "4b. Tool-surface freshness (write-route gate)"
"$DOCKER" exec "$CONTAINER" python3 -c \
  'import json; from mcp.server.fastmcp import FastMCP; from hb_assistant.nas_mcp.broker import NasMcpBroker; from hb_assistant.nas_mcp.config import NasMcpConfig; from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools;
cfg=NasMcpConfig.from_env(); b=NasMcpBroker(cfg); register_nas_mcp_tools(FastMCP("hb-nas-mcp", json_response=True, stateless_http=True), b); r=b.dispatch("pa_tool_surface_freshness_check",{})["result"]; print(json.dumps({"stale": r.get("stale"), "staleness_state": r.get("staleness_state"), "class_changed": len(r.get("class_changed_tools") or []), "family_changed": len(r.get("family_changed_tools") or []), "warnings_tail": (r.get("warnings") or [])[-3:]}, sort_keys=True)); assert r.get("stale") is False, r.get("warnings")'

say "5. Routing spot-check (document_session should not be surface_stale)"
"$DOCKER" exec "$CONTAINER" python3 -c \
  'from mcp.server.fastmcp import FastMCP; from hb_assistant.nas_mcp.broker import NasMcpBroker; from hb_assistant.nas_mcp.config import NasMcpConfig; from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools;
cfg=NasMcpConfig.from_env(); b=NasMcpBroker(cfg); register_nas_mcp_tools(FastMCP("hb-nas-mcp", json_response=True, stateless_http=True), b); r=b.dispatch("pa_prompt_route",{"prompt":"Document this session as decisions and open loops"})["result"]; a=r.get("authorization") or {}; print("workflow", r.get("recommended_workflow"), "executable", a.get("currently_executable"), "blocked", a.get("execution_blocked_reason")); assert r.get("recommended_workflow") == "document_session", r; assert a.get("execution_blocked_reason") != "surface_stale", a; assert a.get("currently_executable") is True, a'

say "DONE"