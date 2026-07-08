#!/usr/bin/env bash
# N8C-22 — connected-client assistant exposure smoke.
# Simulates what a connected client (ChatGPT/Grok/Claude Desktop) can do against the NAS MCP surface:
# builds a REAL FastMCP surface + a fresh migrated test DB, reads the live client tool manifest, and
# exercises the assistant tools (direct + via the fallback gateway) plus fail-closed negatives.
# No production data, no network, no prod mutation. Prints PASS/FAIL per step; exits non-zero on failure.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
export PYTHONPATH="src:subrepos/construction-financial-review/src${PYTHONPATH:+:$PYTHONPATH}"
PY="$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 )"

"$PY" - <<'PY'
import sys, tempfile
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.broker import NasMcpBroker, ALL_ASSISTANT_TOOLS
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools, CLIENT_BRIDGE_HELPER_TOOLS
from hb_assistant.store.migrator import SQLiteMigrator

fails = []
def check(label, cond, detail=""):
    print(("PASS" if cond else "FAIL"), "-", label, ("" if cond else f"[{detail}]"))
    if not cond:
        fails.append(label)

d = Path(tempfile.mkdtemp(prefix="n8c22-smoke-"))
db = str(d/"db.sqlite"); SQLiteMigrator(db_path=db).apply()
vault = d/"vault"; vault.mkdir(exist_ok=True)
cfg = NasMcpConfig(db_path=Path(db), audit_dir=d/"audit",
                   roots={"vault": RootSpec("vault", vault, "read_write")},
                   obsidian=NasObsidianConfig(vault_root=vault, backup_dir=d/"bk", support_dir=d/"sup"))
mcp = FastMCP("hb-nas-mcp", json_response=True, stateless_http=True)
broker = NasMcpBroker(cfg)
register_nas_mcp_tools(mcp, broker)
tools = {t.name: t for t in mcp._tool_manager.list_tools()}   # the LIVE client-facing manifest
fn = {n: t.fn for n, t in tools.items()}

# --- status + manifest visibility (client layer, not just broker) ---
status = broker.dispatch("hb_mcp_status", {}).get("result", {})
check("status check", status.get("assistant_client_exposure_enabled") is True)
check("status exposed_tool_count == 78", status.get("assistant_client_exposed_tool_count") == 78,
      status.get("assistant_client_exposed_tool_count"))
check("client manifest exposes all 78 assistant tools", set(ALL_ASSISTANT_TOOLS) <= set(tools),
      len(set(ALL_ASSISTANT_TOOLS) - set(tools)))
check("client manifest exposes 3 bridge helpers", set(CLIENT_BRIDGE_HELPER_TOOLS) <= set(tools))

q = fn["hb_assistant_tool_query"]
def query_ok(name, args=None):
    r = q(name, args or {})
    return isinstance(r, dict) and r.get("ok") is True

def _synthetic(schema):
    props = schema.get("properties") or {}
    def val(spec):
        k = spec.get("type")
        return 1 if k in ("integer", "number") else False if k == "boolean" else [] if k == "array" else {} if k == "object" else "n8c22-none"
    return {n: val(props.get(n, {})) for n in (schema.get("required") or [])}

def reachable(name, args=None):
    # direct client wrapper reaches the handler: dict result, or fail-closed ValueError on synthetic id.
    call_args = args if args is not None else _synthetic(getattr(tools[name], "parameters", None) or {})
    try:
        return isinstance(fn[name](**call_args), dict)
    except ValueError:
        return True

# --- catalog / help ---
cat = fn["hb_assistant_catalog"]()
check("catalog lists 13 groups / 78 tools", len(cat["groups"]) == 13 and len(cat["tools"]) == 78)
check("help returns schema for a known tool",
      "query" in fn["hb_assistant_tool_help"]("assistant_source_file_search")["required_args"])

# --- Priority 1: source access/search ---
check("assistant source file search", query_ok("assistant_source_file_search", {"query": "contract"}))
check("assistant source file bounded read", reachable("assistant_source_file_read", {"source_ref": "none", "max_chars": 500}))
check("assistant source card search", query_ok("assistant_search_sources", {"query": "invoice", "limit": 5}))
check("assistant source status", query_ok("assistant_source_status"))

# --- Priority 2: context + memory ---
check("context pack list", query_ok("assistant_list_context_packs"))
check("context pack get (reach)", reachable("assistant_get_context_pack"))
check("memory list", query_ok("assistant_list_memory_nodes"))
check("memory get (reach)", reachable("assistant_get_memory_node"))
check("decision list", query_ok("assistant_list_decisions"))
check("preference list", query_ok("assistant_list_preferences"))
check("open-loop list", query_ok("assistant_list_open_loops"))

# --- Priority 3: research / drafts / workflow ---
check("research packet list", query_ok("assistant_list_research_packets"))
check("research packet get (reach)", reachable("assistant_get_research_packet"))
check("research packet citations (reach)", reachable("assistant_get_research_packet_citations"))
check("draft list", query_ok("assistant_list_drafts"))
check("draft get (reach)", reachable("assistant_get_draft"))
check("draft citations (reach)", reachable("assistant_get_draft_citations"))
check("workflow list", query_ok("assistant_list_workflows"))
check("workflow route (reach)", reachable("assistant_route_workflow"))
check("workflow policy (reach)", reachable("assistant_get_workflow_policy"))

# --- Priority 4: review / feedback / action stages / quality ---
check("review list", query_ok("assistant_list_review_items"))
check("review effective state (reach)", reachable("assistant_get_effective_review_state"))
check("feedback list", query_ok("assistant_list_feedback"))
check("feedback recommendations (reach)", reachable("assistant_get_feedback_recommendations"))
check("action stage list", query_ok("assistant_list_action_stages"))
check("action stage get (reach)", reachable("assistant_get_action_stage"))
check("quality list", query_ok("assistant_list_quality"))
check("quality findings (reach)", reachable("assistant_get_quality_findings"))

# --- negatives: all must fail closed ---
def rejected(name, args=None):
    try:
        q(name, args or {}); return False
    except ValueError:
        return True
check("negative: denied tool (raw_sql) rejected", rejected("raw_sql"))
check("negative: raw SQL (hb_db_select) rejected", rejected("hb_db_select", {"table_key": "x", "columns": ["a"]}))
check("negative: shell/exec rejected", rejected("shell") and rejected("exec"))
check("negative: write/finality (ai_outputs_card_upsert) rejected via gateway", rejected("ai_outputs_card_upsert", {"title": "x"}))
check("negative: absolute file read tool rejected", rejected("hb_root_read_file", {"root_key": "home", "relative_path": "/etc/passwd"}))
check("negative: unbounded limit rejected", rejected("assistant_search_sources", {"query": "x", "limit": 999999}))

print()
if fails:
    print(f"SMOKE FAILED: {len(fails)} step(s): {fails}")
    sys.exit(1)
print("SMOKE OK: connected-client layer sees and can call the N8C assistant surface; negatives fail closed.")
PY
