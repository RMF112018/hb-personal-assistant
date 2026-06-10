"""Local Procore structured analytics foundation.

This module is deliberately local-only. It never calls Procore and never performs
external writeback. The raw landing table is a replay/control layer; analytics
acceptance depends on endpoint-family ``procore_raw_*`` structured bronze tables.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from hb_assistant.store.connection import get_connection, transaction

from . import endpoints as endpoint_registry

RAW_LANDING_TABLE = "procore_endpoint_raw_payloads"
SOURCE_QUALITY_LEGACY = "redacted_legacy_projection"

STRUCTURED_TABLE_BY_ENDPOINT: dict[str, str] = {
    "projects": "procore_raw_project_dimensions",
    "rfis": "procore_raw_rfis",
    "rfi-responses": "procore_raw_rfi_responses",
    "submittals": "procore_raw_submittals",
    "submittal-responses": "procore_raw_submittal_responses",
    "submittal-packages": "procore_raw_submittal_packages",
    "observations": "procore_raw_observations",
    "punch-items": "procore_raw_punch_items",
    "meetings": "procore_raw_meetings",
    "meeting-detail": "procore_raw_meeting_details",
    "meeting-topics": "procore_raw_meeting_topics",
    "daily-log-weather": "procore_raw_daily_logs",
    "daily-log-manpower": "procore_raw_daily_logs",
    "daily-log-notes": "procore_raw_daily_logs",
    "daily-log-deliveries": "procore_raw_daily_logs",
    "daily-log-delays-review-routed": "procore_raw_daily_logs",
    "daily-log-inspections": "procore_raw_daily_logs",
    "daily-log-dcrs": "procore_raw_daily_logs",
    "daily-log-accident-review-routed": "procore_raw_daily_logs",
    "daily-log-dumpster": "procore_raw_daily_logs",
    "daily-log-safety-violation-review-routed": "procore_raw_daily_logs",
    "daily-log-visitor": "procore_raw_daily_logs",
    "inspections": "procore_raw_inspections",
    "inspection-sections": "procore_raw_inspection_sections",
    "inspection-items": "procore_raw_inspection_items",
    "schedules": "procore_raw_schedules",
    "activities": "procore_raw_schedule_activities",
    "prime-contracts": "procore_raw_contracts",
    "prime-contract-line-items": "procore_raw_contract_line_items",
    "prime-change-orders": "procore_raw_change_orders",
    "prime-change-order-line-items": "procore_raw_change_order_line_items",
    "payment-applications": "procore_raw_payment_applications",
    "commitment-contracts": "procore_raw_contracts",
    "commitment-line-items": "procore_raw_contract_line_items",
    "commitment-change-orders": "procore_raw_change_orders",
    "commitment-change-order-line-items": "procore_raw_change_order_line_items",
    "purchase-order-contracts": "procore_raw_contracts",
    "purchase-order-line-items": "procore_raw_contract_line_items",
    "purchase-order-detail-line-items": "procore_raw_contract_line_items",
    "billing-periods": "procore_raw_billing_periods",
    "subcontractor-invoices": "procore_raw_invoices",
    "subcontractor-invoice-contract-items": "procore_raw_invoice_items",
    "subcontractor-invoice-contract-detail-items": "procore_raw_invoice_items",
    "subcontractor-invoice-change-order-items": "procore_raw_invoice_items",
    "rfqs": "procore_raw_rfqs",
    "rfq-responses": "procore_raw_rfq_responses",
    "rfq-quotes": "procore_raw_rfq_responses",
    "change-events": "procore_raw_change_events",
    "change-event-comments": "procore_raw_change_event_comments",
    "budget-views": "procore_raw_budget_views",
    "budget-detail-columns": "procore_raw_budget_columns",
    "budget-detail-rows": "procore_raw_budget_rows",
    "budget-change-history": "procore_raw_budget_changes",
    "budget-change-line-items": "procore_raw_budget_change_line_items",
    "budget-modifications": "procore_raw_budget_modifications",
    "prime-contract-attachments": "procore_raw_attachments",
    "commitment-attachments": "procore_raw_attachments",
    "commitment-compliance": "procore_raw_status_dimensions",
}

DIMENSION_TABLES = {
    "procore_raw_project_dimensions",
    "procore_raw_company_dimensions",
    "procore_raw_person_dimensions",
    "procore_raw_cost_code_dimensions",
    "procore_raw_location_dimensions",
    "procore_raw_status_dimensions",
    "procore_raw_date_dimensions",
}

STRUCTURED_TABLES = frozenset(set(STRUCTURED_TABLE_BY_ENDPOINT.values()) | DIMENSION_TABLES)

SECRET_KEY_RE = re.compile(
    r"(access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization|bearer|password|api[_-]?key|signed[_-]?url)",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)


@dataclass(frozen=True)
class BackfillReceipt:
    mode: str
    inspected: int
    raw_landing_written: int
    structured_written: int
    skipped: int
    source_quality: str
    live_procore_calls: int = 0
    external_writeback_performed: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "inspected": self.inspected,
            "raw_landing_written": self.raw_landing_written,
            "structured_written": self.structured_written,
            "skipped": self.skipped,
            "source_quality": self.source_quality,
            "live_procore_calls": self.live_procore_calls,
            "external_writeback_performed": self.external_writeback_performed,
        }


def _hash(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8", "replace")).hexdigest()


def _hash12(value: Any) -> str:
    return _hash(value)[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_ref_hash(*parts: Any) -> str:
    return _hash("|".join(str(part or "") for part in parts))


def request_fingerprint_hash(endpoint_id: str, project_key: str | None, parent_id: str | None) -> str:
    return _hash(f"{endpoint_id}|{project_key or ''}|{parent_id or ''}")


def raw_payload_id_for(
    endpoint_id: str, project_key: str | None, record_id: str, parent_id: str | None, payload_hash: str
) -> str:
    key = "|".join((endpoint_id, project_key or "", parent_id or "", record_id, payload_hash))
    return f"perp-{_hash(key)[:32]}"


def structured_record_key(
    endpoint_id: str, project_key: str | None, record_id: str, parent_id: str | None
) -> str:
    key = "|".join((endpoint_id, project_key or "", parent_id or "", record_id))
    return f"psa-{_hash(key)[:32]}"


def _safe_json_loads(payload_json: str | None) -> Any:
    if not payload_json:
        return {}
    try:
        return json.loads(payload_json)
    except json.JSONDecodeError:
        return {"_unparsed_payload_hash": _hash12(payload_json), "_unparsed_payload_length": len(payload_json)}


def _scrub_value(key: str, value: Any) -> Any:
    if SECRET_KEY_RE.search(key):
        return "[scrubbed]"
    if isinstance(value, str):
        if SECRET_KEY_RE.search(value):
            return "[scrubbed]"
        return URL_RE.sub("[url_scrubbed]", value)
    if isinstance(value, list):
        return [_scrub_value(key, item) for item in value]
    if isinstance(value, dict):
        return scrub_payload(value)
    return value


def scrub_payload(payload: Any) -> Any:
    """Scrub transport/security artifacts without reducing business fields to hashes."""
    if isinstance(payload, list):
        return [scrub_payload(item) for item in payload]
    if not isinstance(payload, dict):
        return payload
    scrubbed: dict[str, Any] = {}
    for key, value in payload.items():
        key_text = str(key)
        safe_key = f"scrubbed_security_field_{_hash12(key_text)}" if SECRET_KEY_RE.search(key_text) else key_text
        scrubbed[safe_key] = _scrub_value(key_text, value)
    return scrubbed


def scrubbed_payload_json(payload_json: str | None) -> str:
    payload = _safe_json_loads(payload_json)
    return json.dumps(scrub_payload(payload), sort_keys=True, separators=(",", ":"))


def payload_has_forbidden_security_artifact(payload_json: str) -> bool:
    return bool(SECRET_KEY_RE.search(payload_json) or re.search(r"https?://[^\s\"']+\\?", payload_json))


def contract_inventory() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    missing_structured = []
    explicit_deferred = []
    for ep in endpoint_registry.list_all():
        table = STRUCTURED_TABLE_BY_ENDPOINT.get(ep.endpoint_id)
        defer_reason = None if table else "unresolved_or_held_endpoint_deferred_from_analytics"
        row = {
            "endpoint_id": ep.endpoint_id,
            "family": ep.family,
            "live_verified": ep.live_verified,
            "raw_landing_target": RAW_LANDING_TABLE,
            "structured_table": table,
            "analytics_eligible": bool(table and ep.live_verified),
            "daily_brief_eligible": bool(table and ep.family not in {"foundation"}),
            "source_ref_supported": bool(table),
            "idempotency_supported": bool(table and ep.record_id_field),
            "defer_reason": defer_reason,
            "response_envelope": ep.response_envelope,
            "record_id_field": ep.record_id_field,
            "parent_record_id_field": ep.parent_record_id_field,
            "sensitivity": ep.sensitivity,
            "no_writeback_posture": "local_read_only",
        }
        if table is None and ep.live_verified:
            missing_structured.append(ep.endpoint_id)
        elif table is None:
            explicit_deferred.append(ep.endpoint_id)
        rows.append(row)
    return {
        "command": "hb-assistant procore analytics contract",
        "endpoint_count": len(rows),
        "raw_landing_table": RAW_LANDING_TABLE,
        "structured_table_count": len(STRUCTURED_TABLES),
        "missing_structured_endpoint_count": len(missing_structured),
        "missing_structured_endpoints": missing_structured,
        "explicit_deferred_endpoint_count": len(explicit_deferred),
        "explicit_deferred_endpoints": explicit_deferred,
        "raw_json_only_is_sufficient": False,
        "acceptance_gate": "structured_endpoint_family_tables_required",
        "rows": rows,
        "guardrails": {
            "live_calls_disabled": True,
            "writeback": "none",
            "raw_json_only_is_sufficient": False,
        },
    }


def _row_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _record_number(payload: dict[str, Any], row: sqlite3.Row) -> str | None:
    return _row_value(payload, "number", "rfi_number", "submittal_number", "name") or row[
        "procore_record_number"
    ]


def _business_date(payload: dict[str, Any]) -> str | None:
    return _row_value(
        payload,
        "date",
        "due_date",
        "required_on",
        "start_date",
        "finish_date",
        "created_at",
        "updated_at",
    )


def _amount(payload: dict[str, Any]) -> str | None:
    value = _row_value(
        payload,
        "amount",
        "total",
        "total_amount",
        "contract_amount",
        "revised_budget",
        "original_budget_amount",
        "current_budget_amount",
    )
    return None if value is None else str(value)


def _normalized_payload(row: sqlite3.Row) -> tuple[dict[str, Any], str, str]:
    scrubbed = scrubbed_payload_json(row["canonical_json_redacted"])
    payload_hash = _hash(scrubbed)
    payload = _safe_json_loads(scrubbed)
    if not isinstance(payload, dict):
        payload = {"payload_array_length": len(payload) if isinstance(payload, list) else None}
    return payload, scrubbed, payload_hash


def _structured_values(
    row: sqlite3.Row,
    *,
    raw_payload_id: str,
    source_hash: str,
    payload_hash: str,
    now_utc: str,
) -> dict[str, Any]:
    payload, _, _ = _normalized_payload(row)
    endpoint_id = row["endpoint_id"]
    adapter = endpoint_registry.get(endpoint_id)
    family = adapter.family if adapter else endpoint_id
    project_key = row["project_key"]
    record_id = str(row["procore_record_id"])
    parent_id = row["parent_procore_id"] or None
    return {
        "record_key": structured_record_key(endpoint_id, project_key, record_id, parent_id),
        "raw_payload_id": raw_payload_id,
        "source_ref_hash": source_hash,
        "endpoint_key": endpoint_id,
        "endpoint_family": family,
        "company_id": None,
        "company_id_hash": None,
        "project_id": row["procore_project_id"],
        "project_id_hash": _hash(row["procore_project_id"]),
        "project_key": project_key,
        "record_id": record_id,
        "record_id_hash": _hash(record_id),
        "parent_record_id": parent_id,
        "parent_record_id_hash": _hash(parent_id) if parent_id else None,
        "record_number": _record_number(payload, row),
        "title_redacted": row["title_redacted"],
        "status": row["status"],
        "current_state": row["status"],
        "owner_name": _row_value(payload, "owner", "manager", "created_by", "responsible_contractor"),
        "assignee_name": _row_value(payload, "assignee", "assigned_to", "ball_in_court"),
        "responsible_party_name": _row_value(payload, "responsible_party", "responsible_contractor"),
        "due_at_utc": _row_value(payload, "due_date", "required_on", "required_date"),
        "start_at_utc": _row_value(payload, "start_date", "start_at"),
        "finish_at_utc": _row_value(payload, "finish_date", "end_date", "completed_at"),
        "business_date": _business_date(payload),
        "cost_code": _row_value(payload, "cost_code", "cost_code_id", "wbs_code"),
        "cost_type": _row_value(payload, "cost_type", "cost_type_id"),
        "amount": _amount(payload),
        "currency": _row_value(payload, "currency", "currency_code"),
        "quantity": _row_value(payload, "quantity", "qty"),
        "unit_of_measure": _row_value(payload, "unit_of_measure", "uom"),
        "source_updated_at_utc": row["updated_at_utc"],
        "payload_captured_at_utc": row["last_seen_at_utc"],
        "payload_seen_first_utc": row["first_seen_at_utc"],
        "payload_seen_last_utc": row["last_seen_at_utc"],
        "payload_hash": payload_hash,
        "raw_payload_linked": 1,
        "is_current": 1,
        "source_quality": SOURCE_QUALITY_LEGACY,
        "analytics_eligible": 1,
        "daily_brief_eligible": 1 if family not in {"foundation"} else 0,
        "security_scrub_status": "scrubbed",
        "retention_class": "local_analytics",
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }


def _insert_raw_payload(conn: sqlite3.Connection, row: sqlite3.Row, now_utc: str) -> str:
    payload, scrubbed, payload_hash = _normalized_payload(row)
    endpoint_id = row["endpoint_id"]
    adapter = endpoint_registry.get(endpoint_id)
    family = adapter.family if adapter else endpoint_id
    project_key = row["project_key"]
    record_id = str(row["procore_record_id"])
    parent_id = row["parent_procore_id"] or None
    raw_payload_id = raw_payload_id_for(endpoint_id, project_key, record_id, parent_id, payload_hash)
    source_hash = source_ref_hash("procore_live_records", project_key, endpoint_id, parent_id, record_id)
    request_hash = request_fingerprint_hash(endpoint_id, project_key, parent_id)
    conn.execute(
        """
        INSERT INTO procore_endpoint_raw_payloads (
          raw_payload_id, capture_run_id, endpoint_key, endpoint_family, endpoint_version,
          company_id, company_id_hash, project_id, project_id_hash, project_key,
          record_type, record_id, record_id_hash, parent_record_id, parent_record_id_hash,
          source_ref_hash, request_fingerprint_hash, payload_hash, payload_json,
          payload_size_bytes, payload_captured_at_utc, payload_seen_first_utc,
          payload_seen_last_utc, is_current, redaction_status, security_scrub_status,
          contains_personal_data, contains_signed_url, contains_secret_like_value,
          retention_class, analytics_eligible, source_quality,
          raw_procore_payload_persisted, external_writeback_performed,
          created_utc, updated_utc
        ) VALUES (
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1,
          'redacted_legacy_projection', 'scrubbed', ?, 0, 0, 'local_analytics', 1, ?,
          0, 0, ?, ?
        )
        ON CONFLICT(raw_payload_id) DO UPDATE SET
          payload_seen_last_utc=excluded.payload_seen_last_utc,
          is_current=1,
          updated_utc=excluded.updated_utc
        """,
        (
            raw_payload_id,
            f"legacy-backfill-{now_utc[:10]}",
            endpoint_id,
            family,
            "legacy_v1",
            None,
            None,
            row["procore_project_id"],
            _hash(row["procore_project_id"]),
            project_key,
            endpoint_id,
            record_id,
            _hash(record_id),
            parent_id,
            _hash(parent_id) if parent_id else None,
            source_hash,
            request_hash,
            payload_hash,
            scrubbed,
            len(scrubbed.encode("utf-8")),
            row["last_seen_at_utc"],
            row["first_seen_at_utc"],
            row["last_seen_at_utc"],
            1 if row["review_required"] else 0,
            SOURCE_QUALITY_LEGACY,
            now_utc,
            now_utc,
        ),
    )
    return raw_payload_id


def _insert_structured(conn: sqlite3.Connection, table: str, values: dict[str, Any]) -> None:
    cols = list(values.keys())
    placeholders = ", ".join("?" for _ in cols)
    assignments = ", ".join(
        f"{col}=excluded.{col}" for col in cols if col not in {"record_key", "created_utc"}
    )
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(record_key) DO UPDATE SET {assignments}"
    )
    conn.execute(sql, tuple(values[col] for col in cols))


def _insert_dimensions(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    now_utc = values["updated_utc"]
    if values.get("project_key"):
        conn.execute(
            """
            INSERT INTO procore_raw_project_dimensions (
              record_key, raw_payload_id, source_ref_hash, endpoint_key, endpoint_family,
              project_id, project_id_hash, project_key, record_id, record_id_hash,
              title_redacted, status,
              payload_hash, source_quality, analytics_eligible, security_scrub_status,
              retention_class, created_utc, updated_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'scrubbed', 'local_analytics', ?, ?)
            ON CONFLICT(record_key) DO UPDATE SET updated_utc=excluded.updated_utc
            """,
            (
                f"procore-project-{_hash(values['project_key'])[:24]}",
                values["raw_payload_id"],
                values["source_ref_hash"],
                values["endpoint_key"],
                values["endpoint_family"],
                values["project_id"],
                values["project_id_hash"],
                values["project_key"],
                values["project_key"],
                _hash(values["project_key"]),
                values.get("project_key"),
                "active",
                values["payload_hash"],
                values["source_quality"],
                now_utc,
                now_utc,
            ),
        )
    if values.get("cost_code"):
        conn.execute(
            """
            INSERT INTO procore_raw_cost_code_dimensions (
              record_key, raw_payload_id, source_ref_hash, endpoint_key, endpoint_family,
              project_key, record_id, record_id_hash, title_redacted, status,
              payload_hash, source_quality, analytics_eligible, security_scrub_status,
              retention_class, created_utc, updated_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'scrubbed', 'local_analytics', ?, ?)
            ON CONFLICT(record_key) DO UPDATE SET updated_utc=excluded.updated_utc
            """,
            (
                f"procore-cost-code-{_hash(str(values['project_key']) + '|' + str(values['cost_code']))[:24]}",
                values["raw_payload_id"],
                values["source_ref_hash"],
                values["endpoint_key"],
                values["endpoint_family"],
                values["project_key"],
                values["cost_code"],
                _hash(values["cost_code"]),
                values["cost_code"],
                "active",
                values["payload_hash"],
                values["source_quality"],
                now_utc,
                now_utc,
            ),
        )
    if values.get("business_date"):
        conn.execute(
            """
            INSERT INTO procore_raw_date_dimensions (
              record_key, raw_payload_id, source_ref_hash, endpoint_key, endpoint_family,
              project_key, record_id, record_id_hash, business_date, title_redacted,
              status, payload_hash, source_quality, analytics_eligible,
              security_scrub_status, retention_class, created_utc, updated_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'scrubbed', 'local_analytics', ?, ?)
            ON CONFLICT(record_key) DO UPDATE SET updated_utc=excluded.updated_utc
            """,
            (
                f"procore-date-{_hash(str(values['project_key']) + '|' + str(values['business_date']))[:24]}",
                values["raw_payload_id"],
                values["source_ref_hash"],
                values["endpoint_key"],
                values["endpoint_family"],
                values["project_key"],
                values["business_date"],
                _hash(values["business_date"]),
                values["business_date"],
                values["business_date"],
                "active",
                values["payload_hash"],
                values["source_quality"],
                now_utc,
                now_utc,
            ),
        )


def _eligible_live_rows(
    conn: sqlite3.Connection,
    *,
    project_key: str | None,
    family: str | None,
    endpoint: str | None,
    limit: int,
) -> list[sqlite3.Row]:
    clauses = []
    params: list[Any] = []
    if project_key:
        clauses.append("project_key = ?")
        params.append(project_key)
    if endpoint:
        clauses.append("endpoint_id = ?")
        params.append(endpoint)
    elif family:
        endpoint_ids = [
            ep.endpoint_id for ep in endpoint_registry.list_all() if ep.family == family and ep.endpoint_id in STRUCTURED_TABLE_BY_ENDPOINT
        ]
        if not endpoint_ids:
            return []
        clauses.append(f"endpoint_id IN ({', '.join('?' for _ in endpoint_ids)})")
        params.extend(endpoint_ids)
    else:
        endpoint_ids = sorted(STRUCTURED_TABLE_BY_ENDPOINT)
        clauses.append(f"endpoint_id IN ({', '.join('?' for _ in endpoint_ids)})")
        params.extend(endpoint_ids)
    sql = "SELECT * FROM procore_live_records"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY project_key, endpoint_id, parent_procore_id, procore_record_id LIMIT ?"
    params.append(limit)
    return list(conn.execute(sql, tuple(params)))


def backfill_from_live_records(
    *,
    db_path: str | Path | None = None,
    apply: bool = False,
    project_key: str | None = None,
    family: str | None = None,
    endpoint: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Backfill raw landing and structured bronze from local legacy live records.

    ``apply=False`` is a dry-run and writes nothing. The source quality is always
    labelled honestly because ``canonical_json_redacted`` is a legacy redacted
    projection, not a complete raw Procore payload.
    """
    conn = get_connection(Path(db_path) if db_path is not None else None)
    rows = _eligible_live_rows(
        conn, project_key=project_key, family=family, endpoint=endpoint, limit=limit
    )
    inspected = len(rows)
    skipped = 0
    structured_targets = CounterLike()
    if not apply:
        for row in rows:
            table = STRUCTURED_TABLE_BY_ENDPOINT.get(row["endpoint_id"])
            if table:
                structured_targets.add(table)
            else:
                skipped += 1
        return {
            **BackfillReceipt(
                mode="dry_run",
                inspected=inspected,
                raw_landing_written=0,
                structured_written=0,
                skipped=skipped,
                source_quality=SOURCE_QUALITY_LEGACY,
            ).as_dict(),
            "would_write_raw_landing": inspected - skipped,
            "would_write_structured": inspected - skipped,
            "structured_targets": structured_targets.as_dict(),
            "filters": {"project_key": project_key, "family": family, "endpoint": endpoint, "limit": limit},
        }
    raw_written = 0
    structured_written = 0
    now_utc = _now()
    with transaction(conn):
        for row in rows:
            table = STRUCTURED_TABLE_BY_ENDPOINT.get(row["endpoint_id"])
            if table is None:
                skipped += 1
                continue
            raw_payload_id = _insert_raw_payload(conn, row, now_utc)
            raw_written += 1
            payload, _, payload_hash = _normalized_payload(row)
            source_hash = source_ref_hash(
                "procore_live_records",
                row["project_key"],
                row["endpoint_id"],
                row["parent_procore_id"],
                row["procore_record_id"],
            )
            values = _structured_values(
                row,
                raw_payload_id=raw_payload_id,
                source_hash=source_hash,
                payload_hash=payload_hash,
                now_utc=now_utc,
            )
            _insert_structured(conn, table, values)
            _insert_dimensions(conn, values)
            structured_targets.add(table)
            structured_written += 1
    return {
        **BackfillReceipt(
            mode="apply",
            inspected=inspected,
            raw_landing_written=raw_written,
            structured_written=structured_written,
            skipped=skipped,
            source_quality=SOURCE_QUALITY_LEGACY,
        ).as_dict(),
        "structured_targets": structured_targets.as_dict(),
        "filters": {"project_key": project_key, "family": family, "endpoint": endpoint, "limit": limit},
    }


class CounterLike:
    def __init__(self) -> None:
        self._items: dict[str, int] = {}

    def add(self, key: str) -> None:
        self._items[key] = self._items.get(key, 0) + 1

    def as_dict(self) -> dict[str, int]:
        return dict(sorted(self._items.items()))


def _table_count(conn: sqlite3.Connection, table: str, where: str = "", params: tuple[Any, ...] = ()) -> int:
    try:
        sql = f"SELECT COUNT(*) FROM {table}"
        if where:
            sql += f" WHERE {where}"
        return int(conn.execute(sql, params).fetchone()[0])
    except sqlite3.Error:
        return 0


def structured_coverage(
    *, db_path: str | Path | None = None, project_key: str | None = None, family: str | None = None
) -> dict[str, Any]:
    conn = get_connection(Path(db_path) if db_path is not None else None)
    rows: list[dict[str, Any]] = []
    total_live = total_raw = total_structured = 0
    for ep in endpoint_registry.list_all():
        if family and ep.family != family:
            continue
        table = STRUCTURED_TABLE_BY_ENDPOINT.get(ep.endpoint_id)
        params: list[Any] = [ep.endpoint_id]
        live_where = "endpoint_id = ?"
        if project_key:
            live_where += " AND project_key = ?"
            params.append(project_key)
        live_count = _table_count(conn, "procore_live_records", live_where, tuple(params))
        raw_count = _table_count(conn, RAW_LANDING_TABLE, live_where.replace("endpoint_id", "endpoint_key"), tuple(params))
        structured_count = 0
        current_count = 0
        if table:
            sparams: list[Any] = [ep.endpoint_id]
            structured_where = "endpoint_key = ?"
            if project_key:
                structured_where += " AND project_key = ?"
                sparams.append(project_key)
            structured_count = _table_count(conn, table, structured_where, tuple(sparams))
            current_count = _table_count(conn, table, structured_where + " AND is_current = 1", tuple(sparams))
        gap = None
        if table is None:
            gap = "missing_structured_table_mapping"
        elif live_count and structured_count == 0:
            gap = "not_reprocessed"
        elif raw_count == 0 and structured_count:
            gap = "structured_without_raw_landing"
        elif raw_count and structured_count < raw_count:
            gap = "partial_structured_coverage"
        rows.append(
            {
                "endpoint_id": ep.endpoint_id,
                "family": ep.family,
                "live_verified": ep.live_verified,
                "raw_landing_table": RAW_LANDING_TABLE,
                "structured_table": table,
                "live_record_rows": live_count,
                "raw_landing_rows": raw_count,
                "structured_rows": structured_count,
                "current_structured_rows": current_count,
                "analytics_eligible": bool(table and ep.live_verified),
                "daily_brief_eligible": bool(table and ep.family != "foundation"),
                "coverage_gap_reason": gap,
                "source_quality": SOURCE_QUALITY_LEGACY if raw_count or structured_count else None,
            }
        )
        total_live += live_count
        total_raw += raw_count
        total_structured += structured_count
    return {
        "command": "hb-assistant procore analytics coverage",
        "project_key": project_key,
        "family": family,
        "endpoint_count": len(rows),
        "total_live_record_rows": total_live,
        "total_raw_landing_rows": total_raw,
        "total_structured_rows": total_structured,
        "structured_acceptance_gate": total_structured > 0 and any(r["structured_table"] for r in rows),
        "raw_json_only_is_sufficient": False,
        "rows": rows,
        "guardrails": {"live_calls_disabled": True, "writeback": "none"},
    }


def structured_counts(
    *, db_path: str | Path | None = None, project_key: str | None = None
) -> dict[str, Any]:
    conn = get_connection(Path(db_path) if db_path is not None else None)
    rows = []
    for table in sorted(STRUCTURED_TABLES):
        where = ""
        params: tuple[Any, ...] = ()
        if project_key and _table_has_column(conn, table, "project_key"):
            where = "project_key = ?"
            params = (project_key,)
        rows.append({"table": table, "rows": _table_count(conn, table, where, params)})
    return {
        "command": "hb-assistant procore analytics structured-counts",
        "project_key": project_key,
        "structured_table_count": len(rows),
        "rows": rows,
        "guardrails": {"live_calls_disabled": True, "writeback": "none"},
    }


def _table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    try:
        return column in {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return False


def ranking_diagnostics(
    *, db_path: str | Path | None = None, brief_date: str | None = None
) -> dict[str, Any]:
    conn = get_connection(Path(db_path) if db_path is not None else None)
    open_count = _table_count(conn, "procore_action_signals", "signal_status = 'open'")
    due_soon = 0
    if brief_date:
        due_soon = _table_count(
            conn,
            "procore_action_signals",
            "signal_status = 'open' AND date(due_at_utc) BETWEEN date(?) AND date(?, '+2 day')",
            (brief_date, brief_date),
        )
    aggregate_sludge = _table_count(
        conn,
        "procore_action_signals",
        """
        signal_status='open'
        AND (due_at_utc IS NULL OR due_at_utc='')
        AND (owner_entity_key IS NULL OR owner_entity_key='')
        AND signal_type IN (
          SELECT signal_type FROM procore_action_signals
          WHERE signal_status='open'
          GROUP BY signal_type HAVING COUNT(*) >= 50
        )
        """,
    )
    closed_as_open = _table_count(
        conn,
        "procore_action_signals",
        "signal_status='open' AND lower(signal_type) LIKE '%closed%'",
    )
    return {
        "command": "hb-assistant procore analytics ranking-diagnostics",
        "brief_date": brief_date,
        "open_signal_count": open_count,
        "due_soon_count": due_soon,
        "aggregate_sludge_count": aggregate_sludge,
        "closed_record_open_signal_count": closed_as_open,
        "daily_brief_projection_rule": "suppress_aggregate_sludge_unless_specific_due_recent_owner_materiality_or_safety_evidence",
        "guardrails": {"live_calls_disabled": True, "writeback": "none"},
    }


def no_raw_leak_scan(paths: Iterable[str | Path]) -> dict[str, Any]:
    patterns = [
        "Bear" + "er" + r"\s+[A-Za-z0-9._-]+",
        "access_" + "token",
        "refresh_" + "token",
        "client_" + "secret",
        "X-Amz-" + "Signature",
        r"https?://api\.procore\.com/[^\s)]+\\?",
        "<ht" + "ml",
    ]
    findings = []
    for pathish in paths:
        path = Path(pathish)
        if path.is_dir():
            candidates = [p for p in path.rglob("*") if p.is_file()]
        elif path.exists():
            candidates = [path]
        else:
            candidates = []
        for file in candidates:
            if file.suffix.lower() in {".sqlite", ".db", ".wal", ".shm"}:
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    findings.append({"path": str(file), "pattern": pattern})
    return {
        "command": "hb-assistant procore analytics no-raw-leak-scan",
        "ok": not findings,
        "unsafe_finding_count": len(findings),
        "findings": findings,
        "guardrails": {"live_calls_disabled": True, "writeback": "none"},
    }


def coverage_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Procore Structured Analytics Coverage",
        "",
        f"- Total live record rows: `{payload['total_live_record_rows']}`",
        f"- Total raw landing rows: `{payload['total_raw_landing_rows']}`",
        f"- Total structured rows: `{payload['total_structured_rows']}`",
        f"- Structured acceptance gate: `{payload['structured_acceptance_gate']}`",
        "",
        "| endpoint | family | raw landing | structured table | structured rows | gap |",
        "|---|---|---:|---|---:|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {endpoint_id} | {family} | {raw_landing_rows} | {structured_table} | {structured_rows} | {coverage_gap_reason} |".format(
                **{**row, "structured_table": row.get("structured_table") or "", "coverage_gap_reason": row.get("coverage_gap_reason") or ""}
            )
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "RAW_LANDING_TABLE",
    "SOURCE_QUALITY_LEGACY",
    "STRUCTURED_TABLES",
    "STRUCTURED_TABLE_BY_ENDPOINT",
    "backfill_from_live_records",
    "contract_inventory",
    "coverage_markdown",
    "no_raw_leak_scan",
    "payload_has_forbidden_security_artifact",
    "ranking_diagnostics",
    "scrub_payload",
    "structured_counts",
    "structured_coverage",
]
