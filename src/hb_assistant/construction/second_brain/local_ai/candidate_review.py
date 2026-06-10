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


def _find_candidate(
    store: ConstructionStore,
    candidate_id: str,
    candidate_type: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Locate a candidate by id (primary-key getter), returning (row, resolved_type)."""
    row = store.get_candidate(candidate_id, candidate_type=candidate_type)
    if row is None:
        return None, None
    return row, str(row.get("candidate_type"))


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
    per_type: dict[str, dict[str, int]] = {"task": {"total": 0}, "commitment": {"total": 0}}
    combined: dict[str, int] = {}
    for r in store.list_review_candidates(project_key=project_key, limit=_FIND_LIMIT):
        ctype = str(r.get("candidate_type"))
        status = str(r.get("review_status") or "pending")
        bucket = per_type.setdefault(ctype, {"total": 0})
        bucket[status] = bucket.get(status, 0) + 1
        bucket["total"] += 1
        combined[status] = combined.get(status, 0) + 1
    combined["total"] = per_type["task"]["total"] + per_type["commitment"]["total"]
    return {
        "ok": True,
        "project_key": project_key,
        "task": per_type["task"],
        "commitment": per_type["commitment"],
        "combined": combined,
    }


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
    candidates = store.list_review_candidates(status=status, project_key=project_key, limit=limit)
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
    store.update_candidate_review_state(
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


#: Review-status groups rendered in the consolidated report, in operator-priority order.
_REPORT_GROUPS: tuple[str, ...] = ("pending", "accepted", "rejected", "snoozed", "suppressed")

#: Below this confidence a still-pending candidate is flagged needs-review (advisory only).
_NEEDS_REVIEW_CONFIDENCE = 0.5


def _safe_candidate_view(
    store: ConstructionStore, cand: dict[str, Any], *, include_source_refs: bool
) -> dict[str, Any]:
    """Project a candidate row to review-safe fields only (redacted) + safe source-ref identifiers."""
    ctype = str(cand.get("candidate_type") or "")
    assignee = cand.get("assignee_class") or cand.get("commitment_actor_class")
    view: dict[str, Any] = {
        "candidate_id": cand.get("candidate_id"),
        "candidate_type": ctype,
        "title_redacted": cand.get("title_redacted"),
        "project_key": cand.get("project_key"),
        "assignee_class": assignee,
        "waiting_state": cand.get("waiting_state"),
        "urgency": cand.get("urgency"),
        "due_at_utc": cand.get("due_at_utc"),
        "safety_category": cand.get("safety_category"),
        "confidence": cand.get("confidence"),
        "recommended_next_action": cand.get("recommended_next_action"),
        "review_status": str(cand.get("review_status") or "pending"),
    }
    if include_source_refs:
        refs = store.list_candidate_source_refs(candidate_id=str(cand.get("candidate_id")), limit=50)
        view["source_refs"] = [
            f"{r.get('source_family', '')}:{r.get('source_ref_hash', '')}".strip(":") for r in refs
        ]
        view["source_ref_count"] = len(refs)
    return view


def build_review_report(
    store: ConstructionStore,
    *,
    project_key: Optional[str] = None,
    limit: int = 2000,
    apply_cap: int = 50,
    include_source_refs: bool = True,
) -> dict[str, Any]:
    """Build one consolidated, review-safe operator report across the candidate lifecycle.

    Read-only: groups candidates by ``review_status`` (pending/accepted/rejected/snoozed/suppressed),
    flags still-pending low-confidence/unclear items as ``needs_review`` (advisory), and previews —
    dry-run, bounded by ``apply_cap`` — the accepted candidates an operator apply would persist/act on.
    Every item carries only redacted fields + safe source-ref identifiers + confidence/safety reasons.
    """
    rows = store.list_review_candidates(project_key=project_key, limit=limit)
    groups: dict[str, list[dict[str, Any]]] = {s: [] for s in _REPORT_GROUPS}
    needs_review: list[dict[str, Any]] = []
    for c in rows:
        view = _safe_candidate_view(store, c, include_source_refs=include_source_refs)
        status = view["review_status"]
        groups.setdefault(status, []).append(view)
        conf = float(c.get("confidence") or 0.0)
        if status == "pending" and (
            conf < _NEEDS_REVIEW_CONFIDENCE or str(c.get("waiting_state") or "") == "unclear"
        ):
            needs_review.append(view)

    accepted = groups.get("accepted", [])
    would_persist = accepted[:apply_cap]
    counts = {s: len(v) for s, v in groups.items()}
    counts["total"] = len(rows)
    counts["needs_review"] = len(needs_review)
    return {
        "ok": True,
        "project_key": project_key,
        "generated_utc": _utc_now(),
        "counts": counts,
        "groups": groups,
        "needs_review": needs_review,
        "preview_apply": {
            "dry_run": True,
            "cap": apply_cap,
            "accepted_total": len(accepted),
            "would_persist_count": len(would_persist),
            "would_persist_candidate_ids": [c["candidate_id"] for c in would_persist],
            "note": (
                "Dry-run preview: accepted candidates ready to act on. Apply review decisions in "
                "bounded batches via `second-brain review accept --candidate-id-file <f> --apply "
                "--max-actions <cap>`; this report never persists."
            ),
        },
        "guardrails": {
            "read_only": True,
            "dry_run": True,
            "redacted_fields_only": True,
            "source_linked": True,
            "no_raw_content": True,
        },
    }


def render_review_report_markdown(report: dict[str, Any]) -> str:
    """Render the consolidated review report as legible, review-safe operator markdown."""
    if not report.get("ok"):
        return f"# Candidate Review Report\n\n_Report unavailable: {report.get('error')}_\n"
    counts = report.get("counts", {})
    proj = report.get("project_key") or "(all projects)"
    lines = [
        "# Candidate Review Report",
        "",
        f"_Project: {proj} · generated {report.get('generated_utc')} · read-only / dry-run._",
        "",
        "## Summary",
        f"- total: {counts.get('total', 0)} · pending: {counts.get('pending', 0)} · "
        f"accepted: {counts.get('accepted', 0)} · rejected: {counts.get('rejected', 0)} · "
        f"snoozed: {counts.get('snoozed', 0)} · suppressed: {counts.get('suppressed', 0)}",
        f"- needs review (advisory): {counts.get('needs_review', 0)}",
    ]

    pa = report.get("preview_apply", {})
    lines += [
        "",
        "## Preview apply (dry-run)",
        f"- accepted ready to act on: {pa.get('accepted_total', 0)}; "
        f"would persist (cap {pa.get('cap', 0)}): {pa.get('would_persist_count', 0)}",
        f"- {pa.get('note', '')}",
    ]

    def _item(it: dict[str, Any]) -> str:
        conf = it.get("confidence")
        conf_s = f"{float(conf):.2f}" if isinstance(conf, (int, float)) else "n/a"
        refs = ", ".join(it.get("source_refs") or []) or "(none)"
        next_a = it.get("recommended_next_action")
        tail = f" · next: {next_a}" if next_a else ""
        return (
            f"- **{it.get('title_redacted') or '(untitled)'}** "
            f"[{it.get('candidate_type')}] _(confidence {conf_s} · "
            f"safety {it.get('safety_category')} · waiting {it.get('waiting_state')})_{tail}\n"
            f"  - id: {it.get('candidate_id')} · project: {it.get('project_key') or '(none)'} · "
            f"source: [{refs}]"
        )

    if report.get("needs_review"):
        lines += ["", "## Needs Bobby's review (pending · low-confidence/unclear)"]
        lines += [_item(it) for it in report["needs_review"]]

    groups = report.get("groups", {})
    headings = {
        "pending": "Pending",
        "accepted": "Accepted",
        "rejected": "Rejected",
        "snoozed": "Snoozed",
        "suppressed": "Suppressed (ignored)",
    }
    for key in _REPORT_GROUPS:
        items = groups.get(key) or []
        lines += ["", f"## {headings[key]} ({len(items)})"]
        lines += [_item(it) for it in items] if items else ["_None._"]
    return "\n".join(lines) + "\n"


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
    for cand in store.list_review_candidates(status=status, project_key=project_key, limit=limit):
        refs = store.list_candidate_source_refs(candidate_id=cand["candidate_id"], limit=200)
        items.append({**cand, "source_refs": refs})
    return {
        "ok": True,
        "status": status,
        "project_key": project_key,
        "count": len(items),
        "items": items,
    }
