#!/bin/sh
# Post-promote verification only (steps 4–5). Use when stage/promote already succeeded.
# RUN ON THE NAS: sudo sh /tmp/hb-manifest-verify-only.sh
set -eu

DOCKER=/usr/local/bin/docker
CONTAINER=hb-personal-assistant-mcp
EXPECT_PUBLISHED=14

say() { printf '\n=== %s ===\n' "$1"; }
die() { printf '\nFATAL: %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "must run as root (sudo)"
[ -x "$DOCKER" ] || die "docker not found"
"$DOCKER" inspect "$CONTAINER" >/dev/null 2>&1 || die "container $CONTAINER not running"

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
  'import json; from hb_assistant.nas_mcp.broker import NasMcpBroker; from hb_assistant.nas_mcp.config import NasMcpConfig; b=NasMcpBroker(NasMcpConfig.from_env()); r=b.dispatch("pa_tool_surface_freshness_check",{})["result"]; print(json.dumps({"stale": r.get("stale"), "staleness_state": r.get("staleness_state"), "class_changed": len(r.get("class_changed_tools") or []), "family_changed": len(r.get("family_changed_tools") or []), "warnings_tail": (r.get("warnings") or [])[-3:]}, sort_keys=True)); assert r.get("stale") is False, r.get("warnings")'

say "5. Routing spot-check (document_session should not be surface_stale)"
"$DOCKER" exec "$CONTAINER" python3 -c \
  'from hb_assistant.nas_mcp.broker import NasMcpBroker; from hb_assistant.nas_mcp.config import NasMcpConfig; b=NasMcpBroker(NasMcpConfig.from_env()); r=b.dispatch("pa_prompt_route",{"prompt":"Document this session as decisions and open loops"})["result"]; a=r.get("authorization") or {}; print("workflow", r.get("recommended_workflow"), "executable", a.get("currently_executable"), "blocked", a.get("execution_blocked_reason"))'

say "DONE"