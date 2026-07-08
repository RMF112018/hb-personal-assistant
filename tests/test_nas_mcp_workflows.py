"""N8C-16 read-only LIVE workflow-consumption MCP tools: six bounded route/context/policy tools over the
N8C-15 router, served from a read-only DB snapshot. No schema, no persistence, no build/apply, no execution,
no final answer, no live source read, no MCP write. Kill-switch gated, finality-guard clean, +6 tool delta."""

from __future__ import annotations

import ast
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import (
    ASSISTANT_ANSWER_DRAFT_TOOLS,
    ASSISTANT_CONTEXT_PACK_TOOLS,
    ASSISTANT_DECISION_MEMORY_TOOLS,
    ASSISTANT_INTELLIGENCE_TOOLS,
    ASSISTANT_MEMORY_TOOLS,
    ASSISTANT_NAV_TOOLS,
    ASSISTANT_RESEARCH_PACKET_TOOLS,
    ASSISTANT_REVIEW_TOOLS,
    ASSISTANT_SOURCE_CONNECTOR_TOOLS,
    ASSISTANT_WORKFLOW_TOOLS,
    NasMcpBroker,
)
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.db_tools import _ro_uri
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_SRC = Path(__file__).resolve().parents[1] / "src" / "hb_assistant"
_FORBIDDEN = ("extract", "apply", "write", "create", "delete", "persist", "upsert", "close", "reopen",
              "accept", "reject", "defer", "dispose", "build", "send", "remind", "answer", "generate",
              "scan", "reindex", "rebuild")
_FINALITY_FIELDS = ("final_answer", "answer_text", "generated_answer", "operator_approved_answer",
                    "authoritative_answer", "send_answer", "generate_answer", "executed_action",
                    "action_completed", "task_created", "calendar_updated", "email_sent")


class _FakeMcp:
    def __init__(self) -> None:
        self.names: list[str] = []

    def tool(self, name: str | None = None):
        def deco(fn):
            self.names.append(name or fn.__name__)
            return fn
        return deco


def _seed_draft(db: str, draft_id: str = "D1") -> None:
    # Checkpoint + close so the row lands in the main DB file — the read-only snapshot opens with
    # ``immutable=1`` and would not see rows still sitting in the -wal file.
    conn = sqlite3.connect(db)
    try:
        conn.execute("INSERT INTO assistant_answer_drafts (draft_id, draft_type, status, citation_count, "
                     "candidate_section_count) VALUES (?,?,?,?,?)",
                     (draft_id, "review_aware_answer_draft", "built", 0, 1))
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _seed_open_loop(db: str, open_loop_id: str = "OL1") -> None:
    conn = sqlite3.connect(db)
    try:
        conn.execute("INSERT INTO assistant_open_loop_records (open_loop_id, identity_key, open_loop_type, "
                     "status, review_state, source_id) VALUES (?,?,?,?,?,?)",
                     (open_loop_id, "k-" + open_loop_id, "commitment", "open", "needs_review", "S1"))
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


@pytest.fixture()
def mcp_env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _seed_draft(db)
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    cfg = NasMcpConfig(
        db_path=Path(db), audit_dir=audit,
        roots={"vault": RootSpec("vault", vault, "read_write")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=audit / "bk", support_dir=audit / "support"),
    )
    _seed_open_loop(db)
    return {"broker": NasMcpBroker(cfg), "db": db}


def _ok(payload: dict) -> dict:
    assert payload["ok"] is True, payload
    return payload["result"]


# -- schema invariance -------------------------------------------------------------------
def test_no_schema_bump() -> None:
    # The workflow/MCP layer itself adds no schema; the head may advance for later N8C phases
    # (e.g. V109 N8C-18 feedback), so this asserts head-agnostic floor + no workflow tables below.
    assert LATEST_SCHEMA_VERSION >= 108


def test_no_workflow_persistence_table_in_migrator() -> None:
    # N8C-16 is MCP-only; the migrator must define no workflow run/event/receipt/history table.
    src = (_SRC / "store" / "migrator.py").read_text().lower()
    assert "assistant_workflow" not in src
    assert "workflow_run" not in src and "workflow_event" not in src


# -- tool inventory + finality -----------------------------------------------------------
def test_workflow_tools_registered_when_enabled(mcp_env) -> None:
    mcp = _FakeMcp()
    register_nas_mcp_tools(mcp, mcp_env["broker"])
    assert set(ASSISTANT_WORKFLOW_TOOLS) <= set(mcp.names)
    assert len(ASSISTANT_WORKFLOW_TOOLS) == 6


def test_kill_switch_disables_only_workflows(mcp_env, monkeypatch) -> None:
    # default ON
    assert _ok(mcp_env["broker"].dispatch("assistant_list_workflows", {}))
    monkeypatch.setenv("HB_MCP_ASSISTANT_WORKFLOWS", "0")
    disabled = mcp_env["broker"].dispatch("assistant_route_workflow", {"workflow_type": "source_file_lookup"})
    assert disabled["ok"] is False and disabled["error"] == "assistant_workflows_disabled"
    # siblings unaffected
    assert mcp_env["broker"].dispatch("assistant_list_drafts", {})["ok"] is True
    # and not registered when off
    mcp = _FakeMcp()
    register_nas_mcp_tools(mcp, mcp_env["broker"])
    assert not (set(ASSISTANT_WORKFLOW_TOOLS) & set(mcp.names))


def test_tool_count_delta_is_exactly_six(mcp_env, monkeypatch) -> None:
    # Delta proof (not brittle absolute): enabling workflows adds exactly the 6 workflow tools.
    monkeypatch.setenv("HB_MCP_ASSISTANT_WORKFLOWS", "0")
    off = _FakeMcp()
    register_nas_mcp_tools(off, mcp_env["broker"])
    monkeypatch.delenv("HB_MCP_ASSISTANT_WORKFLOWS", raising=False)
    on = _FakeMcp()
    register_nas_mcp_tools(on, mcp_env["broker"])
    added = set(on.names) - set(off.names)
    assert added == set(ASSISTANT_WORKFLOW_TOOLS)


def test_no_forbidden_substring_in_workflow_names() -> None:
    for name in ASSISTANT_WORKFLOW_TOOLS:
        assert not [v for v in _FORBIDDEN if v in name], name


def test_existing_finality_guard_still_passes(mcp_env) -> None:
    mcp = _FakeMcp()
    register_nas_mcp_tools(mcp, mcp_env["broker"])
    assistant = [n for n in mcp.names if n.startswith("assistant_")]
    for tools in (ASSISTANT_NAV_TOOLS, ASSISTANT_CONTEXT_PACK_TOOLS, ASSISTANT_MEMORY_TOOLS,
                  ASSISTANT_DECISION_MEMORY_TOOLS, ASSISTANT_REVIEW_TOOLS, ASSISTANT_INTELLIGENCE_TOOLS,
                  ASSISTANT_RESEARCH_PACKET_TOOLS, ASSISTANT_SOURCE_CONNECTOR_TOOLS,
                  ASSISTANT_ANSWER_DRAFT_TOOLS, ASSISTANT_WORKFLOW_TOOLS):
        assert set(tools) <= set(assistant)
    assert not [n for n in assistant if any(v in n for v in _FORBIDDEN)]


# -- tool behavior -----------------------------------------------------------------------
def test_list_workflows_returns_bounded_catalog(mcp_env) -> None:
    res = _ok(mcp_env["broker"].dispatch("assistant_list_workflows", {}))
    cat = res["catalog"]
    assert len(cat["workflow_types"]) == 11 and len(cat["routing_targets"]) == 11
    assert cat["router_version"] == "workflow-router-v1"


def test_route_workflow_returns_envelope_with_policies(mcp_env) -> None:
    res = _ok(mcp_env["broker"].dispatch("assistant_route_workflow",
                                         {"workflow_type": "draft_review", "draft_id": "D1"}))
    env = res["workflow"]
    assert env["status"] == "routed"
    assert env["action_policy"] == "no_execution" and env["execution_policy"] == "route_only"
    assert "draft_has_no_citations" in env["warnings"]


def test_context_is_bounded_whitelisted(mcp_env) -> None:
    res = _ok(mcp_env["broker"].dispatch("assistant_get_workflow_context",
                                         {"workflow_type": "ask_second_brain", "draft_id": "D1"}))
    ctx = res["workflow_context"]
    assert ctx["action_policy"] == "no_execution"
    blob = json.dumps(res)
    for forbidden in ("_json", "section_body", "evidence_excerpt", "result_json"):
        assert forbidden not in blob


def test_artifacts_are_references_not_payloads(mcp_env) -> None:
    res = _ok(mcp_env["broker"].dispatch("assistant_get_workflow_artifacts",
                                         {"workflow_type": "ask_second_brain", "draft_id": "D1"}))
    arts = res["workflow_artifacts"]
    assert "count" in arts and arts["action_policy"] == "no_execution"
    for art in arts["selected_artifacts"]:
        assert set(art) <= {"target", "artifact_kind", "artifact_id", "metadata", "query", "source_root_key"}
        # metadata carries only bounded scalars, never *_json blobs
        assert not any(k.endswith("_json") for k in art.get("metadata", {}))


def test_policy_view_is_no_execution(mcp_env) -> None:
    res = _ok(mcp_env["broker"].dispatch("assistant_get_workflow_policy",
                                         {"workflow_type": "source_file_lookup", "query": "pdf"}))
    pol = res["workflow_policy"]
    assert pol["action_policy"] == "no_execution" and pol["execution_policy"] == "route_only"
    assert pol["review_policy"] == "preserve_review_state"
    assert pol["citation_policy"] == "preserve_citations"
    assert pol["source_policy"] == "use_existing_artifacts_only"


def test_summary_is_nonfinal_route_metadata(mcp_env) -> None:
    res = _ok(mcp_env["broker"].dispatch("assistant_get_workflow_summary",
                                         {"workflow_type": "draft_review", "draft_id": "D1"}))
    summ = res["workflow_summary"]
    assert "counts" in summ and "routing_decision" in summ
    assert summ["action_policy"] == "no_execution"
    blob = json.dumps(res).lower()
    for field in _FINALITY_FIELDS:
        assert field not in blob


def test_route_and_context_return_workflow_sections_for_implemented_workflows(mcp_env) -> None:
    # N8C-17 clarification #11: the UNCHANGED N8C-16 tool names now surface the richer context. Both
    # assistant_route_workflow and assistant_get_workflow_context return non-empty workflow_sections for an
    # implemented context workflow (open_loop_triage has a seeded open loop).
    routed = _ok(mcp_env["broker"].dispatch("assistant_route_workflow",
                                            {"workflow_type": "open_loop_triage"}))["workflow"]
    assert routed["status"] == "routed"
    assert routed["workflow_policy"] == "context_only"
    assert routed["workflow_sections"].get("active_open_loops")  # non-empty section

    ctx = _ok(mcp_env["broker"].dispatch("assistant_get_workflow_context",
                                         {"workflow_type": "open_loop_triage"}))["workflow_context"]
    assert "workflow_sections" in ctx and ctx["workflow_sections"].get("active_open_loops")
    assert ctx["workflow_policy"] == "context_only"
    # still bounded — no raw bodies/blobs leak through the context slice
    blob = json.dumps(ctx)
    for forbidden in ("_json", "section_body", "evidence_excerpt", "claim_text", "result_json"):
        assert forbidden not in blob


def test_daily_brief_route_carries_sections(mcp_env) -> None:
    # daily_brief_context assembles bounded recent-context sections from the seeded draft + open loop.
    env = _ok(mcp_env["broker"].dispatch("assistant_route_workflow",
                                         {"workflow_type": "daily_brief_context"}))["workflow"]
    assert env["status"] == "routed"
    assert any(env["workflow_sections"].get(s) for s in ("candidate_updates", "open_loops"))


def test_inputs_are_clamped(mcp_env) -> None:
    res = _ok(mcp_env["broker"].dispatch("assistant_route_workflow",
                                         {"workflow_type": "source_file_lookup", "query": "x" * 5000}))
    assert len(res["workflow"]["request"]["query"]) <= 1000


def test_source_lookup_routes_without_live_read(mcp_env) -> None:
    res = _ok(mcp_env["broker"].dispatch("assistant_route_workflow",
                                         {"workflow_type": "source_file_lookup", "query": "invoice pdf",
                                          "source_root_key": "work"}))
    env = res["workflow"]
    assert env["routing_decision"]["primary_target"] == "source_connector"


# -- read-only snapshot proof ------------------------------------------------------------
def test_snapshot_is_read_only(mcp_env) -> None:
    conn = sqlite3.connect(_ro_uri(mcp_env["db"]), uri=True)
    conn.execute("PRAGMA query_only=ON")
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE assistant_answer_drafts SET status='superseded'")
    finally:
        conn.close()


def _workflow_nodes() -> list[ast.AST]:
    """The workflow handler method + the four broker-side view helpers, isolated from the rest of broker.py."""
    src = (_SRC / "nas_mcp" / "broker.py").read_text()
    tree = ast.parse(src)
    wanted = {"_invoke_assistant_workflows", "_workflow_context_view", "_workflow_artifacts_view",
              "_workflow_policy_view", "_workflow_summary_view"}
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in wanted]


def test_handler_uses_query_only_and_ro_uri() -> None:
    # The workflow handler must open the RO snapshot with query_only=ON (mirrors the answer-draft handler).
    handler = next(n for n in _workflow_nodes() if n.name == "_invoke_assistant_workflows")
    body = ast.unparse(handler)
    assert "_ro_uri(str(cfg.db_path))" in body
    assert "PRAGMA query_only=ON" in body
    assert "conn.close()" in body


def test_handler_calls_no_writer_or_source_read() -> None:
    # AST guard scoped to ONLY the workflow handler + views: no writer/scan/source-read/LLM symbol.
    called: set[str] = set()
    for node in _workflow_nodes():
        called |= {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
        called |= {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
    forbidden = {"upsert_draft", "upsert_packet", "persist_pack", "read_source_file", "reindex",
                 "build_answer_draft", "record_disposition", "SourceContentProvider", "scan"}
    assert not (called & forbidden), called & forbidden


def test_no_workflow_persistence_tables_written(mcp_env) -> None:
    # Routing must not create any table; the schema table set is unchanged after several routes.
    db = mcp_env["db"]
    with sqlite3.connect(db) as c:
        before = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("assistant_list_workflows", "assistant_route_workflow", "assistant_get_workflow_summary"):
        mcp_env["broker"].dispatch(t, {"workflow_type": "draft_review", "draft_id": "D1"})
    with sqlite3.connect(db) as c:
        after = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert before == after
    # Routing creates no workflow *persistence* table. The static prompt-routing manifest table
    # (``pa_prompt_workflow_recipes``, V114) is a migration-created read-only recipe store, not written
    # by routing — so guard that routing adds no workflow-named table rather than that none exists.
    assert {t for t in after if "workflow" in t} == {t for t in before if "workflow" in t}


def test_ai_outputs_remains_only_write(mcp_env, monkeypatch) -> None:
    # Under safe mode, workflow reads still work; the only remote write stays gated separately.
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    assert mcp_env["broker"].dispatch("assistant_list_workflows", {})["ok"] is True
    w = mcp_env["broker"].dispatch("ai_outputs_card_upsert",
                                   {"title": "t", "body_markdown": "b"})
    assert w["ok"] is False  # write denied under safe mode
