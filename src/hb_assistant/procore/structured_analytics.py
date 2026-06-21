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

from hb_assistant.store.connection import get_connection, open_connection, transaction

from . import endpoints as endpoint_registry

RAW_LANDING_TABLE = "procore_endpoint_raw_payloads"
SOURCE_QUALITY_LEGACY = "redacted_legacy_projection"
SOURCE_QUALITY_LIVE_FULL = "live_full_payload"
SOURCE_QUALITY_FIXTURE_FULL = "fixture_full_payload"

# Deterministic source-quality precedence. Higher rank wins; equal rank is an
# idempotent upsert; a lower rank must never overwrite/downgrade a higher rank.
# Full live/fixture endpoint payloads (the private-DB system of record) outrank the
# redacted legacy projection replayed from ``procore_live_records``.
SOURCE_QUALITY_RANK: dict[str, int] = {
    SOURCE_QUALITY_LIVE_FULL: 100,
    SOURCE_QUALITY_FIXTURE_FULL: 90,
    SOURCE_QUALITY_LEGACY: 10,
}


def _rank(source_quality: str | None) -> int:
    return SOURCE_QUALITY_RANK.get(source_quality or "", 0)

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


# --- Full-payload (private DB) transport-secret scrubbing -------------------------
#
# The private local SQLite DB is the system of record and must preserve full Procore
# business payloads (people, companies, financials, nested objects, attachment
# metadata, custom fields). Only auth/transport SECRETS are removed before storage.
# This is intentionally narrower than ``scrub_payload`` (used for the legacy/outbound
# path), which also collapses business URLs and rewrites secret-like keys.

# Keys whose VALUES are credentials, not business data. Matched by ``search`` so
# nested keys like ``access_token`` / ``refresh_token`` are caught. Scoped to terms
# that are unambiguously credentials in the Procore domain (never "credentials",
# "secretary", "client_name", which are legitimate business fields).
AUTH_SECRET_KEY_RE = re.compile(
    r"(authorization|bearer[_-]?token|^bearer$|access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|client[_-]?secret|app[_-]?secret|api[_-]?key|x[_-]?api[_-]?key|"
    r"password|passwd|private[_-]?key)",
    re.IGNORECASE,
)

# Query-string parameter names that carry signed-URL credentials. Stripped from URL
# values while the scheme/host/path and benign params (page, per_page, …) are kept.
_CREDENTIAL_QUERY_PARAM_NAMES = frozenset(
    {
        "x-amz-signature",
        "x-amz-credential",
        "x-amz-security-token",
        "x-amz-date",
        "x-amz-expires",
        "x-amz-signedheaders",
        "x-amz-algorithm",
        "sharedaccesssignature",
        "sig",
        "signature",
        "token",
        "access_token",
        "api_key",
        "apikey",
        "key",
    }
)

# Post-scrub assertion: detects any transport secret that survived scrubbing. Narrower
# than ``payload_has_forbidden_security_artifact`` (which flags ALL https URLs and so
# cannot gate a full business payload that legitimately carries attachment URLs).
_TRANSPORT_SECRET_TEXT_RE = re.compile(
    r"(bearer\s+[A-Za-z0-9._\-]{8,}|access[_-]?token|refresh[_-]?token|client[_-]?secret|"
    r"app[_-]?secret|api[_-]?key|x[_-]?api[_-]?key|X-Amz-Signature|X-Amz-Credential|"
    r"X-Amz-Security-Token|SharedAccessSignature)",
    re.IGNORECASE,
)
_SURVIVING_CREDENTIAL_PARAM_RE = re.compile(
    r"[?&](sig|signature|token|access_token|api_key|apikey|key)=[^&#\s\"']+", re.IGNORECASE
)


def _strip_url_credentials(value: str) -> str:
    """Drop signed-URL credential query params, preserving host/path + benign params."""
    if not re.match(r"\s*https?://", value, re.IGNORECASE):
        return value
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return value
    if not parts.query:
        return value
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _CREDENTIAL_QUERY_PARAM_NAMES
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))


def _scrub_transport_value(value: Any) -> Any:
    if isinstance(value, str):
        return _strip_url_credentials(value)
    if isinstance(value, list):
        return [_scrub_transport_value(item) for item in value]
    if isinstance(value, dict):
        return scrub_transport_secrets(value)
    return value


def scrub_transport_secrets(payload: Any) -> Any:
    """Remove only auth/transport secrets, preserving every business value.

    Drops keys that hold credentials (tokens, secrets, api keys, passwords) and strips
    credential query params from signed URLs. Nested objects/lists are walked. The
    result is safe to persist into the private DB and should pass ``not
    _has_transport_secret(json)``.
    """
    if isinstance(payload, list):
        return [scrub_transport_secrets(item) for item in payload]
    if not isinstance(payload, dict):
        return payload
    scrubbed: dict[str, Any] = {}
    for key, value in payload.items():
        if AUTH_SECRET_KEY_RE.search(str(key)):
            continue  # drop credential-bearing key entirely (no placeholder to leak)
        scrubbed[str(key)] = _scrub_transport_value(value)
    return scrubbed


def _has_transport_secret(text: str) -> bool:
    """True if a transport/auth secret survived scrubbing (business URLs are allowed)."""
    return bool(_TRANSPORT_SECRET_TEXT_RE.search(text) or _SURVIVING_CREDENTIAL_PARAM_RE.search(text))


# Sentinels that mean "no business value present" for STRUCTURED SCALAR extraction.
# Applied only at projection time; the stored full ``payload_json`` is never mutated.
_PLACEHOLDER_SCALARS = frozenset(
    {"null", "none", "[redacted]", "[scrubbed]", "redacted", "scrubbed", "[url_scrubbed]"}
)


def _clean_scalar(value: Any) -> Any:
    """Return ``value`` unless it is a missing/placeholder sentinel, then ``None``.

    Does not mutate inputs. Used for structured scalar projection so placeholder
    strings (``[redacted]``/``null``/…) and empty containers never populate a column.
    """
    if value is None or value == "" or value == {} or value == []:
        return None
    if isinstance(value, str) and value.strip().lower() in _PLACEHOLDER_SCALARS:
        return None
    return value


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


def _path_value(payload: dict[str, Any], path: str) -> Any:
    """Resolve a flat key or dotted path (e.g. ``summary.current_payment_due``).

    Returns ``None`` for a missing path or an empty/``None`` leaf so callers can
    fall through to the next candidate field.
    """
    cur: Any = payload
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return None if cur in (None, "") else cur


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


# Generic amount probe, retained as the universal fallback for endpoints whose
# payloads already expose a plain monetary key (line items, budget rows, etc.).
_GENERIC_AMOUNT_FIELDS: tuple[str, ...] = (
    "amount",
    "total",
    "total_amount",
    "contract_amount",
    "revised_budget",
    "original_budget_amount",
    "current_budget_amount",
)

# Invoice line items (subcontractor invoice SOV detail/contract/change-order items)
# carry no plain ``amount`` key. Headline = current-period billing, then cumulative,
# then claimed, then the scheduled (SOV) value as a last resort. All four are present
# in the source; ``work_completed_this_period`` is first so the column represents the
# amount billed this period rather than the scheduled value (which answers a different
# analytics question and should be read from the source SOV fields when needed).
_INVOICE_ITEM_AMOUNT_FIELDS: tuple[str, ...] = (
    "work_completed_this_period",
    "total_completed_and_stored_to_date",
    "subcontractor_claimed_amount",
    "scheduled_value",
)

# Endpoint-family-aware monetary extraction, keyed by the same ``endpoint_id`` used by
# ``STRUCTURED_TABLE_BY_ENDPOINT``. Paths may be dotted (resolved via ``_path_value``).
# The generic probe above remains the fallback for any endpoint not listed here.
AMOUNT_FIELDS_BY_ENDPOINT: dict[str, tuple[str, ...]] = {
    # invoices: claimed amount, then nested billing summary totals
    "subcontractor-invoices": (
        "total_claimed_amount",
        "summary.current_payment_due",
        "summary.contract_sum_to_date",
        "summary.total_completed_and_stored_to_date",
    ),
    # invoice line items -> procore_raw_invoice_items
    "subcontractor-invoice-contract-detail-items": _INVOICE_ITEM_AMOUNT_FIELDS,
    "subcontractor-invoice-contract-items": _INVOICE_ITEM_AMOUNT_FIELDS,
    "subcontractor-invoice-change-order-items": _INVOICE_ITEM_AMOUNT_FIELDS,
    # change orders -> procore_raw_change_orders. ``grand_total`` is the dollar total.
    # ``schedule_impact_amount`` is deliberately EXCLUDED: sampled values are schedule
    # day-counts (e.g. "5", "0"), not currency, and would contaminate cost analytics.
    "prime-change-orders": ("grand_total",),
    "commitment-change-orders": ("grand_total",),
    # payment applications: source-absent today (no live endpoint emits rows); mapped so
    # amounts populate automatically if/when source rows arrive.
    "payment-applications": (
        "total_claimed_amount",
        "summary.current_payment_due",
        "amount",
    ),
}


def _amount_with_source(
    payload: dict[str, Any], endpoint_id: str | None = None
) -> tuple[str | None, str | None]:
    """Return ``(amount, source_field)`` using endpoint-aware precedence then the
    generic fallback. ``source_field`` is the matched field path (for diagnostics and
    tests only; it is not persisted — the V46 schema stores ``amount`` alone)."""
    if endpoint_id and endpoint_id in AMOUNT_FIELDS_BY_ENDPOINT:
        for path in AMOUNT_FIELDS_BY_ENDPOINT[endpoint_id]:
            value = _path_value(payload, path)
            if value is not None:
                return str(value), path
    for key in _GENERIC_AMOUNT_FIELDS:
        value = _path_value(payload, key)
        if value is not None:
            return str(value), key
    return None, None


def _amount(payload: dict[str, Any], endpoint_id: str | None = None) -> str | None:
    return _amount_with_source(payload, endpoint_id)[0]


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
        "amount": _amount(payload, endpoint_id),
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


# --- Full raw payload persistence + structured projection from full payloads ------


def _scalarize(value: Any) -> Any:
    """Reduce a nested business object to a representative scalar for a TEXT column.

    Procore payloads frequently express a field as an object (``wbs_code``,
    ``created_by`` …). Pick a stable human/code scalar; lists collapse to ``None``.
    The full nested object is always preserved in the stored ``payload_json``.
    """
    if isinstance(value, dict):
        for key in ("flat_code", "code", "name", "display_name", "login", "title", "label", "id"):
            candidate = value.get(key)
            if candidate not in (None, ""):
                return candidate
        return None
    if isinstance(value, list):
        return None
    return value


def _clean(payload: dict[str, Any], *keys: str) -> Any:
    return _clean_scalar(_scalarize(_row_value(payload, *keys)))


def _resolve_record_id_from_item(
    endpoint_id: str, raw_item: Any, explicit: str | None
) -> str | None:
    if explicit not in (None, ""):
        return str(explicit)
    if not isinstance(raw_item, dict):
        return None
    adapter = endpoint_registry.get(endpoint_id)
    if adapter and getattr(adapter, "record_id_field", None):
        value = raw_item.get(adapter.record_id_field)
        if value not in (None, ""):
            return str(value)
    for key in ("id", "number", "name"):
        value = raw_item.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _existing_source_quality_rank(conn: sqlite3.Connection, table: str, record_key: str) -> int:
    try:
        row = conn.execute(
            f"SELECT source_quality FROM {table} WHERE record_key = ?", (record_key,)
        ).fetchone()
    except sqlite3.Error:
        return 0
    return _rank(row[0]) if row else 0


def _existing_raw_full_rank(
    conn: sqlite3.Connection,
    *,
    endpoint_key: str,
    project_key: str | None,
    parent_record_id: str | None,
    record_id: str,
) -> int:
    """Max source-quality rank of any FULL (persisted=1) raw row for this record id."""
    parent = parent_record_id or None
    try:
        rows = conn.execute(
            """
            SELECT source_quality FROM procore_endpoint_raw_payloads
            WHERE endpoint_key = ? AND project_key IS ? AND parent_record_id IS ? AND record_id = ?
              AND raw_procore_payload_persisted = 1
            """,
            (endpoint_key, project_key, parent, str(record_id)),
        ).fetchall()
    except sqlite3.Error:
        return 0
    return max((_rank(r[0]) for r in rows), default=0)


def _structured_values_from_payload(
    *,
    endpoint_id: str,
    project_key: str | None,
    procore_project_id: str | None,
    company_id: str | None,
    record_id: str,
    parent_id: str | None,
    payload: dict[str, Any],
    raw_payload_id: str,
    source_hash: str,
    payload_hash: str,
    source_quality: str,
    fetched_at: str,
    now_utc: str,
) -> dict[str, Any]:
    """Build a structured bronze row from a FULL endpoint payload dict.

    Mirrors ``_structured_values`` field-for-field, but every business field is sourced
    from the full ``payload`` (via ``_clean`` so placeholders/objects do not pollute a
    scalar) instead of a redacted ``procore_live_records`` row.
    """
    adapter = endpoint_registry.get(endpoint_id)
    family = adapter.family if adapter else endpoint_id
    company_id_clean = str(company_id).strip() if company_id not in (None, "") else None
    return {
        "record_key": structured_record_key(endpoint_id, project_key, record_id, parent_id),
        "raw_payload_id": raw_payload_id,
        "source_ref_hash": source_hash,
        "endpoint_key": endpoint_id,
        "endpoint_family": family,
        "company_id": company_id_clean,
        "company_id_hash": _hash(company_id_clean) if company_id_clean else None,
        "project_id": procore_project_id,
        "project_id_hash": _hash(procore_project_id),
        "project_key": project_key,
        "record_id": record_id,
        "record_id_hash": _hash(record_id),
        "parent_record_id": parent_id,
        "parent_record_id_hash": _hash(parent_id) if parent_id else None,
        "record_number": _clean(payload, "number", "rfi_number", "submittal_number", "name"),
        "title_redacted": _clean(payload, "title", "subject", "name"),
        "status": _clean(payload, "status", "current_state"),
        "current_state": _clean(payload, "current_state", "status"),
        "owner_name": _clean(payload, "owner", "manager", "created_by", "responsible_contractor"),
        "assignee_name": _clean(payload, "assignee", "assigned_to", "ball_in_court"),
        "responsible_party_name": _clean(payload, "responsible_party", "responsible_contractor"),
        "due_at_utc": _clean(payload, "due_date", "required_on", "required_date"),
        "start_at_utc": _clean(payload, "start_date", "start_at"),
        "finish_at_utc": _clean(payload, "finish_date", "end_date", "completed_at"),
        "business_date": _clean_scalar(_scalarize(_business_date(payload))),
        "cost_code": _clean(payload, "cost_code", "cost_code_id", "wbs_code"),
        "cost_type": _clean(payload, "cost_type", "cost_type_id"),
        "amount": _clean_scalar(_amount(payload, endpoint_id)),
        "currency": _clean(payload, "currency", "currency_code"),
        "quantity": _clean(payload, "quantity", "qty"),
        "unit_of_measure": _clean(payload, "unit_of_measure", "uom"),
        "source_updated_at_utc": _clean(payload, "updated_at", "updated_at_utc"),
        "payload_captured_at_utc": fetched_at,
        "payload_seen_first_utc": fetched_at,
        "payload_seen_last_utc": fetched_at,
        "payload_hash": payload_hash,
        "raw_payload_linked": 1,
        "is_current": 1,
        "source_quality": source_quality,
        "analytics_eligible": 1,
        "daily_brief_eligible": 1 if family not in {"foundation"} else 0,
        "security_scrub_status": "transport_secrets_removed",
        "retention_class": "local_analytics",
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }


def _insert_full_raw_payload(
    conn: sqlite3.Connection,
    *,
    raw_payload_id: str,
    capture_run_id: str,
    endpoint_id: str,
    endpoint_family: str,
    company_id: str | None,
    procore_project_id: str | None,
    project_key: str | None,
    record_id: str,
    parent_id: str | None,
    source_hash: str,
    request_hash: str,
    payload_hash: str,
    payload_json: str,
    payload_size: int,
    fetched_at: str,
    source_quality: str,
    now_utc: str,
) -> None:
    company_id_clean = str(company_id).strip() if company_id not in (None, "") else None
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
          ?, ?, ?, ?, 'live_v1', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1,
          'full_business_payload', 'transport_secrets_removed', 1, 0, 0, 'local_analytics', 1, ?,
          1, 0, ?, ?
        )
        ON CONFLICT(raw_payload_id) DO UPDATE SET
          company_id=excluded.company_id,
          company_id_hash=excluded.company_id_hash,
          payload_json=excluded.payload_json,
          payload_hash=excluded.payload_hash,
          payload_size_bytes=excluded.payload_size_bytes,
          payload_seen_last_utc=excluded.payload_seen_last_utc,
          source_quality=excluded.source_quality,
          raw_procore_payload_persisted=excluded.raw_procore_payload_persisted,
          redaction_status=excluded.redaction_status,
          security_scrub_status=excluded.security_scrub_status,
          is_current=1,
          updated_utc=excluded.updated_utc
        """,
        (
            raw_payload_id,
            capture_run_id,
            endpoint_id,
            endpoint_family,
            company_id_clean,
            _hash(company_id_clean) if company_id_clean else None,
            procore_project_id,
            _hash(procore_project_id),
            project_key,
            endpoint_id,
            record_id,
            _hash(record_id),
            parent_id,
            _hash(parent_id) if parent_id else None,
            source_hash,
            request_hash,
            payload_hash,
            payload_json,
            payload_size,
            fetched_at,
            fetched_at,
            fetched_at,
            source_quality,
            now_utc,
            now_utc,
        ),
    )


def _enforce_one_current_full_raw_payload(
    conn: sqlite3.Connection,
    *,
    raw_payload_id: str,
    endpoint_id: str,
    project_key: str | None,
    record_id: str,
    parent_id: str | None,
) -> None:
    """Make the just-written full raw row the only current row for its stable key."""
    conn.execute(
        """
        UPDATE procore_endpoint_raw_payloads
        SET is_current = 0, updated_utc = CURRENT_TIMESTAMP
        WHERE raw_procore_payload_persisted = 1
          AND endpoint_key = ?
          AND project_key IS ?
          AND parent_record_id IS ?
          AND record_id = ?
          AND raw_payload_id <> ?
        """,
        (endpoint_id, project_key, parent_id, record_id, raw_payload_id),
    )
    conn.execute(
        """
        UPDATE procore_endpoint_raw_payloads
        SET is_current = 1
        WHERE raw_payload_id = ?
        """,
        (raw_payload_id,),
    )
    row = conn.execute(
        """
        SELECT
          SUM(CASE WHEN is_current = 1 THEN 1 ELSE 0 END) AS current_count,
          SUM(CASE WHEN raw_payload_id = ? AND is_current = 1 THEN 1 ELSE 0 END) AS incoming_current
        FROM procore_endpoint_raw_payloads
        WHERE raw_procore_payload_persisted = 1
          AND endpoint_key = ?
          AND project_key IS ?
          AND parent_record_id IS ?
          AND record_id = ?
        """,
        (raw_payload_id, endpoint_id, project_key, parent_id, record_id),
    ).fetchone()
    if row is None or row["current_count"] != 1 or row["incoming_current"] != 1:
        raise RuntimeError("full raw current-version invariant failed")


def _run_in_savepoint(conn: sqlite3.Connection, name: str, callback: Any) -> None:
    conn.execute(f"SAVEPOINT {name}")
    try:
        callback(conn)
    except Exception:
        conn.execute(f"ROLLBACK TO {name}")
        conn.execute(f"RELEASE {name}")
        raise
    conn.execute(f"RELEASE {name}")


def upsert_full_raw_payload_and_structured(
    *,
    db_path: str | Path | None = None,
    conn: sqlite3.Connection | None = None,
    endpoint_id: str,
    project_key: str | None,
    procore_project_id: str | None,
    raw_item: Any,
    company_id: str | None = None,
    parent_procore_id: str | None = None,
    record_id: str | None = None,
    fetched_at_utc: str | None = None,
    source_quality: str = SOURCE_QUALITY_LIVE_FULL,
    capture_run_id: str | None = None,
) -> dict[str, Any]:
    """Persist a FULL endpoint item payload + project its structured bronze row.

    The private DB stores the complete business payload (minus transport/auth secrets).
    Honors source-quality precedence: a lower-rank write never overwrites/downgrades a
    higher-rank row. Returns a body-free receipt. Pass ``conn`` to participate in a
    caller's transaction; otherwise a ``db_path`` connection + transaction is opened.
    """
    now_utc = _now()
    receipt: dict[str, Any] = {
        "full_raw_persistence_enabled": True,
        "endpoint_key": endpoint_id,
        "source_quality": source_quality,
        "raw_payload_rows_written": 0,
        "structured_rows_written": 0,
        "raw_procore_payload_persisted": 0,
        "skipped_due_to_higher_quality": 0,
        "skipped_missing_record_id": 0,
        "structured_skipped_no_table": 0,
        "security_scrub_status": "transport_secrets_removed",
        "record_key": None,
        "raw_payload_id": None,
    }
    resolved_id = _resolve_record_id_from_item(endpoint_id, raw_item, record_id)
    if resolved_id is None:
        receipt["skipped_missing_record_id"] = 1
        return receipt
    parent_id = str(parent_procore_id) if parent_procore_id not in (None, "") else None
    fetched_at = fetched_at_utc or now_utc

    item = dict(raw_item) if isinstance(raw_item, dict) else raw_item
    if isinstance(item, dict):
        item.pop("_hb_parent_procore_id", None)  # drop N+1 helper key; not Procore business data
    scrubbed_obj = scrub_transport_secrets(item)
    scrubbed_json = json.dumps(scrubbed_obj, sort_keys=True, separators=(",", ":"))
    if _has_transport_secret(scrubbed_json):
        receipt["security_scrub_status"] = "scrub_failed"
        return receipt
    if isinstance(scrubbed_obj, dict):
        payload = scrubbed_obj
    else:
        payload = {
            "payload_array_length": len(scrubbed_obj) if isinstance(scrubbed_obj, list) else None
        }

    payload_hash = _hash(scrubbed_json)
    payload_size = len(scrubbed_json.encode("utf-8"))
    raw_payload_id = raw_payload_id_for(endpoint_id, project_key, resolved_id, parent_id, payload_hash)
    source_hash = source_ref_hash("procore_live_full", project_key, endpoint_id, parent_id, resolved_id)
    request_hash = request_fingerprint_hash(endpoint_id, project_key, parent_id)
    table = STRUCTURED_TABLE_BY_ENDPOINT.get(endpoint_id)
    record_key = structured_record_key(endpoint_id, project_key, resolved_id, parent_id)
    receipt["record_key"] = record_key
    receipt["raw_payload_id"] = raw_payload_id
    incoming_rank = _rank(source_quality)
    adapter = endpoint_registry.get(endpoint_id)
    family = adapter.family if adapter else endpoint_id

    def _do(active: sqlite3.Connection) -> None:
        if table is not None and _existing_source_quality_rank(active, table, record_key) > incoming_rank:
            receipt["skipped_due_to_higher_quality"] = 1
            return
        _insert_full_raw_payload(
            active,
            raw_payload_id=raw_payload_id,
            capture_run_id=capture_run_id or f"live-full-{now_utc[:10]}",
            endpoint_id=endpoint_id,
            endpoint_family=family,
            company_id=company_id,
            procore_project_id=procore_project_id,
            project_key=project_key,
            record_id=resolved_id,
            parent_id=parent_id,
            source_hash=source_hash,
            request_hash=request_hash,
            payload_hash=payload_hash,
            payload_json=scrubbed_json,
            payload_size=payload_size,
            fetched_at=fetched_at,
            source_quality=source_quality,
            now_utc=now_utc,
        )
        _enforce_one_current_full_raw_payload(
            active,
            raw_payload_id=raw_payload_id,
            endpoint_id=endpoint_id,
            project_key=project_key,
            record_id=resolved_id,
            parent_id=parent_id,
        )
        receipt["raw_payload_rows_written"] = 1
        receipt["raw_procore_payload_persisted"] = 1
        if table is None:
            receipt["structured_skipped_no_table"] = 1
        else:
            values = _structured_values_from_payload(
                endpoint_id=endpoint_id,
                project_key=project_key,
                procore_project_id=procore_project_id,
                company_id=company_id,
                record_id=resolved_id,
                parent_id=parent_id,
                payload=payload,
                raw_payload_id=raw_payload_id,
                source_hash=source_hash,
                payload_hash=payload_hash,
                source_quality=source_quality,
                fetched_at=fetched_at,
                now_utc=now_utc,
            )
            _insert_structured(active, table, values)
            _insert_dimensions(active, values)
            receipt["structured_rows_written"] = 1
        # Endpoint-specific structured projection (V47): additive, registry-driven. Imported
        # lazily to avoid a circular import. Live mode DEGRADES (never raises) on unknown
        # paths; the full raw payload above is already persisted so nothing is lost.
        if isinstance(payload, dict):
            from .projection_engine import MODE_LIVE, project_endpoint_specific

            receipt["endpoint_specific"] = project_endpoint_specific(
                active,
                endpoint_id=endpoint_id,
                project_key=project_key,
                procore_project_id=procore_project_id,
                record_id=resolved_id,
                parent_record_id=parent_id,
                payload=payload,
                raw_payload_id=raw_payload_id,
                payload_hash=payload_hash,
                source_quality=source_quality,
                fetched_at=fetched_at,
                now_utc=now_utc,
                mode=MODE_LIVE,
            )

    if conn is not None:
        if conn.in_transaction:
            _run_in_savepoint(conn, "full_raw_payload_upsert", _do)
        else:
            with transaction(conn):
                _do(conn)
    else:
        with open_connection(Path(db_path) if db_path is not None else None) as active, transaction(active):
            _do(active)
    return receipt


def backfill_from_raw_payloads(
    *,
    db_path: str | Path | None = None,
    apply: bool = False,
    project_key: str | None = None,
    family: str | None = None,
    endpoint: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Project structured bronze rows from FULL raw payload rows (persisted=1).

    This is the preferred structured source: it reuses the complete business payload
    captured at live-sync time rather than the redacted legacy projection. Honors
    source-quality precedence so it never downgrades an existing higher-rank row.
    """
    conn = get_connection(Path(db_path) if db_path is not None else None)
    clauses = ["raw_procore_payload_persisted = 1", "is_current = 1"]
    params: list[Any] = []
    if project_key:
        clauses.append("project_key = ?")
        params.append(project_key)
    if endpoint:
        clauses.append("endpoint_key = ?")
        params.append(endpoint)
    elif family:
        endpoint_ids = [
            ep.endpoint_id
            for ep in endpoint_registry.list_all()
            if ep.family == family and ep.endpoint_id in STRUCTURED_TABLE_BY_ENDPOINT
        ]
        if not endpoint_ids:
            endpoint_ids = ["__none__"]
        clauses.append(f"endpoint_key IN ({', '.join('?' for _ in endpoint_ids)})")
        params.extend(endpoint_ids)
    sql = f"SELECT * FROM {RAW_LANDING_TABLE} WHERE " + " AND ".join(clauses)
    sql += " ORDER BY endpoint_key, project_key, parent_record_id, record_id LIMIT ?"
    params.append(limit)
    try:
        rows = list(conn.execute(sql, tuple(params)))
    except sqlite3.Error:
        rows = []
    inspected = len(rows)
    structured_written = 0
    skipped_higher = 0
    skipped_no_table = 0
    structured_targets = CounterLike()
    now_utc = _now()
    if apply:
        with transaction(conn):
            for row in rows:
                endpoint_id = row["endpoint_key"]
                table = STRUCTURED_TABLE_BY_ENDPOINT.get(endpoint_id)
                if table is None:
                    skipped_no_table += 1
                    continue
                record_id = str(row["record_id"])
                parent_id = row["parent_record_id"] or None
                record_key = structured_record_key(endpoint_id, row["project_key"], record_id, parent_id)
                incoming_rank = _rank(row["source_quality"])
                if _existing_source_quality_rank(conn, table, record_key) > incoming_rank:
                    skipped_higher += 1
                    continue
                payload = _safe_json_loads(row["payload_json"])
                if not isinstance(payload, dict):
                    payload = {"payload_array_length": len(payload) if isinstance(payload, list) else None}
                values = _structured_values_from_payload(
                    endpoint_id=endpoint_id,
                    project_key=row["project_key"],
                    procore_project_id=row["project_id"],
                    company_id=row["company_id"],
                    record_id=record_id,
                    parent_id=parent_id,
                    payload=payload,
                    raw_payload_id=row["raw_payload_id"],
                    source_hash=row["source_ref_hash"],
                    payload_hash=row["payload_hash"],
                    source_quality=row["source_quality"],
                    fetched_at=row["payload_seen_last_utc"] or now_utc,
                    now_utc=now_utc,
                )
                _insert_structured(conn, table, values)
                _insert_dimensions(conn, values)
                structured_targets.add(table)
                structured_written += 1
    return {
        "command": "hb-assistant procore analytics backfill-from-raw-payloads",
        "mode": "apply" if apply else "dry_run",
        "source_quality": "full_raw_payload",
        "raw_full_rows_inspected": inspected,
        "structured_written": structured_written,
        "skipped_due_to_higher_quality": skipped_higher,
        "skipped_no_structured_table": skipped_no_table,
        "structured_targets": structured_targets.as_dict(),
        "live_procore_calls": 0,
        "external_writeback_performed": 0,
        "filters": {"project_key": project_key, "family": family, "endpoint": endpoint, "limit": limit},
        "guardrails": {"live_calls_disabled": True, "writeback": "none"},
    }


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
    skipped_higher = 0
    structured_targets = CounterLike()

    def _legacy_outranked(row: sqlite3.Row, table: str) -> bool:
        """True when a higher-quality (full) row already covers this record, so the
        redacted legacy projection must not overwrite/downgrade it."""
        parent_id = row["parent_procore_id"] or None
        record_id = str(row["procore_record_id"])
        record_key = structured_record_key(row["endpoint_id"], row["project_key"], record_id, parent_id)
        if _existing_source_quality_rank(conn, table, record_key) > _rank(SOURCE_QUALITY_LEGACY):
            return True
        return _existing_raw_full_rank(
            conn,
            endpoint_key=row["endpoint_id"],
            project_key=row["project_key"],
            parent_record_id=parent_id,
            record_id=record_id,
        ) >= _rank(SOURCE_QUALITY_FIXTURE_FULL)

    if not apply:
        for row in rows:
            table = STRUCTURED_TABLE_BY_ENDPOINT.get(row["endpoint_id"])
            if not table:
                skipped += 1
            elif _legacy_outranked(row, table):
                skipped_higher += 1
            else:
                structured_targets.add(table)
        would_write = inspected - skipped - skipped_higher
        return {
            **BackfillReceipt(
                mode="dry_run",
                inspected=inspected,
                raw_landing_written=0,
                structured_written=0,
                skipped=skipped,
                source_quality=SOURCE_QUALITY_LEGACY,
            ).as_dict(),
            "would_write_raw_landing": would_write,
            "would_write_structured": would_write,
            "skipped_due_to_higher_quality": skipped_higher,
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
            if _legacy_outranked(row, table):
                skipped_higher += 1
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
        "skipped_due_to_higher_quality": skipped_higher,
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
    total_raw_persisted = total_full = total_legacy = total_degraded = 0
    for ep in endpoint_registry.list_all():
        if family and ep.family != family:
            continue
        table = STRUCTURED_TABLE_BY_ENDPOINT.get(ep.endpoint_id)
        params: list[Any] = [ep.endpoint_id]
        live_where = "endpoint_id = ?"
        raw_where = "endpoint_key = ?"
        if project_key:
            live_where += " AND project_key = ?"
            raw_where += " AND project_key = ?"
            params.append(project_key)
        live_count = _table_count(conn, "procore_live_records", live_where, tuple(params))
        raw_count = _table_count(conn, RAW_LANDING_TABLE, raw_where, tuple(params))
        raw_persisted = _table_count(
            conn, RAW_LANDING_TABLE, raw_where + " AND raw_procore_payload_persisted = 1", tuple(params)
        )
        structured_count = 0
        current_count = 0
        non_null_amount = 0
        full_rows = legacy_rows = degraded_rows = 0
        source_quality_breakdown: dict[str, int] = {}
        if table:
            sparams: list[Any] = [ep.endpoint_id]
            structured_where = "endpoint_key = ?"
            if project_key:
                structured_where += " AND project_key = ?"
                sparams.append(project_key)
            structured_count = _table_count(conn, table, structured_where, tuple(sparams))
            current_count = _table_count(conn, table, structured_where + " AND is_current = 1", tuple(sparams))
            non_null_amount = _table_count(
                conn, table, structured_where + " AND amount IS NOT NULL AND amount != ''", tuple(sparams)
            )
            full_rows = _table_count(
                conn,
                table,
                structured_where + " AND source_quality IN ('live_full_payload', 'fixture_full_payload')",
                tuple(sparams),
            )
            legacy_rows = _table_count(
                conn, table, structured_where + " AND source_quality = 'redacted_legacy_projection'", tuple(sparams)
            )
            degraded_rows = _table_count(
                conn,
                table,
                structured_where
                + " AND source_quality = 'redacted_legacy_projection' AND (amount IS NULL OR amount = '')",
                tuple(sparams),
            )
            try:
                for sq, cnt in conn.execute(
                    f"SELECT source_quality, COUNT(*) FROM {table} WHERE {structured_where} GROUP BY source_quality",
                    tuple(sparams),
                ):
                    source_quality_breakdown[str(sq)] = int(cnt)
            except sqlite3.Error:
                source_quality_breakdown = {}
        amount_coverage_pct = round(100.0 * non_null_amount / structured_count, 1) if structured_count else 0.0
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
                "non_null_amount_rows": non_null_amount,
                "amount_coverage_pct": amount_coverage_pct,
                "raw_persisted_rows": raw_persisted,
                "full_payload_rows": full_rows,
                "legacy_fallback_rows": legacy_rows,
                "degraded_rows": degraded_rows,
                "source_quality_breakdown": source_quality_breakdown,
                "analytics_eligible": bool(table and ep.live_verified),
                "daily_brief_eligible": bool(table and ep.family != "foundation"),
                "coverage_gap_reason": gap,
                "source_quality": SOURCE_QUALITY_LEGACY if raw_count or structured_count else None,
            }
        )
        total_live += live_count
        total_raw += raw_count
        total_structured += structured_count
        total_raw_persisted += raw_persisted
        total_full += full_rows
        total_legacy += legacy_rows
        total_degraded += degraded_rows
    return {
        "command": "hb-assistant procore analytics coverage",
        "project_key": project_key,
        "family": family,
        "endpoint_count": len(rows),
        "total_live_record_rows": total_live,
        "total_raw_landing_rows": total_raw,
        "total_raw_persisted_rows": total_raw_persisted,
        "total_structured_rows": total_structured,
        "total_full_payload_rows": total_full,
        "total_legacy_fallback_rows": total_legacy,
        "total_degraded_rows": total_degraded,
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
        by_quality: dict[str, int] = {}
        try:
            sql = f"SELECT source_quality, COUNT(*) FROM {table}"
            if where:
                sql += f" WHERE {where}"
            sql += " GROUP BY source_quality"
            for sq, cnt in conn.execute(sql, params):
                by_quality[str(sq)] = int(cnt)
        except sqlite3.Error:
            by_quality = {}
        rows.append(
            {"table": table, "rows": _table_count(conn, table, where, params), "by_source_quality": by_quality}
        )
    raw_where = "raw_procore_payload_persisted = 1"
    raw_params: tuple[Any, ...] = ()
    if project_key:
        raw_where += " AND project_key = ?"
        raw_params = (project_key,)
    return {
        "command": "hb-assistant procore analytics structured-counts",
        "project_key": project_key,
        "structured_table_count": len(rows),
        "raw_persisted_count": _table_count(conn, RAW_LANDING_TABLE, raw_where, raw_params),
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


def reconcile_full_raw_landing(*, db_path: str | Path | None, apply: bool = False) -> dict[str, Any]:
    """Repair copied full-raw landing provenance/currentness without reading live app defaults."""
    if db_path is None:
        return {
            "command": "hb-assistant procore analytics reconcile-full-raw-landing",
            "ok": False,
            "status": "blocked_explicit_db_required",
            "reason": "--db is required; this command never defaults to the live app DB",
            "local_db_write_performed": False,
            "external_writeback_performed": 0,
        }
    if not apply:
        return {
            "command": "hb-assistant procore analytics reconcile-full-raw-landing",
            "ok": False,
            "status": "blocked_apply_required",
            "reason": "--apply is required for reconciliation",
            "db_path": str(db_path),
            "local_db_write_performed": False,
            "external_writeback_performed": 0,
        }

    conn = get_connection(Path(db_path))
    try:
        company_rows_repaired = 0
        stable_keys_reconciled = 0
        rows_marked_current = 0
        rows_marked_non_current = 0
        with transaction(conn):
            rows = conn.execute(
                """
                SELECT p.raw_payload_id, r.company_id
                FROM procore_endpoint_raw_payloads p
                JOIN procore_live_sync_runs r
                  ON r.sync_run_id = p.capture_run_id
                WHERE p.raw_procore_payload_persisted = 1
                  AND (p.company_id IS NULL OR TRIM(p.company_id) = '')
                  AND r.company_id IS NOT NULL
                  AND TRIM(r.company_id) <> ''
                """
            ).fetchall()
            for row in rows:
                company_id = str(row["company_id"]).strip()
                conn.execute(
                    """
                    UPDATE procore_endpoint_raw_payloads
                    SET company_id = ?, company_id_hash = ?, updated_utc = CURRENT_TIMESTAMP
                    WHERE raw_payload_id = ?
                    """,
                    (company_id, _hash(company_id), row["raw_payload_id"]),
                )
                company_rows_repaired += 1

            stable_keys = conn.execute(
                """
                SELECT endpoint_key, project_key, parent_record_id, record_id
                FROM procore_endpoint_raw_payloads
                WHERE raw_procore_payload_persisted = 1
                GROUP BY endpoint_key, project_key, parent_record_id, record_id
                """
            ).fetchall()
            for key in stable_keys:
                versions = conn.execute(
                    """
                    SELECT raw_payload_id, is_current, payload_seen_last_utc, updated_utc
                    FROM procore_endpoint_raw_payloads
                    WHERE raw_procore_payload_persisted = 1
                      AND endpoint_key = ?
                      AND project_key IS ?
                      AND parent_record_id IS ?
                      AND record_id = ?
                    """,
                    (
                        key["endpoint_key"],
                        key["project_key"],
                        key["parent_record_id"],
                        key["record_id"],
                    ),
                ).fetchall()
                if not versions:
                    continue
                winner = max(
                    versions,
                    key=lambda row: (
                        row["payload_seen_last_utc"] or "",
                        row["updated_utc"] or "",
                        row["raw_payload_id"] or "",
                    ),
                )
                changed = False
                for version in versions:
                    target_current = 1 if version["raw_payload_id"] == winner["raw_payload_id"] else 0
                    if version["is_current"] == target_current:
                        continue
                    conn.execute(
                        """
                        UPDATE procore_endpoint_raw_payloads
                        SET is_current = ?, updated_utc = CURRENT_TIMESTAMP
                        WHERE raw_payload_id = ?
                        """,
                        (target_current, version["raw_payload_id"]),
                    )
                    changed = True
                    if target_current:
                        rows_marked_current += 1
                    else:
                        rows_marked_non_current += 1
                current_count = conn.execute(
                    """
                    SELECT SUM(CASE WHEN is_current = 1 THEN 1 ELSE 0 END)
                    FROM procore_endpoint_raw_payloads
                    WHERE raw_procore_payload_persisted = 1
                      AND endpoint_key = ?
                      AND project_key IS ?
                      AND parent_record_id IS ?
                      AND record_id = ?
                    """,
                    (
                        key["endpoint_key"],
                        key["project_key"],
                        key["parent_record_id"],
                        key["record_id"],
                    ),
                ).fetchone()[0]
                if current_count != 1:
                    raise RuntimeError("full raw reconciliation invariant failed")
                if changed:
                    stable_keys_reconciled += 1
        return {
            "command": "hb-assistant procore analytics reconcile-full-raw-landing",
            "ok": True,
            "status": "success",
            "db_path": str(db_path),
            "company_rows_repaired": company_rows_repaired,
            "stable_keys_reconciled": stable_keys_reconciled,
            "rows_marked_current": rows_marked_current,
            "rows_marked_non_current": rows_marked_non_current,
            "raw_payload_body_emitted": False,
            "local_db_write_performed": True,
            "external_writeback_performed": 0,
            "guardrails": {
                "explicit_db_required": True,
                "live_calls_disabled": True,
                "writeback": "none",
            },
        }
    finally:
        conn.close()


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
    "SOURCE_QUALITY_FIXTURE_FULL",
    "SOURCE_QUALITY_LEGACY",
    "SOURCE_QUALITY_LIVE_FULL",
    "SOURCE_QUALITY_RANK",
    "STRUCTURED_TABLES",
    "STRUCTURED_TABLE_BY_ENDPOINT",
    "backfill_from_live_records",
    "backfill_from_raw_payloads",
    "contract_inventory",
    "coverage_markdown",
    "no_raw_leak_scan",
    "payload_has_forbidden_security_artifact",
    "ranking_diagnostics",
    "reconcile_full_raw_landing",
    "scrub_payload",
    "scrub_transport_secrets",
    "structured_counts",
    "structured_coverage",
    "upsert_full_raw_payload_and_structured",
]
