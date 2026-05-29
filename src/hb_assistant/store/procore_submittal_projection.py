"""Phase 04B submittal workflow enrichment projection.

Turns submittals from flat latest-state rows into workflow memory: approvers
(user entity, response, sent/returned/due dates, workflow-duration metrics,
attachments, comment text), inline responses, attachment refs, custom-field
values, and procurement / schedule action signals. Submittals have no dedicated
V7 tables, so everything lands in the cross-cutting enrichment tables. Reads the
raw payload directly (mirrors ``project_rfi``); reuses ``procore_enrichment`` +
the meeting text-scanner. Self-contained store module.
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
    extract_people_refs,
)
from .procore_meeting_projection import _scan_text

# Status fragments that mean the submittal has reached a terminal (non-open) state.
_TERMINAL_TOKENS = ("closed", "void", "completed", "withdrawn", "cancel")
# How close (in days) the required-on-site date must be to raise a procurement signal.
_REQUIRED_ON_SITE_NEAR_DAYS = 14
# Scalar parent fields carried as signal metadata (no raw body; all non-PII).
_PARENT_META_FIELDS = (
    "formatted_number",
    "current_revision",
    "revision",
    "is_rejected",
    "for_record_only",
    "issue_date",
    "required_on_site_date",
    "received_date",
    "specification_section",
)


def _record_key(project_key: str, endpoint_id: str, parent: Optional[str], record_id: Any) -> str:
    return "|".join([project_key, endpoint_id, parent or "", str(record_id)])


def _status(raw: Mapping[str, Any]) -> str:
    return str(raw.get("status") or "").strip().lower()


def _is_approved(raw: Mapping[str, Any]) -> bool:
    return "approv" in _status(raw)


def _is_rejected(raw: Mapping[str, Any]) -> bool:
    return bool(raw.get("is_rejected")) or "reject" in _status(raw)


def _is_open(raw: Mapping[str, Any]) -> bool:
    status = _status(raw)
    if _is_approved(raw) or _is_rejected(raw):
        return False
    return not any(tok in status for tok in _TERMINAL_TOKENS)


def _parse_date(value: Any) -> Optional[date]:
    """Parse the YYYY-MM-DD prefix of an ISO date / datetime string."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _days_between(start: Any, end: Any) -> Optional[int]:
    s, e = _parse_date(start), _parse_date(end)
    if s is not None and e is not None:
        return (e - s).days
    return None


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


def _looks_like_person(ref: Any) -> bool:
    return isinstance(ref, dict) and "login" in ref


def _project_responsibility(
    raw: Mapping[str, Any], *, submittal_rk: str, project_key: str, now_utc: str, db_path: Optional[Path],
) -> None:
    """submittal_manager / received_from / responsible_contractor / scheduled_task edges."""
    for k in extract_people_refs(raw.get("submittal_manager"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=submittal_rk, edge_type="submittal_manager",
                         source_endpoint_id="submittals", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    received_from = raw.get("received_from")
    if _looks_like_person(received_from):
        ref_keys = extract_people_refs(received_from, now_utc=now_utc, db_path=db_path)
    else:
        ref_keys = extract_company_refs(received_from, now_utc=now_utc, db_path=db_path)
    for k in ref_keys:
        emit_record_edge(project_key=project_key, from_record_key=submittal_rk, edge_type="received_from",
                         source_endpoint_id="submittals", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    for k in extract_company_refs(raw.get("responsible_contractor"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=submittal_rk, edge_type="responsible_contractor",
                         source_endpoint_id="submittals", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    task = raw.get("scheduled_task")
    task_id = task.get("id") if isinstance(task, dict) else (task if task not in (None, "") else None)
    if task_id is not None:
        emit_record_edge(
            project_key=project_key, from_record_key=submittal_rk,
            to_record_key=_record_key(project_key, "schedule-tasks", None, task_id),
            edge_type="scheduled_task", source_endpoint_id="submittals", now_utc=now_utc, db_path=db_path,
        )


def _project_approver(
    approver: Mapping[str, Any], *, submittal_id: str, submittal_rk: str, project_key: str,
    now_utc: str, db_path: Optional[Path],
) -> bool:
    """Project a single approver; returns True if it has been returned."""
    if not isinstance(approver, dict):
        return False
    approver_id = approver.get("id")
    approver_rk = _record_key(project_key, "submittal-approvers", submittal_id, approver_id)

    response = approver.get("response") if isinstance(approver.get("response"), dict) else {}
    sent_date = approver.get("sent_date")
    returned_date = approver.get("returned_date")
    days_to_respond = approver.get("days_to_respond")
    if not isinstance(days_to_respond, int):
        days_to_respond = _days_between(sent_date, returned_date or now_utc)
    metadata = {
        "approver_id": str(approver_id) if approver_id is not None else None,
        "approver_type": approver.get("approver_type"),
        "workflow_group": approver.get("workflow_group_id") or approver.get("workflow_group_number"),
        "response_name": response.get("name") or approver.get("response_name"),
        "response_considered": response.get("considered") or approver.get("response_considered"),
        "response_required": bool(approver.get("response_required")),
        "sent_date": sent_date,
        "returned_date": returned_date,
        "due_date": approver.get("due_date"),
        "days_to_respond": days_to_respond,
    }

    user = approver.get("user") if isinstance(approver.get("user"), dict) else approver.get("approver")
    if user is None and approver.get("user_id") is not None:
        user = {"id": approver["user_id"]}
    for k in extract_people_refs(user, now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=submittal_rk, edge_type="approver",
                         source_endpoint_id="submittals", to_entity_key=k, metadata=metadata,
                         now_utc=now_utc, db_path=db_path)

    attachments = list(approver.get("attachments") or [])
    attachments += [{"id": a} for a in (approver.get("attachment_ids") or []) if a not in (None, "")]
    extract_attachment_refs(
        attachments, project_key=project_key, source_record_key=approver_rk,
        source_endpoint_id="submittals", parent_record_key=submittal_rk, now_utc=now_utc, db_path=db_path,
    )

    _emit_text(record_key=approver_rk, endpoint_id="submittals", field="approver_comment",
               text=approver.get("comment"), project_key=project_key, now_utc=now_utc, db_path=db_path)
    return returned_date not in (None, "")


def _project_response(
    response: Mapping[str, Any], *, submittal_id: str, project_key: str, now_utc: str, db_path: Optional[Path],
) -> bool:
    """Project an inline submittal response; returns True if it carries a terminal status."""
    if not isinstance(response, dict) or response.get("id") in (None, ""):
        return False
    response_rk = _record_key(project_key, "submittal-responses", submittal_id, response["id"])
    if response.get("author_id") is not None:
        for k in extract_people_refs({"id": response["author_id"]}, now_utc=now_utc, db_path=db_path):
            emit_record_edge(project_key=project_key, from_record_key=response_rk, edge_type="response_author",
                             source_endpoint_id="submittal-responses", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    _emit_text(record_key=response_rk, endpoint_id="submittal-responses", field="comment",
               text=response.get("comment"), project_key=project_key, now_utc=now_utc, db_path=db_path)
    status = str(response.get("response_status") or "").strip().lower()
    return bool(status) and status not in ("pending", "pending_review", "draft", "open")


def project_submittal(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str] = None,
    now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    submittal_id = str(raw["id"])
    submittal_rk = _record_key(project_key, "submittals", None, submittal_id)
    signals: List[str] = []

    _project_responsibility(raw, submittal_rk=submittal_rk, project_key=project_key,
                            now_utc=now_utc, db_path=db_path)

    extract_custom_field_values(
        raw.get("custom_fields"), project_key=project_key, record_key=submittal_rk,
        endpoint_id="submittals", procore_record_id=submittal_id, now_utc=now_utc, db_path=db_path,
    )

    # Approvers: workflow memory + waiting / returned state.
    approvers = raw.get("approvers") or raw.get("submittal_workflow") or raw.get("workflow_data") or []
    waiting_on_approver = False
    any_returned = False
    for approver in approvers if isinstance(approvers, list) else []:
        returned = _project_approver(approver, submittal_id=submittal_id, submittal_rk=submittal_rk,
                                     project_key=project_key, now_utc=now_utc, db_path=db_path)
        any_returned = any_returned or returned
        if isinstance(approver, dict) and approver.get("response_required") and approver.get("returned_date") in (None, ""):
            waiting_on_approver = True

    # Inline responses.
    for response in raw.get("responses") or []:
        if _project_response(response, submittal_id=submittal_id, project_key=project_key,
                             now_utc=now_utc, db_path=db_path):
            any_returned = True

    # ---- action signals ----------------------------------------------------
    meta = {f: raw.get(f) for f in _PARENT_META_FIELDS if raw.get(f) is not None}
    primary_emitted = False

    def _sig(signal_type: str, importance: str, *, with_meta: bool = False) -> None:
        nonlocal primary_emitted
        attach = meta if (with_meta and not primary_emitted and meta) else None
        emit_action_signal(project_key=project_key, record_key=submittal_rk, endpoint_id="submittals",
                           signal_type=signal_type, importance=importance, metadata=attach,
                           now_utc=now_utc, db_path=db_path)
        if attach is not None:
            primary_emitted = True
        signals.append(signal_type)

    now_date = _parse_date(now_utc)
    is_open = _is_open(raw)

    if _is_rejected(raw):
        _sig("submittal_rejected", "high", with_meta=True)
    if _is_approved(raw):
        _sig("submittal_approved", "medium", with_meta=True)
    if is_open:
        _sig("submittal_open", "medium", with_meta=True)
        due = _parse_date(raw.get("due_date"))
        if due is not None and now_date is not None and due < now_date:
            _sig("submittal_overdue", "high")
        if waiting_on_approver:
            _sig("submittal_waiting_on_approver", "medium")

    required = _parse_date(raw.get("required_on_site_date"))
    if required is not None and now_date is not None and 0 <= (required - now_date).days <= _REQUIRED_ON_SITE_NEAR_DAYS:
        _sig("submittal_required_on_site_date_near", "medium")
    if any_returned:
        _sig("submittal_response_returned", "medium")

    return {"projected": True, "record_key": submittal_rk, "signals": signals}


__all__ = ["project_submittal"]
