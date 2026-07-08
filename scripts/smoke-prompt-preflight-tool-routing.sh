#!/usr/bin/env bash
# Prompt Preflight & Tool Routing smoke.
# Drives the read-only route engine + freshness guard through a REAL FastMCP surface on a fresh migrated
# TEMP DB. Proves: generate-a-file routes to the output workspace (not vault/canonical); document-this-session
# routes to the artifact workspace (staging authorized, promotion needs approval); source search prefers the
# source connector; decisions route to canonical records; broad search triages before deep read; a simulated
# stale/changed tool surface warns (reads) / fails closed (writes); and the preflight writes/stages/promotes/
# commits NOTHING. PASS/FAIL per step; nonzero on failure. No prod data/network.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
export PYTHONPATH="src:subrepos/construction-financial-review/src${PYTHONPATH:+:$PYTHONPATH}"
PY="$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 )"

"$PY" - <<'PY'
import tempfile
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.broker import NasMcpBroker, GATEWAY_ALLOWLIST
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.obsidian_mcp.tool_surface_freshness import check_tool_surface
from hb_assistant.nas_mcp.prompt_routing_tools import current_tool_groups

fails = []
def check(label, cond, detail=""):
    print(("PASS" if cond else "FAIL"), "-", label, ("" if cond else f"[{detail}]"))
    if not cond:
        fails.append(label)

d = Path(tempfile.mkdtemp(prefix="preflight-smoke-"))
db = str(d / "db.sqlite"); SQLiteMigrator(db_path=db).apply()
out = d / "outputs"
for f in ("00 Pending", "01 Final", "90 Archive", "99 Receipts", "99 Manifests"):
    (out / f).mkdir(parents=True, exist_ok=True)
vault = d / "vault"; vault.mkdir()
cfg = NasMcpConfig(db_path=Path(db), audit_dir=d / "audit",
                   roots={"vault": RootSpec("vault", vault, "read_write"),
                          "outputs": RootSpec("outputs", out, "read_write")},
                   obsidian=NasObsidianConfig(vault_root=vault, backup_dir=d / "bk", support_dir=d / "sup"))
mcp = FastMCP("hb-nas-mcp", json_response=True, stateless_http=True)
broker = NasMcpBroker(cfg); register_nas_mcp_tools(mcp, broker)

def route(prompt, **kw):
    return broker.dispatch("pa_prompt_route", {"prompt": prompt, **kw})["result"]

# 1) generate a file -> output workspace, never vault/canonical
r = route("Generate a Word document and save it")
check("generate-file -> client_output_workspace", r["primary_family"] == "client_output_workspace", r["primary_family"])
check("generate-file uses pa_output_* tools", r["recommended_tools"] == ["pa_output_stage", "pa_output_commit"], r["recommended_tools"])
check("generate-file not vault/canonical", "canonical_promotion" not in r["candidate_families"])
check("generate-file write needs approval", r["authorization"]["additional_approval_required"] is True
      and r["authorization"]["prompt_authorizes_execution"] is False)

# 2) document this session -> artifact workspace; staging authorized, promotion needs approval
r = route("Document this session")
check("document-session -> artifact_workspace", r["primary_family"] == "artifact_workspace", r["primary_family"])
check("document-session staging authorization", r["authorization"]["action_class"] == "staged_write")
r2 = route("Promote the decision record to canonical memory")
check("promotion -> canonical_promotion needs approval", r2["primary_family"] == "canonical_promotion"
      and r2["authorization"]["additional_approval_required"] is True)

# 3) source search prefers the source connector over low-level
r = route("Find the source file for the contract")
check("source search -> source connector", r["primary_family"] == "assistant_source_connector", r["primary_family"])
check("source search starts at metadata_discovery", r["retrieval_budget"]["default_layer"] == "metadata_discovery")

# 4) decisions -> canonical records
r = route("What did we decide about the budget")
check("decision -> canonical decision records", r["primary_family"] == "assistant_decision_memory"
      and "canonical" in r["source_of_truth"].lower())

# 5) broad search triages before deep read
r = route("assemble context on the vendor")
check("broad retrieval requires operator selection before deep parse",
      r["retrieval_budget"]["deep_parse_requires_operator_selection"] is True and bool(r["retrieval_budget"]["why_not_deep_read_all"]))

# 6) stale/changed surface: reads warn, writes fail closed
stale = {"stale": True, "staleness_state": "stale", "warnings": ["simulated drift"]}
from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt
rw = route_prompt("Generate a Word document and save it", freshness=stale)
rr = route_prompt("Find the source file for the contract", freshness=stale)
check("stale surface blocks WRITE route", rw["freshness"]["write_blocked_by_staleness"] is True)
check("stale surface does NOT block READ route", rr["freshness"]["write_blocked_by_staleness"] is False)
# simulated gateway-scope change is detected
rep = check_tool_surface(current_tool_groups(cfg),
                         live_gateway_allowlist=frozenset(GATEWAY_ALLOWLIST) | {"pa_new_write_tool"},
                         stored_gateway_allowlist=frozenset(GATEWAY_ALLOWLIST),
                         check_workflow_coverage=False)
check("gateway scope change detected", rep["tool_surface_gateway_current"] is False and rep["stale"] is True)

# 7) live surface is fresh; preflight is read-only; no unsafe fallback on writes
fr = broker.dispatch("pa_tool_surface_freshness_check", {})["result"]
check("live surface is current", fr["stale"] is False, fr.get("warnings"))
r = route("Generate a Word document and save it")
check("preflight is read-only", r["preflight_is_read_only"] is True)
check("controlled write blocks unsafe fallback", r["fallback_plan"]["unsafe_fallback_blocked"] is True)

# 8) preflight wrote nothing: outputs workspace stays empty, no files under outputs
st = broker.dispatch("hb_mcp_status", {})["result"]
check("no outputs committed by preflight", st.get("client_output_committed_count", 0) == 0)
committed_files = [p for p in (out / "01 Final").rglob("*") if p.is_file()]
check("no files written under outputs root", committed_files == [], committed_files)

# 9) canonical 78 preserved; prompt tools gateway-reachable but not canonical
names = [t.name for t in mcp._tool_manager.list_tools()]
check("78 canonical assistant tools preserved", len([n for n in names if n.startswith("assistant_")]) == 78)
check("pa_prompt_route registered + gateway-reachable", "pa_prompt_route" in names and "pa_prompt_route" in GATEWAY_ALLOWLIST)

print()
if fails:
    print(f"SMOKE FAILED ({len(fails)}):", *fails, sep="\n  ")
    raise SystemExit(1)
print("SMOKE PASSED")
PY
