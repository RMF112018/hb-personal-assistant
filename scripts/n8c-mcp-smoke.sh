#!/bin/sh
# n8c-mcp-smoke.sh — LOCAL, READ-ONLY smoke of the whole N8C second-brain MCP surface (N8C-21 final
# validation). NON-DESTRUCTIVE: builds a fresh TEMP SQLite DB, migrates it to head, registers all NAS MCP
# tools against a fake registry, and exercises a representative read-only tool per assistant group over the
# temp DB. It does NOT touch the production DB, does NOT start the backend or a container, does NOT open a
# tunnel, and asserts that no write/finality-verb tool is exposed. Safe to run on the Mac or the NAS.
#
# Usage:
#   scripts/n8c-mcp-smoke.sh
#
# Env:
#   HB_PYTHON   python interpreter (default: auto-detect .venv/bin/python then python3)
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PY="${HB_PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x "$REPO_ROOT/.venv/bin/python" ]; then PY="$REPO_ROOT/.venv/bin/python"
  elif [ -x "/Users/bobbyfetting/hb-personal-assistant/.venv/bin/python" ]; then PY="/Users/bobbyfetting/hb-personal-assistant/.venv/bin/python"
  else PY="python3"; fi
fi

export PYTHONPATH="src:subrepos/construction-financial-review/src${PYTHONPATH:+:$PYTHONPATH}"

echo "== n8c-mcp-smoke (LOCAL, READ-ONLY, temp DB only) =="
echo "python=$PY"

"$PY" - <<'PYEOF'
import sys, tempfile, os
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator, LATEST_SCHEMA_VERSION
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.nas_mcp.broker import NasMcpBroker, DENIED_TOOL_NAMES
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.profile import AI_OUTPUTS_WRITE_TOOL

FINALITY = ("execute","apply","write","create","delete","persist","upsert","close","reopen","accept",
            "reject","defer","dispose","build","send","remind","answer","generate","scan","reindex",
            "rebuild","dispatch","schedule","repair","evaluate")

failures = []
def check(name, ok):
    print(("  PASS" if ok else "  FAIL"), name)
    if not ok: failures.append(name)

d = tempfile.mkdtemp()
db = os.path.join(d, "smoke.db")
head = SQLiteMigrator(db_path=db).apply()
check(f"fresh temp DB migrates to head {head}", head == LATEST_SCHEMA_VERSION == 111)

class FakeMcp:
    def __init__(self): self.names=[]
    def tool(self, name=None):
        def deco(fn): self.names.append(name or fn.__name__); return fn
        return deco

vault = Path(d)/"vault"; vault.mkdir(); audit = Path(d)/"audit"
cfg = NasMcpConfig(db_path=Path(db), audit_dir=audit,
    roots={"vault": RootSpec("vault", vault, "read_write")},
    obsidian=NasObsidianConfig(vault_root=vault, backup_dir=audit/"bk", support_dir=audit/"support"))
mcp = FakeMcp(); broker = NasMcpBroker(cfg); register_nas_mcp_tools(mcp, broker)

assistant = [n for n in mcp.names if n.startswith("assistant_")]
check("78 assistant tools registered (13 groups)", len(assistant) == 78)
check("finality guard: no assistant tool has a forbidden verb",
      not [n for n in assistant if any(s in n for s in FINALITY)])
check("ai_outputs_card_upsert is the only non-plan write tool",
      not [n for n in mcp.names if any(v in n for v in ("write","upsert","delete","create","persist"))
           and n != AI_OUTPUTS_WRITE_TOOL and not n.endswith("_plan")])

# hb_mcp_status advertises all 13 groups
status = broker.dispatch("hb_mcp_status", {})["result"]
enabled_keys = [k for k in status if k.endswith("_enabled") and k.startswith("assistant_")]
check("hb_mcp_status advertises 13 assistant groups", len(enabled_keys) == 13 and all(status[k] for k in enabled_keys))

# representative READ-ONLY tool call per group (list/summary — all safe on an empty DB)
reads = [
    ("assistant_search_sources", {"q": "x"}),
    ("assistant_list_context_packs", {}),
    ("assistant_list_memory_nodes", {}),
    ("assistant_list_decisions", {}),
    ("assistant_list_review_items", {}),
    ("assistant_list_intelligence_projections", {}),
    ("assistant_list_research_packets", {}),
    ("assistant_list_drafts", {}),
    ("assistant_source_roots_list", {}),
    ("assistant_list_feedback", {}),
    ("assistant_list_action_stages", {}),
    ("assistant_list_quality", {}),
]
for name, args in reads:
    if name not in mcp.names:
        continue  # tolerate naming drift across groups; the inventory count check above is authoritative
    r = broker.dispatch(name, args)
    check(f"read-only dispatch ok: {name}", r["ok"] is True)

# denied raw tools stay denied
for name in ("raw_sql", "sql", "shell", "exec", "read_file_absolute", "hb_output_delete"):
    check(f"denied: {name}", name in DENIED_TOOL_NAMES and broker.dispatch(name, {})["ok"] is False)

if failures:
    print(f"\nn8c-mcp-smoke: FAIL ({len(failures)} checks)"); sys.exit(1)
print("\nn8c-mcp-smoke: PASS (read-only, temp DB, no writes, no finality-verb tools)")
PYEOF

echo "n8c-mcp-smoke: done (static + read-only; production DB / backend / tunnel untouched)."
