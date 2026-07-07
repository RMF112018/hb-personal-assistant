"""N8C-15 workflow models: bounded requests, conservative keyword classification, deterministic ephemeral
ids, whitelisted bounded metadata, and the fixed no-execution policy block."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.workflow_models import (
    ACTION_POLICY,
    EXECUTION_POLICY,
    ID_HARD_CAP,
    POLICY_BLOCK,
    QUERY_HARD_CAP,
    WF_DECISION_PREFERENCE_LOOKUP,
    WF_MEETING_PREP,
    WF_SOURCE_FILE_LOOKUP,
    WF_UNKNOWN,
    WORKFLOW_TYPES,
    WorkflowRequest,
    bounded_metadata,
    classify_workflow_type_from_keywords,
    compute_workflow_id,
)


def test_policy_block_is_no_execution() -> None:
    assert POLICY_BLOCK["action_policy"] == ACTION_POLICY == "no_execution"
    assert POLICY_BLOCK["execution_policy"] == EXECUTION_POLICY == "route_only"
    assert POLICY_BLOCK["review_policy"] == "preserve_review_state"
    assert POLICY_BLOCK["citation_policy"] == "preserve_citations"
    assert POLICY_BLOCK["source_policy"] == "use_existing_artifacts_only"


def test_canonical_workflow_types_present() -> None:
    assert len(WORKFLOW_TYPES) == 11
    assert WF_UNKNOWN in WORKFLOW_TYPES


def test_request_bounds_text_and_ids() -> None:
    req = WorkflowRequest.from_inputs(query="x" * (QUERY_HARD_CAP + 500),
                                      draft_id="  d1  ", workflow_type="ask_second_brain")
    assert len(req.query) == QUERY_HARD_CAP
    assert req.draft_id == "d1"  # trimmed
    assert req.artifact_ids() == {"draft_id": "d1"}


def test_request_blank_ids_become_none() -> None:
    req = WorkflowRequest.from_inputs(draft_id="   ", packet_id="")
    assert req.draft_id is None and req.packet_id is None
    assert req.artifact_ids() == {}


def test_keyword_single_category() -> None:
    assert classify_workflow_type_from_keywords("find the invoice pdf", None) == WF_SOURCE_FILE_LOOKUP
    assert classify_workflow_type_from_keywords("what was decided", None) == WF_DECISION_PREFERENCE_LOOKUP
    assert classify_workflow_type_from_keywords("meeting agenda attendee", None) == WF_MEETING_PREP


def test_keyword_ambiguous_or_empty_is_unknown() -> None:
    # two categories → conflicting → unknown (conservative)
    assert classify_workflow_type_from_keywords("draft meeting invoice", None) == WF_UNKNOWN
    assert classify_workflow_type_from_keywords("", None) == WF_UNKNOWN
    assert classify_workflow_type_from_keywords(None, None) == WF_UNKNOWN
    assert classify_workflow_type_from_keywords("hello there", None) == WF_UNKNOWN


def test_workflow_id_is_deterministic_and_bounded() -> None:
    r1 = WorkflowRequest.from_inputs(workflow_type="source_file_lookup", query="pdf")
    r2 = WorkflowRequest.from_inputs(workflow_type="source_file_lookup", query="pdf")
    wid1 = compute_workflow_id("source_file_lookup", r1)
    wid2 = compute_workflow_id("source_file_lookup", r2)
    assert wid1 == wid2 and len(wid1) == 24
    r3 = WorkflowRequest.from_inputs(workflow_type="source_file_lookup", query="other")
    assert compute_workflow_id("source_file_lookup", r3) != wid1


def test_bounded_metadata_drops_json_and_nested() -> None:
    record = {"draft_id": "D", "status": "built", "section_count": 3, "truncated": False,
              "metadata_json": '{"secret": "x"}', "draft_policy_json": "{}", "nested": {"a": 1},
              "body": "y" * 5000}
    out = bounded_metadata(record, ("draft_id", "status", "section_count", "truncated",
                                    "metadata_json", "draft_policy_json", "nested", "body"))
    # scalars kept
    assert out["draft_id"] == "D" and out["status"] == "built"
    assert out["section_count"] == 3 and out["truncated"] is False
    # *_json blobs skipped even when whitelisted; nested dict dropped; body capped
    assert "metadata_json" not in out and "draft_policy_json" not in out
    assert "nested" not in out
    assert len(out["body"]) <= 300  # capped


def test_id_hard_cap() -> None:
    req = WorkflowRequest.from_inputs(draft_id="d" * (ID_HARD_CAP + 100))
    assert len(req.draft_id) == ID_HARD_CAP
