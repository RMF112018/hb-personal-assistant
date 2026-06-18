#!/usr/bin/env python3
"""Read-only Procore SQLite null-projection audit.

Profiles endpoint projection tables and classifies null-heavy fields without emitting
raw payload values. Raw payload JSON is inspected only for path-presence counts.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from hb_assistant.procore import projection_registry

DEFAULT_DB_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "HB Personal Assistant"
    / "db"
    / "hb-personal-assistant.sqlite"
)
DEFAULT_PREFIXES = ("procore_ep_", "procore_endpoint_")
RAW_PAYLOAD_TABLE = "procore_endpoint_raw_payloads"

ROOT_EMPTY_TABLE = "empty_table_no_projection_evidence"
ROOT_SUPPORT = "support_or_guardrail_field"
ROOT_UNMAPPED = "schema_column_not_in_projection_registry"
ROOT_PATH_ABSENT = "registry_path_not_present_in_payload"
ROOT_PATH_PRESENT_NOT_WRITTEN = "registry_path_present_but_projection_not_writing"
ROOT_SOURCE_MISSING = "source_payload_missing_or_endpoint_not_refreshed"
ROOT_EXPECTED_OPTIONAL = "expected_optional_no_current_project_usage"

DEFERRED_BATCH_B_FIELDS = {
    ("procore_ep_inspection_items", "item_response"),
    ("procore_ep_inspection_items", "response"),
    ("procore_ep_inspection_items", "response_set"),
    ("procore_ep_rfis", "ball_in_court"),
    ("procore_ep_rfis", "cost_code"),
    ("procore_ep_rfis", "location"),
    ("procore_ep_rfis", "sub_job"),
    ("procore_ep_submittals", "location"),
    ("procore_ep_submittals", "submittal_package"),
    ("procore_ep_submittals", "submittal_workflow_template"),
    ("procore_ep_daily_log_manpower", "contact"),
    ("procore_ep_daily_log_manpower", "cost_code"),
    ("procore_ep_daily_log_manpower", "location"),
    ("procore_ep_observations", "assignee"),
    ("procore_ep_observations", "assignee_vendor"),
    ("procore_ep_observations", "location"),
    ("procore_ep_observations", "origin"),
    ("procore_ep_observations", "specification_section"),
    ("procore_ep_observations", "trade"),
    ("procore_ep_daily_log_inspections", "location"),
    ("procore_ep_daily_log_notes", "location"),
    ("procore_ep_inspections", "closed_by"),
    ("procore_ep_inspections", "location"),
    ("procore_ep_inspections", "point_of_contact"),
    ("procore_ep_inspections", "responsible_contractor"),
    ("procore_ep_inspections", "specification_section"),
    ("procore_ep_inspections", "trade"),
    ("procore_ep_inspections_signature_requests", "signature"),
    ("procore_ep_observations_assignees", "vendor"),
}

DEFERRED_BATCH_C_FIELDS = {
    ("procore_ep_budget_detail_row_cells", "company_id"),
    ("procore_ep_budget_detail_row_cells", "currency_iso_code"),
    ("procore_ep_inspection_items_response_set_responses", "company_id"),
    ("procore_ep_submittals_approvers", "company_id"),
    ("procore_ep_submittals_approvers_attachments", "company_id"),
    ("procore_ep_rfis_assignees", "company_id"),
    ("procore_ep_inspection_items", "company_id"),
    ("procore_ep_daily_log_dcrs", "company_id"),
    ("procore_ep_budget_detail_rows", "actual_cost"),
    ("procore_ep_budget_detail_rows", "company_id"),
    ("procore_ep_budget_detail_rows", "cost_type"),
    ("procore_ep_budget_detail_rows", "cost_type_id"),
    ("procore_ep_budget_detail_rows", "line_item_type_id"),
    ("procore_ep_rfis", "company_id"),
    ("procore_ep_rfis_questions", "company_id"),
    ("procore_ep_submittals", "company_id"),
    ("procore_ep_daily_log_notes_attachments", "company_id"),
    ("procore_ep_change_events", "event_origin"),
    ("procore_ep_subcontractor_invoices", "company_id"),
    ("procore_ep_subcontractor_invoices_attachments", "company_id"),
    ("procore_ep_daily_log_manpower", "company_id"),
    ("procore_ep_daily_log_dcrs_attachments", "company_id"),
    ("procore_ep_daily_log_manpower_attachments", "company_id"),
    ("procore_ep_inspections_attachments", "company_id"),
    ("procore_ep_budget_detail_columns", "company_id"),
    ("procore_ep_budget_detail_columns", "visible"),
    ("procore_ep_commitment_contracts", "company_id"),
    ("procore_ep_observations", "company_id"),
    ("procore_ep_inspections_distribution_members", "company_id"),
    ("procore_ep_submittals_ball_in_court", "company_id"),
    ("procore_ep_subcontractor_invoice_contract_detail_items", "company_id"),
    ("procore_ep_budget_modifications", "company_id"),
    ("procore_ep_rfis_ball_in_courts", "company_id"),
    ("procore_ep_inspection_sections", "company_id"),
    ("procore_ep_daily_log_weather", "company_id"),
    ("procore_ep_daily_log_inspections", "company_id"),
    ("procore_ep_commitment_compliance_insurance_documents__52b7bf", "company_id"),
    ("procore_ep_inspections_inspectors", "company_id"),
    ("procore_ep_commitment_change_orders", "change_order_change_reason"),
    ("procore_ep_commitment_change_orders", "company_id"),
    ("procore_ep_commitment_change_orders", "designated_reviewer"),
    ("procore_ep_commitment_change_orders", "received_from"),
    ("procore_ep_commitment_change_orders", "reviewed_by"),
    ("procore_ep_meetings", "company_id"),
    ("procore_ep_meetings", "distributed_by"),
    ("procore_ep_budget_change_history", "company_id"),
    ("procore_ep_daily_log_notes", "company_id"),
    ("procore_ep_inspections", "company_id"),
    ("procore_ep_commitment_line_items", "company_id"),
    ("procore_ep_prime_change_orders", "change_order_change_reason"),
    ("procore_ep_prime_change_orders", "company_id"),
    ("procore_ep_prime_change_orders", "designated_reviewer"),
    ("procore_ep_prime_change_orders", "received_from"),
    ("procore_ep_daily_log_deliveries", "company_id"),
    ("procore_ep_commitment_compliance_insurance_documents", "company_id"),
    ("procore_ep_rfqs_change_event_change_event_line_items__0a3e8d", "company_id"),
    ("procore_ep_rfqs_change_event_change_event_line_items", "company_id"),
    ("procore_ep_prime_contract_line_items", "company_id"),
    ("procore_ep_budget_views", "company_id"),
    ("procore_ep_punch_items_assignees", "company_id"),
    ("procore_ep_punch_items_assignments", "company_id"),
    ("procore_ep_rfqs_change_event_attachments", "company_id"),
    ("procore_ep_purchase_order_line_items_cost_code_line_i_779dbd", "company_id"),
    ("procore_ep_subcontractor_invoice_change_order_items", "company_id"),
    ("procore_ep_punch_items", "company_id"),
    ("procore_ep_punch_items_ball_in_court", "company_id"),
    ("procore_ep_billing_periods", "company_id"),
    ("procore_ep_daily_log_deliveries_attachments", "company_id"),
    ("procore_ep_commitment_attachments", "company_id"),
    ("procore_ep_daily_log_inspections_attachments", "company_id"),
    ("procore_ep_projects", "company_id"),
    ("procore_ep_projects", "project_stage"),
    ("procore_ep_purchase_order_line_items", "company_id"),
    ("procore_ep_rfqs_attachments", "company_id"),
    ("procore_ep_projects_custom_fields_custom_field_163287_value", "company_id"),
    ("procore_ep_purchase_order_contracts", "assignee"),
    ("procore_ep_purchase_order_contracts", "company_id"),
    ("procore_ep_purchase_order_contracts", "custom_fields_custom_field_214072_value"),
    ("procore_ep_purchase_order_contracts", "custom_fields_custom_field_214078_value"),
    ("procore_ep_purchase_order_contracts", "custom_fields_custom_field_214087_value"),
    ("procore_ep_inspections_signature_requests", "company_id"),
    ("procore_ep_commitment_compliance", "company_id"),
    ("procore_ep_observations_assignees", "company_id"),
    ("procore_ep_rfqs", "company_id"),
    ("procore_ep_prime_contracts", "company_id"),
    ("procore_ep_projects_custom_fields_custom_field_163290_value", "company_id"),
    ("procore_ep_projects_custom_fields_custom_field_163293_value", "company_id"),
    ("procore_ep_daily_log_visitor", "company_id"),
    ("procore_ep_prime_change_order_line_items", "company_id"),
    ("procore_ep_projects_custom_fields_custom_field_163296_value", "company_id"),
    ("procore_ep_projects_custom_fields_custom_field_163299_value", "company_id"),
    ("procore_ep_projects_custom_fields_custom_field_163302_value", "company_id"),
    ("procore_ep_projects_custom_fields_custom_field_163305_value", "company_id"),
    ("procore_ep_purchase_order_contracts_custom_fields_cus_a0fe65", "company_id"),
}

SUPPORT_TABLES = {
    "procore_endpoint_contracts",
    "procore_endpoint_capture_runs",
    "procore_endpoint_capture_pages",
    "procore_endpoint_capture_errors",
    "procore_endpoint_raw_payloads",
}
EXACT_SUPPORT_COLUMNS = {
    "external_writeback_performed",
    "raw_payload_emitted_to_read_model",
    "raw_payload_emitted_to_evidence",
    "payload_sidecar_json",
    "parent_record_id",
    "parent_record_id_hash",
    "payload_hash",
    "source_ref_hash",
    "request_fingerprint_hash",
    "company_id_hash",
    "project_id_hash",
    "record_id_hash",
    "primary_record_key",
    "parent_item_id",
    "raw_payload_id",
    "capture_run_id",
    "last_sync_run_id",
    "last_receipt_id",
    "created_utc",
    "updated_utc",
    "payload_seen_first_utc",
    "payload_seen_last_utc",
    "payload_captured_at_utc",
}
SUPPORT_SUFFIXES = ("_hash", "_utc", "_run_id", "_receipt")
SAFE_SAMPLE_COLUMNS = {
    "endpoint_key",
    "endpoint_family",
    "endpoint_version",
    "project_key",
    "record_type",
    "source_quality",
    "redaction_status",
    "security_scrub_status",
    "retention_class",
    "is_current",
    "analytics_eligible",
    "raw_procore_payload_persisted",
}
SENSITIVE_NAME_PARTS = (
    "payload_json",
    "sidecar",
    "description",
    "notes",
    "note",
    "comment",
    "comments",
    "body",
    "email",
    "url",
    "signed",
    "token",
    "secret",
    "password",
)


@dataclass(frozen=True)
class ColumnMapping:
    endpoint_key: str
    endpoint_family: str
    json_path: str
    table_role: str


@dataclass(frozen=True)
class PathPresence:
    endpoint_key: str
    json_path: str
    payload_rows_inspected: int
    path_present_count: int
    path_non_empty_count: int
    path_missing_count: int
    parent_path_present_count: int
    source_quality_filter_used: str
    raw_payload_values_emitted: bool = False


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _readonly_uri(path: Path) -> str:
    return f"file:{quote(str(path.resolve()), safe='/')}?mode=ro"


def connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(_readonly_uri(Path(db_path)), uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _is_text_like(declared_type: str) -> bool:
    normalized = declared_type.upper()
    return not normalized or any(
        token in normalized for token in ("TEXT", "CHAR", "CLOB", "VARCHAR")
    )


def _is_support_field(table: str, column: str) -> bool:
    return (
        table in SUPPORT_TABLES
        or column in EXACT_SUPPORT_COLUMNS
        or column.endswith(SUPPORT_SUFFIXES)
    )


def _deferred_disposition(table: str, column: str) -> dict[str, str] | None:
    key = (table, column)
    if key in DEFERRED_BATCH_B_FIELDS:
        return {
            "batch": "Batch B",
            "disposition": "documented_object_container_or_child_field_decomposition",
            "rationale": (
                "Reviewed high-value operational object/container field; registry projects "
                "scalar child fields or child rows instead of promoting the bare object "
                "container column."
            ),
        }
    if key in DEFERRED_BATCH_C_FIELDS:
        if column == "company_id":
            disposition = "deferred_broad_company_id_policy"
            rationale = (
                "Reviewed broad company_id field; no global company_id propagation/backfill "
                "is applied without a separately approved table convention proof."
            )
        elif table.startswith("procore_ep_budget_detail_"):
            disposition = "deferred_budget_detail_convenience_or_optional_field"
            rationale = (
                "Reviewed Budget Detail field; Batch 2 triage did not prove a stable "
                "row-level source requiring projection into this convenience column."
            )
        else:
            disposition = "documented_schema_artifact_or_expected_optional"
            rationale = (
                "Reviewed Batch C field; current evidence supports documentation/deprecation "
                "triage rather than a projection mapping in this batch."
            )
        return {"batch": "Batch C", "disposition": disposition, "rationale": rationale}
    return None


def _safe_sample_allowed(column: str) -> bool:
    lower = column.lower()
    return column in SAFE_SAMPLE_COLUMNS and not any(part in lower for part in SENSITIVE_NAME_PARTS)


def _classify_population(
    total_rows: int, null_rows: int, empty_string_rows: int, min_null_rate: float
) -> str:
    if total_rows == 0:
        return "all_null"
    null_rate = null_rows / total_rows
    if null_rows == total_rows:
        return "all_null"
    if empty_string_rows and null_rows + empty_string_rows == total_rows:
        return "empty_string_instead_of_null"
    if null_rate >= min_null_rate:
        return "mostly_null"
    if null_rows == 0:
        return "fully_populated"
    return "partially_populated"


def _registry_mappings() -> dict[tuple[str, str], ColumnMapping]:
    mappings: dict[tuple[str, str], ColumnMapping] = {}
    for endpoint_key, plan in projection_registry.load_registry().items():
        for rel_path, column in plan.primary_columns:
            mappings[(plan.primary_table, column)] = ColumnMapping(
                endpoint_key=endpoint_key,
                endpoint_family=plan.endpoint_family,
                json_path=_json_path(None, rel_path),
                table_role="primary",
            )
        for child in plan.child_tables:
            for rel_path, column in child.columns:
                mappings[(child.table, column)] = ColumnMapping(
                    endpoint_key=endpoint_key,
                    endpoint_family=plan.endpoint_family,
                    json_path=_json_path(child.array_path, rel_path),
                    table_role="child",
                )
    return mappings


def _json_path(array_path: str | None, rel_path: str) -> str:
    rel = rel_path.strip(".")
    if array_path:
        return f"{array_path}.{rel}" if rel else array_path
    return f"$.{rel}" if rel else "$"


def _discover_tables(conn: sqlite3.Connection, prefixes: tuple[str, ...]) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [row["name"] for row in rows if any(row["name"].startswith(p) for p in prefixes)]


def _table_info(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return conn.execute(f"PRAGMA table_info({_quote_ident(table)})").fetchall()


def _column_stats(
    conn: sqlite3.Connection, table: str, column: str, declared_type: str
) -> dict[str, int]:
    col = _quote_ident(column)
    empty_expr = f"SUM(CASE WHEN {col} = '' THEN 1 ELSE 0 END)" if _is_text_like(declared_type) else "0"
    row = conn.execute(
        f"""
        SELECT
          COUNT(*) AS total_rows,
          SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS null_rows,
          SUM(CASE WHEN {col} IS NOT NULL THEN 1 ELSE 0 END) AS non_null_rows,
          {empty_expr} AS empty_string_rows,
          COUNT(DISTINCT {col}) AS distinct_non_null_rows
        FROM {_quote_ident(table)}
        """
    ).fetchone()
    return {
        "total_rows": int(row["total_rows"] or 0),
        "null_rows": int(row["null_rows"] or 0),
        "non_null_rows": int(row["non_null_rows"] or 0),
        "empty_string_rows": int(row["empty_string_rows"] or 0),
        "distinct_non_null_rows": int(row["distinct_non_null_rows"] or 0),
    }


def _sample_safe_values(conn: sqlite3.Connection, table: str, column: str) -> list[Any]:
    if not _safe_sample_allowed(column):
        return []
    rows = conn.execute(
        f"""
        SELECT DISTINCT {_quote_ident(column)} AS value
        FROM {_quote_ident(table)}
        WHERE {_quote_ident(column)} IS NOT NULL
        ORDER BY {_quote_ident(column)}
        LIMIT 5
        """
    ).fetchall()
    return [row["value"] for row in rows]


def _parent_path(json_path: str) -> str | None:
    if json_path == "$" or "." not in json_path:
        return None
    return json_path.rsplit(".", 1)[0]


def _is_empty_value(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _path_value_status(payload: Any, json_path: str) -> tuple[bool, bool]:
    if json_path == "$":
        return True, not _is_empty_value(payload)
    tokens = _path_tokens(json_path)
    return _walk_path(payload, tokens)


def _path_exists(payload: Any, json_path: str) -> bool:
    exists, _non_empty = _path_value_status(payload, json_path)
    return exists


def _path_tokens(json_path: str) -> list[tuple[str, bool]]:
    body = json_path[2:] if json_path.startswith("$.") else json_path
    tokens: list[tuple[str, bool]] = []
    for segment in body.split("."):
        if not segment:
            continue
        if segment.endswith("[]"):
            tokens.append((segment[:-2], True))
        else:
            tokens.append((segment, False))
    return tokens


def _walk_path(node: Any, tokens: list[tuple[str, bool]]) -> tuple[bool, bool]:
    if not tokens:
        return True, not _is_empty_value(node)
    key, is_array = tokens[0]
    rest = tokens[1:]
    if not isinstance(node, dict) or key not in node:
        return False, False
    value = node[key]
    if is_array:
        if not isinstance(value, list):
            return False, False
        statuses = [_walk_path(item, rest) for item in value]
        return any(exists for exists, _non_empty in statuses), any(
            non_empty for _exists, non_empty in statuses
        )
    return _walk_path(value, rest)


def _raw_payload_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute(f"SELECT 1 FROM {_quote_ident(RAW_PAYLOAD_TABLE)} LIMIT 1").fetchone()
    except sqlite3.Error:
        return False
    return True


def _path_presence(
    conn: sqlite3.Connection, endpoint_key: str, json_path: str
) -> PathPresence | None:
    if not _raw_payload_available(conn):
        return None
    parent = _parent_path(json_path)
    rows = conn.execute(
        f"""
        SELECT payload_json
        FROM {_quote_ident(RAW_PAYLOAD_TABLE)}
        WHERE endpoint_key = ?
          AND is_current = 1
          AND raw_procore_payload_persisted = 1
          AND source_quality = 'live_full_payload'
        ORDER BY raw_payload_id
        """,
        (endpoint_key,),
    ).fetchall()
    present = 0
    non_empty = 0
    parent_present = 0
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        exists, has_value = _path_value_status(payload, json_path)
        if exists:
            present += 1
        if has_value:
            non_empty += 1
        if parent is not None and _path_exists(payload, parent):
            parent_present += 1
    inspected = len(rows)
    return PathPresence(
        endpoint_key=endpoint_key,
        json_path=json_path,
        payload_rows_inspected=inspected,
        path_present_count=present,
        path_non_empty_count=non_empty,
        path_missing_count=max(inspected - present, 0),
        parent_path_present_count=parent_present,
        source_quality_filter_used=(
            "is_current=1 AND raw_procore_payload_persisted=1 "
            "AND source_quality='live_full_payload'"
        ),
    )


def _root_cause(
    *,
    table: str,
    column: str,
    total_rows: int,
    classification: str,
    mapping: ColumnMapping | None,
    presence: PathPresence | None,
    deferred: dict[str, str] | None = None,
) -> tuple[str, str, bool]:
    if total_rows == 0:
        return ROOT_EMPTY_TABLE, "Table has zero rows; nullness does not prove projection failure.", False
    if _is_support_field(table, column):
        return ROOT_SUPPORT, "Metadata, provenance, guardrail, or support-table field.", False
    if deferred is not None and mapping is None:
        return (
            ROOT_UNMAPPED,
            f"Explicitly deferred with documented rationale: {deferred['rationale']}",
            False,
        )
    if mapping is None:
        suspected = classification in {"all_null", "mostly_null", "empty_string_instead_of_null"}
        return (
            ROOT_UNMAPPED,
            "Column exists in SQLite but no committed projection-registry mapping was found.",
            suspected,
        )
    if presence is None or presence.payload_rows_inspected == 0:
        return (
            ROOT_SOURCE_MISSING,
            "No current live_full_payload rows were available for this endpoint in raw landing.",
            False,
        )
    if presence.path_present_count == 0:
        if presence.parent_path_present_count > 0:
            return (
                ROOT_PATH_ABSENT,
                "Registry path was mapped, but current raw payloads contain the parent path without this leaf.",
                False,
            )
        return (
            ROOT_EXPECTED_OPTIONAL,
            "Registry path was mapped, but current raw payloads do not show usage for this path.",
            False,
        )
    if classification == "all_null" and presence.path_non_empty_count > 0:
        return (
            ROOT_PATH_PRESENT_NOT_WRITTEN,
            "Raw payload path has non-empty values, but the projected column is all-null.",
            True,
        )
    if classification == "all_null":
        return (
            ROOT_EXPECTED_OPTIONAL,
            "Registry path is present only as null/empty in current raw payloads.",
            False,
        )
    if classification == "mostly_null":
        return (
            ROOT_EXPECTED_OPTIONAL,
            "Column has some projected values and appears optional in the current payload set.",
            False,
        )
    return (
        ROOT_EXPECTED_OPTIONAL,
        "Column is populated or partially populated; no projection defect indicated by null profile.",
        False,
    )


def audit_database(
    db_path: str | Path,
    *,
    table_prefixes: tuple[str, ...] = DEFAULT_PREFIXES,
    min_null_rate: float = 0.95,
    include_mostly_null: bool = False,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    with connect_readonly(db_path) as conn:
        mappings = _registry_mappings()
        tables = _discover_tables(conn, table_prefixes)
        table_profiles: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        path_presence_cache: dict[tuple[str, str], PathPresence | None] = {}

        for table in tables:
            columns = _table_info(conn, table)
            table_total = 0
            table_records: list[dict[str, Any]] = []
            for column_info in columns:
                column = str(column_info["name"])
                declared_type = str(column_info["type"] or "")
                stats = _column_stats(conn, table, column, declared_type)
                table_total = stats["total_rows"]
                classification = _classify_population(
                    stats["total_rows"],
                    stats["null_rows"],
                    stats["empty_string_rows"],
                    min_null_rate,
                )
                mapping = mappings.get((table, column))
                presence = None
                if mapping and classification in {"all_null", "mostly_null", "empty_string_instead_of_null"}:
                    cache_key = (mapping.endpoint_key, mapping.json_path)
                    if cache_key not in path_presence_cache:
                        path_presence_cache[cache_key] = _path_presence(
                            conn, mapping.endpoint_key, mapping.json_path
                        )
                    presence = path_presence_cache[cache_key]
                deferred = _deferred_disposition(table, column)
                root, note, suspected = _root_cause(
                    table=table,
                    column=column,
                    total_rows=stats["total_rows"],
                    classification=classification,
                    mapping=mapping,
                    presence=presence,
                    deferred=deferred,
                )
                record = {
                    "table": table,
                    "column": column,
                    "declared_type": declared_type,
                    **stats,
                    "table_total_rows": stats["total_rows"],
                    "null_rate": round(
                        stats["null_rows"] / stats["total_rows"], 6
                        if stats["total_rows"]
                        else 0
                    )
                    if stats["total_rows"]
                    else 0.0,
                    "classification": classification,
                    "root_cause_class": root,
                    "suspected_projection_defect": suspected,
                    "suspected_root_cause": note,
                    "endpoint_key": mapping.endpoint_key if mapping else None,
                    "endpoint_family": mapping.endpoint_family if mapping else None,
                    "table_role": mapping.table_role if mapping else None,
                    "json_path": mapping.json_path if mapping else None,
                    "raw_payload_path_checked": presence is not None,
                    "raw_payload_values_emitted": False,
                    "safe_metadata_values": _sample_safe_values(conn, table, column),
                    "explicitly_deferred": deferred is not None,
                    "deferred_batch": deferred["batch"] if deferred else None,
                    "deferred_disposition": deferred["disposition"] if deferred else None,
                    "deferred_rationale": deferred["rationale"] if deferred else None,
                    "recommended_action": _recommended_action(root, suspected, deferred),
                }
                if presence is not None:
                    record["raw_path_presence"] = {
                        "endpoint_key": presence.endpoint_key,
                        "json_path": presence.json_path,
                        "payload_rows_inspected": presence.payload_rows_inspected,
                        "path_present_count": presence.path_present_count,
                        "path_non_empty_count": presence.path_non_empty_count,
                        "path_missing_count": presence.path_missing_count,
                        "parent_path_present_count": presence.parent_path_present_count,
                        "source_quality_filter_used": presence.source_quality_filter_used,
                        "raw_payload_values_emitted": presence.raw_payload_values_emitted,
                    }
                records.append(record)
                table_records.append(record)
            table_profiles.append(
                {
                    "table": table,
                    "total_rows": table_total,
                    "column_count": len(columns),
                    "all_null_columns": sum(1 for r in table_records if r["classification"] == "all_null"),
                    "suspected_projection_defect_columns": sum(
                        1 for r in table_records if r["suspected_projection_defect"]
                    ),
                }
            )

    priority = _priority_records(records, include_mostly_null=include_mostly_null)
    summary = {
        "tables_audited": len(table_profiles),
        "columns_audited": len(records),
        "all_null_fields": sum(1 for r in records if r["classification"] == "all_null"),
        "mostly_null_fields": sum(1 for r in records if r["classification"] == "mostly_null"),
        "suspected_projection_defects": sum(1 for r in records if r["suspected_projection_defect"]),
        "expected_optional_fields": sum(
            1 for r in records if r["root_cause_class"] == ROOT_EXPECTED_OPTIONAL
        ),
        "support_or_guardrail_fields": sum(1 for r in records if r["root_cause_class"] == ROOT_SUPPORT),
        "empty_tables": sum(1 for t in table_profiles if t["total_rows"] == 0),
        "explicitly_deferred_fields": sum(1 for r in records if r["explicitly_deferred"]),
        "priority_field_count": len(priority),
    }
    return {
        "command": "scripts/proofs/procore_null_projection_audit.py",
        "db_path": str(db_path),
        "started_at_utc": started,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "table_prefixes": list(table_prefixes),
        "min_null_rate": min_null_rate,
        "include_mostly_null": include_mostly_null,
        "summary": summary,
        "priority_fields": priority,
        "tables": table_profiles,
        "columns": records,
        "guardrails": {
            "read_only_sqlite": True,
            "query_only": True,
            "live_calls_disabled": True,
            "writeback": "none",
            "raw_payload_values_emitted": False,
        },
    }


def _recommended_action(
    root_cause: str, suspected: bool, deferred: dict[str, str] | None = None
) -> str:
    if deferred is not None:
        return (
            "No immediate projection remediation; preserve documented deferral unless "
            "separate source-path proof approves mapping or deprecation."
        )
    if root_cause == ROOT_SUPPORT:
        return "No remediation; preserve guardrail/provenance semantics."
    if root_cause == ROOT_EMPTY_TABLE:
        return "No projection conclusion; refresh/source coverage must exist before judging columns."
    if root_cause == ROOT_UNMAPPED:
        return "Review migration/read-model origin and add or document projection mapping only after approval."
    if root_cause == ROOT_PATH_PRESENT_NOT_WRITTEN:
        return "Investigate projection extraction/write path for this mapped field."
    if root_cause == ROOT_PATH_ABSENT:
        return "Review registry path against current payload shape before changing schema."
    if root_cause == ROOT_SOURCE_MISSING:
        return "Verify endpoint freshness/source coverage before changing projection code."
    if root_cause == ROOT_EXPECTED_OPTIONAL:
        return "No immediate remediation; document as optional unless new evidence shows missing projection."
    if suspected:
        return "Investigate as suspected projection defect."
    return "No remediation recommended by null-profile audit."


def _priority_records(
    records: list[dict[str, Any]], *, include_mostly_null: bool
) -> list[dict[str, Any]]:
    selected = [
        r
        for r in records
        if r["classification"] == "all_null"
        or (include_mostly_null and r["classification"] == "mostly_null")
        or r["suspected_projection_defect"]
    ]
    return sorted(
        selected,
        key=lambda r: (
            not r["suspected_projection_defect"],
            r["classification"] != "all_null",
            -int(r["total_rows"]),
            r["table"],
            r["column"],
        ),
    )


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Procore Null Projection Audit",
        "",
        "## Executive Summary",
        "",
        f"- Tables audited: `{summary['tables_audited']}`",
        f"- Columns audited: `{summary['columns_audited']}`",
        f"- All-null fields: `{summary['all_null_fields']}`",
        f"- Mostly-null fields: `{summary['mostly_null_fields']}`",
        f"- Suspected projection defects: `{summary['suspected_projection_defects']}`",
        f"- Expected optional fields: `{summary['expected_optional_fields']}`",
        f"- Support/guardrail fields: `{summary['support_or_guardrail_fields']}`",
        f"- Empty tables: `{summary['empty_tables']}`",
        f"- Explicitly deferred fields: `{summary['explicitly_deferred_fields']}`",
        "",
        "## High-Priority Remediation Review",
        "",
        "| table | column | table rows | null % | classification | root cause | endpoint | recommendation |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["priority_fields"][:200]:
        lines.append(
            "| {table} | {column} | {rows} | {null_pct:.1f} | {classification} | "
            "{root} | {endpoint} | {action} |".format(
                table=row["table"],
                column=row["column"],
                rows=row["table_total_rows"],
                null_pct=float(row["null_rate"]) * 100.0,
                classification=row["classification"],
                root=row["root_cause_class"],
                endpoint=row.get("endpoint_key") or "",
                action=row["recommended_action"],
            )
        )
    if not payload["priority_fields"]:
        lines.append("|  |  | 0 | 0.0 |  |  |  | No priority fields found. |")

    lines += [
        "",
        "## Root-Cause Notes",
        "",
    ]
    for row in payload["priority_fields"][:200]:
        lines.append(
            f"- `{row['table']}.{row['column']}`: `{row['root_cause_class']}`; "
            f"rows={row['table_total_rows']}; null_rate={float(row['null_rate']) * 100.0:.1f}%; "
            f"{row['suspected_root_cause']}"
        )
        if row.get("explicitly_deferred"):
            lines.append(
                f"  Deferred: `{row['deferred_batch']}` / `{row['deferred_disposition']}`; "
                f"{row['deferred_rationale']}"
            )
        presence = row.get("raw_path_presence")
        if presence:
            lines.append(
                "  Path presence: "
                f"`{presence['json_path']}` inspected={presence['payload_rows_inspected']} "
                f"present={presence['path_present_count']} missing={presence['path_missing_count']} "
                "values_emitted=false."
            )

    lines += [
        "",
        "## Table-by-Table Null Profile",
        "",
        "| table | rows | columns | all-null columns | suspected defects |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for table in payload["tables"]:
        lines.append(
            f"| {table['table']} | {table['total_rows']} | {table['column_count']} | "
            f"{table['all_null_columns']} | {table['suspected_projection_defect_columns']} |"
        )

    lines += [
        "",
        "## Body-Free Privacy Attestation",
        "",
        "- Raw payload JSON was inspected only for key/path presence counts.",
        "- The JSON and Markdown reports emit path names and counts only, not payload fragments or values.",
        "- `raw_payload_values_emitted` is `false` for every column/path record.",
        "",
        "## Remediation Not Applied",
        "",
        "No schema, registry, migration, projection, scheduled-refresh, live-fetch, or read-model remediation was applied by this audit.",
        "",
    ]
    return "\n".join(lines)


def write_reports(payload: dict[str, Any], json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    markdown_out.write_text(render_markdown(payload), encoding="utf-8")


def _default_evidence_paths() -> tuple[Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path("docs/evidence/procore-null-projection-audit") / stamp
    return root / "procore-null-projection-audit.json", root / "procore-null-projection-audit.md"


def parse_args() -> argparse.Namespace:
    json_default, markdown_default = _default_evidence_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--table-prefix", action="append", dest="table_prefixes")
    parser.add_argument("--min-null-rate", type=float, default=0.95)
    parser.add_argument("--include-mostly-null", action="store_true")
    parser.add_argument("--json-out", default=str(json_default))
    parser.add_argument("--markdown-out", default=str(markdown_default))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prefixes = tuple(args.table_prefixes or DEFAULT_PREFIXES)
    payload = audit_database(
        args.db_path,
        table_prefixes=prefixes,
        min_null_rate=args.min_null_rate,
        include_mostly_null=args.include_mostly_null,
    )
    write_reports(payload, Path(args.json_out), Path(args.markdown_out))
    print(
        json.dumps(
            {
                "ok": True,
                "json_out": args.json_out,
                "markdown_out": args.markdown_out,
                "summary": payload["summary"],
                "guardrails": payload["guardrails"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
