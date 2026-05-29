"""Phase 04B punch-item workflow enrichment projection.

Turns punch items into action memory: assignments (assignee person + vendor
company, status, notified/responded/manager-accepted dates), location hierarchy,
trade, ball-in-court, unresolved/resolved response state, attachment refs,
schedule-risk-reason + description text intelligence, and cost/schedule-impact
signals. Punch items have no dedicated V7 tables, so everything lands in the
cross-cutting enrichment tables. Reads the raw payload directly (mirrors
``project_submittal``); reuses ``procore_enrichment`` + the meeting text-scanner.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .procore_enrichment import (
    emit_action_signal,
    emit_record_edge,
    emit_text_intelligence,
    extract_attachment_refs,
    extract_company_refs,
    extract_custom_field_values,
    extract_location_refs,
    extract_people_refs,
)
from .procore_meeting_projection import _scan_text

# Status fragments that mean the punch item is no longer open.
_CLOSED_TOKENS = ("closed", "completed", "resolved", "void", "cancel")
# Scalar impact fields carried as signal metadata (no raw body; non-PII).
_IMPACT_META_FIELDS = (
    "cost_impact",
    "cost_impact_amount",
    "schedule_impact",
    "schedule_impact_days",
    "schedule_risk",
)


def _record_key(project_key: str, endpoint_id: str, parent: Optional[str], record_id: Any) -> str:
    return "|".join([project_key, endpoint_id, parent or "", str(record_id)])


def _parse_date(value: Any) -> Optional[date]:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _is_open(raw: Mapping[str, Any]) -> bool:
    if raw.get("closed_at") not in (None, ""):
        return False
    status = str(raw.get("status") or "").strip().lower()
    return not any(tok in status for tok in _CLOSED_TOKENS)


def _emit_text(
    *, record_key: str, endpoint_id: str, field: str, text: Any, project_key: str, now_utc: str,
    db_path: Optional[Path],
) -> None:
    if not isinstance(text, str) or not text.strip():
        return
    scan = _scan_text(text)
    emit_text_intelligence(
        project_key=project_key, record_key=record_key, endpoint_id=endpoint_id,
        source_field_path=field, text=text,
        topics=scan["detected_topics"],
        mentioned_records=[m["ref"] for m in scan["mentioned_records"]],
        action_candidates=scan["action_candidates"],
        risk_terms=scan["risk_terms"],
        review_required=bool(scan["risk_terms"]),
        store_encrypted=True, excerpt_chars=160, now_utc=now_utc, db_path=db_path,
    )


def _company_from_name(name: Any) -> List[Mapping[str, Any]]:
    return [{"name": name}] if isinstance(name, str) and name.strip() else []


def _project_assignment(
    assignment: Mapping[str, Any], *, punch_rk: str, project_key: str, now_utc: str, db_path: Optional[Path],
) -> tuple[bool, bool]:
    """Project one inline assignment. Returns (is_unresolved, is_waiting)."""
    if not isinstance(assignment, dict):
        return (False, False)
    status = str(assignment.get("status") or "").strip().lower()
    notified = assignment.get("notified_at")
    responded = assignment.get("responded_at")
    metadata = {
        "assignment_id": assignment.get("id"),
        "approved": bool(assignment.get("approved")),
        "status": assignment.get("status"),
        "notified_at": notified,
        "responded_at": responded,
        "manager_accepted_at": assignment.get("manager_accepted_at"),
    }
    for k in extract_people_refs(assignment.get("login_information"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=punch_rk, edge_type="assignee",
                         source_endpoint_id="punch-items", to_entity_key=k, metadata=metadata,
                         now_utc=now_utc, db_path=db_path)
    for k in extract_company_refs(assignment.get("vendor"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=punch_rk, edge_type="vendor",
                         source_endpoint_id="punch-items", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    extract_attachment_refs(
        assignment.get("attachments"), project_key=project_key, source_record_key=punch_rk,
        source_endpoint_id="punch-items", parent_record_key=punch_rk, now_utc=now_utc, db_path=db_path,
    )
    _emit_text(record_key=punch_rk, endpoint_id="punch-items", field="assignment_comment",
               text=assignment.get("comment"), project_key=project_key, now_utc=now_utc, db_path=db_path)
    is_unresolved = status == "unresolved"
    is_waiting = notified not in (None, "") and responded in (None, "")
    return (is_unresolved, is_waiting)


def project_punch_item(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str] = None,
    now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    punch_id = str(raw["id"])
    punch_rk = _record_key(project_key, "punch-items", None, punch_id)
    signals: List[str] = []

    # location / trade / ball-in-court / created-by edges
    for k in extract_location_refs(raw.get("location"), project_key=project_key, now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=punch_rk, edge_type="at_location",
                         source_endpoint_id="punch-items", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    for k in extract_company_refs(raw.get("trade"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=punch_rk, edge_type="trade",
                         source_endpoint_id="punch-items", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    for k in extract_people_refs(raw.get("ball_in_court"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=punch_rk, edge_type="ball_in_court",
                         source_endpoint_id="punch-items", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    for k in extract_people_refs(raw.get("created_by"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=punch_rk, edge_type="created_by",
                         source_endpoint_id="punch-items", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    created_by = raw.get("created_by")
    if isinstance(created_by, dict):
        for k in extract_company_refs(_company_from_name(created_by.get("company_name")), now_utc=now_utc, db_path=db_path):
            emit_record_edge(project_key=project_key, from_record_key=punch_rk, edge_type="created_by_company",
                             source_endpoint_id="punch-items", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    extract_custom_field_values(
        raw.get("custom_fields"), project_key=project_key, record_key=punch_rk,
        endpoint_id="punch-items", procore_record_id=punch_id, now_utc=now_utc, db_path=db_path,
    )

    # inline assignments (metadata-bearing assignee edges — emitted before the
    # plain top-level assignees edge so the workflow metadata is the first write
    # for a shared person: the edge ON CONFLICT clause does not overwrite it).
    any_unresolved = False
    any_waiting = False
    for assignment in raw.get("assignments") or []:
        unresolved, waiting = _project_assignment(assignment, punch_rk=punch_rk, project_key=project_key,
                                                  now_utc=now_utc, db_path=db_path)
        any_unresolved = any_unresolved or unresolved
        any_waiting = any_waiting or waiting
    for k in extract_people_refs(raw.get("assignees"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=punch_rk, edge_type="assignee",
                         source_endpoint_id="punch-items", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    # text intelligence
    _emit_text(record_key=punch_rk, endpoint_id="punch-items", field="schedule_risk_reason",
               text=raw.get("schedule_risk_reason"), project_key=project_key, now_utc=now_utc, db_path=db_path)
    _emit_text(record_key=punch_rk, endpoint_id="punch-items", field="description",
               text=raw.get("description"), project_key=project_key, now_utc=now_utc, db_path=db_path)

    # ---- action signals ----------------------------------------------------
    meta = {f: raw.get(f) for f in _IMPACT_META_FIELDS if raw.get(f) is not None}
    primary_emitted = False

    def _sig(signal_type: str, importance: str) -> None:
        nonlocal primary_emitted
        attach = meta if (not primary_emitted and meta) else None
        emit_action_signal(project_key=project_key, record_key=punch_rk, endpoint_id="punch-items",
                           signal_type=signal_type, importance=importance, metadata=attach,
                           now_utc=now_utc, db_path=db_path)
        if attach is not None:
            primary_emitted = True
        signals.append(signal_type)

    now_date = _parse_date(now_utc)
    due = _parse_date(raw.get("due_date"))
    is_open = _is_open(raw)

    if is_open and due is not None and now_date is not None:
        delta = (due - now_date).days
        if delta < 0:
            _sig("punch_overdue", "high")
        elif delta == 1:
            _sig("punch_due_tomorrow", "medium")
    if raw.get("has_unresolved_responses") or any_unresolved:
        _sig("punch_unresolved_response", "high")
    if is_open and any_waiting:
        _sig("punch_assignment_waiting", "medium")

    return {"projected": True, "record_key": punch_rk, "signals": signals}


__all__ = ["project_punch_item"]
