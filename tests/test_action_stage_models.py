"""N8C-19 action-stage models: deterministic + idempotent identity, bounded caps, fixed no-execution policy,
pinned non-execution item fields, and provenance-anchored citations."""

from __future__ import annotations

from hb_assistant.obsidian_mcp import action_stage_models as M


def _item(kind: str = "open_loop_follow_up", state: str = M.STATE_CANDIDATE, **anchors: str):
    return M.ActionStageItem(action_kind=kind, staged_state=state, target_kind="open_loop",
                             target_id="OL1", anchors=dict(anchors))


def test_request_digest_is_deterministic() -> None:
    a = M.compute_request_digest("open_loop_actions", "open_loop_triage", "wf1", "pol", "bud")
    b = M.compute_request_digest("open_loop_actions", "open_loop_triage", "wf1", "pol", "bud")
    assert a == b and len(a) == 24


def test_stage_id_varies_by_type_and_input() -> None:
    rd = M.compute_request_digest("open_loop_actions", "open_loop_triage", "wf1", "pol", "bud")
    idg = M.compute_stage_input_digest(rd, "ctx1")
    base = M.compute_stage_id("open_loop_actions", "open_loop_triage", rd, idg)
    assert M.compute_stage_id("mixed_actions", "open_loop_triage", rd, idg) != base
    assert M.compute_stage_id("open_loop_actions", "open_loop_triage", rd,
                              M.compute_stage_input_digest(rd, "ctx2")) != base


def test_source_context_digest_order_independent() -> None:
    assert M.compute_source_context_digest(["a", "b"]) == M.compute_source_context_digest(["b", "a"])


def test_fixed_policy_block_is_no_execution() -> None:
    assert M.STAGE_POLICY_BLOCK == {
        "action_policy": "no_execution",
        "execution_policy": "staged_only",
        "workflow_policy": "staging_only",
        "review_policy": "preserve_review_state",
        "citation_policy": "preserve_citations",
        "source_policy": "use_existing_artifacts_only",
        "requires_operator_review": 1,
    }


def test_item_row_pins_non_execution_fields() -> None:
    row = _item(open_loop_id="OL1").to_row("stage1", 0)
    assert row["execution_status"] == "not_executed"
    assert row["external_system"] == "none"
    assert row["external_ref"] is None
    assert row["requires_operator_review"] == 1
    assert row["staged_state"] == M.STATE_CANDIDATE
    assert row["open_loop_id"] == "OL1"


def test_item_rejects_unknown_action_kind() -> None:
    it = M.ActionStageItem(action_kind="send_email")
    try:
        it.to_row("s", 0)
        raised = False
    except M.ActionStageValidationError:
        raised = True
    assert raised


def test_item_rejects_unknown_staged_state() -> None:
    it = M.ActionStageItem(action_kind="review_candidate", staged_state="active")
    try:
        it.to_row("s", 0)
        raised = False
    except M.ActionStageValidationError:
        raised = True
    assert raised


def test_action_kinds_are_internal_review_only() -> None:
    # No external-execution kind may exist in the vocabulary.
    forbidden = ("send", "email", "schedule", "dispatch", "create_task", "remind", "execute", "notify")
    for kind in M.ACTION_KINDS:
        assert not any(bad in kind for bad in forbidden), kind


def test_item_normalized_anchors_drops_unknown() -> None:
    it = M.ActionStageItem(action_kind="review_candidate",
                           anchors={"open_loop_id": "x", "not_a_field": "y", "feedback_id": "f"})
    assert it.normalized_anchors() == {"open_loop_id": "x", "feedback_id": "f"}


def test_citation_requires_anchor_or_target() -> None:
    cit = M.ActionStageCitation(stage_item_id="i")
    try:
        cit.to_row("s", 0)
        raised = False
    except M.ActionStageValidationError:
        raised = True
    assert raised


def test_citation_with_anchor_ok() -> None:
    cit = M.ActionStageCitation(stage_item_id="i", anchors={"open_loop_id": "OL1"})
    row = cit.to_row("s", 0)
    assert row["open_loop_id"] == "OL1"
    assert row["stage_item_id"] == "i"


def test_budget_clamps_and_never_carries_excerpts() -> None:
    b = M.ActionStageBudget(max_items=100000, include_citation_excerpts=True).clamped()
    assert b.max_items <= M.MAX_ITEMS_HARD_CAP
    assert b.include_citation_excerpts is False  # excerpts are never carried


def test_title_and_detail_are_bounded() -> None:
    it = M.ActionStageItem(action_kind="review_candidate", title="x" * (M.TITLE_HARD_CAP + 100),
                           detail="y" * (M.DETAIL_HARD_CAP + 100))
    row = it.to_row("s", 0)
    assert len(row["title"]) <= M.TITLE_HARD_CAP
    assert len(row["detail"]) <= M.DETAIL_HARD_CAP
