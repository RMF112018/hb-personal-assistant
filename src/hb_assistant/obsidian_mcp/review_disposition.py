"""N8C-9 local/operator disposition service (append-only, overlay-only).

A disposition records an explicit operator decision (accept / reject / defer / mark_not_required /
mark_stale / mark_superseded / request_more_context) about a review item. It writes ONLY the N8C-9 review
tables (via ``ReviewRepository.record_disposition``) — it NEVER mutates a source advisory table, executes
any action, sends any email/notification, creates any task/reminder, or calls N8D. Accept/reject/defer/…
change only the review-overlay effective state.

``preview_disposition`` is fully read-only: it resolves the current effective state and the state the
disposition WOULD move it to, without writing. ``apply_disposition(..., apply=True)`` appends one
disposition + one lifecycle event. The ledger is append-only — the same decision recorded twice yields two
distinct rows (each with an event-unique id), so a prior decision is never silently overwritten.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from .review_models import ReviewValidationError, disposition_states


def preview_disposition(repo: Any, *, review_item_id: str, disposition_type: str,
                        operator_id: str | None = None, reason: str | None = None,
                        conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Read-only: what the disposition would do. Raises on unknown disposition_type / missing item."""
    to_review_state, to_effective_state = disposition_states(disposition_type)
    current = repo.get_effective_state(review_item_id, conn=conn)
    if current is None:
        raise ReviewValidationError(f"review_item_not_found:{review_item_id}")
    return {
        "applied": False, "review_item_id": review_item_id, "disposition_type": disposition_type,
        "from_review_state": current["effective_review_state"],
        "from_effective_state": current["effective_state"],
        "to_review_state": to_review_state, "to_effective_state": to_effective_state,
        "operator_id": operator_id, "would_record": True,
    }


def apply_disposition(repo: Any, *, review_item_id: str, disposition_type: str,
                      operator_id: str | None = None, reason: str | None = None,
                      evidence_note: str | None = None, apply: bool = False, created_by: str = "cli",
                      conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Preview unless ``apply``; when ``apply`` append one disposition + one event (overlay tables only)."""
    preview = preview_disposition(repo, review_item_id=review_item_id,
                                  disposition_type=disposition_type, operator_id=operator_id,
                                  reason=reason, conn=conn)
    if not apply:
        return preview
    result = repo.record_disposition(
        review_item_id=review_item_id, disposition_type=disposition_type, operator_id=operator_id,
        reason=reason, evidence_note=evidence_note, created_by=created_by, conn=conn)
    return {"applied": True, **result,
            "from_review_state": preview["from_review_state"],
            "from_effective_state": preview["from_effective_state"]}
