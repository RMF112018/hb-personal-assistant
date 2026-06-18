#!/usr/bin/env python3
"""Body-free Batch 2 source-path triage for Procore budget/financial nulls."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

DEFAULT_DB_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "HB Personal Assistant"
    / "db"
    / "hb-personal-assistant.sqlite"
)
RAW_PAYLOAD_TABLE = "procore_endpoint_raw_payloads"

CLASS_ROW_SOURCE = "row_level_source_field_exists"
CLASS_DYNAMIC_CELL = "dynamic_budget_detail_cell_exists"
CLASS_DEAD_COLUMN = "read_model_convenience_or_dead_column"
CLASS_SCHEMA_ARTIFACT = "schema_artifact"
CLASS_EXPECTED_OPTIONAL = "expected_optional"
CLASS_INSUFFICIENT = "local_evidence_insufficient"

NEXT_ACTIONS = {
    "no_action_expected_optional",
    "no_action_dynamic_cell_already_handled",
    "no_action_dead_column_candidate",
    "document_schema_artifact",
    "approve_mapping_patch_next",
    "approve_deprecation_patch_next",
    "defer_pending_live_source_evidence",
}


@dataclass(frozen=True)
class TargetField:
    table: str
    column: str
    endpoint_key: str
    endpoint_family: str
    candidate_paths: tuple[str, ...]
    dynamic_cell_aliases: tuple[str, ...] = ()
    source_shape: str = "endpoint_path"


TARGETS: tuple[TargetField, ...] = (
    TargetField(
        table="procore_ep_budget_detail_rows",
        column="actual_cost",
        endpoint_key="budget-detail-rows",
        endpoint_family="budget",
        candidate_paths=("$.actual_cost",),
        dynamic_cell_aliases=("actualcost", "actualcosts"),
        source_shape="budget_detail_row",
    ),
    TargetField(
        table="procore_ep_budget_detail_rows",
        column="cost_type",
        endpoint_key="budget-detail-rows",
        endpoint_family="budget",
        candidate_paths=("$.cost_type", "$.line_item_type"),
        source_shape="budget_detail_row",
    ),
    TargetField(
        table="procore_ep_budget_detail_rows",
        column="cost_type_id",
        endpoint_key="budget-detail-rows",
        endpoint_family="budget",
        candidate_paths=(
            "$.cost_type_id",
            "$.cost_type.id",
            "$.line_item_type_id",
            "$.line_item_type.id",
        ),
        source_shape="budget_detail_row",
    ),
    TargetField(
        table="procore_ep_budget_detail_rows",
        column="line_item_type_id",
        endpoint_key="budget-detail-rows",
        endpoint_family="budget",
        candidate_paths=("$.line_item_type_id", "$.line_item_type.id"),
        source_shape="budget_detail_row",
    ),
    TargetField(
        table="procore_ep_budget_detail_row_cells",
        column="currency_iso_code",
        endpoint_key="budget-detail-rows",
        endpoint_family="budget",
        candidate_paths=(
            "$.currency_iso_code",
            "$.currency_code",
            "$.currency_configuration.currency_iso_code",
        ),
        source_shape="budget_detail_cell_currency",
    ),
    TargetField(
        table="procore_ep_change_events_change_items",
        column="cost_impact_contract_confirmed",
        endpoint_key="change-events",
        endpoint_family="change_events",
        candidate_paths=(
            "$.change_items[].cost_impact.contract_confirmed",
            "$.change_items[].cost_impact.contract.confirmed",
        ),
        source_shape="change_event_confirmation",
    ),
    TargetField(
        table="procore_ep_change_events_change_items",
        column="cost_impact_vendor_confirmed",
        endpoint_key="change-events",
        endpoint_family="change_events",
        candidate_paths=(
            "$.change_items[].cost_impact.vendor_confirmed",
            "$.change_items[].cost_impact.vendor.confirmed",
        ),
        source_shape="change_event_confirmation",
    ),
)


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _readonly_uri(path: Path) -> str:
    return f"file:{quote(str(path.resolve()), safe='/')}?mode=ro"


def connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(_readonly_uri(Path(db_path)), uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    if not _table_exists(conn, table):
        return False
    return any(row["name"] == column for row in conn.execute(f"PRAGMA table_info({_quote_ident(table)})"))


def _column_stats(conn: sqlite3.Connection, table: str, column: str) -> dict[str, Any]:
    if not _column_exists(conn, table, column):
        return {
            "table_exists": _table_exists(conn, table),
            "column_exists": False,
            "table_row_count": 0,
            "null_rows": 0,
            "non_null_rows": 0,
            "null_rate": 0.0,
        }
    row = conn.execute(
        f"""
        SELECT
          COUNT(*) AS total_rows,
          SUM(CASE WHEN {_quote_ident(column)} IS NULL THEN 1 ELSE 0 END) AS null_rows,
          SUM(CASE WHEN {_quote_ident(column)} IS NOT NULL THEN 1 ELSE 0 END) AS non_null_rows
        FROM {_quote_ident(table)}
        """
    ).fetchone()
    total = int(row["total_rows"] or 0)
    nulls = int(row["null_rows"] or 0)
    return {
        "table_exists": True,
        "column_exists": True,
        "table_row_count": total,
        "null_rows": nulls,
        "non_null_rows": int(row["non_null_rows"] or 0),
        "null_rate": round(nulls / total, 6) if total else 0.0,
    }


def _is_empty_value(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


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
        return any(exists for exists, _ in statuses), any(non_empty for _, non_empty in statuses)
    return _walk_path(value, rest)


def _path_value_status(payload: Any, json_path: str) -> tuple[bool, bool]:
    if json_path == "$":
        return True, not _is_empty_value(payload)
    return _walk_path(payload, _path_tokens(json_path))


def _raw_rows(conn: sqlite3.Connection, endpoint_key: str, project_keys: tuple[str, ...]) -> list[sqlite3.Row]:
    if not _table_exists(conn, RAW_PAYLOAD_TABLE):
        return []
    clauses = [
        "endpoint_key = ?",
        "is_current = 1",
        "raw_procore_payload_persisted = 1",
        "source_quality = 'live_full_payload'",
    ]
    params: list[Any] = [endpoint_key]
    if project_keys:
        placeholders = ", ".join("?" for _ in project_keys)
        clauses.append(f"project_key IN ({placeholders})")
        params.extend(project_keys)
    return conn.execute(
        f"""
        SELECT raw_payload_id, endpoint_key, project_key, payload_json
        FROM {_quote_ident(RAW_PAYLOAD_TABLE)}
        WHERE {' AND '.join(clauses)}
        ORDER BY raw_payload_id
        """,
        tuple(params),
    ).fetchall()


def _path_presence(
    conn: sqlite3.Connection,
    endpoint_key: str,
    json_path: str,
    project_keys: tuple[str, ...],
) -> dict[str, Any]:
    rows = _raw_rows(conn, endpoint_key, project_keys)
    present = 0
    non_empty = 0
    parse_errors = 0
    projects: set[str] = set()
    for row in rows:
        if row["project_key"]:
            projects.add(str(row["project_key"]))
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            parse_errors += 1
            continue
        exists, has_value = _path_value_status(payload, json_path)
        if exists:
            present += 1
        if has_value:
            non_empty += 1
    inspected = len(rows)
    return {
        "endpoint_key": endpoint_key,
        "json_path": json_path,
        "payload_rows_inspected": inspected,
        "path_present_count": present,
        "path_non_empty_count": non_empty,
        "path_missing_count": max(inspected - present, 0),
        "parse_error_count": parse_errors,
        "projects_observed": sorted(projects),
        "source_quality_filter_used": (
            "is_current=1 AND raw_procore_payload_persisted=1 "
            "AND source_quality='live_full_payload'"
        ),
        "raw_payload_values_emitted": False,
    }


def _normalize_label(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _dynamic_cell_evidence(
    conn: sqlite3.Connection,
    aliases: tuple[str, ...],
    project_keys: tuple[str, ...],
) -> dict[str, Any]:
    if not aliases or not _table_exists(conn, "procore_ep_budget_detail_row_cells"):
        return {
            "aliases_checked": list(aliases),
            "cell_rows_inspected": 0,
            "matching_cell_rows": 0,
            "matching_decimal_rows": 0,
            "matching_currency_non_null_rows": 0,
            "raw_payload_values_emitted": False,
        }
    clauses = ["is_current = 1"]
    params: list[Any] = []
    if project_keys:
        placeholders = ", ".join("?" for _ in project_keys)
        clauses.append(f"project_key IN ({placeholders})")
        params.extend(project_keys)
    rows = conn.execute(
        f"""
        SELECT column_name, column_label, field_path, value_decimal_text, currency_iso_code
        FROM procore_ep_budget_detail_row_cells
        WHERE {' AND '.join(clauses)}
        """,
        tuple(params),
    ).fetchall()
    matching = 0
    decimals = 0
    currencies = 0
    alias_set = set(aliases)
    for row in rows:
        normalized_names = {
            _normalize_label(row["column_name"]),
            _normalize_label(row["column_label"]),
            _normalize_label(row["field_path"]),
        }
        if normalized_names & alias_set:
            matching += 1
            if row["value_decimal_text"] not in (None, ""):
                decimals += 1
            if row["currency_iso_code"] not in (None, ""):
                currencies += 1
    return {
        "aliases_checked": list(aliases),
        "cell_rows_inspected": len(rows),
        "matching_cell_rows": matching,
        "matching_decimal_rows": decimals,
        "matching_currency_non_null_rows": currencies,
        "raw_payload_values_emitted": False,
    }


def _cell_currency_evidence(
    conn: sqlite3.Connection, project_keys: tuple[str, ...]
) -> dict[str, Any]:
    if not _table_exists(conn, "procore_ep_budget_detail_row_cells"):
        return {
            "cell_rows_inspected": 0,
            "currency_non_null_rows": 0,
            "currency_null_rows": 0,
            "raw_payload_values_emitted": False,
        }
    clauses = ["is_current = 1"]
    params: list[Any] = []
    if project_keys:
        placeholders = ", ".join("?" for _ in project_keys)
        clauses.append(f"project_key IN ({placeholders})")
        params.extend(project_keys)
    row = conn.execute(
        f"""
        SELECT
          COUNT(*) AS total_rows,
          SUM(CASE WHEN currency_iso_code IS NOT NULL AND currency_iso_code <> '' THEN 1 ELSE 0 END)
            AS non_null_rows
        FROM procore_ep_budget_detail_row_cells
        WHERE {' AND '.join(clauses)}
        """,
        tuple(params),
    ).fetchone()
    total = int(row["total_rows"] or 0)
    non_null = int(row["non_null_rows"] or 0)
    return {
        "cell_rows_inspected": total,
        "currency_non_null_rows": non_null,
        "currency_null_rows": max(total - non_null, 0),
        "raw_payload_values_emitted": False,
    }


def _load_audit_records(path: str | Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text())
    records = payload.get("columns", [])
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        table = record.get("table")
        column = record.get("column")
        if table and column:
            out[(str(table), str(column))] = record
    return out


def _has_sufficient_local_rows(path_checks: list[dict[str, Any]]) -> bool:
    return any(check["payload_rows_inspected"] > 0 for check in path_checks)


def _any_path_non_empty(path_checks: list[dict[str, Any]]) -> bool:
    return any(check["path_non_empty_count"] > 0 for check in path_checks)


def _any_path_present(path_checks: list[dict[str, Any]]) -> bool:
    return any(check["path_present_count"] > 0 for check in path_checks)


def _classify_budget_detail(
    target: TargetField,
    stats: dict[str, Any],
    path_checks: list[dict[str, Any]],
    dynamic: dict[str, Any] | None,
    cell_currency: dict[str, Any] | None,
) -> tuple[str, str, str]:
    if not _has_sufficient_local_rows(path_checks):
        return (
            CLASS_INSUFFICIENT,
            "defer_pending_live_source_evidence",
            "No current local live_full_payload rows were available for the target endpoint.",
        )
    if _any_path_non_empty(path_checks):
        return (
            CLASS_ROW_SOURCE,
            "approve_mapping_patch_next",
            "A stable row-level source path exists in local raw payloads.",
        )
    if _any_path_present(path_checks):
        return (
            CLASS_EXPECTED_OPTIONAL,
            "no_action_expected_optional",
            "Candidate row-level source paths are present only as null or empty values.",
        )
    if target.column == "currency_iso_code" and cell_currency:
        if cell_currency["currency_non_null_rows"] > 0:
            return (
                CLASS_DYNAMIC_CELL,
                "no_action_dynamic_cell_already_handled",
                "Budget Detail cell currency is already represented in dynamic cell rows.",
            )
        return (
            CLASS_DEAD_COLUMN,
            "no_action_dead_column_candidate",
            "No row-level currency source was observed for current Budget Detail rows.",
        )
    if dynamic and dynamic["matching_cell_rows"] > 0:
        return (
            CLASS_DYNAMIC_CELL,
            "no_action_dynamic_cell_already_handled",
            "Only dynamic Budget Detail cell evidence was observed for this semantic field.",
        )
    if stats["table_row_count"] > 0:
        return (
            CLASS_DEAD_COLUMN,
            "no_action_dead_column_candidate",
            "Current rows exist, but neither row-level source nor dynamic-cell evidence supports projection.",
        )
    return (
        CLASS_SCHEMA_ARTIFACT,
        "document_schema_artifact",
        "The target schema exists without current row evidence.",
    )


def _classify_change_event(
    path_checks: list[dict[str, Any]],
) -> tuple[str, str, str]:
    if not _has_sufficient_local_rows(path_checks):
        return (
            CLASS_INSUFFICIENT,
            "defer_pending_live_source_evidence",
            "No current local live_full_payload rows were available for change-events.",
        )
    if _any_path_non_empty(path_checks):
        return (
            CLASS_ROW_SOURCE,
            "approve_mapping_patch_next",
            "A checked cost-impact confirmation path exists with non-empty source data.",
        )
    if _any_path_present(path_checks):
        return (
            CLASS_EXPECTED_OPTIONAL,
            "no_action_expected_optional",
            "The checked confirmation path exists only as null or empty in current payloads.",
        )
    return (
        CLASS_SCHEMA_ARTIFACT,
        "document_schema_artifact",
        "Current change-event payloads do not contain the checked confirmation paths.",
    )


def triage_database(
    db_path: str | Path,
    *,
    audit_json: str | Path | None = None,
    project_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    audit_records = _load_audit_records(audit_json)
    records: list[dict[str, Any]] = []
    with connect_readonly(db_path) as conn:
        for target in TARGETS:
            stats = _column_stats(conn, target.table, target.column)
            audit_record = audit_records.get((target.table, target.column), {})
            path_checks = [
                _path_presence(conn, target.endpoint_key, path, project_keys)
                for path in target.candidate_paths
            ]
            dynamic = None
            cell_currency = None
            if target.dynamic_cell_aliases:
                dynamic = _dynamic_cell_evidence(conn, target.dynamic_cell_aliases, project_keys)
            if target.source_shape == "budget_detail_cell_currency":
                cell_currency = _cell_currency_evidence(conn, project_keys)
            if target.source_shape.startswith("budget_detail"):
                classification, next_action, rationale = _classify_budget_detail(
                    target, stats, path_checks, dynamic, cell_currency
                )
            else:
                classification, next_action, rationale = _classify_change_event(path_checks)
            if next_action not in NEXT_ACTIONS:
                raise ValueError(f"invalid next action for {target.table}.{target.column}: {next_action}")
            records.append(
                {
                    "table": target.table,
                    "column": target.column,
                    "endpoint_key": target.endpoint_key,
                    "endpoint_family": target.endpoint_family,
                    **stats,
                    "audit_null_rate": audit_record.get("null_rate"),
                    "audit_root_cause_class": audit_record.get("root_cause_class"),
                    "audit_classification": audit_record.get("classification"),
                    "path_checks": path_checks,
                    "dynamic_cell_evidence": dynamic,
                    "cell_currency_evidence": cell_currency,
                    "local_evidence_sufficient": _has_sufficient_local_rows(path_checks),
                    "classification": classification,
                    "next_action": next_action,
                    "rationale": rationale,
                    "raw_payload_values_emitted": False,
                }
            )
    return {
        "command": "scripts/proofs/procore_budget_financial_source_path_triage.py",
        "db_path": str(db_path),
        "audit_json": str(audit_json) if audit_json else None,
        "started_at_utc": started,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_keys": list(project_keys),
        "summary": {
            "target_fields": len(records),
            "local_evidence_sufficient_fields": sum(
                1 for row in records if row["local_evidence_sufficient"]
            ),
            "approve_mapping_patch_next": sum(
                1 for row in records if row["next_action"] == "approve_mapping_patch_next"
            ),
            "dynamic_cell_already_handled": sum(
                1 for row in records if row["next_action"] == "no_action_dynamic_cell_already_handled"
            ),
            "dead_column_candidates": sum(
                1 for row in records if row["next_action"] == "no_action_dead_column_candidate"
            ),
            "schema_artifacts_to_document": sum(
                1 for row in records if row["next_action"] == "document_schema_artifact"
            ),
            "deferred_pending_live_source_evidence": sum(
                1 for row in records if row["next_action"] == "defer_pending_live_source_evidence"
            ),
        },
        "target_fields": records,
        "guardrails": {
            "read_only_sqlite": True,
            "query_only": True,
            "live_calls_performed": False,
            "scheduler_called": False,
            "source_refresh_orchestrator_called": False,
            "budget_detail_refresh_or_reconciliation_called": False,
            "schema_registry_projection_migration_changed": False,
            "writeback": "none",
            "raw_payload_values_emitted": False,
        },
        "closeout": "No remediation was applied; null projection counts were intentionally unchanged.",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Batch 2 Budget/Financial Source-Path Triage",
        "",
        "## Executive Summary",
        "",
        f"- Target fields: `{summary['target_fields']}`",
        f"- Local evidence sufficient fields: `{summary['local_evidence_sufficient_fields']}`",
        f"- Approve mapping patch next: `{summary['approve_mapping_patch_next']}`",
        f"- Dynamic-cell already handled: `{summary['dynamic_cell_already_handled']}`",
        f"- Dead column candidates: `{summary['dead_column_candidates']}`",
        f"- Schema artifacts to document: `{summary['schema_artifacts_to_document']}`",
        f"- Deferred pending live source evidence: `{summary['deferred_pending_live_source_evidence']}`",
        "",
        "## Target Field Matrix",
        "",
        "| Table | Column | Rows | Null Rate | Audit Root Cause | Paths Checked | "
        "Local Evidence | Classification | Next Action |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["target_fields"]:
        paths = "<br>".join(check["json_path"] for check in row["path_checks"])
        audit_null_rate = row["audit_null_rate"]
        null_rate = audit_null_rate if audit_null_rate is not None else row["null_rate"]
        lines.append(
            "| {table} | {column} | {rows} | {null_rate} | {root} | {paths} | {evidence} | "
            "{classification} | {next_action} |".format(
                table=row["table"],
                column=row["column"],
                rows=row["table_row_count"],
                null_rate=null_rate,
                root=row["audit_root_cause_class"] or "not_in_audit_json",
                paths=paths,
                evidence="sufficient" if row["local_evidence_sufficient"] else "insufficient",
                classification=row["classification"],
                next_action=row["next_action"],
            )
        )
    lines.extend(
        [
            "",
            "## Body-Free Path Evidence",
            "",
        ]
    )
    for row in payload["target_fields"]:
        lines.extend(
            [
                f"### {row['table']}.{row['column']}",
                "",
                f"- Endpoint: `{row['endpoint_key']}`",
                f"- Classification: `{row['classification']}`",
                f"- Next action: `{row['next_action']}`",
                f"- Rationale: {row['rationale']}",
                "",
                "| JSON Path | Inspected | Present | Non-Empty | Missing |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for check in row["path_checks"]:
            lines.append(
                f"| `{check['json_path']}` | {check['payload_rows_inspected']} | "
                f"{check['path_present_count']} | {check['path_non_empty_count']} | "
                f"{check['path_missing_count']} |"
            )
        if row["dynamic_cell_evidence"]:
            dyn = row["dynamic_cell_evidence"]
            lines.extend(
                [
                    "",
                    "- Dynamic cell evidence:",
                    f"  - aliases checked: `{', '.join(dyn['aliases_checked'])}`",
                    f"  - cell rows inspected: `{dyn['cell_rows_inspected']}`",
                    f"  - matching cell rows: `{dyn['matching_cell_rows']}`",
                    f"  - matching decimal rows: `{dyn['matching_decimal_rows']}`",
                ]
            )
        if row["cell_currency_evidence"]:
            cur = row["cell_currency_evidence"]
            lines.extend(
                [
                    "",
                    "- Cell currency evidence:",
                    f"  - cell rows inspected: `{cur['cell_rows_inspected']}`",
                    f"  - currency non-null rows: `{cur['currency_non_null_rows']}`",
                    f"  - currency null rows: `{cur['currency_null_rows']}`",
                ]
            )
        lines.append("")
    lines.extend(
        [
            "## Guardrails",
            "",
            "- No live calls were made.",
            "- No scheduler or SourceRefreshOrchestrator path was called.",
            "- No Budget Detail refresh or reconciliation path was called.",
            "- No schema, registry, projection, migration, or writeback change was applied.",
            "- Raw payload bodies, fragments, and values were not emitted.",
            "",
            "## Closeout",
            "",
            "No remediation was applied; null projection counts were intentionally unchanged.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--audit-json")
    parser.add_argument("--project-key", action="append", default=[])
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = triage_database(
        args.db_path,
        audit_json=args.audit_json,
        project_keys=tuple(args.project_key or ()),
    )
    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    if args.markdown_out:
        path = Path(args.markdown_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
