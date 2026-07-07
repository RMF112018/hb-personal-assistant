"""N8C-18 feedback capture + review-loop derivation service.

Deterministic and bounded. ``preview_feedback`` assembles a complete feedback plan WITHOUT writing anything;
``capture_feedback(..., apply=True)`` hands that plan to ``FeedbackRepository.upsert_feedback`` (the single
sanctioned local write, into feedback-owned tables only). Recommendations are derived deterministically and
are ALWAYS advisory + operator-review-required.

No LLM, no network, no source_file_read, no scan/reindex, no source-card generation, no review-disposition
write, no mutation of any upstream record. Feedback captures what the operator references (bounded ids +
provenance the caller supplies from the workflow context they are giving feedback on) — it does not re-fetch
or mutate source truth.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from . import feedback_models as M
from .feedback_repository import FeedbackRepository
from .memory_models import bound_text, sha256_hex


def _target_digest(kind: str, target_id: str, anchors: dict[str, str]) -> str:
    joined = ";".join(f"{k}={v}" for k, v in sorted(anchors.items()))
    return sha256_hex(f"{kind}|{target_id}|{joined}")[:24]


def _coerce_targets(targets: list[dict[str, Any]] | None) -> list[M.FeedbackTarget]:
    if not targets:
        return []
    out: list[M.FeedbackTarget] = []
    for raw in list(targets)[:M.MAX_TARGETS]:
        kind = str(raw.get("target_kind") or "").strip()
        tid = str(raw.get("target_id") or "").strip()
        if not kind or not tid:
            raise M.FeedbackValidationError("target_requires_kind_and_id")
        anchors = {k: raw.get(k) for k in M.TARGET_ANCHOR_FIELDS if raw.get(k)}
        out.append(M.FeedbackTarget(
            target_kind=kind, target_id=tid, target_label=raw.get("target_label"),
            anchors=anchors, review_state=raw.get("review_state") or None,
            effective_state=raw.get("effective_state") or None,
            metadata=raw.get("metadata") or {}))
    return out


def _source_related(feedback_type: str) -> bool:
    return feedback_type in ("wrong_source", "missing_source")


def preview_feedback(*, feedback_type: str, targets: list[dict[str, Any]] | None,
                     note: str | None = None, workflow_type: str | None = None,
                     workflow_id: str | None = None, created_by: str = "service") -> dict[str, Any]:
    """Read-only: assemble the full feedback plan (record + targets + advisory recommendations + receipt)."""
    if feedback_type not in M.FEEDBACK_TYPES:
        raise M.FeedbackValidationError(f"unknown_feedback_type:{feedback_type}")
    fb_targets = _coerce_targets(targets)
    if not fb_targets:
        raise M.FeedbackValidationError("feedback_requires_at_least_one_target")

    note_b = bound_text(note, M.NOTE_HARD_CAP) or None
    signatures = [t.signature() for t in fb_targets]
    input_digest = M.compute_feedback_input_digest(feedback_type, signatures, note_b, created_by)
    feedback_id = M.compute_feedback_id(feedback_type, signatures, note_b, created_by)

    # Bounded target rows (each carries a stable target_digest for provenance).
    target_rows: list[dict[str, Any]] = []
    for order, t in enumerate(fb_targets):
        if t.target_digest is None:
            t.target_digest = _target_digest(t.target_kind, t.target_id, t.normalized_anchors())
        target_rows.append(t.to_row(feedback_id, order))

    # Deterministic ADVISORY recommendations.
    recommendations = M.derive_recommendations(feedback_type, fb_targets)
    rec_rows = [r.to_row(feedback_id, order) for order, r in enumerate(recommendations)]

    warnings: list[str] = []
    if _source_related(feedback_type) and not any(
            tr.get("source_ref") or tr.get("source_id") or tr.get("rel_path") for tr in target_rows):
        warnings.append("missing_source_ref")

    output_digest = M.compute_feedback_output_digest(
        [tr["feedback_target_id"] for tr in target_rows],
        [rr["recommendation_id"] for rr in rec_rows])

    record = {
        "feedback_id": feedback_id,
        "feedback_type": feedback_type,
        "note": note_b,
        "workflow_type": bound_text(workflow_type, M.ID_HARD_CAP) or None,
        "workflow_id": bound_text(workflow_id, M.ID_HARD_CAP) or None,
        "status": "open",
        **M.FEEDBACK_POLICY_BLOCK,
        "created_by": bound_text(created_by or "service", M.ID_HARD_CAP) or "service",
        "input_digest": input_digest,
        "output_digest": output_digest,
        "target_count": len(target_rows),
        "recommendation_count": len(rec_rows),
        "truncated": 0,
    }
    receipt = {
        "feedback_receipt_id": M.compute_feedback_receipt_id(feedback_id, input_digest, output_digest),
        "feedback_id": feedback_id,
        "builder_version": M.FEEDBACK_BUILDER_VERSION,
        "input_digest": input_digest,
        "output_digest": output_digest,
        "target_count": len(target_rows),
        "recommendation_count": len(rec_rows),
        "dropped_count": 0,
        "truncated": 0,
    }
    return {
        "applied": False,
        "feedback": record,
        "targets": target_rows,
        "recommendations": rec_rows,
        "receipt": receipt,
        "counts": {"targets": len(target_rows), "recommendations": len(rec_rows)},
        "warnings": warnings,
        "input_digest": input_digest,
        "output_digest": output_digest,
    }


def capture_feedback(repo: FeedbackRepository, *, feedback_type: str,
                     targets: list[dict[str, Any]] | None, note: str | None = None,
                     workflow_type: str | None = None, workflow_id: str | None = None,
                     created_by: str = "service", apply: bool = False,
                     conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Preview, then (only when ``apply``) persist to the feedback-owned tables via the repository."""
    plan = preview_feedback(feedback_type=feedback_type, targets=targets, note=note,
                            workflow_type=workflow_type, workflow_id=workflow_id, created_by=created_by)
    if not apply:
        return plan
    result = repo.upsert_feedback(plan["feedback"], plan["targets"], plan["recommendations"],
                                  plan["receipt"], conn=conn)
    return {**plan, "applied": True, "result": result}


def export_feedback(repo: FeedbackRepository, *, feedback_id: str, limit: int = 200,
                    conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Bounded JSON export of one feedback record + its targets + recommendations. Pure read."""
    record = repo.get_feedback(feedback_id, conn=conn)
    if record is None:
        raise M.FeedbackValidationError(f"feedback_not_found:{feedback_id}")
    targets = repo.list_targets(feedback_id, limit=limit, conn=conn)
    recommendations = repo.list_recommendations(feedback_id, limit=limit, conn=conn)
    return {"format": "feedback_export_v1", "feedback": record, "targets": targets,
            "recommendations": recommendations, "target_count": len(targets),
            "recommendation_count": len(recommendations)}
