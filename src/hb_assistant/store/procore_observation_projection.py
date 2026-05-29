"""Phase 04B observation + safety enrichment projection.

Turns observations into safety/action memory: description text intelligence,
assignee (with vendor), created-by, location hierarchy, trade, and category /
type / priority / personal / safety-classification signals. Observations have no
dedicated V7 tables, so everything lands in the cross-cutting enrichment tables.
Reads the raw payload directly (mirrors ``project_submittal``); reuses
``procore_enrichment`` + the meeting text-scanner. The safety heuristic mirrors
the keyword set in ``normalizers/observation.py``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .procore_enrichment import (
    emit_action_signal,
    emit_record_edge,
    emit_text_intelligence,
    extract_company_refs,
    extract_custom_field_values,
    extract_location_refs,
    extract_people_refs,
)
from .procore_meeting_projection import _scan_text

# Safety classification tokens (mirrors normalizers/observation.py safety set).
_SAFETY_TOKENS = (
    "safety", "incident", "injury", "near-miss", "near_miss", "near miss",
    "unsafe", "violation", "ppe", "fall", "first aid", "corrective",
)
_CLOSED_TOKENS = ("closed", "completed", "resolved", "void", "cancel")
_HIGH_PRIORITY = {"high", "urgent", "critical"}
_DUE_SOON_DAYS = 3
# Scalar metadata carried on the primary signal (no raw body; non-PII).
_META_FIELDS = ("category", "type", "subtype", "priority", "severity", "personal", "date_notified")


def _record_key(project_key: str, endpoint_id: str, parent: Optional[str], record_id: Any) -> str:
    return "|".join([project_key, endpoint_id, parent or "", str(record_id)])


def _parse_date(value: Any) -> Optional[date]:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _label(value: Any) -> str:
    """Lower-cased label for a field that may be a str or a {name|category} dict."""
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, dict):
        return " ".join(
            str(value.get(k) or "") for k in ("name", "category", "title")
        ).lower()
    return ""


def _is_open(raw: Mapping[str, Any]) -> bool:
    if raw.get("closed_at") not in (None, ""):
        return False
    status = str(raw.get("status") or "").strip().lower()
    return not any(tok in status for tok in _CLOSED_TOKENS)


def _is_safety(raw: Mapping[str, Any]) -> bool:
    haystack = " ".join(
        _label(raw.get(f)) for f in ("type", "subtype", "status", "title", "description", "category")
    )
    return any(tok in haystack for tok in _SAFETY_TOKENS)


def _emit_text(
    *, record_key: str, field: str, text: Any, project_key: str, now_utc: str, db_path: Optional[Path],
) -> None:
    if not isinstance(text, str) or not text.strip():
        return
    scan = _scan_text(text)
    emit_text_intelligence(
        project_key=project_key, record_key=record_key, endpoint_id="observations",
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


def project_observation(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str] = None,
    now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    obs_id = str(raw["id"])
    obs_rk = _record_key(project_key, "observations", None, obs_id)
    signals: List[str] = []

    # location / trade / vendor edges
    for k in extract_location_refs(raw.get("location"), project_key=project_key, now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=obs_rk, edge_type="at_location",
                         source_endpoint_id="observations", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    for k in extract_company_refs(raw.get("trade"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=obs_rk, edge_type="trade",
                         source_endpoint_id="observations", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    assignee = raw.get("assignee") if isinstance(raw.get("assignee"), dict) else None
    vendor = raw.get("vendor")
    if vendor is None and isinstance(assignee, dict):
        vendor = assignee.get("vendor")
    for k in extract_company_refs(vendor, now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=obs_rk, edge_type="vendor",
                         source_endpoint_id="observations", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    # assignee / created-by people (+ created-by company)
    assignee_ref = assignee if assignee is not None else (
        {"id": raw["assignee_id"]} if raw.get("assignee_id") not in (None, "") else None
    )
    for k in extract_people_refs(assignee_ref, now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=obs_rk, edge_type="assignee",
                         source_endpoint_id="observations", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    created_by = raw.get("created_by") if isinstance(raw.get("created_by"), dict) else (
        {"id": raw["created_by_id"]} if raw.get("created_by_id") not in (None, "") else None
    )
    for k in extract_people_refs(created_by, now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=obs_rk, edge_type="created_by",
                         source_endpoint_id="observations", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    if isinstance(raw.get("created_by"), dict):
        for k in extract_company_refs(_company_from_name(raw["created_by"].get("company_name")),
                                      now_utc=now_utc, db_path=db_path):
            emit_record_edge(project_key=project_key, from_record_key=obs_rk, edge_type="created_by_company",
                             source_endpoint_id="observations", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    extract_custom_field_values(
        raw.get("custom_fields"), project_key=project_key, record_key=obs_rk,
        endpoint_id="observations", procore_record_id=obs_id, now_utc=now_utc, db_path=db_path,
    )

    # text intelligence: description (+ rich text)
    for field in ("description", "rich_text_description", "html_description"):
        _emit_text(record_key=obs_rk, field=field, text=raw.get(field),
                   project_key=project_key, now_utc=now_utc, db_path=db_path)

    # ---- action signals ----------------------------------------------------
    meta = {f: raw.get(f) for f in _META_FIELDS if raw.get(f) is not None}
    safety = _is_safety(raw)
    meta["safety"] = safety
    primary_emitted = False

    def _sig(signal_type: str, importance: str) -> None:
        nonlocal primary_emitted
        attach = meta if not primary_emitted else None
        emit_action_signal(project_key=project_key, record_key=obs_rk, endpoint_id="observations",
                           signal_type=signal_type, importance=importance, metadata=attach,
                           now_utc=now_utc, db_path=db_path)
        primary_emitted = True
        signals.append(signal_type)

    is_open = _is_open(raw)
    priority = str(raw.get("priority") or "").strip().lower()
    severity = str(raw.get("severity") or "").strip().lower()
    now_date = _parse_date(now_utc)
    due = _parse_date(raw.get("due_date"))

    if not is_open:
        _sig("observation_closed", "low")
    else:
        if safety:
            _sig("observation_open_safety", "high")
        if priority in _HIGH_PRIORITY or severity in _HIGH_PRIORITY:
            _sig("observation_high_priority", "high")
        if due is not None and now_date is not None and 0 <= (due - now_date).days <= _DUE_SOON_DAYS:
            _sig("observation_due_soon", "medium")

    return {"projected": True, "record_key": obs_rk, "signals": signals}


__all__ = ["project_observation"]
