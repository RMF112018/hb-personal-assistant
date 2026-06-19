#!/usr/bin/env python3
"""Body-free raw-payload source-path audit for Procore null projection fields."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from hb_assistant.procore import projection_paths as pp
from hb_assistant.procore import projection_registry

DEFAULT_DB_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "HB Personal Assistant"
    / "db"
    / "hb-personal-assistant.sqlite"
)
RAW_PAYLOAD_TABLE = "procore_endpoint_raw_payloads"

SUPPORT_ROOTS = {
    "empty_table_no_projection_evidence",
    "support_or_guardrail_field",
}
ROOT_UNMAPPED = "schema_column_not_in_projection_registry"
NULL_CLASSES = {"all_null", "mostly_null", "empty_string_instead_of_null"}
DATE_LEAVES = (
    "closed_at",
    "closed_on",
    "closed_date",
    "created_at",
    "updated_at",
    "due_date",
    "date",
    "datetime",
)
OBJECT_REPRESENTATIVE_KEYS = ("id", "name", "login", "code", "flat_code", "title", "number")
ALLOWED_ACTIONS = {
    "map_scalar_path",
    "map_object_id",
    "map_object_name",
    "map_object_json_only_if_existing_column_is_json",
    "map_child_table",
    "leave_unmapped_source_absent",
    "leave_unmapped_expected_optional",
    "schema_migration_needed",
    "deprecation_candidate",
    "no_mapping_already_populated",
    "no_mapping_mapped_optional",
    "repair_projection_write_path",
}
SWEEP_CLASSIFICATIONS = {
    "already_populated",
    "source_path_exists_not_mapped",
    "mapped_source_present_projection_not_writing",
    "source_absent_in_current_payloads",
    "expected_optional_source_null",
    "schema_artifact_candidate",
}
PATCH1_SCALAR_FIELDS = {
    ("procore_ep_commitment_change_orders", "change_order_change_reason_id"),
    ("procore_ep_commitment_change_orders", "change_order_change_reason_change_reason"),
    ("procore_ep_commitment_change_orders", "designated_reviewer_id"),
    ("procore_ep_commitment_change_orders", "designated_reviewer_name"),
    ("procore_ep_commitment_change_orders", "received_from_id"),
    ("procore_ep_commitment_change_orders", "received_from_name"),
    ("procore_ep_commitment_change_orders", "reviewed_by_id"),
    ("procore_ep_commitment_change_orders", "reviewed_by_name"),
    ("procore_ep_prime_change_orders", "change_order_change_reason_id"),
    ("procore_ep_prime_change_orders", "change_order_change_reason_change_reason"),
    ("procore_ep_prime_change_orders", "designated_reviewer_id"),
    ("procore_ep_prime_change_orders", "designated_reviewer_name"),
    ("procore_ep_prime_change_orders", "received_from_id"),
    ("procore_ep_prime_change_orders", "received_from_name"),
}
COMPANY_ID_POLICY_FIELDS = {
    ("procore_ep_projects", "company_id"),
    ("procore_ep_purchase_order_line_items", "company_id"),
    ("procore_ep_rfqs", "company_id"),
    ("procore_ep_rfqs_change_event_change_event_line_items", "company_id"),
}
BUDGET_DETAIL_DEAD_CONVENIENCE_FIELDS = {
    ("procore_ep_budget_detail_rows", "actual_cost"),
    ("procore_ep_budget_detail_rows", "cost_type"),
    ("procore_ep_budget_detail_rows", "cost_type_id"),
    ("procore_ep_budget_detail_rows", "line_item_type_id"),
}
BUDGET_DETAIL_OPTIONAL_FIELDS = {
    ("procore_ep_budget_detail_row_cells", "currency_iso_code"),
}
BUDGET_DETAIL_READ_MODEL_ARTIFACT_FIELDS = {
    ("procore_ep_budget_detail_columns", "company_id"),
    ("procore_ep_budget_detail_columns", "visible"),
}
SCALAR_MAPPING_ACTIONS = {"map_scalar_path", "map_object_id", "map_object_name"}


@dataclass(frozen=True)
class TablePlan:
    endpoint_key: str
    endpoint_family: str
    role: str
    array_path: str | None
    existing_columns: frozenset[str]
    column_rels: dict[str, str]


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _readonly_uri(path: Path) -> str:
    return f"file:{quote(str(path.resolve()), safe='/')}?mode=ro"


def connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(_readonly_uri(Path(db_path)), uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _table_plans() -> dict[str, TablePlan]:
    out: dict[str, TablePlan] = {}
    for endpoint_key, plan in projection_registry.load_registry().items():
        out[plan.primary_table] = TablePlan(
            endpoint_key=endpoint_key,
            endpoint_family=plan.endpoint_family,
            role="primary",
            array_path=None,
            existing_columns=frozenset(column for _rel, column in plan.primary_columns),
            column_rels={column: rel for rel, column in plan.primary_columns},
        )
        for child in plan.child_tables:
            out[child.table] = TablePlan(
                endpoint_key=endpoint_key,
                endpoint_family=plan.endpoint_family,
                role="child",
                array_path=child.array_path,
                existing_columns=frozenset(column for _rel, column in child.columns),
                column_rels={column: rel for rel, column in child.columns},
            )
    return out


def _physical_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({_quote_ident(table)})")}
    except sqlite3.Error:
        return set()


def _column_info(conn: sqlite3.Connection, table: str) -> dict[str, dict[str, Any]]:
    try:
        return {
            str(row["name"]): dict(row)
            for row in conn.execute(f"PRAGMA table_info({_quote_ident(table)})")
        }
    except sqlite3.Error:
        return {}


def _column_stats(conn: sqlite3.Connection, table: str, column: str) -> dict[str, Any]:
    try:
        row = conn.execute(
            f"""
            SELECT
              COUNT(*) AS total_rows,
              SUM(CASE WHEN {_quote_ident(column)} IS NULL THEN 1 ELSE 0 END) AS null_rows,
              SUM(CASE WHEN {_quote_ident(column)} IS NOT NULL THEN 1 ELSE 0 END) AS non_null_rows
            FROM {_quote_ident(table)}
            """
        ).fetchone()
    except sqlite3.Error:
        return {"total_rows": None, "null_rows": None, "non_null_rows": None, "null_rate": None}
    total = int(row["total_rows"] or 0)
    nulls = int(row["null_rows"] or 0)
    non_null = int(row["non_null_rows"] or 0)
    return {
        "total_rows": total,
        "null_rows": nulls,
        "non_null_rows": non_null,
        "null_rate": round(nulls / total, 6) if total else 0.0,
    }


def _raw_payloads(conn: sqlite3.Connection, endpoint_key: str) -> list[dict[str, Any]]:
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
    payloads: list[dict[str, Any]] = []
    for row in rows:
        try:
            loaded = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(loaded, dict):
            payloads.append(loaded)
    return payloads


def _is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def _tokens(json_path: str) -> list[tuple[str, bool]]:
    body = json_path[2:] if json_path.startswith("$.") else json_path
    out: list[tuple[str, bool]] = []
    for segment in body.split("."):
        if not segment:
            continue
        out.append((segment[:-2], True) if segment.endswith("[]") else (segment, False))
    return out


def _values_at(node: Any, json_path: str) -> list[Any]:
    values = [node]
    for key, is_array in _tokens(json_path):
        next_values: list[Any] = []
        for value in values:
            if not isinstance(value, dict) or key not in value:
                continue
            child = value[key]
            if is_array:
                if isinstance(child, list):
                    next_values.extend(child)
            else:
                next_values.append(child)
        values = next_values
        if not values:
            break
    return values


def _path_check(payloads: list[dict[str, Any]], json_path: str) -> dict[str, Any]:
    present = 0
    non_empty = 0
    empty = 0
    object_keys: Counter[str] = Counter()
    for payload in payloads:
        values = _values_at(payload, json_path)
        if values:
            present += 1
        if any(not _is_empty(value) for value in values):
            non_empty += 1
        if values and all(_is_empty(value) for value in values):
            empty += 1
        for value in values:
            if isinstance(value, dict):
                object_keys.update(str(key) for key in value)
    return {
        "json_path": json_path,
        "path_present_count": present,
        "path_non_empty_count": non_empty,
        "path_null_or_empty_count": empty,
        "path_missing_count": max(len(payloads) - present, 0),
        "object_keys_present": sorted(object_keys)[:40],
        "raw_payload_values_emitted": False,
    }


def _observed_paths(payloads: list[dict[str, Any]]) -> set[str]:
    paths: set[str] = set()
    for payload in payloads:
        paths.update(pp.walk_paths(payload))
    return paths


def _date_candidates(column: str) -> list[str]:
    candidates: list[str] = []
    if column in DATE_LEAVES or column.endswith(("_at", "_date", "_on")):
        candidates.extend(f"$.{leaf}" for leaf in DATE_LEAVES)
        if "_" in column:
            prefix, _, suffix = column.rpartition("_")
            if suffix in {"at", "date", "on"} and prefix:
                candidates.extend(f"$.{prefix}.{leaf}" for leaf in DATE_LEAVES)
    return candidates


def _company_candidates(plan: TablePlan, column: str) -> list[str]:
    if column != "company_id":
        return []
    candidates = ["$.company_id", "$.company.id", "$.project.company_id", "$.project.company.id"]
    if plan.array_path:
        candidates.extend(
            [
                f"{plan.array_path}[].company_id",
                f"{plan.array_path}[].company.id",
                f"{plan.array_path}[].project.company_id",
            ]
        )
    return candidates


def _basic_candidates(plan: TablePlan, column: str, observed: set[str]) -> list[str]:
    base = column
    candidates = [f"$.{base}"]
    if plan.array_path:
        candidates.append(f"{plan.array_path}[].{base}")
    candidates.extend(_date_candidates(column))
    candidates.extend(_company_candidates(plan, column))

    for path in observed:
        rel_anchor = plan.array_path if plan.array_path and path.startswith(plan.array_path) else None
        sanitized = pp.sanitize_identifier(path, relative_to=rel_anchor)
        leaf = pp.leaf_key(path)
        if sanitized == column or leaf == column:
            candidates.append(path)
        if column.endswith("_id") and sanitized == column[:-3]:
            candidates.append(path)
        if column.endswith("_name") and sanitized == column[:-5]:
            candidates.append(path)
    return sorted(dict.fromkeys(candidates))


def _registry_path(plan: TablePlan, column: str) -> str | None:
    rel = plan.column_rels.get(column)
    if rel is None:
        return None
    if plan.array_path:
        return f"{plan.array_path}[].{rel}"
    return f"$.{rel}"


def _is_date_like_column(column: str) -> bool:
    return (
        column in DATE_LEAVES
        or column.endswith("_at")
        or column.endswith("_date")
        or column.endswith("_on")
    )


def _has_decomposition_columns(column: str, physical_columns: set[str]) -> bool:
    prefixes = {column, column.removesuffix("_id").removesuffix("_name").removesuffix("_login")}
    for prefix in prefixes:
        if not prefix:
            continue
        if any(f"{prefix}_{suffix}" in physical_columns for suffix in OBJECT_REPRESENTATIVE_KEYS):
            return True
    return False


def _recommend(
    *,
    column: str,
    declared_type: str,
    plan: TablePlan,
    physical_columns: set[str],
    checks: list[dict[str, Any]],
    root_cause: str,
) -> tuple[str, str, str]:
    is_unmapped_defect = root_cause == ROOT_UNMAPPED
    ranked_checks = checks
    if column in DATE_LEAVES or column.endswith(("_at", "_date", "_on")):
        exact_date = [
            check
            for check in checks
            if check["json_path"] == f"$.{column}" or check["json_path"].endswith(f".{column}")
        ]
        if exact_date:
            ranked_checks = exact_date
    if plan.array_path:
        scoped = [
            check
            for check in ranked_checks
            if check["json_path"].startswith(f"{plan.array_path}[]")
        ]
        if scoped:
            ranked_checks = scoped
    best = max(
        ranked_checks,
        key=lambda c: (
            c["path_non_empty_count"],
            c["path_present_count"],
            not c["object_keys_present"],
        ),
        default=None,
    )
    if best is None or best["path_present_count"] == 0:
        return "leave_unmapped_source_absent", "source_absent_in_current_payloads", "high"
    if best["path_non_empty_count"] == 0:
        return "leave_unmapped_expected_optional", "expected_optional_source_null", "high"
    if not is_unmapped_defect:
        return "leave_unmapped_expected_optional", "source_path_observed_for_non_unmapped_field", "medium"

    object_keys = set(best["object_keys_present"])
    is_object = bool(object_keys)
    if column == "company_id" and best["json_path"] != "$.company_id":
        return "schema_migration_needed", "company_id_requires_derivation_policy", "medium"
    if is_object:
        if "id" in object_keys and column.endswith("_id"):
            return "map_object_id", "source_path_exists_not_mapped", "high"
        if {"name", "title", "login"} & object_keys and column.endswith(("_name", "_title", "_login")):
            return "map_object_name", "source_path_exists_not_mapped", "high"
        if _has_decomposition_columns(column, physical_columns):
            return "deprecation_candidate", "object_container_requires_decomposition", "high"
        if "JSON" in declared_type.upper():
            return "map_object_json_only_if_existing_column_is_json", "source_path_exists_not_mapped", "medium"
        return "deprecation_candidate", "object_container_requires_decomposition", "high"
    if plan.role == "child":
        return "map_child_table", "source_path_exists_not_mapped", "high"
    return "map_scalar_path", "source_path_exists_not_mapped", "high"


def _selected_fields(current_audit: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in current_audit.get("columns", []):
        key = (row.get("table"), row.get("column"))
        if key in seen:
            continue
        if row.get("root_cause_class") in SUPPORT_ROOTS:
            continue
        selected = (
            row.get("explicitly_deferred") is True
            or row.get("suspected_projection_defect") is True
            or row.get("classification") in NULL_CLASSES
        )
        if selected:
            out.append(row)
            seen.add(key)
    return out


def _audit_lookup(current_audit: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row.get("table")), str(row.get("column"))): row
        for row in current_audit.get("columns", [])
    }


def _field_from_physical(
    *,
    conn: sqlite3.Connection,
    table: str,
    column: str,
    current_lookup: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    found = current_lookup.get((table, column))
    if found is not None:
        stats = _column_stats(conn, table, column)
        merged = dict(found)
        merged.setdefault("table_total_rows", stats["total_rows"])
        merged.setdefault("total_rows", stats["total_rows"])
        merged.setdefault("null_rows", stats["null_rows"])
        merged.setdefault("non_null_rows", stats["non_null_rows"])
        merged.setdefault("null_rate", stats["null_rate"])
        return merged
    info = _column_info(conn, table).get(column)
    if info is None:
        return None
    stats = _column_stats(conn, table, column)
    return {
        "table": table,
        "column": column,
        "classification": "not_null_profiled",
        "declared_type": info.get("type"),
        "root_cause_class": None,
        "suspected_projection_defect": False,
        "table_total_rows": stats["total_rows"],
        "total_rows": stats["total_rows"],
        "null_rows": stats["null_rows"],
        "non_null_rows": stats["non_null_rows"],
        "null_rate": stats["null_rate"],
    }


def _explicit_fields(
    *,
    conn: sqlite3.Connection,
    plans: dict[str, TablePlan],
    current_lookup: dict[tuple[str, str], dict[str, Any]],
    field_specs: set[tuple[str, str]],
    date_field_sweep: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for table, column in sorted(field_specs):
        field = _field_from_physical(
            conn=conn, table=table, column=column, current_lookup=current_lookup
        )
        if field is not None:
            out.append(field | {"selection_reason": "explicit_field"})
            seen.add((table, column))
    if not date_field_sweep:
        return out
    for table in sorted(plans):
        for column in sorted(_physical_columns(conn, table)):
            key = (table, column)
            if key in seen or not _is_date_like_column(column):
                continue
            field = _field_from_physical(
                conn=conn, table=table, column=column, current_lookup=current_lookup
            )
            if field is not None:
                out.append(field | {"selection_reason": "date_field_sweep"})
                seen.add(key)
    return out


def _sweep_recommendation(
    *,
    mapped: bool,
    non_null_rows: int | None,
    checks: list[dict[str, Any]],
) -> tuple[str, str, str]:
    if non_null_rows and non_null_rows > 0:
        return "no_mapping_already_populated", "already_populated", "high"
    best = max(
        checks,
        key=lambda c: (
            c["path_non_empty_count"],
            c["path_present_count"],
            not c["object_keys_present"],
        ),
        default=None,
    )
    if best is not None and best["path_non_empty_count"] > 0:
        if mapped:
            return "repair_projection_write_path", "mapped_source_present_projection_not_writing", "high"
        return "map_scalar_path", "source_path_exists_not_mapped", "high"
    if best is not None and best["path_present_count"] > 0:
        return "no_mapping_mapped_optional", "expected_optional_source_null", "high"
    if mapped:
        return "leave_unmapped_source_absent", "source_absent_in_current_payloads", "high"
    return "deprecation_candidate", "schema_artifact_candidate", "medium"


def _raw_detection_for_field(field: dict[str, Any]) -> dict[str, Any]:
    return {
        "classification": field.get("classification"),
        "root_cause_class": field.get("root_cause_class"),
        "suspected_projection_defect": bool(field.get("suspected_projection_defect")),
    }


def _post_proof_decision(
    *,
    table: str,
    column: str,
    action: str,
    classification: str,
    confidence: str,
    selection_reason: str,
) -> dict[str, Any]:
    key = (table, column)
    if key in PATCH1_SCALAR_FIELDS:
        return {
            "decision_class": "patch1_scalar_decomposition_verified",
            "decision_status": "resolved_by_existing_mapping_and_replay_proof",
            "mapping_candidate": False,
            "next_action": "no_action_patch1_scalar_decomposition_verified",
            "evidence_basis": "Patch 1 copied-DB reset replay evidence.",
        }
    if key in BUDGET_DETAIL_DEAD_CONVENIENCE_FIELDS:
        return {
            "decision_class": "budget_detail_dead_convenience_column",
            "decision_status": "no_action",
            "mapping_candidate": False,
            "next_action": "no_action_dead_column_candidate",
            "evidence_basis": "Batch 2 Budget Detail source-path triage found no row-level or dynamic-cell source support.",
        }
    if key in BUDGET_DETAIL_OPTIONAL_FIELDS:
        return {
            "decision_class": "expected_optional_no_action",
            "decision_status": "no_action",
            "mapping_candidate": False,
            "next_action": "no_action_expected_optional",
            "evidence_basis": "Batch 2 triage found no approved required cell-level currency source proof.",
        }
    if key in BUDGET_DETAIL_READ_MODEL_ARTIFACT_FIELDS:
        return {
            "decision_class": "budget_detail_read_model_schema_artifact",
            "decision_status": "documentation_or_deprecation_decision",
            "mapping_candidate": False,
            "next_action": "document_schema_artifact",
            "evidence_basis": "Budget Detail read-model artifact; no approved source-path proof supports mapping.",
        }
    if key in COMPANY_ID_POLICY_FIELDS or (
        column == "company_id" and classification == "company_id_requires_derivation_policy"
    ):
        return {
            "decision_class": "company_id_policy_deferred",
            "decision_status": "policy_deferred",
            "mapping_candidate": False,
            "next_action": "defer_company_id_policy",
            "evidence_basis": "Standard company_id requires repository-wide derivation policy and table convention proof.",
        }
    if classification == "object_container_requires_decomposition":
        return {
            "decision_class": "object_container_requires_decomposition_or_deprecation",
            "decision_status": "design_decision_required",
            "mapping_candidate": False,
            "next_action": "approve_decomposition_schema_design_next_or_deprecation",
            "evidence_basis": "Raw payload path is an object/container; whole-object projection into bare scalar column is disallowed.",
        }
    if classification == "source_absent_in_current_payloads":
        return {
            "decision_class": "source_absent_in_current_payloads",
            "decision_status": "no_current_mapping_action",
            "mapping_candidate": False,
            "next_action": "no_action_source_absent_current_payloads",
            "evidence_basis": "Current local live_full_payload rows do not contain a non-empty source path.",
        }
    if classification in {
        "expected_optional_source_null",
        "source_path_observed_for_non_unmapped_field",
        "already_populated",
    }:
        return {
            "decision_class": "expected_optional_no_action",
            "decision_status": "no_current_mapping_action",
            "mapping_candidate": False,
            "next_action": "no_action_expected_optional",
            "evidence_basis": "Current source proof indicates optional, already mapped, or already populated behavior.",
        }
    if action in SCALAR_MAPPING_ACTIONS and confidence == "high":
        return {
            "decision_class": "high_confidence_scalar_mapping_candidate",
            "decision_status": "unresolved_mapping_candidate",
            "mapping_candidate": True,
            "next_action": "approve_mapping_patch_next",
            "evidence_basis": "Non-empty scalar source path exists with compatible destination but no mapping/projection proof.",
        }
    if action == "repair_projection_write_path" and confidence == "high":
        return {
            "decision_class": "mapped_source_present_projection_not_writing",
            "decision_status": "unresolved_projection_write_candidate",
            "mapping_candidate": True,
            "next_action": "repair_projection_write_path_next",
            "evidence_basis": "Mapped source path is non-empty but the destination is not populated.",
        }
    if selection_reason == "date_field_sweep":
        return {
            "decision_class": "date_sweep_clear",
            "decision_status": "no_current_mapping_action",
            "mapping_candidate": False,
            "next_action": "no_action_date_sweep_clear",
            "evidence_basis": "Date/datetime sweep found no source-backed unmapped date mapping requirement for this field.",
        }
    if classification == "schema_artifact_candidate":
        return {
            "decision_class": "no_current_mapping_action",
            "decision_status": "schema_artifact_candidate",
            "mapping_candidate": False,
            "next_action": "document_schema_artifact",
            "evidence_basis": "No current source-path proof supports mapping this schema column.",
        }
    return {
        "decision_class": "no_current_mapping_action",
        "decision_status": "no_current_mapping_action",
        "mapping_candidate": False,
        "next_action": "no_action",
        "evidence_basis": "No current high-confidence scalar mapping action is supported by source proof.",
    }


def _record_for_field(
    *,
    conn: sqlite3.Connection,
    field: dict[str, Any],
    plan: TablePlan,
    payloads: list[dict[str, Any]],
    observed: set[str],
    strict: bool,
    explicit_mode: bool,
) -> dict[str, Any]:
    table = str(field.get("table"))
    column = str(field.get("column"))
    physical_columns = _physical_columns(conn, table)
    registry_path = _registry_path(plan, column)
    candidates = [registry_path] if registry_path else _basic_candidates(plan, column, observed)
    if not candidates:
        candidates = _basic_candidates(plan, column, observed)
    checks = [_path_check(payloads, candidate) for candidate in sorted(dict.fromkeys(candidates))]
    if explicit_mode:
        action, classification, confidence = _sweep_recommendation(
            mapped=registry_path is not None,
            non_null_rows=field.get("non_null_rows"),
            checks=checks,
        )
    else:
        action, classification, confidence = _recommend(
            column=column,
            declared_type=str(field.get("declared_type") or ""),
            plan=plan,
            physical_columns=physical_columns,
            checks=checks,
            root_cause=str(field.get("root_cause_class") or ""),
        )
    assert action in ALLOWED_ACTIONS
    if explicit_mode:
        assert classification in SWEEP_CLASSIFICATIONS
    child_items = 0
    if plan.array_path:
        for payload in payloads:
            child_items += len(_values_at(payload, plan.array_path + "[]"))
    object_keys = sorted(
        {
            key
            for check in checks
            for key in check.get("object_keys_present", [])
        }
    )
    selection_reason = field.get("selection_reason", "current_audit_candidate")
    post_proof_decision = _post_proof_decision(
        table=table,
        column=column,
        action=action,
        classification=classification,
        confidence=confidence,
        selection_reason=str(selection_reason),
    )
    return {
        "table": table,
        "column": column,
        "declared_type": field.get("declared_type"),
        "row_count": field.get("table_total_rows") or field.get("total_rows"),
        "null_count": field.get("null_rows"),
        "non_null_count": field.get("non_null_rows"),
        "null_rate": field.get("null_rate"),
        "inferred_endpoint_key": plan.endpoint_key,
        "endpoint_family": plan.endpoint_family,
        "current_root_cause_class": field.get("root_cause_class"),
        "current_null_classification": field.get("classification"),
        "selection_reason": selection_reason,
        "inferred_table_role": plan.role,
        "associated_raw_endpoint_key": plan.endpoint_key,
        "registry_mapped": registry_path is not None,
        "registry_json_path": registry_path,
        "raw_payload_rows_inspected": len(payloads),
        "raw_child_items_inspected": child_items,
        "candidate_json_paths_checked": checks,
        "object_keys_present": object_keys[:40],
        "recommended_mapping": action,
        "classification": classification,
        "confidence": confidence,
        "strict": strict,
        "raw_detection": _raw_detection_for_field(field),
        "post_proof_decision": post_proof_decision,
        "raw_payload_values_emitted": False,
    }


def audit_source_paths(
    *,
    db_path: str | Path,
    current_audit_json: str | Path,
    endpoints: set[str] | None = None,
    tables: set[str] | None = None,
    strict: bool = False,
    explicit_fields: set[tuple[str, str]] | None = None,
    date_field_sweep: bool = False,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    current_audit = json.loads(Path(current_audit_json).read_text(encoding="utf-8"))
    plans = _table_plans()
    records: list[dict[str, Any]] = []
    payload_cache: dict[str, list[dict[str, Any]]] = {}
    observed_cache: dict[str, set[str]] = {}

    with connect_readonly(db_path) as conn:
        current_lookup = _audit_lookup(current_audit)
        selected = _selected_fields(current_audit)
        selected.extend(
            _explicit_fields(
                conn=conn,
                plans=plans,
                current_lookup=current_lookup,
                field_specs=explicit_fields or set(),
                date_field_sweep=date_field_sweep,
            )
        )
        seen: set[tuple[str, str, str]] = set()
        for field in selected:
            table = str(field.get("table"))
            column = str(field.get("column"))
            reason = str(field.get("selection_reason", "current_audit_candidate"))
            unique_key = (table, column, reason)
            if unique_key in seen:
                continue
            seen.add(unique_key)
            if tables and table not in tables:
                continue
            plan = plans.get(table)
            if plan is None:
                continue
            if endpoints and plan.endpoint_key not in endpoints:
                continue
            payloads = payload_cache.setdefault(plan.endpoint_key, _raw_payloads(conn, plan.endpoint_key))
            observed = observed_cache.setdefault(plan.endpoint_key, _observed_paths(payloads))
            records.append(
                _record_for_field(
                    conn=conn,
                    field=field,
                    plan=plan,
                    payloads=payloads,
                    observed=observed,
                    strict=strict,
                    explicit_mode=reason in {"explicit_field", "date_field_sweep"},
                )
            )

    unique_records = {
        (record["table"], record["column"]): record
        for record in records
    }
    decision_class_counts = Counter(
        record["post_proof_decision"]["decision_class"]
        for record in unique_records.values()
    )
    high_confidence_scalar_mapping_candidates = sum(
        1
        for record in unique_records.values()
        if record["post_proof_decision"]["mapping_candidate"] is True
        and record["post_proof_decision"]["decision_class"]
        == "high_confidence_scalar_mapping_candidate"
    )
    date_datetime_mapping_candidates = sum(
        1
        for record in unique_records.values()
        if record.get("selection_reason") == "date_field_sweep"
        and record["post_proof_decision"]["mapping_candidate"] is True
    )
    patch1_scalar_decomposition_defects = sum(
        1
        for record in unique_records.values()
        if (record["table"], record["column"]) in PATCH1_SCALAR_FIELDS
        and record["post_proof_decision"]["mapping_candidate"] is True
    )
    summary = {
        "fields_audited": len(records),
        "unique_fields_audited": len(unique_records),
        "high_confidence_mapping_candidates": sum(
            1
            for record in records
            if record["confidence"] == "high"
            and str(record["recommended_mapping"]).startswith("map_")
        ),
        "high_confidence_scalar_mapping_candidates": high_confidence_scalar_mapping_candidates,
        "date_datetime_mapping_candidates": date_datetime_mapping_candidates,
        "patch1_scalar_decomposition_defects": patch1_scalar_decomposition_defects,
        "left_unmapped_with_source_rationale": sum(
            1 for record in records if not str(record["recommended_mapping"]).startswith("map_")
        ),
        "post_proof_decision_class_counts": dict(sorted(decision_class_counts.items())),
        "raw_payload_values_emitted": False,
        "explicit_field_count": sum(
            1 for record in records if record.get("selection_reason") == "explicit_field"
        ),
        "date_field_sweep_count": sum(
            1 for record in records if record.get("selection_reason") == "date_field_sweep"
        ),
    }
    return {
        "command": "scripts/proofs/procore_raw_payload_mapping_audit.py",
        "db_path": str(db_path),
        "current_audit_json": str(current_audit_json),
        "started_at_utc": started,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "strict": strict,
        "date_field_sweep": date_field_sweep,
        "explicit_fields": [
            f"{table}.{column}" for table, column in sorted(explicit_fields or set())
        ],
        "summary": summary,
        "fields": records,
        "guardrails": {
            "read_only_sqlite": True,
            "query_only": True,
            "live_calls_disabled": True,
            "writeback": "none",
            "raw_payload_values_emitted": False,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Procore Raw Payload Source-Path Mapping Audit",
        "",
        "## Summary",
        "",
        f"- Fields audited: `{summary['fields_audited']}`",
        f"- Raw high-confidence mapping candidates: `{summary['high_confidence_mapping_candidates']}`",
        "- High-confidence scalar mapping candidates after source proof: "
        f"`{summary['high_confidence_scalar_mapping_candidates']}`",
        f"- Date/datetime mapping candidates: `{summary['date_datetime_mapping_candidates']}`",
        "- Patch 1 scalar decomposition defects: "
        f"`{summary['patch1_scalar_decomposition_defects']}`",
        f"- Left unmapped with source rationale: `{summary['left_unmapped_with_source_rationale']}`",
        f"- Explicit fields inspected: `{summary['explicit_field_count']}`",
        f"- Date field sweep records: `{summary['date_field_sweep_count']}`",
        "- Raw payload values emitted: `false`",
        "",
        "## Field Decisions",
        "",
        "| table | column | endpoint | selection | mapped | rows | null rate | action | classification | decision class | mapping candidate | paths checked |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- | ---: |",
    ]
    for row in payload["fields"]:
        decision = row["post_proof_decision"]
        lines.append(
            f"| {row['table']} | {row['column']} | {row['inferred_endpoint_key']} | "
            f"{row['selection_reason']} | {row['registry_mapped']} | "
            f"{row['row_count']} | {float(row['null_rate'] or 0):.3f} | "
            f"{row['recommended_mapping']} | {row['classification']} | "
            f"{decision['decision_class']} | {decision['mapping_candidate']} | "
            f"{len(row['candidate_json_paths_checked'])} |"
        )
    lines += [
        "",
        "## Body-Free Privacy Attestation",
        "",
        "- Payload JSON was inspected locally only for path presence and non-empty counts.",
        "- Reports contain path names, object key names, and counts only.",
        "- No payload bodies, fragments, sample values, comments, notes, descriptions, emails, signed URLs, credentials, or business text were emitted.",
    ]
    return "\n".join(lines)


def write_reports(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", "--db", dest="db_path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--current-audit-json")
    parser.add_argument("--out")
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--endpoint", action="append", dest="endpoints")
    parser.add_argument("--table", action="append", dest="tables")
    parser.add_argument("--field", action="append", dest="fields")
    parser.add_argument("--date-field-sweep", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", dest="emit_json")
    return parser.parse_args()


def _parse_fields(values: list[str] | None) -> set[tuple[str, str]]:
    fields: set[tuple[str, str]] = set()
    for value in values or []:
        if "." not in value:
            raise SystemExit(f"--field must be table.column, got {value!r}")
        table, column = value.rsplit(".", 1)
        if not table or not column:
            raise SystemExit(f"--field must be table.column, got {value!r}")
        fields.add((table, column))
    return fields


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out) if args.out else None
    current_audit_json = (
        args.current_audit_json
        or (
            str(out_dir / "post-patch2-null-projection-audit.json")
            if out_dir is not None
            else None
        )
    )
    if current_audit_json is None:
        raise SystemExit("--current-audit-json is required unless --out is provided")
    out_json = Path(
        args.out_json
        or (
            out_dir / "post-patch2-raw-payload-mapping-audit.json"
            if out_dir is not None
            else "raw-payload-mapping-audit.json"
        )
    )
    out_md = Path(
        args.out_md
        or (
            out_dir / "post-patch2-raw-payload-mapping-audit.md"
            if out_dir is not None
            else "raw-payload-mapping-audit.md"
        )
    )
    payload = audit_source_paths(
        db_path=args.db_path,
        current_audit_json=current_audit_json,
        endpoints=set(args.endpoints or []) or None,
        tables=set(args.tables or []) or None,
        strict=args.strict,
        explicit_fields=_parse_fields(args.fields),
        date_field_sweep=args.date_field_sweep,
    )
    write_reports(payload, out_json, out_md)
    output = (
        payload
        if args.emit_json
        else {
            "ok": True,
            "summary": payload["summary"],
            "json_out": str(out_json),
            "markdown_out": str(out_md),
            "guardrails": payload["guardrails"],
        }
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
