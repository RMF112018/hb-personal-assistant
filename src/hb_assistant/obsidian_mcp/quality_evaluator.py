"""N8C-20 quality evaluator — deterministic, read-only, NO execution, NO repair, NO LLM.

Evaluates ONE existing N8C target (action stage, feedback record, answer draft, research packet, workflow
route, or review item) by REUSING that family's read-only repository, and emits **advisory** quality findings
(freshness / citation coverage / review-state consistency / source-ref validity / policy compliance /
duplication / boundedness). It never rebuilds an artifact, repairs anything, executes anything, stages an
action, writes a review disposition, mutates any upstream record, contacts an external system, reads a source
file, or calls an LLM.

``preview_quality`` is fully read-only; rows are persisted only by ``build_quality(apply=True)`` and only into
the five V111 quality tables (via the repository). Determinism makes re-evaluation idempotent; a changed target
(new ``target_digest``) yields a new ``quality_run_id`` that supersedes the prior run of the same target +
policy lineage.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from hb_assistant.store.assistant_review_tables import EFFECTIVE_STATE_VALUES, REVIEW_STATE_VALUES

from . import quality_models as M

_VALID_REVIEW_STATES = frozenset(REVIEW_STATE_VALUES)
_VALID_EFFECTIVE_STATES = frozenset(EFFECTIVE_STATE_VALUES)
_HEX = set("0123456789abcdef")

# Language that must never appear in a bounded advisory artifact (staged candidate, feedback note, draft body).
_EXECUTION_TERMS = (
    "send email", "send an email", "schedule meeting", "create task", "create a task", "dispatch",
    "execute the", "run the job", "kick off", "remind me to", "book a", "reply to", "auto-send",
)
_FINALITY_TERMS = (
    "final answer", "authoritative answer", "operator approved", "operator-approved", "confirmed truth",
    "guaranteed correct", "definitive answer",
)

# Expected fixed policy per target kind (for the policy_mismatch check). Only kinds with a known pinned policy.
_EXPECTED_POLICY = {
    "action_stage": {"action_policy": "no_execution", "execution_policy": "staged_only"},
    "action_stage_item": {"execution_status": "not_executed", "external_system": "none"},
    "feedback": {"action_policy": "no_execution", "execution_policy": "feedback_only",
                 "review_policy": "advisory_review_loop"},
}

_SUPPORT_SECTION_TYPES = frozenset({
    "direct_answer", "trusted_context", "candidate_context", "source_summary", "implementation_note",
})


@dataclass
class QualityProviders:
    action_stage_repo: Any = None
    feedback_repo: Any = None
    draft_repo: Any = None
    packet_repo: Any = None
    review_repo: Any = None
    source_repo: Any = None
    router: Any = None


def _valid_review_state(v: Any) -> str | None:
    s = str(v) if v else ""
    return s if s in _VALID_REVIEW_STATES else None


def _valid_effective_state(v: Any) -> str | None:
    s = str(v) if v else ""
    return s if s in _VALID_EFFECTIVE_STATES else None


def _text_risks(text: str | None) -> list[str]:
    """Return the risk finding_types implied by advisory text (execution/finality language)."""
    out: list[str] = []
    if not text:
        return out
    low = f" {str(text).lower()} "
    if any(t in low for t in _EXECUTION_TERMS):
        out.append("execution_language_risk")
    if any(t in low for t in _FINALITY_TERMS):
        out.append("finality_language_risk")
    return out


def _source_ref_finding(source_id: Any, source_repo: Any,
                        conn: sqlite3.Connection | None) -> str | None:
    """None if valid/unknown-shape/no-repo; else ``missing_source_ref`` / ``stale_source_ref``."""
    sid = str(source_id or "")
    if len(sid) != 32 or any(ch not in _HEX for ch in sid) or source_repo is None:
        return None
    detail = source_repo.get_source_detail(sid, conn=conn)
    if detail is None:
        return "missing_source_ref"
    if detail.get("deleted"):
        return "stale_source_ref"
    return None


def _policy_mismatch(record: dict[str, Any], expected: dict[str, str]) -> list[str]:
    return ["policy_mismatch"] if any(record.get(k) != v for k, v in expected.items()) else []


def _f(finding_type: str, *, severity: str, detail: str, target_kind: str, target_id: str | None = None,
       advice: str | None = None, anchors: dict[str, Any] | None = None,
       review_state: str | None = None, effective_state: str | None = None) -> M.QualityFinding:
    return M.QualityFinding(finding_type=finding_type, severity=severity, target_kind=target_kind,
                            target_id=target_id, detail=detail, advice=advice, anchors=anchors or {},
                            review_state=_valid_review_state(review_state),
                            effective_state=_valid_effective_state(effective_state))


# --- per-target-kind evaluators (each returns (findings, target, signals)) ----------------------------
def _eval_action_stage(p: QualityProviders, stage_id: str,
                       conn: sqlite3.Connection | None) -> tuple[list[M.QualityFinding], M.QualityTarget,
                                                                 list[str]]:
    findings: list[M.QualityFinding] = []
    tk = "action_stage"
    if p.action_stage_repo is None:
        return ([_f("unknown_target", severity="warn", detail="action_stage_repo_unavailable",
                    target_kind=tk, target_id=stage_id)],
                M.QualityTarget(target_kind=tk, target_id=stage_id), [stage_id])
    stage = p.action_stage_repo.get_stage(stage_id, conn=conn)
    if stage is None:
        return ([_f("unknown_target", severity="warn", detail=f"action_stage_not_found:{stage_id}",
                    target_kind=tk, target_id=stage_id)],
                M.QualityTarget(target_kind=tk, target_id=stage_id), [stage_id])
    items = p.action_stage_repo.list_items(stage_id, conn=conn)
    citations = p.action_stage_repo.list_citations(stage_id, conn=conn)
    cited_items = {c.get("stage_item_id") for c in citations}
    item_ids = {it.get("stage_item_id") for it in items}
    findings += [_f(t, severity="risk", detail=f"stage_policy:{t}", target_kind=tk, target_id=stage_id,
                    advice="Review the stage policy before use.")
                 for t in _policy_mismatch(stage, _EXPECTED_POLICY["action_stage"])]
    seen: set[str] = set()
    for it in items:
        iid = it.get("stage_item_id")
        anchors = {"stage_id": stage_id, "stage_item_id": iid}
        # execution/finality language
        for t in _text_risks(f"{it.get('title') or ''} {it.get('detail') or ''}"):
            findings.append(_f(t, severity="risk", detail=f"item {iid}: advisory text reads like {t}",
                               target_kind="action_stage_item", target_id=iid, anchors=anchors,
                               advice="Confirm this stays an advisory candidate, not an executed action."))
        # missing citation: a grounded candidate (has anchors/target) with no backing citation
        has_prov = bool(it.get("target_id")) or any(it.get(a) for a in
            ("open_loop_id", "decision_id", "preference_id", "review_item_id", "claim_id", "source_id"))
        if has_prov and iid not in cited_items:
            findings.append(_f("missing_citation", severity="warn",
                               detail=f"item {iid} has provenance but no backing citation",
                               target_kind="action_stage_item", target_id=iid, anchors=anchors,
                               advice="Add a source-backing citation before relying on this candidate.",
                               review_state=it.get("review_state"), effective_state=it.get("effective_state")))
        # source-ref validity
        sr = _source_ref_finding(it.get("source_id"), p.source_repo, conn)
        if sr:
            findings.append(_f(sr, severity="warn", detail=f"item {iid}: {sr}",
                               target_kind="action_stage_item", target_id=iid, anchors=anchors))
        # duplicate candidate
        sig = f"{it.get('action_kind')}|{it.get('target_kind')}|{it.get('target_id')}"
        if sig in seen:
            findings.append(_f("duplicate_stage_candidate", severity="info",
                               detail=f"item {iid} duplicates {sig}", target_kind="action_stage_item",
                               target_id=iid, anchors=anchors))
        seen.add(sig)
    # orphan citations
    for c in citations:
        if c.get("stage_item_id") not in item_ids:
            findings.append(_f("orphan_stage_citation", severity="warn",
                               detail=f"citation {c.get('stage_citation_id')} references missing item",
                               target_kind="action_stage", target_id=stage_id,
                               anchors={"stage_id": stage_id, "citation_id": c.get("stage_citation_id")}))
    signals = [stage_id, str(stage.get("status")), str(stage.get("input_digest")),
               str(stage.get("output_digest")), str(len(items)), str(len(citations))]
    target = M.QualityTarget(target_kind=tk, target_id=stage_id, target_label=stage.get("title"),
                             anchors={"stage_id": stage_id, "workflow_id": stage.get("workflow_id")})
    return findings, target, signals


def _eval_feedback(p: QualityProviders, feedback_id: str,
                   conn: sqlite3.Connection | None) -> tuple[list[M.QualityFinding], M.QualityTarget,
                                                             list[str]]:
    findings: list[M.QualityFinding] = []
    tk = "feedback"
    if p.feedback_repo is None:
        return ([_f("unknown_target", severity="warn", detail="feedback_repo_unavailable", target_kind=tk,
                    target_id=feedback_id)], M.QualityTarget(target_kind=tk, target_id=feedback_id),
                [feedback_id])
    rec = p.feedback_repo.get_feedback(feedback_id, conn=conn)
    if rec is None:
        return ([_f("unknown_target", severity="warn", detail=f"feedback_not_found:{feedback_id}",
                    target_kind=tk, target_id=feedback_id)],
                M.QualityTarget(target_kind=tk, target_id=feedback_id), [feedback_id])
    targets = p.feedback_repo.list_targets(feedback_id, conn=conn)
    recs = p.feedback_repo.list_recommendations(feedback_id, conn=conn)
    anchors = {"feedback_id": feedback_id}
    findings += [_f(t, severity="risk", detail=f"feedback_policy:{t}", target_kind=tk,
                    target_id=feedback_id, anchors=anchors)
                 for t in _policy_mismatch(rec, _EXPECTED_POLICY["feedback"])]
    for t in _text_risks(rec.get("note")):
        findings.append(_f(t, severity="warn", detail=f"feedback note reads like {t}", target_kind=tk,
                           target_id=feedback_id, anchors=anchors))
    # source-related feedback missing a source ref among its targets
    if rec.get("feedback_type") in ("wrong_source", "missing_source") and not any(
            tt.get("source_ref") or tt.get("source_id") or tt.get("rel_path") for tt in targets):
        findings.append(_f("missing_source_ref", severity="warn",
                           detail="source-related feedback has no source-anchored target", target_kind=tk,
                           target_id=feedback_id, anchors=anchors))
    # recommendation with no target → orphan
    for r in recs:
        if not r.get("target_id"):
            findings.append(_f("orphan_feedback_target", severity="info",
                               detail=f"recommendation {r.get('recommendation_id')} has no target",
                               target_kind="feedback_recommendation", target_id=r.get("recommendation_id"),
                               anchors={"feedback_id": feedback_id,
                                        "recommendation_id": r.get("recommendation_id")}))
    # source-ref validity across targets
    for tt in targets:
        sr = _source_ref_finding(tt.get("source_id"), p.source_repo, conn)
        if sr:
            findings.append(_f(sr, severity="warn", detail=f"feedback target: {sr}", target_kind=tk,
                               target_id=feedback_id, anchors=anchors))
    signals = [feedback_id, str(rec.get("status")), str(rec.get("input_digest")),
               str(rec.get("output_digest")), str(len(targets)), str(len(recs))]
    target = M.QualityTarget(target_kind=tk, target_id=feedback_id, anchors=anchors,
                             review_state=None, effective_state=None)
    return findings, target, signals


def _eval_answer_draft(p: QualityProviders, draft_id: str,
                       conn: sqlite3.Connection | None) -> tuple[list[M.QualityFinding], M.QualityTarget,
                                                                 list[str]]:
    findings: list[M.QualityFinding] = []
    tk = "answer_draft"
    if p.draft_repo is None:
        return ([_f("unknown_target", severity="warn", detail="draft_repo_unavailable", target_kind=tk,
                    target_id=draft_id)], M.QualityTarget(target_kind=tk, target_id=draft_id), [draft_id])
    draft = p.draft_repo.get_answer_draft(draft_id, conn=conn)
    if draft is None:
        return ([_f("unknown_target", severity="warn", detail=f"draft_not_found:{draft_id}", target_kind=tk,
                    target_id=draft_id)], M.QualityTarget(target_kind=tk, target_id=draft_id), [draft_id])
    sections = p.draft_repo.list_answer_draft_sections(draft_id, conn=conn)
    citations = p.draft_repo.list_answer_draft_citations(draft_id, conn=conn)
    cited_sections = {c.get("draft_section_id") for c in citations}
    for s in sections:
        sid = s.get("draft_section_id")
        anchors = {"draft_id": draft_id, "draft_section_id": sid}
        stype = s.get("section_type")
        if stype in _SUPPORT_SECTION_TYPES and sid not in cited_sections:
            findings.append(_f("missing_citation", severity="warn",
                               detail=f"support section {sid} ({stype}) has no citation", target_kind=tk,
                               target_id=draft_id, anchors=anchors,
                               review_state=s.get("review_state"), effective_state=s.get("effective_state")))
        if int(s.get("candidate") or 0) == 1 and not s.get("review_label"):
            findings.append(_f("candidate_without_label", severity="warn",
                               detail=f"candidate section {sid} lacks a review label", target_kind=tk,
                               target_id=draft_id, anchors=anchors))
        if int(s.get("excluded") or 0) == 1 and stype in _SUPPORT_SECTION_TYPES:
            findings.append(_f("excluded_used_as_support", severity="risk",
                               detail=f"excluded section {sid} used as support ({stype})", target_kind=tk,
                               target_id=draft_id, anchors=anchors))
        if int(s.get("trusted") or 0) == 1 and _valid_effective_state(s.get("effective_state")) not in (
                "accepted", None):
            findings.append(_f("trusted_without_accepted_review", severity="warn",
                               detail=f"trusted section {sid} effective_state={s.get('effective_state')}",
                               target_kind=tk, target_id=draft_id, anchors=anchors,
                               effective_state=s.get("effective_state")))
    signals = [draft_id, str(draft.get("status")), str(draft.get("input_digest")),
               str(draft.get("output_digest")), str(len(sections)), str(len(citations))]
    target = M.QualityTarget(target_kind=tk, target_id=draft_id, target_label=draft.get("title"),
                             anchors={"draft_id": draft_id, "packet_id": draft.get("packet_id")})
    return findings, target, signals


def _eval_workflow(p: QualityProviders, workflow_type: str,
                   conn: sqlite3.Connection | None) -> tuple[list[M.QualityFinding], M.QualityTarget,
                                                             list[str]]:
    findings: list[M.QualityFinding] = []
    tk = "workflow"
    if p.router is None:
        return ([_f("unknown_target", severity="warn", detail="router_unavailable", target_kind=tk,
                    target_id=workflow_type)], M.QualityTarget(target_kind=tk, target_id=workflow_type),
                [workflow_type])
    from .workflow_models import WorkflowRequest

    env = p.router.route(WorkflowRequest.from_inputs(workflow_type=workflow_type), conn=conn)
    sections = env.get("workflow_sections") or {}
    status = env.get("status")
    wf_id = env.get("workflow_id")
    anchors = {"workflow_id": wf_id}
    non_empty = sum(1 for v in sections.values() if isinstance(v, list) and v)
    if non_empty == 0:
        findings.append(_f("workflow_section_empty", severity="info",
                           detail=f"workflow {workflow_type} produced no populated sections", target_kind=tk,
                           target_id=workflow_type, anchors=anchors))
    if status in ("insufficient_context", "needs_clarification"):
        findings.append(_f("insufficient_context", severity="info",
                           detail=f"workflow {workflow_type} status={status}", target_kind=tk,
                           target_id=workflow_type, anchors=anchors))
    signals = [workflow_type, str(status), str(wf_id), str(non_empty)]
    target = M.QualityTarget(target_kind=tk, target_id=workflow_type, anchors=anchors)
    return findings, target, signals


_EVALUATORS = {
    "action_stage": _eval_action_stage,
    "feedback": _eval_feedback,
    "answer_draft": _eval_answer_draft,
    "workflow": _eval_workflow,
}


def preview_quality(providers: QualityProviders, *, target_kind: str, target_id: str,
                    created_by: str = "service",
                    conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Evaluate one target and assemble a full quality plan WITHOUT persisting. Read-only."""
    if target_kind not in M.QUALITY_TARGET_KINDS:
        raise M.QualityValidationError(f"unknown_target_kind:{target_kind}")
    tid = (target_id or "").strip()
    if not tid:
        raise M.QualityValidationError("target_id_required")

    evaluator = _EVALUATORS.get(target_kind)
    if evaluator is None:
        findings = [_f("unknown_target", severity="info",
                       detail=f"no evaluator for target_kind={target_kind}", target_kind=target_kind,
                       target_id=tid)]
        target = M.QualityTarget(target_kind=target_kind, target_id=tid)
        signals = [tid]
    else:
        findings, target, signals = evaluator(providers, tid, conn)

    policy_json = M.canonical_json({"target_kind": target_kind, **M.QUALITY_POLICY_BLOCK})
    target_digest = M.compute_target_digest(target_kind, tid, signals)
    target.target_digest = target_digest
    request_digest = M.compute_request_digest(target_kind, tid, policy_json)
    input_digest = M.compute_input_digest(request_digest, target_digest)
    quality_run_id = M.compute_quality_run_id(target_kind, tid, request_digest, input_digest)

    finding_rows = [f.to_row(quality_run_id, i) for i, f in enumerate(findings[:M.MAX_FINDINGS])]
    truncated = len(findings) > M.MAX_FINDINGS
    target_rows = [target.to_row(quality_run_id, 0)]
    counts = M.severity_counts(finding_rows)
    output_digest = M.compute_output_digest([r["finding_id"] for r in finding_rows])

    run = {
        "quality_run_id": quality_run_id, "target_kind": target_kind, "target_id": tid,
        "target_digest": target_digest, "title": f"quality {target_kind} {tid}"[:M.LABEL_HARD_CAP],
        "status": "evaluated", **M.QUALITY_POLICY_BLOCK, "evaluator_version": M.QUALITY_EVALUATOR_VERSION,
        "created_by": created_by, "request_digest": request_digest, "input_digest": input_digest,
        "output_digest": output_digest, "policy_json": policy_json, "finding_count": len(finding_rows),
        "risk_count": counts["risk"], "warn_count": counts["warn"], "info_count": counts["info"],
        "truncated": 1 if truncated else 0,
    }
    receipt = {
        "quality_receipt_id": M.compute_quality_receipt_id(quality_run_id, input_digest, output_digest),
        "quality_run_id": quality_run_id, "evaluator_version": M.QUALITY_EVALUATOR_VERSION,
        "request_digest": request_digest, "input_digest": input_digest, "output_digest": output_digest,
        "finding_count": len(finding_rows), "risk_count": counts["risk"], "warn_count": counts["warn"],
        "info_count": counts["info"], "dropped_count": len(findings) - len(finding_rows),
        "truncated": 1 if truncated else 0,
    }
    return {"applied": False, "quality_run_id": quality_run_id, "run": run, "findings": finding_rows,
            "targets": target_rows, "receipt": receipt, "counts": counts, "truncated": truncated,
            "input_digest": input_digest, "output_digest": output_digest}


def build_quality(providers: QualityProviders, repo: Any, *, target_kind: str, target_id: str,
                  apply: bool = False, created_by: str = "service",
                  conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Preview, and — only when ``apply`` — persist into the five quality tables (nothing else). Idempotent:
    unchanged target creates no duplicate; a changed target changes ``input_digest`` → a new run that
    supersedes the prior one of the same target + policy lineage."""
    preview = preview_quality(providers, target_kind=target_kind, target_id=target_id,
                              created_by=created_by, conn=conn)
    if not apply:
        return preview
    res = repo.upsert_quality_run(preview["run"], preview["findings"], preview["targets"],
                                  preview["receipt"], conn=conn)
    return {"applied": True, "quality_run_id": preview["quality_run_id"], "created": res["created"],
            "reused": res.get("reused", False), "superseded": res.get("superseded", []),
            "counts": preview["counts"], "truncated": preview["truncated"]}


def export_quality(repo: Any, *, quality_run_id: str, limit: int = 200,
                   conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Bounded JSON export of a persisted quality run: header + bounded findings + bounded targets. NO raw
    bodies, no full payloads, no repair/execution fields."""
    header = repo.get_quality_run(quality_run_id, conn=conn)
    if header is None:
        raise M.QualityValidationError(f"quality_run_not_found:{quality_run_id}")
    findings = repo.list_findings(quality_run_id, limit=limit, conn=conn)
    targets = repo.list_targets(quality_run_id, limit=limit, conn=conn)
    return {"format": "quality_export_v1", "run": header, "findings": findings, "targets": targets,
            "finding_count": len(findings), "target_count": len(targets)}
