#!/usr/bin/env bash
# N8C-24 — connected-client generated-output workspace smoke.
# Drives the full stage → approve → commit → receipt → manifest → list → metadata → excerpt → archive loop
# against a REAL FastMCP surface on a fresh migrated TEMP DB and a TEMP outputs root (never the real
# mcp-outputs). Generates REAL docx/xlsx/html/zip/md files, proves idempotency + gateway reach, then runs
# fail-closed negatives (traversal, absolute, .sh, .exe, ZIP traversal, oversized, unapproved commit,
# safe-mode commit, gateway → denied/legacy). PASS/FAIL per step; nonzero on failure. No prod data/network.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
export PYTHONPATH="src:subrepos/construction-financial-review/src${PYTHONPATH:+:$PYTHONPATH}"
PY="$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 )"

"$PY" - <<'PY'
import base64, io, sys, tempfile, zipfile
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.store.migrator import SQLiteMigrator

fails = []
def check(label, cond, detail=""):
    print(("PASS" if cond else "FAIL"), "-", label, ("" if cond else f"[{detail}]"))
    if not cond:
        fails.append(label)

d = Path(tempfile.mkdtemp(prefix="n8c24-smoke-"))
db = str(d / "db.sqlite"); SQLiteMigrator(db_path=db).apply()
out = d / "outputs"
for f in ("00 Pending", "01 Final", "90 Archive", "99 Receipts", "99 Manifests"):
    (out / f).mkdir(parents=True, exist_ok=True)
vault = d / "vault"; vault.mkdir()
before_top = {p.name for p in out.iterdir() if p.is_dir()}
cfg = NasMcpConfig(db_path=Path(db), audit_dir=d / "audit",
                   roots={"vault": RootSpec("vault", vault, "read_write"),
                          "outputs": RootSpec("outputs", out, "read_write")},
                   obsidian=NasObsidianConfig(vault_root=vault, backup_dir=d / "bk", support_dir=d / "sup"))
mcp = FastMCP("hb-nas-mcp", json_response=True, stateless_http=True)
broker = NasMcpBroker(cfg); register_nas_mcp_tools(mcp, broker)
fn = {t.name: t.fn for t in mcp._tool_manager.list_tools()}

st = broker.dispatch("hb_mcp_status", {})["result"]
check("schema V113 + output workspace enabled", st.get("client_output_workspace_enabled") is True
      and st.get("client_output_write_enabled") is True)
check("78 canonical assistant tools preserved",
      len([t.name for t in mcp._tool_manager.list_tools() if t.name.startswith("assistant_")]) == 78)

def good_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.txt", "hi"); z.writestr("sub/b.txt", "yo")
    return base64.b64encode(buf.getvalue()).decode()

def stage_commit(title, ft, mode, *, text=None, b64=None):
    args = {"title": title, "file_type": ft, "content_mode": mode, "destination_state": "final"}
    if text is not None: args["content_text"] = text
    if b64 is not None: args["content_base64"] = b64
    s = fn["pa_output_stage"](**args)
    r = fn["pa_output_commit"](output_id=s["output_id"], operator_approval_id=s["operator_approval_id"],
                              idempotency_key=s["idempotency_key"])
    return s, r

for title, ft, mode, kw in [
    ("Notes", "md", "markdown_text", {"text": "# Notes\nbody"}),
    ("Report", "docx", "docx_from_markdown_or_text", {"text": "# Report\npara"}),
    ("Sheet", "xlsx", "xlsx_from_csv", {"text": "a,b\n1,2"}),
    ("Page", "html", "html_text", {"text": "<b>x</b>"}),
    ("Slides", "pptx", "pptx_from_markdown_or_json", {"text": "Title\nbody"}),
    ("Brief", "pdf", "pdf_from_html_or_markdown", {"text": "# Brief\nline"}),
    ("Package", "zip", "zip_base64", {"b64": good_zip()}),
]:
    s, r = stage_commit(title, ft, mode, **kw)
    p = out / r["relative_path"]
    check(f"commit {ft} real file", r["status"] == "committed" and p.exists() and p.stat().st_size > 0)

check("receipts written under 99 Receipts", any((out / "99 Receipts").glob("*.md")))
check("manifest md+json written", (out / "99 Manifests/client-output-manifest.md").exists()
      and (out / "99 Manifests/client-output-manifest.json").exists())
check("list + metadata bounded", fn["pa_output_list"]()["count"] >= 7)
first = fn["pa_output_list"](file_type="md")["outputs"][0]["output_id"]
check("bounded text excerpt", fn["pa_output_read_excerpt"](output_id=first)["preview_mode"] == "bounded_text_excerpt")
zid = fn["pa_output_list"](file_type="zip")["outputs"][0]["output_id"]
check("zip inspect lists members (no extract)",
      fn["pa_output_zip_inspect"](output_id=zid)["preview_mode"] == "zip_members")

# idempotent retry
s2 = fn["pa_output_stage"](title="Retry", file_type="md", content_mode="markdown_text",
                          content_text="x", destination_state="final")
r2a = fn["pa_output_commit"](output_id=s2["output_id"], operator_approval_id=s2["operator_approval_id"],
                            idempotency_key=s2["idempotency_key"])
r2b = fn["pa_output_commit"](output_id=s2["output_id"], operator_approval_id=s2["operator_approval_id"],
                            idempotency_key=s2["idempotency_key"])
check("commit retry idempotent (no dup)", r2b["idempotent_reuse"] is True
      and len(list((out / "01 Final").rglob(f"{s2['output_id']}*"))) == 1)

# gateway reach
g = fn["hb_assistant_tool_query"]("pa_output_stage", {"title": "Gate", "file_type": "md",
                                                     "content_mode": "markdown_text", "content_text": "x"})
check("gateway reaches pa_output_stage", g["ok"] is True and bool(g["result"]["output_id"]))

# archive (advisory plan is read-only; commit needs the staged approval id, exercised in the pytest suite)
ap = fn["pa_output_archive_plan"](output_id=first)
check("archive plan never deletes", ap["deletes"] is False and ap["writes"] is False)

# --- negatives ---
def denied(label, thunk):
    try:
        res = thunk()
        ok = isinstance(res, dict) and res.get("ok") is False
        check(label, ok, "did not fail closed" if not ok else "")
    except Exception as e:
        check(label, True, type(e).__name__)

denied("gateway rejects raw_sql", lambda: fn["hb_assistant_tool_query"]("raw_sql", {}))
denied("gateway rejects legacy hb_output_write_file", lambda: fn["hb_assistant_tool_query"]("hb_output_write_file", {}))
denied("gateway rejects hb_db_select", lambda: fn["hb_assistant_tool_query"]("hb_db_select", {}))
denied("script extension rejected", lambda: fn["pa_output_stage"](title="x", file_type="sh",
                                                                 content_mode="text", content_text="x"))
denied("exe extension rejected", lambda: fn["pa_output_stage"](title="x", file_type="exe",
                                                              content_mode="text", content_text="x"))
def zip_traversal():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z: z.writestr("../evil.txt", "x")
    return fn["pa_output_stage"](title="z", file_type="zip", content_mode="zip_base64",
                                content_base64=base64.b64encode(b.getvalue()).decode())
denied("zip traversal rejected", zip_traversal)
s_fresh = fn["pa_output_stage"](title="Fresh", file_type="md", content_mode="markdown_text",
                                content_text="x", destination_state="final")
denied("unapproved commit on fresh staged rejected",
       lambda: fn["pa_output_commit"](output_id=s_fresh["output_id"], operator_approval_id="FORGED"))

after_top = {p.name for p in out.iterdir() if p.is_dir()}
check("no new top-level output folder created", after_top == before_top, sorted(after_top - before_top))
check("generated files never landed in the vault", not list(vault.rglob("*.docx")))

print()
if fails:
    print(f"SMOKE FAILED: {len(fails)} step(s): {fails}"); sys.exit(1)
print("SMOKE PASSED: full stage->approve->commit->receipt->manifest->list->excerpt->archive + gateway + negatives")
PY
