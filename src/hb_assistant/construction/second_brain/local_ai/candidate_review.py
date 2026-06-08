"""Phase 10A — candidate review service layer.

Pure functions that hold the business logic for operator review of local-model
action candidates (``task_candidates`` / ``commitment_candidates``). The later
Typer verbs are thin wrappers over these; nothing here imports Typer, touches the
network, or reads raw content.

Contract:
- ``review_status`` is validated against the canonical ``ReviewStatus`` enum. The
  operator-facing ``ignore`` verb normalizes to the stored value ``suppressed``.
- Review actions are local DB updates only (status transition + optional V43
  lifecycle columns + a ``candidate_review_events`` audit row). Source refs are
  read-only and never mutated.
- Outputs are safe dicts: candidate rows already carry only redacted fields
  (``title_redacted`` / ``reason_redacted`` / ``evidence_redacted``); free-text
  operator notes and edit diffs are bounded via ``_truncate``. No raw email body,
  document text, calendar/Procore payload, prompt, response, URL, or token is ever
  read or emitted.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional, get_args

from hb_assistant.construction.store import ConstructionStore

from .models import Assignee, ReviewStatus, WaitingState
from .raw_action_intelligence import _truncate

_REVIEW_STATUSES: frozenset[str] = frozenset(get_args(ReviewStatus))
_ASSIGNEES: frozenset[str] = frozenset(get_args(Assignee))
_WAITING_STATES: frozenset[str] = frozenset(get_args(WaitingState))
_CANDIDATE_TYPES: tuple[str, ...] = ("task", "commitment")

_NOTE_MAX = 400
_TITLE_MAX = 240
_CHANGES_MAX = 400

# Large fetch bound used to locate a single candidate by id via the list helpers
# (the store has no by-id getter; this mirrors the existing phase-10 review path).
_FIND_LIMIT = 100_000


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _list_for_type(
    store: ConstructionStore,
    candidate_type: str,
    *,
    project_key: Optional[str] = None,
    review_status: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if candidate_type == "task":
        rows = store.list_task_candidates(
            project_key=project_key, review_status=review_status, limit=limit
        )
    else:
        rows = store.list_commitment_candidates(
            project_key=project_key, review_status=review_status, limit=limit
        )
    for r in rows:
        r["candidate_type"] = candidate_type
    return rows


def _find_candidate(
    store: ConstructionStore,
    candidate_id: str,
    candidate_type: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Locate a candidate by id, returning (row, resolved_type) or (None, None)."""
    types = (candidate_type,) if candidate_type in _CANDIDATE_TYPES else _CANDIDATE_TYPES
    for ctype in types:
        for row in _list_for_type(store, ctype, limit=_FIND_LIMIT):
            if row.get("candidate_id") == candidate_id:
                return row, ctype
    return None, None


def _require_type(candidate_type: str) -> None:
    if candidate_type not in _CANDIDATE_TYPES:
        raise ValueError(f"invalid candidate_type: {candidate_type!r} (expected task|commitment)")


# ---------------------------------------------------------------------------
# Read-only surfaces
# ---------------------------------------------------------------------------
def review_summary(
    store: ConstructionStore, *, project_key: Optional[str] = None
) -> dict[str, Any]:
    """Counts by review_status for task + commitment candidates (read-only)."""
    out: dict[str, Any] = {"ok": True, "project_key": project_key}
    combined: dict[str, int] = {}
    for ctype in _CANDIDATE_TYPES:
        buckets: dict[str, int] = {}
        rows = _list_for_type(store, ctype, project_key=project_key, limit=_FIND_LIMIT)
        for r in rows:
            status = str(r.get("review_status") or "pending")
            buckets[status] = buckets.get(status, 0) + 1
            combined[status] = combined.get(status, 0) + 1
        buckets["total"] = len(rows)
        out[ctype] = buckets
    combined["total"] = out["task"]["total"] + out["commitment"]["total"]
    out["combined"] = combined
    return out


def list_review_candidates(
    store: ConstructionStore,
    *,
    status: Optional[str] = None,
    project_key: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    """List task + commitment candidates (safe fields), optionally filtered by status."""
    if status is not None and status not in _REVIEW_STATUSES:
        raise ValueError(f"invalid review_status: {status!r} (expected {sorted(_REVIEW_STATUSES)})")
    candidates: list[dict[str, Any]] = []
    for ctype in _CANDIDATE_TYPES:
        candidates.extend(
            _list_for_type(
                store, ctype, project_key=project_key, review_status=status, limit=limit
            )
        )
    candidates = candidates[:limit]
    return {
        "ok": True,
        "status": status,
        "project_key": project_key,
        "count": len(candidates),
        "candidates": candidates,
    }


def show_review_candidate(
    store: ConstructionStore,
    *,
    candidate_id: str,
    candidate_type: Optional[str] = None,
) -> dict[str, Any]:
    """Return a single candidate + its (read-only, preserved) source refs."""
    cand, ctype = _find_candidate(store, candidate_id, candidate_type)
    if not cand or ctype is None:
        return {"ok": False, "error": "candidate_not_found", "candidate_id": candidate_id}
    refs = store.list_candidate_source_refs(candidate_id=candidate_id, limit=200)
    return {
        "ok": True,
        "candidate_type": ctype,
        "candidate": cand,
        "source_refs": refs,
    }


# ---------------------------------------------------------------------------
# Review decisions (local DB updates only)
# ---------------------------------------------------------------------------
def _apply_decision(
    store: ConstructionStore,
    *,
    candidate_id: str,
    candidate_type: str,
    action: str,
    new_status: str,
    reviewer: str,
    note: Optional[str],
    snoozed_until_utc: Optional[str] = None,
) -> dict[str, Any]:
    _require_type(candidate_type)
    cand, ctype = _find_candidate(store, candidate_id, candidate_type)
    if not cand or ctype is None:
        return {"ok": False, "error": "candidate_not_found", "candidate_id": candidate_id}
    prior_status = str(cand.get("review_status") or "pending")
    note_red = _truncate(note, _NOTE_MAX) if note else None
    now = _utc_now()
    store.set_candidate_review_status(
        candidate_type=ctype,
        candidate_id=candidate_id,
        review_status=new_status,
        reviewed_utc=now,
        reviewed_by=reviewer,
        review_note_redacted=note_red,
        snoozed_until_utc=snoozed_until_utc,
    )
    review_event_id = store.insert_candidate_review_event(
        candidate_type=ctype,
        candidate_id=candidate_id,
        decision=action,
        reason_redacted=note_red,
        reviewer_ref=reviewer,
        prior_status=prior_status,
        new_status=new_status,
        snoozed_until_utc=snoozed_until_utc,
    )
    return {
        "ok": True,
        "candidate_id": candidate_id,
        "candidate_type": ctype,
        "action": action,
        "prior_review_status": prior_status,
        "new_review_status": new_status,
        "reviewed_by": reviewer,
        "reviewed_utc": now,
        "review_note_redacted": note_red,
        "snoozed_until_utc": snoozed_until_utc,
        "review_event_id": review_event_id,
    }


def accept_candidate(
    store: ConstructionStore,
    *,
    candidate_id: str,
    candidate_type: str,
    reviewer: str = "operator",
    note: Optional[str] = None,
) -> dict[str, Any]:
    return _apply_decision(
        store,
        candidate_id=candidate_id,
        candidate_type=candidate_type,
        action="accept",
        new_status="accepted",
        reviewer=reviewer,
        note=note,
    )


def reject_candidate(
    store: ConstructionStore,
    *,
    candidate_id: str,
    candidate_type: str,
    reviewer: str = "operator",
    note: Optional[str] = None,
) -> dict[str, Any]:
    return _apply_decision(
        store,
        candidate_id=candidate_id,
        candidate_type=candidate_type,
        action="reject",
        new_status="rejected",
        reviewer=reviewer,
        note=note,
    )


def ignore_candidate(
    store: ConstructionStore,
    *,
    candidate_id: str,
    candidate_type: str,
    reviewer: str = "operator",
    note: Optional[str] = None,
) -> dict[str, Any]:
    """Operator 'ignore' — normalized to the stored review_status 'suppressed'."""
    return _apply_decision(
        store,
        candidate_id=candidate_id,
        candidate_type=candidate_type,
        action="ignore",
        new_status="suppressed",
        reviewer=reviewer,
        note=note,
    )


def snooze_candidate(
    store: ConstructionStore,
    *,
    candidate_id: str,
    candidate_type: str,
    until: str,
    reviewer: str = "operator",
    note: Optional[str] = None,
) -> dict[str, Any]:
    """Snooze a candidate until an ISO-8601 timestamp (review_status -> 'snoozed')."""
    try:
        datetime.fromisoformat(until)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid until (expected ISO-8601): {until!r}") from exc
    return _apply_decision(
        store,
        candidate_id=candidate_id,
        candidate_type=candidate_type,
        action="snooze",
        new_status="snoozed",
        reviewer=reviewer,
        note=note,
        snoozed_until_utc=until,
    )


def edit_candidate(
    store: ConstructionStore,
    *,
    candidate_id: str,
    candidate_type: str,
    title: Optional[str] = None,
    assignee: Optional[str] = None,
    waiting_state: Optional[str] = None,
    reviewer: str = "operator",
    note: Optional[str] = None,
) -> dict[str, Any]:
    """Edit editable candidate fields (title/assignee/waiting_state). review_status untouched.

    Records a before/after diff in the audit trail (changes_json_redacted). Does not
    touch source refs, stable_key, or guard columns.
    """
    _require_type(candidate_type)
    if assignee is not None and assignee not in _ASSIGNEES:
        raise ValueError(f"invalid assignee: {assignee!r} (expected {sorted(_ASSIGNEES)})")
    if waiting_state is not None and waiting_state not in _WAITING_STATES:
        raise ValueError(
            f"invalid waiting_state: {waiting_state!r} (expected {sorted(_WAITING_STATES)})"
        )
    if title is None and assignee is None and waiting_state is None:
        return {"ok": False, "error": "no_edits", "candidate_id": candidate_id}

    cand, ctype = _find_candidate(store, candidate_id, candidate_type)
    if not cand or ctype is None:
        return {"ok": False, "error": "candidate_not_found", "candidate_id": candidate_id}

    assignee_col = "assignee_class" if ctype == "task" else "commitment_actor_class"
    fields: dict[str, str] = {}
    changes: dict[str, dict[str, Any]] = {}
    if title is not None:
        new_title = _truncate(title, _TITLE_MAX) or ""
        fields["title_redacted"] = new_title
        changes["title_redacted"] = {"from": cand.get("title_redacted"), "to": new_title}
    if assignee is not None:
        fields[assignee_col] = assignee
        changes[assignee_col] = {"from": cand.get(assignee_col), "to": assignee}
    if waiting_state is not None:
        fields["waiting_state"] = waiting_state
        changes["waiting_state"] = {"from": cand.get("waiting_state"), "to": waiting_state}

    updated = store.update_candidate_fields(
        candidate_type=ctype, candidate_id=candidate_id, fields=fields
    )
    review_status = str(cand.get("review_status") or "pending")
    changes_red = _truncate(json.dumps(changes, sort_keys=True, default=str), _CHANGES_MAX)
    review_event_id = store.insert_candidate_review_event(
        candidate_type=ctype,
        candidate_id=candidate_id,
        decision="edit",
        reason_redacted=_truncate(note, _NOTE_MAX) if note else None,
        reviewer_ref=reviewer,
        prior_status=review_status,
        new_status=review_status,
        changes_json_redacted=changes_red,
    )
    return {
        "ok": bool(updated),
        "candidate_id": candidate_id,
        "candidate_type": ctype,
        "action": "edit",
        "review_status": review_status,
        "changes": changes,
        "reviewed_by": reviewer,
        "review_event_id": review_event_id,
    }


def export_review_queue(
    store: ConstructionStore,
    *,
    status: Optional[str] = None,
    project_key: Optional[str] = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Build a safe review-queue payload (candidates + their source refs).

    The caller (CLI layer) is responsible for writing the file; this returns the
    structured, redacted payload only.
    """
    if status is not None and status not in _REVIEW_STATUSES:
        raise ValueError(f"invalid review_status: {status!r} (expected {sorted(_REVIEW_STATUSES)})")
    items: list[dict[str, Any]] = []
    for ctype in _CANDIDATE_TYPES:
        for cand in _list_for_type(
            store, ctype, project_key=project_key, review_status=status, limit=limit
        ):
            refs = store.list_candidate_source_refs(
                candidate_id=cand["candidate_id"], limit=200
            )
            items.append({**cand, "source_refs": refs})
    items = items[:limit]
    return {
        "ok": True,
        "status": status,
        "project_key": project_key,
        "count": len(items),
        "items": items,
    }
