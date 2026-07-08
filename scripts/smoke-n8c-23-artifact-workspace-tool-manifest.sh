#!/usr/bin/env bash
# N8C-23 — structured artifact workspace + Obsidian card materialization + client tool operating manifest smoke.
# Drives the full loop a connected client + operator would run against a REAL FastMCP surface on a fresh
# migrated TEMP DB and a TEMP vault mirroring the real folder structure (never the synced vault):
#   register/build client tool manifest -> freshness check -> stage session capture -> stage proposal bundle
#   -> review (approve / reject / request_revision / session_note_only) -> plan -> validate -> promote
#   -> assert canonical rows + cards in EXISTING folders + frontmatter/tags/backlinks + receipt + manifests
#   -> retry promote (idempotent, no dup) -> staged manifest refresh -> promote -> negatives (forged approval,
#   unvalidated promote, new-top-level path, gateway rejects pa_, silent manifest rewrite impossible).
# No production data, no network, no prod mutation, no new top-level vault folder. PASS/FAIL per step; nonzero on failure.
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
from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.obsidian_mcp.vault_path_resolver import EXISTING_TOP_LEVEL_FOLDERS
from hb_assistant.store.migrator import SQLiteMigrator

fails = []
def check(label, cond, detail=""):
    print(("PASS" if cond else "FAIL"), "-", label, ("" if cond else f"[{detail}]"))
    if not cond:
        fails.append(label)

d = Path(tempfile.mkdtemp(prefix="n8c23-smoke-"))
db = str(d / "db.sqlite"); SQLiteMigrator(db_path=db).apply()
vault = d / "vault"
for f in EXISTING_TOP_LEVEL_FOLDERS:
    (vault / f).mkdir(parents=True, exist_ok=True)
for sub in ("Work/03 Decisions", "Work/04 Actions", "Work/07 Knowledge", "99 System/Receipts", "99 System/Manifests"):
    (vault / sub).mkdir(parents=True, exist_ok=True)
before_top = {p.name for p in vault.iterdir() if p.is_dir()}

cfg = NasMcpConfig(db_path=Path(db), audit_dir=d / "audit",
                   roots={"vault": RootSpec("vault", vault, "read_write")},
                   obsidian=NasObsidianConfig(vault_root=vault, backup_dir=d / "bk", support_dir=d / "sup"))
mcp = FastMCP("hb-nas-mcp", json_response=True, stateless_http=True)
broker = NasMcpBroker(cfg)
register_nas_mcp_tools(mcp, broker)
tools = {t.name: t for t in mcp._tool_manager.list_tools()}
fn = {n: t.fn for n, t in tools.items()}

# --- schema + invariants ---
st = broker.dispatch("hb_mcp_status", {})["result"]
check("schema V112 + workspace status", st.get("artifact_workspace_schema_version") == 112)
check("78 assistant tools preserved", len([n for n in tools if n.startswith("assistant_")]) == 78)
check("client tool manifest freshness field present", "client_tool_manifest_staleness_state" in st)

# --- client tool operating manifest: build (staged refresh) + freshness ---
fr0 = fn["pa_tool_manifest_freshness_check"]()
check("freshness reports stale when no manifest yet", fr0["tool_manifest_stale"] is True)
stg_m = fn["pa_tool_manifest_refresh_stage"]()
check("manifest refresh is staged (not silent)", stg_m["status"] == "staged" and stg_m["writes"] is False)
prom_m = fn["pa_tool_manifest_refresh_promote"](refresh_proposal_id=stg_m["refresh_proposal_id"],
                                                operator_approval_id=stg_m["operator_approval_id"])
check("manifest promoted to 99 System/Manifests (md+json)",
      prom_m["status"] == "promoted"
      and (vault / "99 System/Manifests/client-tool-operating-manifest.md").exists()
      and (vault / "99 System/Manifests/client-tool-operating-manifest.json").exists())
fr1 = fn["pa_tool_manifest_freshness_check"]()
check("freshness fresh after promote", fr1["tool_manifest_stale"] is False)

# --- document this session: capture -> propose -> review -> plan -> validate -> promote ---
sc = fn["pa_session_capture_stage"](source_client="chatgpt", session_title="Planning discussion",
                                    capture_trigger="document this session",
                                    session_summary="We agreed to use staged promotion for canonical memory.",
                                    selected_excerpts=["operator: let's use staging"])
bd = fn["pa_artifact_proposal_stage"](session_id=sc["session_id"], candidate_artifacts=[
    {"artifact_type": "decision", "title": "Use staged artifact promotion", "domain": "work",
     "body_markdown": "Promote through staging + review.", "summary": "Staged promotion."},
    {"artifact_type": "preference", "title": "Clients draft; server is authority", "domain": "work",
     "body_markdown": "Connected clients are drafting assistants.", "summary": "Drafting pref."},
    {"artifact_type": "open_loop", "title": "Name the canonical artifact tools", "domain": "work",
     "body_markdown": "Define pa_ tool names.", "summary": "Naming loop."},
    {"artifact_type": "session_note", "title": "Misc aside", "domain": "work",
     "body_markdown": "Not canonical-worthy.", "summary": "Aside."}])
pids = bd["proposal_ids"]
check("proposal bundle staged", len(pids) == 4 and bd["proposal_bundle_id"])
fn["pa_artifact_proposal_review"](proposal_id=pids[0], decision="approve", operator_id="bobby")
fn["pa_artifact_proposal_review"](proposal_id=pids[1], decision="approve", operator_id="bobby")
fn["pa_artifact_proposal_review"](proposal_id=pids[2], decision="request_revision", operator_id="bobby",
                                  review_notes="tighten scope")
rev = fn["pa_artifact_proposal_revise"](proposal_id=pids[2], body_markdown="Define pa_ tool names precisely.",
                                        revision_summary="tightened")
check("revision creates a new version (v1 preserved)", rev.get("version", 1) >= 2)
fn["pa_artifact_proposal_review"](proposal_id=pids[2], decision="approve", operator_id="bobby")
fn["pa_artifact_proposal_review"](proposal_id=pids[3], decision="session_note_only", operator_id="bobby")

plan = fn["pa_artifact_proposal_plan_promotion"](proposal_bundle_id=bd["proposal_bundle_id"])
check("plan is advisory (destination paths shown)",
      plan.get("writes") is False and bool(plan.get("would_create")))
val = fn["pa_artifact_promotion_validate"](proposal_bundle_id=bd["proposal_bundle_id"], operator_id="bobby")
check("validate mints server approval + idempotency + hash",
      bool(val.get("operator_approval_id")) and bool(val.get("idempotency_key")) and bool(val.get("validation_hash")))

res = fn["pa_artifact_promotion_apply"](promotion_bundle_id=val["promotion_bundle_id"],
                                        operator_approval_id=val["operator_approval_id"],
                                        idempotency_key=val["idempotency_key"])
check("promotion writes 3 approved canonical artifacts", res["status"] == "promoted" and res["created_count"] == 3)

# cards landed in EXISTING folders with frontmatter/tags/session backlink
ok_cards = True
for rel in res["created_paths"]:
    p = vault / rel
    txt = p.read_text() if p.exists() else ""
    top = rel.split("/", 1)[0]
    ok_cards = ok_cards and p.exists() and top in EXISTING_TOP_LEVEL_FOLDERS \
        and "canonical_id:" in txt and "second-brain/canonical" in txt and "[[SESSION-" in txt
check("cards materialized into existing folders w/ frontmatter+tags+backlink", ok_cards)
check("promotion receipt card written to 99 System/Receipts",
      (vault / res["receipt_vault_path"]).exists() and res["receipt_vault_path"].startswith("99 System/Receipts"))
check("canonical manifest (md+json) written",
      (vault / "99 System/Manifests/canonical-artifact-manifest.md").exists()
      and (vault / "99 System/Manifests/canonical-artifact-manifest.json").exists())

# future retrieval
lst = fn["pa_canonical_artifact_list"]()
check("promoted artifacts retrievable next session", len(lst["canonical_artifacts"]) == 3)

# idempotent retry — no dup rows / cards
res2 = fn["pa_artifact_promotion_apply"](promotion_bundle_id=val["promotion_bundle_id"],
                                         operator_approval_id=val["operator_approval_id"],
                                         idempotency_key=val["idempotency_key"])
check("promotion retry is idempotent (no duplication)",
      res2.get("idempotent_reuse") is True
      and len(fn["pa_canonical_artifact_list"]()["canonical_artifacts"]) == 3)

# --- negatives (all fail closed) ---
def denied(label, thunk):
    try:
        thunk(); check(label, False, "did not raise")
    except Exception as e:
        check(label, True, type(e).__name__)

denied("forged operator approval rejected on fresh bundle",
       lambda: fn["pa_artifact_promotion_apply"](promotion_bundle_id="PROMOB-forged", operator_approval_id="FORGED"))
denied("unvalidated promotion bundle rejected",
       lambda: fn["pa_artifact_promotion_apply"](promotion_bundle_id="PROMOB-nope", operator_approval_id="x"))
denied("override into NEW top-level folder rejected",
       lambda: fn["pa_vault_path_resolve"](artifact_type="decision", title="t",
                                           operator_override_path="Second Brain/Canonical/x.md"))
denied("traversal override rejected",
       lambda: fn["pa_vault_path_resolve"](artifact_type="decision", title="t", operator_override_path="../escape.md"))
denied("assistant gateway rejects pa_ tools",
       lambda: fn["hb_assistant_tool_query"]("pa_artifact_promotion_apply", {}))
denied("manifest refresh with forged approval rejected",
       lambda: fn["pa_tool_manifest_refresh_promote"](refresh_proposal_id="MREFRESH-x", operator_approval_id="FORGED"))

# no new top-level vault folder created anywhere in the run
after_top = {p.name for p in vault.iterdir() if p.is_dir()}
check("no new top-level vault folder created", after_top == before_top, sorted(after_top - before_top))

print()
if fails:
    print(f"SMOKE FAILED: {len(fails)} step(s): {fails}"); sys.exit(1)
print("SMOKE PASSED: full staged->reviewed->promoted->materialized->receipted->manifested->retrieved loop + negatives")
PY
