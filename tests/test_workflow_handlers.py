"""N8C-17 deterministic, read-only workflow context-assembly handlers.

Proves the four context handlers (daily_brief_context, meeting_prep, project_intelligence_context,
open_loop_triage) assemble bounded ``workflow_sections`` over EXISTING N8C artifacts with conservative
review-state classification, no execution, no persistence, no source-file read, and no raw-body/blob leak.
"""

from __future__ import annotations

import ast
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import workflow_handlers as H
from hb_assistant.obsidian_mcp.workflow_models import WorkflowRequest
from hb_assistant.obsidian_mcp.workflow_router import WorkflowRouter
from hb_assistant.store.migrator import SQLiteMigrator

_SRC = Path(__file__).resolve().parents[1] / "src" / "hb_assistant"

# Execution verbs that must NEVER appear in advisory_next_steps (clarification #9).
_EXEC_VERBS = ("send", "schedule", "create task", "remind", "email", "notify", "assign", "close ",
               "reopen", "accept", "reject", "defer", "dispose", "launch", "run ", "execute", "build",
               "apply", "scan", "reindex", "create n8d")


# -- seed helpers ----------------------------------------------------------------------------
def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "h.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def _exec(db: str, sql: str, params: tuple) -> None:
    with sqlite3.connect(db) as c:
        c.execute(sql, params)


def _decision(db: str, did: str, *, status: str = "accepted", review_state: str = "operator_accepted",
              domain: str | None = None) -> None:
    _exec(db, "INSERT INTO assistant_decision_records (decision_id, identity_key, decision_type, status, "
              "review_state, domain, source_id) VALUES (?,?,?,?,?,?,?)",
          (did, "k-" + did, "decision", status, review_state, domain, "S1"))


def _preference(db: str, pid: str, *, status: str = "accepted",
                review_state: str = "operator_accepted") -> None:
    _exec(db, "INSERT INTO assistant_preference_records (preference_id, identity_key, preference_type, "
              "status, review_state, source_id) VALUES (?,?,?,?,?,?)",
          (pid, "k-" + pid, "user_preference", status, review_state, "S1"))


def _open_loop(db: str, oid: str, *, otype: str = "commitment", status: str = "open",
               review_state: str = "unreviewed", priority: str = "medium") -> None:
    _exec(db, "INSERT INTO assistant_open_loop_records (open_loop_id, identity_key, open_loop_type, status, "
              "review_state, priority, source_id) VALUES (?,?,?,?,?,?,?)",
          (oid, "k-" + oid, otype, status, review_state, priority, "S1"))


def _claim(db: str, cid: str, *, status: str = "accepted", review_state: str = "operator_accepted") -> None:
    _exec(db, "INSERT INTO assistant_claims (claim_id, claim_type, claim_text, evidence_excerpt, "
              "confidence, status, review_state, extracted_by, source_id, source_root_key, source_rel_path) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
          (cid, "fact", "SECRET CLAIM BODY", "SECRET EVIDENCE EXCERPT", 0.9, status, review_state,
           "rule_based", "S1", "work", "a/b.pdf"))


def _draft(db: str, did: str = "D1", *, citation_count: int = 0, candidate: int = 1) -> None:
    _exec(db, "INSERT INTO assistant_answer_drafts (draft_id, draft_type, title, status, citation_count, "
              "candidate_section_count, excluded_count) VALUES (?,?,?,?,?,?,?)",
          (did, "review_aware_answer_draft", "T", "built", citation_count, candidate, 0))


def _packet(db: str, pid: str = "P1") -> None:
    _exec(db, "INSERT INTO assistant_research_packets (packet_id, packet_type, title, status) "
              "VALUES (?,?,?,?)", (pid, "decision_research_context", "T", "built"))


def _route(db: str, wf: str, **inputs) -> dict:
    return WorkflowRouter(db).route(WorkflowRequest.from_inputs(workflow_type=wf, **inputs))


# ============================================================================================
# classification (clarification #8)
# ============================================================================================
@pytest.mark.parametrize("rec,expected", [
    ({"status": "accepted", "review_state": "operator_accepted"}, H.TRUSTED),
    ({"review_state": "operator_accepted"}, H.TRUSTED),
    ({"effective_state": "accepted"}, H.TRUSTED),
    ({"status": "candidate", "review_state": "unreviewed"}, H.CANDIDATE),
    ({"review_state": "needs_review"}, H.CANDIDATE),
    ({"effective_state": "candidate"}, H.CANDIDATE),
    ({"status": "rejected"}, H.EXCLUDED),
    ({"review_state": "operator_rejected"}, H.EXCLUDED),
    ({"effective_state": "superseded"}, H.EXCLUDED),
    ({"effective_state": "stale"}, H.EXCLUDED),
    ({"effective_state": "not_required"}, H.EXCLUDED),
    ({}, H.CANDIDATE),                                            # missing → candidate
    ({"status": "built"}, H.CANDIDATE),                          # unknown token → candidate
    ({"status": "accepted", "review_state": "needs_review"}, H.CANDIDATE),   # contradictory → candidate
    # overlay WINS over the record's own status
    ({"status": "accepted", "review_state": "operator_rejected"}, H.EXCLUDED),
    ({"status": "accepted", "review_state": "unreviewed"}, H.CANDIDATE),
])
def test_classify_is_conservative(rec: dict, expected: str) -> None:
    assert H._classify(rec) == expected


# ============================================================================================
# daily_brief_context
# ============================================================================================
def test_daily_brief_sections_present_and_split(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _decision(db, "DTRUST", review_state="operator_accepted")
    _decision(db, "DCAND", status="candidate", review_state="unreviewed")
    _decision(db, "DREJ", status="rejected", review_state="operator_rejected")
    _open_loop(db, "OL1", status="open")
    env = _route(db, "daily_brief_context")
    ws = env["workflow_sections"]
    assert env["status"] == "routed" and env["workflow_policy"] == "context_only"
    for name in ("trusted_updates", "candidate_updates", "open_loops", "review_needed"):
        assert name in ws
    t_ids = {a["artifact_id"] for a in ws["trusted_updates"]}
    c_ids = {a["artifact_id"] for a in ws["candidate_updates"]}
    assert "DTRUST" in t_ids
    assert "DCAND" in c_ids
    # rejected/superseded/stale NEVER appears in a trusted section
    assert "DREJ" not in t_ids
    assert "OL1" in {a["artifact_id"] for a in ws["open_loops"]}


def test_daily_brief_empty_db_is_insufficient_context(tmp_path: Path) -> None:
    env = _route(_db(tmp_path), "daily_brief_context")
    assert env["status"] == "insufficient_context"
    assert not any(env["workflow_sections"].values())
    assert env["requires_operator_review"] is False or env["requires_operator_review"] is True  # bool


def test_daily_brief_candidate_flagged_and_caveated(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _decision(db, "DCAND", status="candidate", review_state="unreviewed")
    env = _route(db, "daily_brief_context")
    assert env["candidate_items"]
    assert any("candidate" in c.lower() for c in env["risks_or_caveats"])
    assert env["requires_operator_review"] is True


# ============================================================================================
# meeting_prep
# ============================================================================================
def test_meeting_prep_named_sections_and_objective_echo(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _decision(db, "DEC1")
    _preference(db, "PREF1")
    _open_loop(db, "OL1")
    env = _route(db, "meeting_prep", objective="scope", meeting_title="Weekly",
                 attendee_names=["Alice", "Bob"])
    ws = env["workflow_sections"]
    for name in ("meeting_objective", "trusted_context", "candidate_context", "prior_decisions",
                 "known_preferences", "open_loops", "questions_to_resolve"):
        assert name in ws
    echo = ws["meeting_objective"][0]
    assert echo["objective"] == "scope" and echo["meeting_title"] == "Weekly"
    assert echo["attendee_count"] == 2
    assert {a["artifact_id"] for a in ws["prior_decisions"]} == {"DEC1"}


def test_meeting_prep_missing_supplied_artifact_warns_not_builds(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _decision(db, "DEC1")
    env = _route(db, "meeting_prep", draft_id="NOPE")
    assert "missing_draft" in env["warnings"]
    assert env["status"] == "routed"  # other context still assembled
    assert any("could not be found" in q for q in env["workflow_sections"]["questions_to_resolve"])


def test_meeting_prep_explicit_draft_citations_and_missing_coverage(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _draft(db, "D1", citation_count=0, candidate=1)   # trusted-selected explicit artifact, zero citations
    env = _route(db, "meeting_prep", draft_id="D1")
    # the supplied draft is trusted_context by operator selection; it has no citations/source refs
    assert any(a["artifact_id"] == "D1" for a in env["workflow_sections"]["trusted_context"])
    assert "missing_citation_coverage" in env["warnings"]
    assert "draft_has_no_citations" in env["warnings"]


# ============================================================================================
# project_intelligence_context
# ============================================================================================
def test_project_intelligence_sections_and_scope(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _claim(db, "C1", review_state="operator_accepted")
    _claim(db, "C2", review_state="unreviewed")
    _decision(db, "DEC1")
    _open_loop(db, "OL1")
    env = _route(db, "project_intelligence_context", query="rfi", project_key="TWN", domain="construction")
    ws = env["workflow_sections"]
    for name in ("project_scope", "trusted_facts", "candidate_findings", "source_files",
                 "decisions_preferences", "open_loops", "review_needed"):
        assert name in ws
    assert ws["project_scope"][0]["project_key"] == "TWN"
    assert "C1" in {a["artifact_id"] for a in ws["trusted_facts"]}
    assert "C2" in {a["artifact_id"] for a in ws["candidate_findings"]}


def test_project_intelligence_claim_bodies_never_leak(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _claim(db, "C1", review_state="operator_accepted")
    env = _route(db, "project_intelligence_context", query="rfi")
    blob = json.dumps(env)
    assert "SECRET CLAIM BODY" not in blob
    assert "SECRET EVIDENCE EXCERPT" not in blob
    assert "claim_text" not in blob and "evidence_excerpt" not in blob


def test_source_files_carry_bounded_metadata_never_snippet() -> None:
    # A source-index row shape → the handler's whitelist keeps refs/metadata but NEVER a snippet/body.
    from hb_assistant.obsidian_mcp.workflow_models import bounded_metadata
    from hb_assistant.obsidian_mcp.workflow_router import _SOURCE_FILE_WL
    row = {"source_id": "sid", "source_ref": "ref", "source_root_key": "work", "rel_path": "a/b.pdf",
           "source_kind": "external_file", "extension": "pdf", "mime_type": "application/pdf",
           "snippet": "RAW FILE CONTENT SNIPPET"}
    out = bounded_metadata(row, _SOURCE_FILE_WL)
    assert "snippet" not in out
    assert out["source_ref"] == "ref" and out["rel_path"] == "a/b.pdf"


def test_project_intelligence_source_files_absent_index_is_empty(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _claim(db, "C1", review_state="operator_accepted")
    env = _route(db, "project_intelligence_context", query="rfi", source_root_key="work")
    assert env["workflow_sections"]["source_files"] == []  # no index rows → empty, no crash, no live read


# ============================================================================================
# open_loop_triage
# ============================================================================================
def test_open_loop_triage_buckets(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _open_loop(db, "ACT", otype="commitment", status="open", review_state="unreviewed")
    _open_loop(db, "WAIT", otype="waiting_for", status="open")
    _open_loop(db, "CAND", otype="commitment", status="candidate")
    _open_loop(db, "STALE", otype="commitment", status="stale")
    _open_loop(db, "CLOSED", otype="commitment", status="closed")
    _decision(db, "DEC1")
    env = _route(db, "open_loop_triage")
    ws = env["workflow_sections"]
    assert {a["artifact_id"] for a in ws["active_open_loops"]} == {"ACT"}
    assert {a["artifact_id"] for a in ws["blocked_or_waiting"]} == {"WAIT"}
    assert {a["artifact_id"] for a in ws["candidate_open_loops"]} == {"CAND"}
    assert {a["artifact_id"] for a in ws["stale_or_superseded"]} == {"STALE"}
    assert "ACT" in {a["artifact_id"] for a in ws["review_needed"]}
    # stale is inactive → NOT also flagged as needing review
    assert "STALE" not in {a["artifact_id"] for a in ws["review_needed"]}
    # closed (resolved) is surfaced nowhere
    all_ids = {a["artifact_id"] for sec in ws.values() for a in sec if isinstance(a, dict) and "artifact_id" in a}
    assert "CLOSED" not in all_ids
    assert {a["artifact_id"] for a in ws["related_decisions"]} == {"DEC1"}


def test_open_loop_triage_explicit_missing_is_missing_required(tmp_path: Path) -> None:
    env = _route(_db(tmp_path), "open_loop_triage", open_loop_id="NOPE")
    assert env["status"] == "missing_required_artifact"
    assert env["deferred_capabilities"]  # gap reported, never built


def test_open_loop_triage_explicit_present(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _open_loop(db, "OL1", status="open")
    env = _route(db, "open_loop_triage", open_loop_id="OL1")
    assert env["status"] == "routed"
    assert "OL1" in {a["artifact_id"] for a in env["workflow_sections"]["active_open_loops"]}


# ============================================================================================
# cross-cutting invariants
# ============================================================================================
_WORKFLOWS = ("daily_brief_context", "meeting_prep", "project_intelligence_context", "open_loop_triage")


@pytest.mark.parametrize("wf", _WORKFLOWS)
def test_policies_intact_and_context_only(tmp_path: Path, wf: str) -> None:
    db = _db(tmp_path)
    _decision(db, "DEC1")
    _open_loop(db, "OL1")
    env = _route(db, wf, query="rfi", project_key="TWN")
    assert env["action_policy"] == "no_execution"
    assert env["execution_policy"] == "route_only"
    assert env["review_policy"] == "preserve_review_state"
    assert env["citation_policy"] == "preserve_citations"
    assert env["source_policy"] == "use_existing_artifacts_only"
    assert env["workflow_policy"] == "context_only"


@pytest.mark.parametrize("wf", _WORKFLOWS)
def test_no_raw_bodies_or_blobs(tmp_path: Path, wf: str) -> None:
    db = _db(tmp_path)
    _decision(db, "DEC1")
    _preference(db, "PREF1")
    _open_loop(db, "OL1")
    _claim(db, "C1", review_state="operator_accepted")
    _draft(db, "D1")
    env = _route(db, wf, draft_id="D1", query="rfi", project_key="TWN")
    blob = json.dumps(env)
    for forbidden in ("_json", "metadata_json", "section_body", "evidence_excerpt", "claim_text",
                      "result_json", "snippet", "SECRET CLAIM BODY", "SECRET EVIDENCE EXCERPT"):
        assert forbidden not in blob, (wf, forbidden)


@pytest.mark.parametrize("wf", _WORKFLOWS)
def test_advisory_next_steps_are_advisory_only(tmp_path: Path, wf: str) -> None:
    db = _db(tmp_path)
    _decision(db, "DEC1")
    _open_loop(db, "OL1")
    env = _route(db, wf, query="rfi", project_key="TWN")
    for step in env["advisory_next_steps"]:
        low = step.lower()
        for verb in _EXEC_VERBS:
            assert verb not in low, (wf, verb, step)


@pytest.mark.parametrize("wf", _WORKFLOWS)
def test_bounded_no_build_marker(tmp_path: Path, wf: str) -> None:
    env = _route(_db(tmp_path), wf)
    assert not any(cap.startswith("build_") for cap in env["deferred_capabilities"])


def test_limit_is_clamped() -> None:
    from hb_assistant.obsidian_mcp.workflow_models import DEFAULT_ASSEMBLY_LIMIT, MAX_ITEMS
    assert WorkflowRequest.from_inputs(limit=99999).limit == MAX_ITEMS
    assert WorkflowRequest.from_inputs(limit=0).limit == 1
    assert WorkflowRequest.from_inputs(limit="nope").limit == DEFAULT_ASSEMBLY_LIMIT
    assert WorkflowRequest.from_inputs().limit == DEFAULT_ASSEMBLY_LIMIT


def test_unmigrated_db_degrades_not_crashes(tmp_path: Path) -> None:
    empty = str(tmp_path / "empty.sqlite")
    sqlite3.connect(empty).close()  # no assistant tables
    for wf in _WORKFLOWS:
        env = WorkflowRouter(empty).route(WorkflowRequest.from_inputs(workflow_type=wf, query="x"))
        assert env["status"] in ("routed", "insufficient_context", "missing_required_artifact")


# -- AST guard: handlers are read-only (no writer/worker/source-read/LLM) ---------------------
def test_handlers_source_has_no_writer_or_source_read() -> None:
    tree = ast.parse((_SRC / "obsidian_mcp" / "workflow_handlers.py").read_text())
    called = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    forbidden_calls = {"upsert_draft", "upsert_packet", "persist_pack", "record_disposition",
                       "build_answer_draft", "build_research_packet", "read_source_file",
                       "source_file_read", "reindex", "scan", "list_source_files"}
    assert not (called & forbidden_calls), called & forbidden_calls
    forbidden_imports = {"SourceContentProvider", "answer_draft_builder", "research_packet_builder"}
    assert not (imported & forbidden_imports), imported & forbidden_imports
