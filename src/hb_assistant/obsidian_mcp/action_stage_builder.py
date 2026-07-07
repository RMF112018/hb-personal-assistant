"""N8C-19 action-stage builder — deterministic, source-backed, workflow-scoped, NO execution, NO LLM.

Materializes a bounded stage of proposed follow-up CANDIDATES for ONE N8C-17 workflow request by REUSING that
workflow's read-only CONTEXT envelope (``WorkflowRouter.route``) and, optionally, the N8C-18 ADVISORY feedback
recommendations (``FeedbackRepository.list_recommendations``). It never re-derives review state, never infers
new facts, never reads a source file, and never mutates any upstream record.

  1. ``router.route(request, conn=conn)`` returns the workflow envelope with named ``workflow_sections``,
     ``advisory_next_steps``, ``citations`` and ``source_refs`` — all already bounded + read-only.
  2. Each workflow section is mapped to a candidate ``action_kind`` (open_loops → open_loop_follow_up,
     review_needed → review_candidate, risks_or_caveats → project_risk_review, questions_to_resolve →
     information_gap_review, prior/related decisions → decision_review, known_preferences → preference_review,
     source_files → source_review). Trusted/context sections (trusted_facts/updates/items, project_scope) are
     established knowledge, NOT follow-ups → skipped. Terminal sections (stale_or_superseded, excluded_items)
     stage as ``blocked`` only.
  3. Each ``advisory_next_steps`` entry stages as ``human_follow_up`` — UNLESS it reads like an execution
     instruction (send/email/schedule/create-task/…), in which case it is staged ``blocked`` with
     ``block_reason='execution_like_advisory'`` (never active). This is the advisory-only gate.
  4. Each feedback recommendation stages as an advisory review candidate, anchored to its feedback lineage.
  5. Every staged item is pinned to not_executed / external_system=none / external_ref=None /
     requires_operator_review=1, and carries preserved provenance (bounded ids) + a source-backing citation
     when it is grounded in an existing artifact.

``preview`` is fully read-only; rows are persisted only by ``build_action_stage(apply=True)`` and only into the
five V110 action-stage tables (via the repository). Determinism makes rebuilds idempotent; a changed workflow
context / feedback recommendation changes ``input_digest`` → a new stage that supersedes the prior one of the
same type + workflow + request + policy.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from hb_assistant.store.assistant_review_tables import EFFECTIVE_STATE_VALUES, REVIEW_STATE_VALUES

from . import action_stage_models as M
from .workflow_models import WorkflowRequest

_VALID_REVIEW_STATES = frozenset(REVIEW_STATE_VALUES)
_VALID_EFFECTIVE_STATES = frozenset(EFFECTIVE_STATE_VALUES)

# workflow_type → stage_type (the N8C-17 workflow the context came from).
_WORKFLOW_STAGE_TYPE = {
    "daily_brief_context": "daily_brief_actions",
    "meeting_prep": "meeting_follow_ups",
    "project_intelligence_context": "project_actions",
    "open_loop_triage": "open_loop_actions",
    "draft_review": "review_follow_ups",
}

# workflow_sections name → (action_kind, staged_state). A None value means the section is established context,
# not a follow-up action (skipped). Terminal sections stage blocked-only.
_C, _B = M.STATE_CANDIDATE, M.STATE_BLOCKED
_SECTION_MAP: dict[str, tuple[str, str] | None] = {
    "open_loops": ("open_loop_follow_up", _C),
    "active_open_loops": ("open_loop_follow_up", _C),
    "candidate_open_loops": ("open_loop_follow_up", _C),
    "blocked_or_waiting": ("open_loop_follow_up", _C),
    "review_needed": ("review_candidate", _C),
    "candidate_updates": ("review_candidate", _C),
    "candidate_findings": ("review_candidate", _C),
    "candidate_items": ("review_candidate", _C),
    "risks_or_caveats": ("project_risk_review", _C),
    "questions_to_resolve": ("information_gap_review", _C),
    "prior_decisions": ("decision_review", _C),
    "related_decisions": ("decision_review", _C),
    "decisions_preferences": ("decision_review", _C),
    "known_preferences": ("preference_review", _C),
    "source_files": ("source_review", _C),
    # Established context — never a follow-up action.
    "trusted_facts": None,
    "trusted_updates": None,
    "trusted_items": None,
    "project_scope": None,
    # Terminal — staged blocked only (surfaced but withheld from candidacy).
    "stale_or_superseded": ("open_loop_follow_up", _B),
    "excluded_items": ("review_candidate", _B),
}

# artifact_kind → the provenance anchor field that carries its id.
_KIND_ANCHOR = {
    "open_loop": "open_loop_id", "decision": "decision_id", "preference": "preference_id",
    "review_item": "review_item_id", "claim": "claim_id", "projection_item": "projection_item_id",
    "draft": "draft_id", "packet": "packet_id", "context_pack": "context_pack_id",
    "memory_node": "memory_node_id", "source_file": "source_id",
}

# feedback recommendation_type → candidate action_kind (advisory; operator-review-required by construction).
_FEEDBACK_REC_MAP = {
    "suggest_review": "review_candidate",
    "suggest_more_context": "information_gap_review",
    "suggest_source_check": "source_review",
    "suggest_relabel_candidate": "review_candidate",
    "suggest_relabel_trusted": "review_candidate",
    "suggest_exclude": "review_candidate",
    "suggest_deduplicate": "review_candidate",
    "operator_note": "human_follow_up",
    "unknown": "human_follow_up",
}

# An advisory step reading like one of these is execution-like → staged blocked, never active.
_EXECUTION_VERBS = (
    "send ", "send an", "email", "schedule", "create task", "create a task", "add task", "remind",
    "reminder", "call ", "text ", "message ", "post ", "submit", "dispatch", "notify", "assign ",
    "book ", "execute", "run the", "file a", "reply to", "respond to", "draft an email",
)

# Deterministic stage ordering: candidate kinds first (by rank), blocked last.
_KIND_RANK = {
    "open_loop_follow_up": 0, "review_candidate": 1, "source_review": 2, "information_gap_review": 3,
    "project_risk_review": 4, "decision_review": 5, "preference_review": 6, "human_follow_up": 7,
    "unknown": 8,
}


@dataclass
class ActionStageProviders:
    router: Any                # workflow_router.WorkflowRouter
    feedback_repo: Any = None  # feedback_repository.FeedbackRepository | None (read-only advisory input)


def _valid_review_state(value: Any) -> str | None:
    v = str(value) if value else ""
    return v if v in _VALID_REVIEW_STATES else None


def _valid_effective_state(value: Any) -> str | None:
    v = str(value) if value else ""
    return v if v in _VALID_EFFECTIVE_STATES else None


def _is_execution_like(text: str) -> bool:
    low = f" {text.lower().strip()} "
    return any(v in low for v in _EXECUTION_VERBS)


def _item_from_entry(section_name: str, action_kind: str, state: str,
                     entry: Any) -> M.ActionStageItem | None:
    """Map one workflow-section entry (a bounded artifact dict, or a plain string) to a staged item."""
    if not isinstance(entry, dict):
        text = str(entry).strip()
        if not text:
            return None
        return M.ActionStageItem(action_kind=action_kind, staged_state=state, source_section=section_name,
                                 title=text, detail=text)
    kind = entry.get("artifact_kind")
    art_id = entry.get("artifact_id")
    meta = entry.get("metadata") or {}
    anchors: dict[str, Any] = {}
    anchor_field = _KIND_ANCHOR.get(str(kind))
    if anchor_field and art_id:
        anchors[anchor_field] = art_id
    for f in M.ITEM_ANCHOR_FIELDS:
        if meta.get(f):
            anchors[f] = meta[f]
    title = (meta.get("title") or meta.get("subject") or meta.get("summary") or art_id or section_name)
    detail = (meta.get("summary") or meta.get("description") or meta.get("review_label") or None)
    return M.ActionStageItem(
        action_kind=action_kind, staged_state=state, source_section=section_name,
        title=str(title) if title else None, detail=str(detail) if detail else None,
        target_kind=str(kind) if kind else None, target_id=str(art_id) if art_id else None,
        anchors=anchors, review_state=_valid_review_state(meta.get("review_state")),
        effective_state=_valid_effective_state(meta.get("effective_state")))


def _item_from_advisory(step: str, workflow_id: str | None) -> M.ActionStageItem:
    """An advisory next step → human_follow_up, UNLESS it is execution-like → blocked (never active)."""
    text = str(step).strip()
    if _is_execution_like(text):
        return M.ActionStageItem(action_kind="human_follow_up", staged_state=M.STATE_BLOCKED,
                                 source_section="advisory_next_steps", title=text, detail=text,
                                 block_reason="execution_like_advisory",
                                 anchors={"workflow_id": workflow_id} if workflow_id else {})
    return M.ActionStageItem(action_kind="human_follow_up", staged_state=M.STATE_CANDIDATE,
                             source_section="advisory_next_steps", title=text, detail=text,
                             anchors={"workflow_id": workflow_id} if workflow_id else {})


def _item_from_recommendation(rec: dict[str, Any]) -> M.ActionStageItem:
    """An N8C-18 ADVISORY feedback recommendation → an advisory review candidate, anchored to its lineage."""
    rtype = str(rec.get("recommendation_type") or "unknown")
    action_kind = _FEEDBACK_REC_MAP.get(rtype, "review_candidate")
    anchors: dict[str, Any] = {}
    for f in ("feedback_id", "recommendation_id"):
        if rec.get(f):
            anchors[f] = rec[f]
    tk, ti = rec.get("target_kind"), rec.get("target_id")
    if ti:
        anchors.setdefault(str(_KIND_ANCHOR.get(str(tk), "")) or "target", ti)
    title = rec.get("rationale") or f"Feedback recommendation: {rtype}"
    return M.ActionStageItem(
        action_kind=action_kind, staged_state=M.STATE_CANDIDATE, source_section="feedback_recommendations",
        title=str(title), detail=str(rec.get("rationale") or rtype),
        target_kind=str(tk) if tk else None, target_id=str(ti) if ti else None, anchors=anchors)


def _order_items(items: list[M.ActionStageItem]) -> list[M.ActionStageItem]:
    return sorted(items, key=lambda it: (
        1 if it.staged_state == M.STATE_BLOCKED else 0,
        _KIND_RANK.get(it.action_kind, 8),
        it.source_section or "", it.target_id or "", (it.title or "")[:80]))


def _citation_for_item(item: M.ActionStageItem, stage_item_id: str, order: int) -> M.ActionStageCitation | None:
    """One bounded source-backing citation per grounded item (carries the item's own provenance anchors).
    Text-only items (advisory/questions with no anchor + no target) get no citation."""
    anchors = item.normalized_anchors()
    if not anchors and not item.target_id:
        return None
    return M.ActionStageCitation(
        stage_item_id=stage_item_id, citation_order=order,
        citation_type=item.target_kind or "workflow_artifact",
        target_kind=item.target_kind, target_id=item.target_id, anchors=dict(anchors),
        citation_label=item.source_section)


def preview_action_stage(providers: ActionStageProviders, *, request_inputs: dict[str, Any] | None = None,
                         stage_type: str | None = None, budget: M.ActionStageBudget | None = None,
                         title: str | None = None, include_feedback: bool = True,
                         feedback_limit: int = 25, created_by: str = "service",
                         conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Build a bounded stage of proposed follow-up CANDIDATES WITHOUT persisting. Read-only."""
    budget = (budget or M.ActionStageBudget()).clamped()
    request = WorkflowRequest.from_inputs(**(request_inputs or {}))
    envelope = providers.router.route(request, conn=conn)
    wf_type = envelope.get("workflow_type")
    wf_id = envelope.get("workflow_id")
    resolved_type = stage_type or _WORKFLOW_STAGE_TYPE.get(str(wf_type), "mixed_actions")
    if resolved_type not in M.STAGE_TYPES:
        resolved_type = "unknown"

    raw: list[M.ActionStageItem] = []
    # 1. workflow_sections → candidate/blocked items.
    for section_name, entries in (envelope.get("workflow_sections") or {}).items():
        mapped = _SECTION_MAP.get(section_name)
        if mapped is None or not isinstance(entries, list):
            continue
        action_kind, state = mapped
        if state == M.STATE_BLOCKED and not budget.include_blocked:
            continue
        if state == M.STATE_CANDIDATE and not budget.include_candidates:
            continue
        per = 0
        for entry in entries:
            if per >= budget.max_items_per_section:
                break
            item = _item_from_entry(section_name, action_kind, state, entry)
            if item is not None:
                raw.append(item)
                per += 1
    # 2. advisory_next_steps → human_follow_up (execution-like → blocked).
    for step in (envelope.get("advisory_next_steps") or [])[:budget.max_items_per_section]:
        item = _item_from_advisory(str(step), wf_id)
        if item.staged_state == M.STATE_BLOCKED and not budget.include_blocked:
            continue
        raw.append(item)
    # 3. feedback recommendations → advisory review candidates.
    if include_feedback and providers.feedback_repo is not None and budget.include_candidates:
        try:
            recs = providers.feedback_repo.list_recommendations(None, limit=feedback_limit, conn=conn)
        except Exception:
            recs = []
        for rec in recs[:budget.max_items_per_section]:
            raw.append(_item_from_recommendation(rec))

    ordered = _order_items(raw)
    truncated = len(ordered) > budget.max_items
    kept = ordered[:budget.max_items]

    stage_policy_json = M.canonical_json({"stage_type": resolved_type, **M.STAGE_POLICY_BLOCK})
    budget_json = M.canonical_json(budget.to_dict())
    request_digest = M.compute_request_digest(resolved_type, wf_type, wf_id, stage_policy_json, budget_json)

    signatures = [it.signature() for it in kept]
    source_context_digest = M.compute_source_context_digest(signatures)
    input_digest = M.compute_stage_input_digest(request_digest, source_context_digest)
    stage_id = M.compute_stage_id(resolved_type, wf_type, request_digest, input_digest)

    item_rows: list[dict[str, Any]] = []
    citation_rows: list[dict[str, Any]] = []
    blocked_count = 0
    for order, item in enumerate(kept):
        if item.item_digest is None:
            item.item_digest = M.sha256_hex(item.signature())[:24]
        row = item.to_row(stage_id, order)
        item_rows.append(row)
        if row["staged_state"] == M.STATE_BLOCKED:
            blocked_count += 1
        cit = _citation_for_item(item, row["stage_item_id"], 0)
        if cit is not None:
            citation_rows.append(cit.to_row(stage_id, len(citation_rows)))

    output_digest = M.compute_stage_output_digest([r["stage_item_id"] for r in item_rows])
    stage = {
        "stage_id": stage_id, "stage_type": resolved_type,
        "workflow_type": wf_type, "workflow_id": wf_id,
        "title": (title or f"{resolved_type} for {wf_type or 'workflow'}")[:M.TITLE_HARD_CAP],
        "status": "staged", **M.STAGE_POLICY_BLOCK,
        "created_by": created_by, "request_digest": request_digest,
        "source_context_digest": source_context_digest, "input_digest": input_digest,
        "output_digest": output_digest, "stage_policy_json": stage_policy_json, "budget_json": budget_json,
        "item_count": len(item_rows), "blocked_count": blocked_count,
        "citation_count": len(citation_rows), "truncated": 1 if truncated else 0,
    }
    receipt = {
        "stage_receipt_id": M.compute_stage_receipt_id(stage_id, input_digest, output_digest),
        "stage_id": stage_id, "builder_version": M.ACTION_STAGE_BUILDER_VERSION,
        "request_digest": request_digest, "source_context_digest": source_context_digest,
        "input_digest": input_digest, "output_digest": output_digest, "item_count": len(item_rows),
        "blocked_count": blocked_count, "citation_count": len(citation_rows),
        "dropped_count": len(ordered) - len(kept), "truncated": 1 if truncated else 0,
    }
    return {
        "applied": False, "stage_id": stage_id, "stage": stage, "items": item_rows,
        "citations": citation_rows, "receipt": receipt, "workflow_type": wf_type, "workflow_id": wf_id,
        "workflow_status": envelope.get("status"), "counts": {"items": len(item_rows),
        "blocked": blocked_count, "citations": len(citation_rows)}, "truncated": truncated,
        "input_digest": input_digest, "output_digest": output_digest,
    }


def build_action_stage(providers: ActionStageProviders, repo: Any, *,
                       request_inputs: dict[str, Any] | None = None, stage_type: str | None = None,
                       budget: M.ActionStageBudget | None = None, apply: bool = False,
                       title: str | None = None, include_feedback: bool = True, feedback_limit: int = 25,
                       created_by: str = "service",
                       conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Preview, and — only when ``apply`` — persist into the five stage tables (nothing else). Idempotent:
    unchanged inputs create no duplicate; a changed workflow context / feedback recommendation changes
    ``input_digest`` → a new stage that supersedes the prior one of the same type+workflow+request+policy."""
    preview = preview_action_stage(providers, request_inputs=request_inputs, stage_type=stage_type,
                                   budget=budget, title=title, include_feedback=include_feedback,
                                   feedback_limit=feedback_limit, created_by=created_by, conn=conn)
    if not apply:
        return preview
    res = repo.upsert_stage(preview["stage"], preview["items"], preview["citations"], preview["receipt"],
                            conn=conn)
    return {"applied": True, "stage_id": preview["stage_id"], "created": res["created"],
            "reused": res.get("reused", False), "superseded": res.get("superseded", []),
            "counts": preview["counts"], "truncated": preview["truncated"],
            "workflow_type": preview["workflow_type"]}


def export_action_stage(repo: Any, *, stage_id: str, limit: int = 200,
                        conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Bounded JSON export of a persisted stage: header + bounded items + bounded citations. NO raw source/
    card/vault/email bodies, no full payloads, no execution fields, no external refs."""
    header = repo.get_stage(stage_id, conn=conn)
    if header is None:
        raise M.ActionStageValidationError(f"stage_not_found:{stage_id}")
    items = repo.list_items(stage_id, limit=limit, conn=conn)
    citations = repo.list_citations(stage_id, limit=limit, conn=conn)
    return {"format": "action_stage_export_v1", "stage": header, "items": items, "citations": citations,
            "item_count": len(items), "citation_count": len(citations)}
