"""Phase 04B RFI + RFI-response enrichment projection.

Extracts RFI responsibility (received_from / responsible_contractor / rfi_manager /
assignees / ball_in_court), question + proposed-solution text, cost/schedule
impact signals, and response answers / official-answer state into the
cross-cutting enrichment tables (RFIs have no dedicated V7 tables). Replies are
projected from the orchestrator's inline ``replies`` under the parent RFI.
Self-contained store module — reuses ``procore_enrichment`` + the meeting
text-scanner; reads ``change_events`` for the ball-in-court signal.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .procore_enrichment import (
    emit_action_signal,
    emit_record_edge,
    emit_text_intelligence,
    extract_attachment_refs,
    extract_company_refs,
    extract_people_refs,
)
from .procore_meeting_projection import _scan_text

# cost_impact / schedule_impact status values that mean "no impact" (not flagged).
_NO_IMPACT = {"", "none", "no_impact", "no impact", "tbd", "n/a", "na", "no"}
# status tokens that mean the RFI is no longer open.
_CLOSED_RFI_TOKENS = ("closed", "answered", "resolved")


def _record_key(project_key: str, endpoint_id: str, parent: Optional[str], record_id: Any) -> str:
    return "|".join([project_key, endpoint_id, parent or "", str(record_id)])


def _impact_flagged(impact: Any) -> bool:
    if not isinstance(impact, dict):
        return False
    status = str(impact.get("status") or "").strip().lower()
    return bool(status) and status not in _NO_IMPACT


def _is_open(raw: Mapping[str, Any]) -> bool:
    for key in ("status", "translated_status"):
        v = str(raw.get(key) or "").strip().lower()
        if v and any(tok in v for tok in _CLOSED_RFI_TOKENS):
            return False
    return True


def _overdue(raw: Mapping[str, Any]) -> bool:
    return any("overdue" in str(raw.get(k) or "").lower() for k in ("status", "translated_status"))


def _ball_in_court_people(raw: Mapping[str, Any]) -> List[Any]:
    out: List[Any] = []
    bic = raw.get("ball_in_court")
    if isinstance(bic, dict):
        out.append(bic)
    courts = raw.get("ball_in_courts")
    if isinstance(courts, list):
        out.extend(c for c in courts if isinstance(c, dict))
    return out


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


def project_rfi_response(
    raw: Mapping[str, Any], *, parent_rfi_id: Optional[str], project_key: str,
    now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    response_id = str(raw["id"])
    response_rk = _record_key(project_key, "rfi-responses", parent_rfi_id, response_id)
    rfi_rk = _record_key(project_key, "rfis", None, parent_rfi_id) if parent_rfi_id else None

    for field in ("plain_text_body", "rich_text_body"):
        _emit_text(record_key=response_rk, endpoint_id="rfi-responses", field=field,
                   text=raw.get(field), project_key=project_key, now_utc=now_utc, db_path=db_path)
    extract_attachment_refs(
        raw.get("attachments"), project_key=project_key, source_record_key=response_rk,
        source_endpoint_id="rfi-responses", parent_record_key=rfi_rk, now_utc=now_utc, db_path=db_path,
    )
    if raw.get("created_by_id") is not None:
        for k in extract_people_refs({"id": raw["created_by_id"]}, now_utc=now_utc, db_path=db_path):
            emit_record_edge(project_key=project_key, from_record_key=response_rk, edge_type="created_by",
                             source_endpoint_id="rfi-responses", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    if rfi_rk is not None:
        emit_record_edge(project_key=project_key, from_record_key=response_rk, to_record_key=rfi_rk,
                         edge_type="response_to_rfi", source_endpoint_id="rfi-responses", now_utc=now_utc, db_path=db_path)
        if raw.get("official"):
            emit_action_signal(project_key=project_key, record_key=rfi_rk, endpoint_id="rfis",
                               signal_type="rfi_official_answer_added", importance="high", now_utc=now_utc, db_path=db_path)
            emit_action_signal(project_key=project_key, record_key=rfi_rk, endpoint_id="rfis",
                               signal_type="rfi_answered", importance="medium", now_utc=now_utc, db_path=db_path)
    return {"projected": True, "record_key": response_rk, "official": bool(raw.get("official"))}


def _ball_in_court_changed(rfi_rk: str, sync_run_id: Optional[str], db_path: Optional[Path]) -> bool:
    conn = sqlite3.connect(str(db_path)) if db_path is not None else None
    if conn is None:
        return False
    try:
        if sync_run_id:
            row = conn.execute(
                "SELECT 1 FROM procore_live_record_change_events WHERE record_key=? "
                "AND change_category='ball_in_court_changed' AND sync_run_id=? LIMIT 1",
                (rfi_rk, sync_run_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM procore_live_record_change_events WHERE record_key=? "
                "AND change_category='ball_in_court_changed' LIMIT 1",
                (rfi_rk,),
            ).fetchone()
        return row is not None
    finally:
        conn.close()


def project_rfi(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str] = None,
    now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    rfi_id = str(raw["id"])
    rfi_rk = _record_key(project_key, "rfis", None, rfi_id)
    signals: List[str] = []

    # people / company edges
    for ref_key, edge in (
        ("received_from", "received_from"), ("rfi_manager", "rfi_manager"),
        ("assignee", "assignee"), ("created_by", "created_by"),
    ):
        for k in extract_people_refs(raw.get(ref_key), now_utc=now_utc, db_path=db_path):
            emit_record_edge(project_key=project_key, from_record_key=rfi_rk, edge_type=edge,
                             source_endpoint_id="rfis", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    for k in extract_people_refs(raw.get("assignees"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=rfi_rk, edge_type="assignee",
                         source_endpoint_id="rfis", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    for k in extract_people_refs(_ball_in_court_people(raw), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=rfi_rk, edge_type="ball_in_court",
                         source_endpoint_id="rfis", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    for k in extract_company_refs(raw.get("responsible_contractor"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=rfi_rk, edge_type="responsible_contractor",
                         source_endpoint_id="rfis", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    # text intelligence: questions + proposed solution
    for q in raw.get("questions") or []:
        if isinstance(q, dict):
            _emit_text(record_key=rfi_rk, endpoint_id="rfis", field="question",
                       text=q.get("body"), project_key=project_key, now_utc=now_utc, db_path=db_path)
    _emit_text(record_key=rfi_rk, endpoint_id="rfis", field="proposed_solution",
               text=raw.get("proposed_solution"), project_key=project_key, now_utc=now_utc, db_path=db_path)

    # responses present inline?
    official_present = any(isinstance(r, dict) and r.get("official") for r in (raw.get("replies") or []))

    # action signals
    def _sig(signal_type: str, importance: str) -> None:
        emit_action_signal(project_key=project_key, record_key=rfi_rk, endpoint_id="rfis",
                           signal_type=signal_type, importance=importance, now_utc=now_utc, db_path=db_path)
        signals.append(signal_type)

    if _is_open(raw):
        _sig("rfi_open", "medium")
        if not official_present:
            _sig("rfi_unanswered", "medium")
    if _overdue(raw):
        _sig("rfi_overdue", "high")
    if _impact_flagged(raw.get("cost_impact")):
        _sig("rfi_cost_impact_flagged", "high")
    if _impact_flagged(raw.get("schedule_impact")):
        _sig("rfi_schedule_impact_flagged", "high")
    if _ball_in_court_changed(rfi_rk, sync_run_id, db_path):
        _sig("rfi_ball_in_court_changed", "medium")

    # inline replies
    for reply in raw.get("replies") or []:
        if isinstance(reply, dict):
            project_rfi_response(reply, parent_rfi_id=rfi_id, project_key=project_key,
                                 now_utc=now_utc, db_path=db_path)

    return {"projected": True, "record_key": rfi_rk, "signals": signals}


__all__ = ["project_rfi", "project_rfi_response"]
