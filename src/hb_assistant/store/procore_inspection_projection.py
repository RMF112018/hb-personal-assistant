"""Phase 04B inspection enrichment projections.

Projects the ``inspections`` / ``inspection-sections`` / ``inspection-items``
payloads into the dedicated V7 inspection tables, derives second-brain meaning
(safety detection, open/closed/overdue, response interpretation, evidence rules,
risk category), and emits the required action signals + relationship edges via
the shared enrichment framework.

Operates on the **raw** payload because the inspection-item normalizer drops
``evidence_configuration``; only structural ids / labels / flags are persisted
(never a raw-body blob). Checklist names (inspection / section / item / response
labels) are not personal PII and are kept verbatim; people (inspectors /
created_by) are hashed via ``extract_people_refs``. Self-contained except for
sibling store imports.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .connection import open_connection, transaction
from .procore_enrichment import (
    emit_action_signal,
    emit_record_edge,
    extract_company_refs,
    extract_location_refs,
    extract_people_refs,
)

_SAFETY_FRAGMENTS = ("safety", "incident", "injury", "near miss", "near-miss", "osha", "ppe", "fall")
_INSPECTION_ENDPOINTS = {"inspections", "inspection-sections", "inspection-items"}


def _hash(*parts: Any) -> str:
    return hashlib.sha256("|".join("" if p is None else str(p) for p in parts).encode("utf-8")).hexdigest()[:32]


def _record_key(project_key: str, endpoint_id: str, parent: Optional[str], record_id: Any) -> str:
    return "|".join([project_key, endpoint_id, parent or "", str(record_id)])


def _json(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, dict)) and not value:
        return None
    return json.dumps(value, default=str, sort_keys=True)


def _is_safety(name: Any) -> bool:
    if not isinstance(name, str):
        return False
    low = name.lower()
    return any(frag in low for frag in _SAFETY_FRAGMENTS)


def _risk_category(section_name: Any) -> str:
    n = (section_name or "").lower() if isinstance(section_name, str) else ""
    if any(k in n for k in ("highest", "high risk", "high-risk", "fall", "critical", "severe", "safety", "hazard")):
        return "high"
    if "medium" in n or "moderate" in n:
        return "medium"
    if "low" in n:
        return "low"
    return "general"


_NO_RESPONSE_TOKENS = {"", "no response", "none", "not answered", "unanswered", "n/r"}
_NA_TOKENS = {"not_applicable", "not applicable", "n/a"}


def _interpret_response(responded_with: Any, response_set: Any) -> Dict[str, Any]:
    """Map ``responded_with`` against the response set to conformance flags."""
    options = response_set.get("responses") if isinstance(response_set, dict) else None
    rw = "" if responded_with is None else str(responded_with).strip()
    chosen: Optional[Dict[str, Any]] = None
    for opt in options or []:
        if isinstance(opt, dict) and str(opt.get("name", "")).strip().lower() == rw.lower():
            chosen = opt
            break
    category = (chosen.get("status") if isinstance(chosen, dict) else None) or ""
    cat = category.strip().lower()
    is_conforming = cat == "conforming"
    is_deficient = cat == "deficient"
    is_na = cat in _NA_TOKENS
    is_unanswered = rw.lower() in _NO_RESPONSE_TOKENS or not (is_conforming or is_deficient or is_na)
    return {
        "response_id": chosen.get("id") if isinstance(chosen, dict) else None,
        "response_name": rw or None,
        "response_status": cat or ("no_response" if is_unanswered else None),
        "is_unanswered": is_unanswered,
        "is_conforming": is_conforming,
        "is_deficient": is_deficient,
        "is_not_applicable": is_na,
    }


# ---------------------------------------------------------------------------
# Parent inspection record
# ---------------------------------------------------------------------------


def project_inspection_record(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str] = None,
    now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    inspection_id = str(raw["id"])
    key = _hash("inspection", project_key, inspection_id)
    rk = _record_key(project_key, "inspections", None, inspection_id)
    inspection_type = raw.get("inspection_type") if isinstance(raw.get("inspection_type"), dict) else {}
    type_name = inspection_type.get("name")
    is_safety = _is_safety(type_name)
    status = raw.get("status")
    closed = bool(raw.get("closed_at")) or (isinstance(status, str) and "clos" in status.lower())
    overdue = bool(raw.get("overdue"))
    deficient = raw.get("deficient_item_count") or 0
    respondable = raw.get("respondable_item_count") or 0
    inspected = raw.get("inspected_item_count") or 0
    unanswered_count = max(int(respondable) - int(inspected), 0) if isinstance(respondable, int) and isinstance(inspected, int) else 0

    with open_connection(db_path) as conn, transaction(conn):
        conn.execute(
            """
            INSERT INTO procore_inspection_records (
              inspection_record_key, project_key, inspection_id, name_redacted, identifier, number,
              status, inspection_date, due_at_utc, closed_at_utc, list_template_id,
              list_template_name_redacted, inspection_type_name, is_safety, private, overdue,
              item_count, respondable_item_count, inspected_item_count, conforming_item_count,
              deficient_item_count, observations_count, closed_observations_count, created_at_utc,
              updated_at_utc, last_sync_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(inspection_record_key) DO UPDATE SET
              name_redacted=excluded.name_redacted, status=excluded.status,
              inspection_date=excluded.inspection_date, due_at_utc=excluded.due_at_utc,
              closed_at_utc=excluded.closed_at_utc, list_template_name_redacted=excluded.list_template_name_redacted,
              inspection_type_name=excluded.inspection_type_name, is_safety=excluded.is_safety,
              private=excluded.private, overdue=excluded.overdue, item_count=excluded.item_count,
              respondable_item_count=excluded.respondable_item_count,
              inspected_item_count=excluded.inspected_item_count,
              conforming_item_count=excluded.conforming_item_count,
              deficient_item_count=excluded.deficient_item_count,
              observations_count=excluded.observations_count,
              closed_observations_count=excluded.closed_observations_count,
              updated_at_utc=excluded.updated_at_utc, last_sync_run_id=excluded.last_sync_run_id
            """,
            (
                key, project_key, inspection_id, raw.get("name"), raw.get("identifier"),
                str(raw.get("number")) if raw.get("number") is not None else None, status,
                raw.get("inspection_date"), raw.get("due_at"), raw.get("closed_at"),
                raw.get("list_template_id"), raw.get("list_template_name"), type_name,
                1 if is_safety else 0, 1 if raw.get("private") else 0, 1 if overdue else 0,
                raw.get("item_count"), raw.get("respondable_item_count"), raw.get("inspected_item_count"),
                raw.get("conforming_item_count"), raw.get("deficient_item_count"),
                raw.get("observations_count"), raw.get("closed_observations_count"),
                raw.get("created_at"), raw.get("updated_at"), sync_run_id,
            ),
        )

    # entities + edges
    inspector_keys = extract_people_refs(raw.get("inspectors"), now_utc=now_utc, db_path=db_path)
    for k in inspector_keys:
        emit_record_edge(project_key=project_key, from_record_key=rk, edge_type="inspector",
                         source_endpoint_id="inspections", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    for k in extract_people_refs(raw.get("created_by"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=rk, edge_type="created_by",
                         source_endpoint_id="inspections", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    for k in extract_company_refs(raw.get("responsible_contractor"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=rk, edge_type="responsible_contractor",
                         source_endpoint_id="inspections", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    for k in extract_location_refs(raw.get("location"), project_key=project_key, now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=rk, edge_type="at_location",
                         source_endpoint_id="inspections", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    for k in extract_company_refs(raw.get("trade"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=rk, edge_type="trade",
                         source_endpoint_id="inspections", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    # action signals
    signals: List[str] = []
    if is_safety and not closed:
        emit_action_signal(project_key=project_key, record_key=rk, endpoint_id="inspections",
                           signal_type="inspection_open_safety", importance="high", now_utc=now_utc, db_path=db_path)
        signals.append("inspection_open_safety")
    if overdue:
        emit_action_signal(project_key=project_key, record_key=rk, endpoint_id="inspections",
                           signal_type="inspection_overdue", importance="high", now_utc=now_utc, db_path=db_path)
        signals.append("inspection_overdue")
    if isinstance(deficient, int) and deficient > 0:
        emit_action_signal(project_key=project_key, record_key=rk, endpoint_id="inspections",
                           signal_type="inspection_has_deficient_items", importance="high", now_utc=now_utc, db_path=db_path)
        signals.append("inspection_has_deficient_items")
    if unanswered_count > 0:
        emit_action_signal(project_key=project_key, record_key=rk, endpoint_id="inspections",
                           signal_type="inspection_has_unanswered_items", importance="medium", now_utc=now_utc, db_path=db_path)
        signals.append("inspection_has_unanswered_items")

    return {"projected": True, "record_key": rk, "is_safety": is_safety, "signals": signals}


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def project_inspection_section(
    raw: Mapping[str, Any], *, project_key: str, now_utc: str, db_path: Optional[Path] = None
) -> Dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    section_id = str(raw["id"])
    key = _hash("inspection_section", project_key, section_id)
    risk = _risk_category(raw.get("name"))
    with open_connection(db_path) as conn, transaction(conn):
        conn.execute(
            """
            INSERT INTO procore_inspection_sections (
              inspection_section_key, project_key, section_id, inspection_id, template_section_id,
              name_redacted, position, risk_category, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(inspection_section_key) DO UPDATE SET
              name_redacted=excluded.name_redacted, position=excluded.position,
              risk_category=excluded.risk_category, updated_at_utc=excluded.updated_at_utc
            """,
            (
                key, project_key, section_id, raw.get("inspection_id"), raw.get("template_section_id"),
                raw.get("name"), raw.get("position"), risk, raw.get("updated_at"),
            ),
        )
    return {"projected": True, "section_key": key, "risk_category": risk}


# ---------------------------------------------------------------------------
# Items (+ response sets/options + evidence rules)
# ---------------------------------------------------------------------------


def _project_response_set(response_set: Any, *, project_key: str, now_utc: str, db_path: Optional[Path]) -> Optional[str]:
    if not isinstance(response_set, dict) or response_set.get("id") in (None, ""):
        return None
    rs_id = str(response_set["id"])
    rs_key = _hash("response_set", project_key, rs_id)
    with open_connection(db_path) as conn, transaction(conn):
        conn.execute(
            """
            INSERT INTO procore_inspection_response_sets (
              response_set_key, project_key, response_set_id, name_redacted, active,
              procore_standard, created_at_utc, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(response_set_key) DO UPDATE SET
              name_redacted=excluded.name_redacted, active=excluded.active,
              procore_standard=excluded.procore_standard, updated_at_utc=excluded.updated_at_utc
            """,
            (
                rs_key, project_key, rs_id, response_set.get("name"),
                1 if response_set.get("active") else 0, 1 if response_set.get("procore_standard") else 0,
                response_set.get("created_at"), response_set.get("updated_at"),
            ),
        )
        for opt in response_set.get("responses") or []:
            if not isinstance(opt, dict) or opt.get("id") in (None, ""):
                continue
            opt_id = str(opt["id"])
            opt_key = _hash("response_option", project_key, rs_id, opt_id)
            conn.execute(
                """
                INSERT INTO procore_inspection_response_options (
                  response_option_key, project_key, response_set_id, response_option_id,
                  name_redacted, item_status_id, status_category
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(response_option_key) DO UPDATE SET
                  name_redacted=excluded.name_redacted, item_status_id=excluded.item_status_id,
                  status_category=excluded.status_category
                """,
                (
                    opt_key, project_key, rs_id, opt_id, opt.get("name"),
                    opt.get("item_status_id"), opt.get("status"),
                ),
            )
    return rs_key


def _project_evidence_rules(raw: Mapping[str, Any], *, project_key: str, item_id: str, now_utc: str, db_path: Optional[Path]) -> Dict[str, bool]:
    ec = raw.get("evidence_configuration") if isinstance(raw.get("evidence_configuration"), dict) else {}
    observation = ec.get("observation") if isinstance(ec.get("observation"), dict) else {}
    photo = ec.get("photo") if isinstance(ec.get("photo"), dict) else {}
    obs_opts = observation.get("response_option_ids") or []
    obs_status = observation.get("status_ids") or []
    photo_opts = photo.get("response_option_ids") or []
    photo_status = photo.get("status_ids") or []
    item_refs = raw.get("item_reference_ids") or []
    requires_observation = bool(obs_opts or obs_status)
    requires_photo = bool(photo_opts or photo_status)
    if not (ec or item_refs):
        return {"requires_observation": False, "requires_photo": False}
    key = _hash("evidence_rule", project_key, item_id)
    with open_connection(db_path) as conn, transaction(conn):
        conn.execute(
            """
            INSERT INTO procore_inspection_evidence_rules (
              evidence_rule_key, project_key, item_id, item_reference_ids_json,
              observation_response_option_ids_json, observation_status_ids_json,
              photo_response_option_ids_json, photo_status_ids_json,
              requires_observation, requires_photo, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(evidence_rule_key) DO UPDATE SET
              item_reference_ids_json=excluded.item_reference_ids_json,
              observation_response_option_ids_json=excluded.observation_response_option_ids_json,
              observation_status_ids_json=excluded.observation_status_ids_json,
              photo_response_option_ids_json=excluded.photo_response_option_ids_json,
              photo_status_ids_json=excluded.photo_status_ids_json,
              requires_observation=excluded.requires_observation,
              requires_photo=excluded.requires_photo, updated_at_utc=excluded.updated_at_utc
            """,
            (
                key, project_key, item_id, _json(item_refs), _json(obs_opts), _json(obs_status),
                _json(photo_opts), _json(photo_status),
                1 if requires_observation else 0, 1 if requires_photo else 0, raw.get("updated_at"),
            ),
        )
    return {"requires_observation": requires_observation, "requires_photo": requires_photo}


def project_inspection_item(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str] = None,
    now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    item_id = str(raw["id"])
    list_id = raw.get("list_id")
    section_id = raw.get("section_id")
    key = _hash("inspection_item", project_key, item_id)
    item_rk = _record_key(project_key, "inspection-items", str(list_id) if list_id is not None else None, item_id)

    interp = _interpret_response(raw.get("responded_with"), raw.get("response_set"))
    rs_key = _project_response_set(raw.get("response_set"), project_key=project_key, now_utc=now_utc, db_path=db_path)
    evidence = _project_evidence_rules(raw, project_key=project_key, item_id=item_id, now_utc=now_utc, db_path=db_path)

    with open_connection(db_path) as conn, transaction(conn):
        conn.execute(
            """
            INSERT INTO procore_inspection_items (
              inspection_item_key, project_key, item_id, inspection_id, list_id, section_id,
              template_item_id, parent_item_id, item_number, item_name_redacted, status,
              responded_with, response_id, response_name, response_status, is_unanswered,
              is_deficient, is_conforming, is_not_applicable, position, relative_position,
              updated_at_utc, last_sync_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(inspection_item_key) DO UPDATE SET
              section_id=excluded.section_id, item_number=excluded.item_number,
              item_name_redacted=excluded.item_name_redacted, status=excluded.status,
              responded_with=excluded.responded_with, response_id=excluded.response_id,
              response_name=excluded.response_name, response_status=excluded.response_status,
              is_unanswered=excluded.is_unanswered, is_deficient=excluded.is_deficient,
              is_conforming=excluded.is_conforming, is_not_applicable=excluded.is_not_applicable,
              position=excluded.position, relative_position=excluded.relative_position,
              updated_at_utc=excluded.updated_at_utc, last_sync_run_id=excluded.last_sync_run_id
            """,
            (
                key, project_key, item_id, str(list_id) if list_id is not None else None,
                str(list_id) if list_id is not None else None,
                str(section_id) if section_id is not None else None,
                raw.get("template_item_id"), raw.get("parent_item_id"), raw.get("number"),
                raw.get("name"), raw.get("status"), interp["response_name"], interp["response_id"],
                interp["response_name"], interp["response_status"],
                1 if interp["is_unanswered"] else 0, 1 if interp["is_deficient"] else 0,
                1 if interp["is_conforming"] else 0, 1 if interp["is_not_applicable"] else 0,
                raw.get("position"), raw.get("relative_position"), raw.get("updated_at"), sync_run_id,
            ),
        )

    # edges
    if list_id is not None:
        inspection_rk = _record_key(project_key, "inspections", None, list_id)
        emit_record_edge(project_key=project_key, from_record_key=inspection_rk, to_record_key=item_rk,
                         edge_type="has_item", source_endpoint_id="inspection-items", now_utc=now_utc, db_path=db_path)
    if section_id is not None:
        section_rk = _record_key(project_key, "inspection-sections", None, section_id)
        emit_record_edge(project_key=project_key, from_record_key=section_rk, to_record_key=item_rk,
                         edge_type="section_has_item", source_endpoint_id="inspection-items", now_utc=now_utc, db_path=db_path)
    if rs_key is not None:
        emit_record_edge(project_key=project_key, from_record_key=item_rk, to_entity_key=rs_key,
                         edge_type="uses_response_set", source_endpoint_id="inspection-items", now_utc=now_utc, db_path=db_path)

    # action signals
    signals: List[str] = []

    def _sig(signal_type: str, importance: str) -> None:
        emit_action_signal(project_key=project_key, record_key=item_rk, endpoint_id="inspection-items",
                           signal_type=signal_type, importance=importance, now_utc=now_utc, db_path=db_path)
        signals.append(signal_type)

    if interp["is_unanswered"]:
        _sig("inspection_item_unanswered", "medium")
    if interp["is_deficient"]:
        _sig("inspection_item_non_conforming", "high")
    if interp["is_deficient"] or str(interp["response_name"] or "").strip().lower() == "fail":
        _sig("inspection_item_failed", "high")
    if evidence["requires_photo"]:
        _sig("inspection_item_requires_photo_evidence", "medium")
    if evidence["requires_observation"]:
        _sig("inspection_item_requires_observation", "medium")

    return {"projected": True, "record_key": item_rk, "interpretation": interp, "signals": signals}


def project_inspection(
    endpoint_id: str, raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str] = None,
    now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Dispatch a raw inspection-family payload to its projection."""
    if endpoint_id == "inspections":
        return project_inspection_record(raw, project_key=project_key, sync_run_id=sync_run_id, now_utc=now_utc, db_path=db_path)
    if endpoint_id == "inspection-sections":
        return project_inspection_section(raw, project_key=project_key, now_utc=now_utc, db_path=db_path)
    if endpoint_id == "inspection-items":
        return project_inspection_item(raw, project_key=project_key, sync_run_id=sync_run_id, now_utc=now_utc, db_path=db_path)
    return {"projected": False}


__all__ = [
    "project_inspection",
    "project_inspection_item",
    "project_inspection_record",
    "project_inspection_section",
]
