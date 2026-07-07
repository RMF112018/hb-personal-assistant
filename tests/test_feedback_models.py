"""N8C-18 feedback models: deterministic + idempotent identity, bounded caps, fixed advisory policy, and the
conservative feedback-type → ADVISORY recommendation derivation (never an applied disposition)."""

from __future__ import annotations

from hb_assistant.obsidian_mcp import feedback_models as M


def _target(kind: str = "open_loop", tid: str = "ol-1", **anchors: str) -> M.FeedbackTarget:
    return M.FeedbackTarget(target_kind=kind, target_id=tid, anchors=dict(anchors))


def test_feedback_id_is_deterministic_and_idempotent() -> None:
    sigs = [_target().signature()]
    a = M.compute_feedback_id("needs_review", sigs, "note", "cli")
    b = M.compute_feedback_id("needs_review", sigs, "note", "cli")
    assert a == b and len(a) == 24


def test_feedback_id_varies_by_type_targets_note_author() -> None:
    sigs = [_target().signature()]
    base = M.compute_feedback_id("needs_review", sigs, "note", "cli")
    assert M.compute_feedback_id("incorrect", sigs, "note", "cli") != base
    assert M.compute_feedback_id("needs_review", [_target(tid="ol-2").signature()], "note", "cli") != base
    assert M.compute_feedback_id("needs_review", sigs, "other", "cli") != base
    assert M.compute_feedback_id("needs_review", sigs, "note", "service") != base


def test_target_signature_folds_sorted_anchors() -> None:
    t1 = _target(open_loop_id="ol-1", workflow_id="wf-1")
    t2 = _target(workflow_id="wf-1", open_loop_id="ol-1")
    assert t1.signature() == t2.signature()  # anchor order does not matter


def test_normalized_anchors_drops_unknown_and_bounds() -> None:
    t = M.FeedbackTarget(target_kind="citation", target_id="c1",
                         anchors={"citation_id": "cid", "not_a_field": "x", "source_ref": "sr"})
    anchors = t.normalized_anchors()
    assert anchors == {"citation_id": "cid", "source_ref": "sr"}


def test_target_to_row_rejects_unknown_kind() -> None:
    t = M.FeedbackTarget(target_kind="not_a_kind", target_id="x")
    try:
        t.to_row("f", 0)
        raised = False
    except M.FeedbackValidationError:
        raised = True
    assert raised


def test_target_to_row_requires_target_id() -> None:
    t = M.FeedbackTarget(target_kind="open_loop", target_id="   ")
    try:
        t.to_row("f", 0)
        raised = False
    except M.FeedbackValidationError:
        raised = True
    assert raised


def test_note_is_bounded() -> None:
    long_note = "x" * (M.NOTE_HARD_CAP + 500)
    d1 = M.compute_feedback_input_digest("operator_note", [_target().signature()], long_note, "cli")
    # digest folds bound_text(note) — a note past the cap is truncated before hashing, never stored raw here.
    assert len(d1) == 24


def test_fixed_policy_block_is_advisory_no_execution() -> None:
    assert M.FEEDBACK_POLICY_BLOCK == {
        "action_policy": "no_execution",
        "execution_policy": "feedback_only",
        "review_policy": "advisory_review_loop",
        "source_policy": "preserve_source_truth",
        "citation_policy": "preserve_citations",
        "requires_operator_review": 1,
    }


def test_recommendation_row_pins_advisory_and_operator_review() -> None:
    rec = M.FeedbackRecommendation(recommendation_type="suggest_review", target_kind="open_loop",
                                   target_id="ol-1")
    row = rec.to_row("f", 0)
    assert row["review_policy"] == "advisory_review_loop"
    assert row["requires_operator_review"] == 1


def test_recommendation_rejects_unknown_type() -> None:
    rec = M.FeedbackRecommendation(recommendation_type="accept")
    try:
        rec.to_row("f", 0)
        raised = False
    except M.FeedbackValidationError:
        raised = True
    assert raised


def test_useful_derives_no_recommendation() -> None:
    assert M.derive_recommendations("useful", [_target()]) == []


def test_derivation_maps_are_advisory_only() -> None:
    # Every derived recommendation type must be a SUGGESTION — never an accept/reject/defer/dispose value.
    forbidden = {"accept", "reject", "defer", "dispose", "apply", "execute", "close"}
    for ftype in M.FEEDBACK_TYPES:
        recs = M.derive_recommendations(ftype, [_target()])
        for r in recs:
            assert r.recommendation_type in M.RECOMMENDATION_TYPES
            assert not any(bad in r.recommendation_type for bad in forbidden)


def test_specific_type_mappings() -> None:
    assert M.derive_recommendations("wrong_source", [_target()])[0].recommendation_type == \
        "suggest_source_check"
    assert M.derive_recommendations("duplicate", [_target()])[0].recommendation_type == \
        "suggest_deduplicate"
    assert M.derive_recommendations("candidate_should_be_trusted", [_target()])[0].recommendation_type == \
        "suggest_relabel_trusted"
    assert M.derive_recommendations("should_be_excluded", [_target()])[0].recommendation_type == \
        "suggest_exclude"


def test_recommendation_anchored_to_primary_target() -> None:
    recs = M.derive_recommendations("needs_review", [_target(tid="ol-primary"), _target(tid="ol-2")])
    assert recs[0].target_id == "ol-primary"
