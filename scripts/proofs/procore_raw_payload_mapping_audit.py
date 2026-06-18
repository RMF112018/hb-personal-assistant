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
}


@dataclass(frozen=True)
class TablePlan:
    endpoint_key: str
    endpoint_family: str
    role: str
    array_path: str | None
    existing_columns: frozenset[str]


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
        )
        for child in plan.child_tables:
            out[child.table] = TablePlan(
                endpoint_key=endpoint_key,
                endpoint_family=plan.endpoint_family,
                role="child",
                array_path=child.array_path,
                existing_columns=frozenset(column for _rel, column in child.columns),
            )
    return out


def _physical_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({_quote_ident(table)})")}
    except sqlite3.Error:
        return set()


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


def audit_source_paths(
    *,
    db_path: str | Path,
    current_audit_json: str | Path,
    endpoints: set[str] | None = None,
    tables: set[str] | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    current_audit = json.loads(Path(current_audit_json).read_text(encoding="utf-8"))
    plans = _table_plans()
    records: list[dict[str, Any]] = []
    payload_cache: dict[str, list[dict[str, Any]]] = {}
    observed_cache: dict[str, set[str]] = {}

    with connect_readonly(db_path) as conn:
        for field in _selected_fields(current_audit):
            table = str(field.get("table"))
            column = str(field.get("column"))
            if tables and table not in tables:
                continue
            plan = plans.get(table)
            if plan is None:
                continue
            if endpoints and plan.endpoint_key not in endpoints:
                continue
            payloads = payload_cache.setdefault(plan.endpoint_key, _raw_payloads(conn, plan.endpoint_key))
            observed = observed_cache.setdefault(plan.endpoint_key, _observed_paths(payloads))
            physical_columns = _physical_columns(conn, table)
            candidates = _basic_candidates(plan, column, observed)
            checks = [_path_check(payloads, candidate) for candidate in candidates]
            action, classification, confidence = _recommend(
                column=column,
                declared_type=str(field.get("declared_type") or ""),
                plan=plan,
                physical_columns=physical_columns,
                checks=checks,
                root_cause=str(field.get("root_cause_class") or ""),
            )
            assert action in ALLOWED_ACTIONS
            child_items = 0
            if plan.array_path:
                for payload in payloads:
                    child_items += len(_values_at(payload, plan.array_path + "[]"))
            records.append(
                {
                    "table": table,
                    "column": column,
                    "declared_type": field.get("declared_type"),
                    "row_count": field.get("table_total_rows") or field.get("total_rows"),
                    "null_count": field.get("null_rows"),
                    "null_rate": field.get("null_rate"),
                    "inferred_endpoint_key": plan.endpoint_key,
                    "endpoint_family": plan.endpoint_family,
                    "current_root_cause_class": field.get("root_cause_class"),
                    "inferred_table_role": plan.role,
                    "associated_raw_endpoint_key": plan.endpoint_key,
                    "raw_payload_rows_inspected": len(payloads),
                    "raw_child_items_inspected": child_items,
                    "candidate_json_paths_checked": checks,
                    "recommended_mapping": action,
                    "classification": classification,
                    "confidence": confidence,
                    "strict": strict,
                    "raw_payload_values_emitted": False,
                }
            )

    summary = {
        "fields_audited": len(records),
        "high_confidence_mapping_candidates": sum(
            1
            for record in records
            if record["confidence"] == "high"
            and str(record["recommended_mapping"]).startswith("map_")
        ),
        "left_unmapped_with_source_rationale": sum(
            1 for record in records if not str(record["recommended_mapping"]).startswith("map_")
        ),
        "raw_payload_values_emitted": False,
    }
    return {
        "command": "scripts/proofs/procore_raw_payload_mapping_audit.py",
        "db_path": str(db_path),
        "current_audit_json": str(current_audit_json),
        "started_at_utc": started,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "strict": strict,
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
        f"- High-confidence mapping candidates: `{summary['high_confidence_mapping_candidates']}`",
        f"- Left unmapped with source rationale: `{summary['left_unmapped_with_source_rationale']}`",
        "- Raw payload values emitted: `false`",
        "",
        "## Field Decisions",
        "",
        "| table | column | endpoint | rows | null rate | action | classification | confidence | paths checked |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- | ---: |",
    ]
    for row in payload["fields"]:
        lines.append(
            f"| {row['table']} | {row['column']} | {row['inferred_endpoint_key']} | "
            f"{row['row_count']} | {float(row['null_rate'] or 0):.3f} | "
            f"{row['recommended_mapping']} | {row['classification']} | {row['confidence']} | "
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
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--current-audit-json", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--endpoint", action="append", dest="endpoints")
    parser.add_argument("--table", action="append", dest="tables")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = audit_source_paths(
        db_path=args.db_path,
        current_audit_json=args.current_audit_json,
        endpoints=set(args.endpoints or []) or None,
        tables=set(args.tables or []) or None,
        strict=args.strict,
    )
    write_reports(payload, Path(args.out_json), Path(args.out_md))
    print(
        json.dumps(
            {
                "ok": True,
                "summary": payload["summary"],
                "json_out": args.out_json,
                "markdown_out": args.out_md,
                "guardrails": payload["guardrails"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
