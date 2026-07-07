"""N8C-15 deterministic route-only router: intent resolution, artifact routing over existing N8C read
surfaces, deferred capabilities, bounded no-execution envelope, and hard no-build/no-write/no-MCP guards."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.workflow_models import WorkflowRequest
from hb_assistant.obsidian_mcp.workflow_router import WorkflowRouter, route_request
from hb_assistant.store.migrator import SQLiteMigrator

_SRC = Path(__file__).resolve().parents[1] / "src" / "hb_assistant"


def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "wf.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def _seed_draft(db: str, draft_id: str = "D1") -> None:
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO assistant_answer_drafts (draft_id, draft_type, title, status, "
                  "citation_count, candidate_section_count, excluded_count) VALUES (?,?,?,?,?,?,?)",
                  (draft_id, "review_aware_answer_draft", "T", "built", 0, 1, 0))


def _seed_packet(db: str, packet_id: str = "P1") -> None:
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO assistant_research_packets (packet_id, packet_type, title, status) "
                  "VALUES (?,?,?,?)", (packet_id, "decision_research_context", "T", "built"))


def _seed_decision(db: str, decision_id: str = "DEC1") -> None:
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO assistant_decision_records (decision_id, identity_key, decision_type, "
                  "status, review_state, source_id) VALUES (?,?,?,?,?,?)",
                  (decision_id, "k-" + decision_id, "decision", "accepted", "unreviewed", "S1"))


def _seed_open_loop(db: str, open_loop_id: str = "OL1") -> None:
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO assistant_open_loop_records (open_loop_id, identity_key, open_loop_type, "
                  "status, review_state, source_id) VALUES (?,?,?,?,?,?)",
                  (open_loop_id, "k-" + open_loop_id, "commitment", "open", "unreviewed", "S1"))


def _router(tmp_path: Path) -> WorkflowRouter:
    return WorkflowRouter(_db(tmp_path))


# -- intent resolution -------------------------------------------------------------------
def test_explicit_type_wins_over_keyword(tmp_path: Path) -> None:
    env = _router(tmp_path).route(WorkflowRequest.from_inputs(
        workflow_type="meeting_prep", query="find the invoice pdf"))
    assert env["workflow_type"] == "meeting_prep"
    assert env["metadata"]["resolution"] == "explicit"


def test_invalid_workflow_type_needs_clarification(tmp_path: Path) -> None:
    env = _router(tmp_path).route(WorkflowRequest.from_inputs(workflow_type="bogus"))
    assert env["workflow_type"] == "unknown"
    assert env["status"] == "needs_clarification"
    assert "unknown_workflow_type" in env["warnings"]


def test_ambiguous_query_insufficient_context(tmp_path: Path) -> None:
    env = _router(tmp_path).route(WorkflowRequest.from_inputs(query="draft meeting invoice"))
    assert env["workflow_type"] == "unknown"
    assert env["status"] == "insufficient_context"


def test_keyword_fallback_source_lookup(tmp_path: Path) -> None:
    env = _router(tmp_path).route(WorkflowRequest.from_inputs(query="which contract pdf covers this"))
    assert env["workflow_type"] == "source_file_lookup"
    assert env["metadata"]["resolution"] == "keyword_fallback"


# -- routing behavior --------------------------------------------------------------------
def test_source_file_lookup_routes_to_source_connector(tmp_path: Path) -> None:
    env = _router(tmp_path).route(WorkflowRequest.from_inputs(
        workflow_type="source_file_lookup", query="spec.pdf", source_root_key="work"))
    assert env["routing_decision"]["primary_target"] == "source_connector"
    assert env["status"] == "routed"
    assert env["selected_artifacts"][0]["target"] == "source_connector"
    assert env["selected_artifacts"][0]["source_root_key"] == "work"


def test_research_answer_routes_to_answer_drafts_when_draft_exists(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_draft(db)
    _seed_packet(db)
    env = WorkflowRouter(db).route(WorkflowRequest.from_inputs(
        workflow_type="research_answer", draft_id="D1", packet_id="P1"))
    assert env["status"] == "routed"
    assert env["selected_artifacts"][0]["target"] == "answer_drafts"  # draft preferred over packet


def test_research_answer_routes_to_packet_when_no_draft(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_packet(db)
    env = WorkflowRouter(db).route(WorkflowRequest.from_inputs(
        workflow_type="research_answer", packet_id="P1"))
    assert env["selected_artifacts"][0]["target"] == "research_packets"


def test_research_answer_without_id_needs_clarification(tmp_path: Path) -> None:
    env = _router(tmp_path).route(WorkflowRequest.from_inputs(workflow_type="research_answer"))
    assert env["status"] == "needs_clarification"
    assert env["selected_artifacts"] == []


def test_ask_prefers_draft_then_packet(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_draft(db)
    _seed_packet(db)
    env = WorkflowRouter(db).route(WorkflowRequest.from_inputs(
        workflow_type="ask_second_brain", draft_id="D1", packet_id="P1"))
    assert env["selected_artifacts"][0]["target"] == "answer_drafts"
    env2 = WorkflowRouter(db).route(WorkflowRequest.from_inputs(
        workflow_type="ask_second_brain", packet_id="P1"))
    assert env2["selected_artifacts"][0]["target"] == "research_packets"


def test_ask_without_artifact_is_insufficient_context(tmp_path: Path) -> None:
    env = _router(tmp_path).route(WorkflowRequest.from_inputs(workflow_type="ask_second_brain"))
    assert env["status"] == "insufficient_context"


def test_missing_required_artifact_not_built(tmp_path: Path) -> None:
    env = _router(tmp_path).route(WorkflowRequest.from_inputs(
        workflow_type="research_answer", draft_id="NOPE"))
    assert env["status"] == "missing_required_artifact"
    assert env["deferred_capabilities"]  # gap reported, never built


def test_meeting_prep_routes_but_marks_deferred(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_packet(db)
    env = WorkflowRouter(db).route(WorkflowRequest.from_inputs(
        workflow_type="meeting_prep", packet_id="P1"))
    assert env["status"] == "routed"
    assert "build_meeting_prep_context" in env["deferred_capabilities"]


def test_daily_brief_and_project_context_mark_deferred(tmp_path: Path) -> None:
    r = _router(tmp_path)
    for wf in ("daily_brief_context", "project_intelligence_context"):
        env = r.route(WorkflowRequest.from_inputs(workflow_type=wf))
        assert env["deferred_capabilities"]
        assert any("deferred to N8C-17" in s for s in env["advisory_next_steps"])


def test_open_loop_triage_routes_without_task_creation(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_open_loop(db)
    env = WorkflowRouter(db).route(WorkflowRequest.from_inputs(
        workflow_type="open_loop_triage", open_loop_id="OL1"))
    assert env["status"] == "routed"
    assert env["selected_artifacts"][0]["target"] == "open_loops"
    assert env["action_policy"] == "no_execution"


def test_decision_preference_lookup_routes_to_decision_memory(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_decision(db)
    env = WorkflowRouter(db).route(WorkflowRequest.from_inputs(
        workflow_type="decision_preference_lookup", decision_id="DEC1"))
    assert env["selected_artifacts"][0]["target"] == "decision_memory"


def test_draft_review_preserves_labels_and_flags_warnings(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_draft(db)  # citation_count=0, candidate_section_count=1
    env = WorkflowRouter(db).route(WorkflowRequest.from_inputs(
        workflow_type="draft_review", draft_id="D1"))
    assert env["status"] == "routed"
    assert "draft_has_no_citations" in env["warnings"]
    assert "draft_contains_candidate_content" in env["warnings"]


def test_action_draft_preparation_deferred_only(tmp_path: Path) -> None:
    env = _router(tmp_path).route(WorkflowRequest.from_inputs(
        workflow_type="action_draft_preparation"))
    assert env["status"] == "deferred"
    assert "stage_action_draft" in env["deferred_capabilities"]
    assert env["selected_artifacts"] == []
    assert env["action_policy"] == "no_execution" and env["execution_policy"] == "route_only"


# -- envelope invariants -----------------------------------------------------------------
def test_envelope_has_fixed_policies_and_is_bounded(tmp_path: Path) -> None:
    env = _router(tmp_path).route(WorkflowRequest.from_inputs(
        workflow_type="source_file_lookup", query="pdf"))
    for k, v in (("action_policy", "no_execution"), ("execution_policy", "route_only"),
                 ("review_policy", "preserve_review_state"), ("citation_policy", "preserve_citations"),
                 ("source_policy", "use_existing_artifacts_only")):
        assert env[k] == v
    assert len(env["workflow_id"]) == 24
    # normalized envelope carries every contract key
    for key in ("workflow_type", "request", "routing_decision", "selected_artifacts", "trusted_items",
                "candidate_items", "excluded_items", "citations", "source_refs", "review_labels",
                "open_questions", "risks_or_caveats", "deferred_capabilities", "advisory_next_steps",
                "requires_operator_review", "status", "warnings", "metadata"):
        assert key in env


def test_no_suggested_next_steps_field_uses_advisory(tmp_path: Path) -> None:
    # clarification #5: advisory-only naming, never an executable "suggested_next_steps"
    env = _router(tmp_path).route(WorkflowRequest.from_inputs(workflow_type="action_draft_preparation"))
    assert "suggested_next_steps" not in env
    assert "advisory_next_steps" in env


def test_envelope_carries_no_raw_bodies_or_payloads(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_draft(db)
    env = WorkflowRouter(db).route(WorkflowRequest.from_inputs(
        workflow_type="ask_second_brain", draft_id="D1"))
    blob = json.dumps(env)
    for forbidden in ("_json", "metadata_json", "section_body", "evidence_excerpt", "result_json"):
        assert forbidden not in blob


# -- hard boundary guards (AST: real calls/names, not docstring prose) -------------------
def test_router_calls_no_writer_or_worker() -> None:
    import ast

    tree = ast.parse((_SRC / "obsidian_mcp" / "workflow_router.py").read_text())
    called_attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    forbidden_calls = {
        "upsert_draft", "upsert_packet", "upsert_projection", "persist_pack", "persist_compilation",
        "record_disposition", "mark_open_loop_stale", "mark_answer_draft_stale_if_needed",
        "mark_research_packet_stale_if_needed", "mark_projection_stale_if_needed", "refresh_node_counts",
        "build_answer_draft", "build_research_packet", "read_source_file", "reindex", "scan",
    }
    assert not (called_attrs & forbidden_calls), called_attrs & forbidden_calls
    forbidden_imports = {"SourceContentProvider", "answer_draft_builder", "research_packet_builder"}
    assert not (imported & forbidden_imports), imported & forbidden_imports


def test_no_mcp_workflow_tools_added() -> None:
    for name in ("broker.py", "profile.py", "tool_registration.py"):
        text = (_SRC / "nas_mcp" / name).read_text().lower()
        assert "workflow" not in text, f"nas_mcp/{name} must not gain a workflow reference"


def test_convenience_route_request(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_packet(db)
    env = route_request(db, workflow_type="research_answer", packet_id="P1")
    assert env["status"] == "routed"


@pytest.mark.parametrize("wf", ["ask_second_brain", "research_answer", "source_file_lookup"])
def test_unmigrated_db_degrades_not_crashes(tmp_path: Path, wf: str) -> None:
    # A getter hitting a not-yet-provisioned table returns "absent" rather than raising.
    empty = str(tmp_path / "empty.sqlite")
    sqlite3.connect(empty).close()  # no migration → no assistant tables
    env = WorkflowRouter(empty).route(WorkflowRequest.from_inputs(workflow_type=wf, draft_id="X",
                                                                  packet_id="Y", query="pdf"))
    assert env["status"] in ("routed", "missing_required_artifact", "insufficient_context")
