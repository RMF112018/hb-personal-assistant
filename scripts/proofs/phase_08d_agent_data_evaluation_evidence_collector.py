#!/usr/bin/env python3
# ruff: noqa: I001
"""Collect Phase 08A-08D agent data evaluation evidence.

This script writes an evaluation evidence packet, not a data readiness report.
It intentionally emits structure, aggregate counts, linkage metadata, and safety
evidence only. It does not export raw source records, raw note bodies, prompts,
responses, URLs, tokens, or risky free-text values.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from hb_assistant.config.path_policy import PathPolicy  # noqa: E402
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION  # noqa: E402


EVIDENCE_DIR = (
    REPO_ROOT / "docs" / "evidence" / "construction-intelligence-phase-08d-agent-data-quality-evaluation"
)
ARCHITECTURE_NOTE = (
    REPO_ROOT / "docs" / "architecture" / "118-phase-08d-agent-data-quality-evaluation-evidence-packet.md"
)

PACKET_FILES = [
    "00-repo-data-baseline",
    "01-sqlite-structure-inventory",
    "02-sqlite-field-profile",
    "03-source-to-table-lineage",
    "04-agent-consumption-map",
    "05-project-entity-relationship-linkage",
    "06-data-completeness-freshness-shape",
    "07-review-queue-and-human-in-loop-evidence",
    "08-financial-data-structure-quality-evidence",
    "09-generated-output-structure-quality-evidence",
    "10-mcp-data-exposure-evidence",
    "11-obsidian-structure-linkage-evidence",
    "12-data-dictionary-and-evaluator-index",
    "13-proof-packet-safety-scan",
    "14-final-evidence-closeout",
    "15-evaluator-readiness-index",
]

EVALUATOR_USE_MAP = {
    "data_structure": ["01-sqlite-structure-inventory", "12-data-dictionary-and-evaluator-index"],
    "source_coverage": ["03-source-to-table-lineage", "06-data-completeness-freshness-shape"],
    "field_completeness": ["02-sqlite-field-profile", "06-data-completeness-freshness-shape"],
    "source_to_table_lineage": ["03-source-to-table-lineage"],
    "agent_to_data_dependency_mapping": ["04-agent-consumption-map", "15-evaluator-readiness-index"],
    "sqlite_to_obsidian_relationship": ["11-obsidian-structure-linkage-evidence"],
    "review_queue_burden": ["07-review-queue-and-human-in-loop-evidence"],
    "mcp_exposure_safety": ["10-mcp-data-exposure-evidence", "13-proof-packet-safety-scan"],
    "phase_09_retrieval_readiness": [
        "04-agent-consumption-map",
        "06-data-completeness-freshness-shape",
        "12-data-dictionary-and-evaluator-index",
        "15-evaluator-readiness-index",
    ],
}

SOURCE_FAMILIES = {
    "outlook_email": ["mail", "email", "message", "thread"],
    "calendar": ["calendar", "event", "meeting"],
    "microsoft_graph": ["graph", "m365", "drive", "sharepoint", "onedrive"],
    "sharepoint_onedrive": ["drive", "file", "document", "sharepoint", "onedrive"],
    "local_files": ["local_file", "file_ingestion", "extraction"],
    "obsidian": ["obsidian", "vault", "note"],
    "procore": ["procore", "rfi", "submittal", "commitment", "change_event", "daily_log"],
    "financial": ["financial", "amount", "budget", "invoice", "cost", "payment", "forecast"],
    "daily_brief": ["daily_brief", "brief"],
    "research_packet": ["research", "packet"],
    "review_queue": ["review"],
    "memory": ["memory", "preference", "feedback"],
    "mcp": ["mcp", "tool", "resource", "prompt", "permission"],
    "automation": ["automation", "launchd", "run_registry", "delivery", "notification"],
    "agent_receipts": ["agent", "receipt", "model_call"],
}

FUNCTIONAL_AREAS = {
    "source registry": ["source", "registry", "scope"],
    "ingestion state": ["sync", "ingestion", "crawl", "delta", "run"],
    "Microsoft Graph": ["graph", "m365"],
    "email": ["email", "mail", "message", "thread"],
    "calendar": ["calendar", "event", "meeting"],
    "SharePoint / OneDrive": ["drive", "sharepoint", "onedrive", "file"],
    "local files": ["local_file", "extraction", "download"],
    "Procore": ["procore", "rfi", "submittal", "daily_log"],
    "financial facts and readiness": ["financial", "amount", "budget", "invoice", "cost", "payment"],
    "second-brain retrieval": ["retrieval", "query", "context", "research"],
    "daily briefs": ["daily_brief", "brief"],
    "research packets": ["research_packet", "research"],
    "review queues": ["review"],
    "memory candidates": ["memory", "preference"],
    "relationship intelligence": ["relationship", "entity", "linkage"],
    "agent receipts": ["agent", "model_call", "synthesis"],
    "automation receipts": ["automation", "delivery", "notification", "open_status"],
    "MCP tools/resources/prompts/receipts": ["mcp", "tool", "resource", "prompt"],
    "validation and data-quality proofs": ["validation", "quality", "proof", "gate"],
    "Obsidian integration": ["obsidian", "vault", "note"],
}

AGENT_CONSUMER_MATRIX = [
    {
        "agent_or_workflow": "Deterministic Retrieval Broker",
        "phase": "08A",
        "required_input_tables": ["retrieval_policy_*", "source-linked read models"],
        "optional_input_tables": ["obsidian_index_entries", "research_packets"],
        "expected_source_families": ["email", "calendar", "documents", "Procore", "financial", "Obsidian"],
        "required_linkage_fields": ["source_id", "source_record_id", "project_key"],
        "required_freshness_fields": ["created_at_utc", "updated_at_utc", "last_seen_utc"],
        "required_review_confidence_fields": ["review_required", "confidence_label"],
        "output_read_model_tables": ["retrieval_context_*", "query_tool_receipts"],
        "evidence_receipt_tables": ["model_call_receipts", "agent_run_receipts"],
    },
    {
        "agent_or_workflow": "Research Packet Agent",
        "phase": "08A",
        "required_input_tables": ["research_packets", "retrieval/query read models"],
        "optional_input_tables": ["obsidian_index_entries", "daily_brief_context_items"],
        "expected_source_families": ["approved source-linked local corpus"],
        "required_linkage_fields": ["packet_id", "source_id", "source_record_id"],
        "required_freshness_fields": ["generated_at_utc", "source_updated_at_utc"],
        "required_review_confidence_fields": ["context_quality", "review_required"],
        "output_read_model_tables": ["research_packets", "research_packet_items"],
        "evidence_receipt_tables": ["model_call_receipts", "agent_run_receipts"],
    },
    {
        "agent_or_workflow": "Output Evaluation Agent",
        "phase": "08A",
        "required_input_tables": ["generated_output_evaluations", "research_packets"],
        "optional_input_tables": ["daily_brief_runs", "synthesis_outputs"],
        "expected_source_families": ["generated outputs with source references"],
        "required_linkage_fields": ["output_id", "packet_id", "source_reference_count"],
        "required_freshness_fields": ["evaluated_at_utc", "generated_at_utc"],
        "required_review_confidence_fields": ["evaluation_status", "review_required", "confidence_label"],
        "output_read_model_tables": ["generated_output_evaluations"],
        "evidence_receipt_tables": ["model_call_receipts", "agent_run_receipts"],
    },
    {
        "agent_or_workflow": "Daily Brief Agent",
        "phase": "08A/08B",
        "required_input_tables": ["daily_brief_context_items", "daily_brief_runs"],
        "optional_input_tables": ["review_queue", "freshness/automation health tables"],
        "expected_source_families": ["calendar", "email", "documents", "Procore", "financial", "memory"],
        "required_linkage_fields": ["brief_date", "source_id", "source_record_id", "project_key"],
        "required_freshness_fields": ["brief_date", "generated_at_utc", "source_updated_at_utc"],
        "required_review_confidence_fields": ["review_required", "evaluation_status", "confidence_label"],
        "output_read_model_tables": ["daily_brief_runs", "daily_brief_render_views"],
        "evidence_receipt_tables": ["daily_brief_delivery_receipts", "brief_open_receipts"],
    },
    {
        "agent_or_workflow": "Financial Fact Readiness Agent",
        "phase": "08C",
        "required_input_tables": ["financial_amount_facts", "financial_source_coverage", "financial_review_items"],
        "optional_input_tables": ["financial_exposure_marts", "forecast_readiness_gates"],
        "expected_source_families": ["Procore financial endpoints"],
        "required_linkage_fields": ["project_key", "source_family", "source_record_id", "source_field_path"],
        "required_freshness_fields": ["source_updated_at_utc", "last_evaluated_utc"],
        "required_review_confidence_fields": ["review_required", "review_tier", "confidence_label"],
        "output_read_model_tables": ["financial_exposure_*", "forecast_readiness_*"],
        "evidence_receipt_tables": ["financial_review_items", "financial_no_writeback_proofs"],
    },
    {
        "agent_or_workflow": "Review Load / Memory Review Workflows",
        "phase": "08A/08D",
        "required_input_tables": ["review_queue*", "memory_candidates"],
        "optional_input_tables": ["operator_preferences", "quality_signals"],
        "expected_source_families": ["memory", "relationship", "financial", "daily brief", "MCP"],
        "required_linkage_fields": ["review_item_id", "source_id", "source_record_id"],
        "required_freshness_fields": ["created_at_utc", "updated_at_utc"],
        "required_review_confidence_fields": ["review_status", "review_tier", "confidence_label"],
        "output_read_model_tables": ["review summaries", "memory_items"],
        "evidence_receipt_tables": ["memory_reviews", "operator_feedback"],
    },
    {
        "agent_or_workflow": "MCP Tool Broker Agent",
        "phase": "08D",
        "required_input_tables": ["mcp_tool_call_receipts", "mcp_denial_receipts", "mcp_permission_audit_runs"],
        "optional_input_tables": ["mcp_resource_registry_snapshots", "mcp_prompt_registry_snapshots"],
        "expected_source_families": ["approved workflow wrappers only"],
        "required_linkage_fields": ["tool_name", "wrapper", "receipt_id"],
        "required_freshness_fields": ["called_at_utc", "audited_at_utc", "snapshot_at_utc"],
        "required_review_confidence_fields": ["allowed", "denial_reason", "policy_version"],
        "output_read_model_tables": ["safe MCP resources/prompts/tools registries"],
        "evidence_receipt_tables": ["mcp_*_receipts", "mcp_permission_audit_runs"],
    },
    {
        "agent_or_workflow": "Phase 09 Retrieval Readiness Inputs",
        "phase": "09 handoff",
        "required_input_tables": ["source-linked safe read models", "retrieval/query receipts"],
        "optional_input_tables": ["obsidian_index_entries", "research_packets", "daily_brief_context_items"],
        "expected_source_families": ["approved local corpus behind retrieval broker"],
        "required_linkage_fields": ["source_id", "source_record_id", "project_key"],
        "required_freshness_fields": ["created_at_utc", "updated_at_utc", "last_seen_utc"],
        "required_review_confidence_fields": ["review_required", "excluded_from_synthesis", "confidence_label"],
        "output_read_model_tables": ["future embeddings/retrieval index"],
        "evidence_receipt_tables": ["query_tool_receipts", "retrieval broker receipts"],
    },
]

RISKY_FIELD_RE = re.compile(
    r"(body|content|html|payload|raw|prompt|response|secret|token|authorization|bearer|url|"
    r"download|signed|attachment|blob|base64|email|address|subject|snippet|text|name)",
    re.IGNORECASE,
)
TEXTISH_RE = re.compile(r"(text|char|clob|varchar|json)", re.IGNORECASE)
TIMESTAMP_RE = re.compile(r"(date|time|utc|at$|_at|timestamp)", re.IGNORECASE)
PROJECT_RE = re.compile(r"(project|job)", re.IGNORECASE)
SOURCE_RE = re.compile(r"(source|record|external|graph|procore|drive|message|event)", re.IGNORECASE)
REVIEW_RE = re.compile(r"(review|status|tier|decision|disposition)", re.IGNORECASE)
CONFIDENCE_RE = re.compile(r"(confidence|score|probability)", re.IGNORECASE)

UNSAFE_PATTERNS = [
    ("access_token_assignment", re.compile(r"access[_-]?token[\"'\s:=]+[A-Za-z0-9._~-]{12,}", re.I)),
    ("refresh_token_assignment", re.compile(r"refresh[_-]?token[\"'\s:=]+[A-Za-z0-9._~-]{12,}", re.I)),
    ("client_secret_assignment", re.compile(r"client[_-]?secret[\"'\s:=]+[A-Za-z0-9._~-]{8,}", re.I)),
    ("authorization_header", re.compile(r"Authorization\s*[:=]\s*[A-Za-z0-9._~+\-/]+", re.I)),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._~+\-/]{12,}", re.I)),
    ("signed_url_query", re.compile(r"https?://\S+[?&](sig|signature|se)=\S+", re.I)),
    ("private_graph_url", re.compile(r"https://graph\.microsoft\.com/\S+", re.I)),
    ("private_sharepoint_url", re.compile(r"https://\S*sharepoint\.com/\S+", re.I)),
    ("private_onedrive_url", re.compile(r"https://\S*onedrive\.live\.com/\S+", re.I)),
    ("html_body", re.compile(r"<html\b|<body\b|</html>", re.I)),
    ("base64_blob", re.compile(r"\b[A-Za-z0-9+/]{240,}={0,2}\b")),
]


class StopCondition(RuntimeError):
    """Raised when a required safety stop condition is reached."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_command(args: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=REPO_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        return {
            "command": " ".join(args),
            "exit_code": completed.returncode,
            "stdout_lines": len(completed.stdout.splitlines()),
            "stderr_lines": len(completed.stderr.splitlines()),
            "stdout_sha256": sha256_text(completed.stdout),
            "stderr_sha256": sha256_text(completed.stderr),
        }
    except Exception as exc:  # pragma: no cover - defensive for local env drift
        return {"command": " ".join(args), "exit_code": None, "error": repr(exc)}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def redact_path(path: Path | str) -> str:
    raw = str(path)
    home = str(Path.home())
    if raw.startswith(home):
        return raw.replace(home, "~", 1)
    if raw.startswith(str(REPO_ROOT)):
        return raw.replace(str(REPO_ROOT), "<repo>", 1)
    return raw


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_md(path: Path, title: str, payload: dict[str, Any], sections: list[str] | None = None) -> None:
    lines = [
        f"# {title}",
        "",
        "This file is part of an evaluation evidence packet. It records measurable evidence only and does not conclude that the underlying data is usable, meaningful, high quality, or production-ready.",
        "",
    ]
    for section in sections or []:
        lines.extend([section, ""])
    lines.extend(["## Machine-Readable Summary", "", "```json"])
    lines.append(json.dumps(payload, indent=2, sort_keys=True))
    lines.extend(["```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def sqlite_readonly_connection(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise StopCondition("SQLite database path does not exist")
    uri = f"file:{db_path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    query_only = conn.execute("PRAGMA query_only").fetchone()[0]
    if int(query_only) != 1:
        raise StopCondition("SQLite read-only query_only pragma could not be confirmed")
    try:
        conn.execute("CREATE TABLE __packet_readonly_probe(x INTEGER)")
        raise StopCondition("SQLite read-only probe unexpectedly allowed mutation")
    except sqlite3.OperationalError:
        pass
    return conn


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    return conn.execute(sql, params).fetchone()[0]


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def classify_table_area(table: str) -> str:
    lower = table.lower()
    for area, terms in FUNCTIONAL_AREAS.items():
        if any(term in lower for term in terms):
            return area
    return "unknown / uncategorized"


def source_families_for_name(name: str) -> list[str]:
    lower = name.lower()
    return [family for family, terms in SOURCE_FAMILIES.items() if any(term in lower for term in terms)]


def table_inventory(conn: sqlite3.Connection, db_path: Path) -> dict[str, Any]:
    objects = rows(
        conn,
        "SELECT name, type, sql FROM sqlite_master WHERE type IN ('table','view','index','trigger') ORDER BY type, name",
    )
    tables = [o for o in objects if o["type"] == "table" and not o["name"].startswith("sqlite_")]
    views = [o for o in objects if o["type"] == "view"]
    indexes = [o for o in objects if o["type"] == "index"]
    triggers = [o for o in objects if o["type"] == "trigger"]
    table_summaries: list[dict[str, Any]] = []
    total_rows = 0
    grouped: dict[str, list[str]] = defaultdict(list)
    for table in tables:
        name = str(table["name"])
        count = int(scalar(conn, f"SELECT COUNT(*) FROM {qident(name)}"))
        total_rows += count
        columns = rows(conn, f"PRAGMA table_info({qident(name)})")
        column_names = [str(c["name"]) for c in columns]
        area = classify_table_area(name)
        grouped[area].append(name)
        summary = {
            "table": name,
            "functional_area": area,
            "row_count": count,
            "column_count": len(columns),
            "source_families": source_families_for_name(name),
            "has_json_fields": any("json" in c.lower() or c.endswith("_metadata") for c in column_names),
            "has_source_reference_fields": any(SOURCE_RE.search(c) for c in column_names),
            "has_project_entity_reference_fields": any(PROJECT_RE.search(c) for c in column_names),
            "has_timestamp_fields": any(TIMESTAMP_RE.search(c) for c in column_names),
            "guard_columns": [c for c in column_names if c.startswith("no_") or c.endswith("_persisted")],
            "possible_raw_content_risk_fields": [c for c in column_names if RISKY_FIELD_RE.search(c)],
        }
        table_summaries.append(summary)
    migrations = []
    if any(t["name"] == "schema_migrations" for t in tables):
        migrations = rows(
            conn,
            "SELECT version, applied_at FROM schema_migrations ORDER BY version",
        )
    stat = db_path.stat()
    return {
        "database_path_redacted": redact_path(db_path),
        "read_only_confirmed": True,
        "file_size_bytes": stat.st_size,
        "last_modified_utc": dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat(),
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "schema_version_current": migrations[-1]["version"] if migrations else None,
        "table_count": len(tables),
        "view_count": len(views),
        "index_count": len(indexes),
        "trigger_count": len(triggers),
        "total_row_count": total_rows,
        "table_list": [t["name"] for t in tables],
        "view_list": [v["name"] for v in views],
        "empty_tables": [s["table"] for s in table_summaries if s["row_count"] == 0],
        "high_row_count_tables": sorted(
            [s for s in table_summaries if s["row_count"] >= 100], key=lambda x: x["row_count"], reverse=True
        )[:25],
        "tables_grouped_by_functional_area": {k: sorted(v) for k, v in sorted(grouped.items())},
        "table_summaries": table_summaries,
        "migration_history": migrations,
    }


def column_profile(conn: sqlite3.Connection, table: str, column: dict[str, Any], row_count: int) -> dict[str, Any]:
    name = str(column["name"])
    col = qident(name)
    tbl = qident(table)
    col_type = str(column.get("type") or "")
    risky = bool(RISKY_FIELD_RE.search(name))
    non_null = int(scalar(conn, f"SELECT COUNT({col}) FROM {tbl}"))
    null_count = row_count - non_null
    empty_count = int(
        scalar(
            conn,
            f"SELECT COALESCE(SUM(CASE WHEN typeof({col})='text' AND length(trim({col}))=0 THEN 1 ELSE 0 END),0) FROM {tbl}",
        )
    )
    distinct_count = int(scalar(conn, f"SELECT COUNT(DISTINCT {col}) FROM {tbl}"))
    max_len = scalar(conn, f"SELECT MAX(length({col})) FROM {tbl}")
    avg_len = scalar(conn, f"SELECT AVG(length({col})) FROM {tbl}")
    timestamp_min = timestamp_max = None
    numeric_min = numeric_max = None
    if TIMESTAMP_RE.search(name):
        timestamp_min = scalar(conn, f"SELECT MIN({col}) FROM {tbl} WHERE {col} IS NOT NULL")
        timestamp_max = scalar(conn, f"SELECT MAX({col}) FROM {tbl} WHERE {col} IS NOT NULL")
    elif not risky and not TEXTISH_RE.search(col_type):
        numeric_min = scalar(conn, f"SELECT MIN({col}) FROM {tbl} WHERE {col} IS NOT NULL")
        numeric_max = scalar(conn, f"SELECT MAX({col}) FROM {tbl} WHERE {col} IS NOT NULL")
    json_valid_count = None
    json_key_inventory: list[str] = []
    if "json" in name.lower() or "json" in col_type.lower() or name.endswith("_metadata"):
        json_valid_count = int(
            scalar(
                conn,
                f"SELECT COALESCE(SUM(CASE WHEN json_valid({col}) THEN 1 ELSE 0 END),0) FROM {tbl}",
            )
        )
        if not risky:
            try:
                keys = rows(
                    conn,
                    f"SELECT DISTINCT j.key AS key FROM {tbl}, json_each({tbl}.{col}) AS j "
                    f"WHERE json_valid({tbl}.{col}) AND j.key IS NOT NULL ORDER BY j.key LIMIT 100",
                )
                json_key_inventory = [str(k["key"]) for k in keys]
            except sqlite3.OperationalError:
                json_key_inventory = []
    stale_date_count = None
    if TIMESTAMP_RE.search(name):
        stale_cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)).isoformat()
        stale_date_count = int(
            scalar(
                conn,
                f"SELECT COALESCE(SUM(CASE WHEN {col} IS NOT NULL AND {col} < ? THEN 1 ELSE 0 END),0) FROM {tbl}",
                (stale_cutoff,),
            )
        )
    usefulness = {
        "null_rate": round(null_count / row_count, 6) if row_count else None,
        "empty_rate": round(empty_count / row_count, 6) if row_count else None,
        "stale_date_rate_90d": round(stale_date_count / row_count, 6) if row_count and stale_date_count is not None else None,
        "orphan_reference_risk": bool(("id" in name.lower() or "key" in name.lower()) and null_count > 0),
        "missing_project_link_count": null_count if PROJECT_RE.search(name) else None,
        "missing_source_reference_count": null_count if SOURCE_RE.search(name) else None,
        "missing_timestamp_count": null_count if TIMESTAMP_RE.search(name) else None,
        "missing_review_status_count": null_count if REVIEW_RE.search(name) else None,
        "missing_confidence_label_count": null_count if CONFIDENCE_RE.search(name) else None,
        "inconsistent_enum_values_indicator": (distinct_count > 30 and REVIEW_RE.search(name) is not None),
        "json_key_drift_indicator": bool(json_key_inventory and len(json_key_inventory) > 25),
        "likely_raw_content_risk_field": risky,
    }
    return {
        "column_name": name,
        "data_type": col_type,
        "nullable": not bool(column.get("notnull")),
        "primary_key": bool(column.get("pk")),
        "row_count": row_count,
        "non_null_count": non_null,
        "null_count": null_count,
        "empty_string_count": empty_count,
        "distinct_count": distinct_count,
        "min_value": numeric_min,
        "max_value": numeric_max,
        "earliest_timestamp": timestamp_min,
        "latest_timestamp": timestamp_max,
        "maximum_observed_string_length": max_len,
        "average_string_length": round(float(avg_len), 3) if avg_len is not None else None,
        "json_validity_count": json_valid_count,
        "json_key_inventory": json_key_inventory,
        "potential_identifier_field": "id" in name.lower() or name.lower().endswith("_key"),
        "potential_source_reference_field": bool(SOURCE_RE.search(name)),
        "potential_project_link_field": bool(PROJECT_RE.search(name)),
        "potential_entity_link_field": "entity" in name.lower() or "relationship" in name.lower(),
        "potential_review_status_field": bool(REVIEW_RE.search(name)),
        "potential_confidence_score_field": bool(CONFIDENCE_RE.search(name)),
        "potential_raw_content_risk_field": risky,
        "field_level_usefulness_indicators": usefulness,
    }


def field_profiles(conn: sqlite3.Connection, tables: list[str]) -> dict[str, Any]:
    table_profiles: list[dict[str, Any]] = []
    all_fields: list[dict[str, Any]] = []
    for table in tables:
        row_count = int(scalar(conn, f"SELECT COUNT(*) FROM {qident(table)}"))
        columns = rows(conn, f"PRAGMA table_info({qident(table)})")
        indexes = rows(conn, f"PRAGMA index_list({qident(table)})")
        foreign_keys = rows(conn, f"PRAGMA foreign_key_list({qident(table)})")
        field_rows = [column_profile(conn, table, column, row_count) for column in columns]
        table_profiles.append(
            {
                "table": table,
                "row_count": row_count,
                "indexes": indexes,
                "foreign_keys": foreign_keys,
                "fields": field_rows,
            }
        )
        all_fields.extend({"table": table, **field} for field in field_rows)
    risk_fields = [f for f in all_fields if f["potential_raw_content_risk_field"]]
    return {
        "table_count_profiled": len(table_profiles),
        "field_count_profiled": len(all_fields),
        "raw_content_risk_field_count": len(risk_fields),
        "raw_content_risk_fields": [
            {"table": f["table"], "column": f["column_name"], "metadata_only": True} for f in risk_fields
        ],
        "table_profiles": table_profiles,
    }


def source_lineage(inventory: dict[str, Any]) -> dict[str, Any]:
    by_family: dict[str, dict[str, Any]] = {}
    for family in SOURCE_FAMILIES:
        matching = [
            t
            for t in inventory["table_summaries"]
            if family in t["source_families"] or any(term in t["table"].lower() for term in SOURCE_FAMILIES[family])
        ]
        by_family[family] = {
            "configured_status": "present_in_schema" if matching else "not_observed_in_table_names",
            "ingestion_tables": [t["table"] for t in matching if t["functional_area"] in {"ingestion state", "source registry"}],
            "derived_read_model_tables": [
                t["table"]
                for t in matching
                if t["functional_area"] not in {"ingestion state", "source registry", "review queues"}
            ],
            "review_tables": [t["table"] for t in matching if "review" in t["table"].lower()],
            "receipt_tables": [t["table"] for t in matching if "receipt" in t["table"].lower()],
            "record_count": sum(int(t["row_count"]) for t in matching),
            "project_linked_table_count": sum(1 for t in matching if t["has_project_entity_reference_fields"]),
            "source_reference_table_count": sum(1 for t in matching if t["has_source_reference_fields"]),
            "known_gaps_in_lineage": []
            if matching
            else ["No table-name evidence for this source family in the current SQLite structure."],
        }
    return {"source_families": by_family}


def review_queue_evidence(inventory: dict[str, Any], profiles: dict[str, Any]) -> dict[str, Any]:
    review_tables = [t for t in inventory["table_summaries"] if "review" in t["table"].lower()]
    status_fields = []
    for table in profiles["table_profiles"]:
        for field in table["fields"]:
            if field["potential_review_status_field"]:
                status_fields.append(
                    {
                        "table": table["table"],
                        "field": field["column_name"],
                        "missing_review_status_count": field["field_level_usefulness_indicators"][
                            "missing_review_status_count"
                        ],
                    }
                )
    return {
        "review_queue_tables_present": [t["table"] for t in review_tables],
        "review_queue_table_count": len(review_tables),
        "review_item_row_count_total": sum(int(t["row_count"]) for t in review_tables),
        "review_status_fields": status_fields,
        "review_not_performed": True,
    }


def generated_output_evidence(inventory: dict[str, Any]) -> dict[str, Any]:
    generated_tables = [
        t
        for t in inventory["table_summaries"]
        if any(term in t["table"].lower() for term in ("daily_brief", "research", "synthesis", "evaluation", "output"))
    ]
    return {
        "generated_output_tables": generated_tables,
        "generated_output_table_count": len(generated_tables),
        "generated_output_row_count_total": sum(int(t["row_count"]) for t in generated_tables),
        "raw_prompts_or_responses_exported": False,
        "content_quality_evaluated": False,
    }


def financial_evidence(inventory: dict[str, Any], profiles: dict[str, Any]) -> dict[str, Any]:
    financial_tables = [t for t in inventory["table_summaries"] if "financial" in t["table"].lower()]
    financial_fields = [
        {"table": table["table"], "field": field["column_name"], "indicators": field["field_level_usefulness_indicators"]}
        for table in profiles["table_profiles"]
        if "financial" in table["table"].lower()
        for field in table["fields"]
    ]
    return {
        "financial_tables": financial_tables,
        "financial_table_count": len(financial_tables),
        "financial_row_count_total": sum(int(t["row_count"]) for t in financial_tables),
        "financial_field_usefulness_indicators": financial_fields,
        "financial_determinations_made": False,
    }


def mcp_evidence() -> dict[str, Any]:
    commands = [
        [".venv/bin/hb-assistant", "second-brain", "mcp", "tools", "--help"],
        [".venv/bin/hb-assistant", "second-brain", "mcp", "resources", "--help"],
        [".venv/bin/hb-assistant", "second-brain", "mcp", "prompts", "--help"],
        [".venv/bin/hb-assistant", "second-brain", "mcp", "no-raw-access", "--help"],
        [".venv/bin/hb-assistant", "second-brain", "mcp", "no-writeback", "--help"],
        [".venv/bin/hb-assistant", "second-brain", "data-quality", "phase-08d-gates", "--help"],
    ]
    contracts = {}
    contract_dir = REPO_ROOT / "resources" / "json"
    for path in sorted(contract_dir.glob("phase_08d_*.json")):
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            parsed = {}
        contracts[path.name] = {
            "top_level_keys": sorted(parsed.keys()) if isinstance(parsed, dict) else [],
            "sha256": sha256_text(path.read_text(encoding="utf-8")),
        }
    return {
        "cli_help_surfaces_checked": [run_command(cmd) for cmd in commands],
        "phase_08d_contract_inventory": contracts,
        "unsafe_mcp_calls_executed": False,
        "mcp_content_exposure_evaluated_from_registry_and_proof_metadata": True,
    }


def obsidian_evidence(policy: PathPolicy) -> dict[str, Any]:
    vault = policy.get_vault_root()
    if not vault.exists():
        return {"status": "not_readable", "redacted_vault_root": redact_path(vault), "reason": "vault root missing"}
    if not vault.is_dir():
        return {"status": "not_applicable", "redacted_vault_root": redact_path(vault), "reason": "not a directory"}
    note_count = attachment_count = generated_count = manual_count = 0
    sqlite_linked = source_linked = project_linked = frontmatter_count = stale_count = 0
    folder_counter: Counter[str] = Counter()
    frontmatter_keys: Counter[str] = Counter()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)
    for path in vault.rglob("*"):
        if path.is_dir():
            continue
        rel_parts = path.relative_to(vault).parts
        if rel_parts:
            folder_counter[rel_parts[0]] += 1
        suffix = path.suffix.lower()
        if suffix == ".md":
            note_count += 1
            mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
            if mtime < cutoff:
                stale_count += 1
            rel_lower = str(path.relative_to(vault)).lower()
            if any(term in rel_lower for term in ("daily_brief", "research", "hb personal assistant", "generated")):
                generated_count += 1
            else:
                manual_count += 1
            try:
                with path.open("r", encoding="utf-8", errors="replace") as fh:
                    first = fh.readline()
                    if first.strip() == "---":
                        frontmatter_count += 1
                        for line in fh:
                            if line.strip() == "---":
                                break
                            key = line.split(":", 1)[0].strip()
                            if key:
                                frontmatter_keys[key] += 1
                                key_lower = key.lower()
                                if "sqlite" in key_lower or "database" in key_lower:
                                    sqlite_linked += 1
                                if "source" in key_lower:
                                    source_linked += 1
                                if "project" in key_lower:
                                    project_linked += 1
            except OSError:
                continue
        else:
            attachment_count += 1
    return {
        "status": "readable_structure_only",
        "redacted_vault_root": redact_path(vault),
        "markdown_note_count": note_count,
        "attachment_count": attachment_count,
        "generated_note_count_indicator": generated_count,
        "manual_note_count_indicator": manual_count,
        "notes_with_frontmatter": frontmatter_count,
        "frontmatter_key_inventory": sorted(frontmatter_keys),
        "sqlite_linked_note_count_by_frontmatter_key": sqlite_linked,
        "source_linked_note_count_by_frontmatter_key": source_linked,
        "project_linked_note_count_by_frontmatter_key": project_linked,
        "stale_note_count_90d_by_mtime": stale_count,
        "folder_coverage_top_level": [
            {
                "folder_label": f"folder_{idx:03d}",
                "folder_name_sha256_12": sha256_text(name)[:12],
                "file_count": count,
            }
            for idx, (name, count) in enumerate(sorted(folder_counter.items()), 1)
        ],
        "raw_note_bodies_inspected": False,
        "broken_body_link_references_inspected": False,
        "body_reference_limitation": "Not inspected because body scanning would risk raw note content exposure.",
    }


def data_dictionary(inventory: dict[str, Any], profiles: dict[str, Any]) -> dict[str, Any]:
    return {
        "table_dictionary": [
            {
                "table": t["table"],
                "functional_area": t["functional_area"],
                "row_count": t["row_count"],
                "source_families": t["source_families"],
            }
            for t in inventory["table_summaries"]
        ],
        "field_dictionary": [
            {
                "table": table["table"],
                "field": field["column_name"],
                "data_type": field["data_type"],
                "raw_content_risk": field["potential_raw_content_risk_field"],
            }
            for table in profiles["table_profiles"]
            for field in table["fields"]
        ],
        "source_family_dictionary": SOURCE_FAMILIES,
        "agent_workflow_dictionary": [row["agent_or_workflow"] for row in AGENT_CONSUMER_MATRIX],
        "evidence_file_dictionary": PACKET_FILES,
        "evaluator_use_map": EVALUATOR_USE_MAP,
        "data_consumer_matrix": AGENT_CONSUMER_MATRIX,
    }


def safety_scan(directory: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*")):
        if path.suffix not in {".md", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in UNSAFE_PATTERNS:
            for match in pattern.finditer(text):
                findings.append(
                    {
                        "file": path.name,
                        "finding": label,
                        "offset": match.start(),
                        "value_exported": False,
                    }
                )
        for line_no, line in enumerate(text.splitlines(), 1):
            if len(line) > 5000:
                findings.append(
                    {
                        "file": path.name,
                        "finding": "unexpectedly_long_line",
                        "line": line_no,
                        "length": len(line),
                        "value_exported": False,
                    }
                )
    return {
        "scan_status": "pass" if not findings else "fail",
        "unsafe_findings": findings,
        "unsafe_finding_count": len(findings),
        "limitations": [
            "The scan is deterministic and pattern-based; it cannot prove semantic absence of every possible unsafe value.",
            "Detector label names may appear in documentation, but values matching unsafe token/URL/body patterns are findings.",
        ],
    }


def baseline(policy: PathPolicy, db_path: Path, commands_run: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "generated_utc": utc_now(),
        "packet_title": "Phase_08A_08D_Agent_Data_Structure_And_Quality_Evaluation_Evidence_Packet",
        "branch": run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "head_commit": run_command(["git", "rev-parse", "HEAD"]),
        "working_tree_status": run_command(["git", "status", "--short"]),
        "package_version": "1.3.0",
        "sqlite_schema_version_expected": LATEST_SCHEMA_VERSION,
        "sqlite_database_location_redacted": redact_path(db_path),
        "sqlite_database_exists": db_path.exists(),
        "obsidian_vault_location_redacted": redact_path(policy.get_vault_root()),
        "obsidian_vault_exists": policy.get_vault_root().exists(),
        "phase_08a_08d_evidence_directories": [
            "docs/evidence/construction-intelligence-phase-08a-second-brain-runtime",
            "docs/evidence/construction-intelligence-phase-08b-automation-hardening",
            "docs/evidence/construction-intelligence-phase-08c-financial-readiness",
            "docs/evidence/construction-intelligence-phase-08d-mcp-bridge",
        ],
        "command_metadata_collected": commands_run,
        "data_quality_conclusions_made": False,
    }


def write_architecture_note() -> None:
    ARCHITECTURE_NOTE.write_text(
        """# Phase 08D Agent Data Evaluation Evidence Packet

**Status:** Implemented as an evidence collection surface for later evaluation.

This run adds `scripts/proofs/phase_08d_agent_data_evaluation_evidence_collector.py`
and writes `docs/evidence/construction-intelligence-phase-08d-agent-data-quality-evaluation/`.
The packet is explicitly not a readiness report. It records measurable structure,
completeness, linkage, freshness, lineage, source coverage, review burden, MCP exposure
safety, SQLite-to-Obsidian relationship evidence, and Phase 09 retrieval-readiness inputs.

Safety posture:

- SQLite is opened read-only and `PRAGMA query_only=ON` is verified before profiling.
- Risky text fields are represented by metadata only: counts, lengths, null/empty rates,
  hash/count posture, JSON key inventories where safe, and risk labels.
- Obsidian inspection is limited to filesystem metadata and frontmatter keys; note bodies
  are not read or exported.
- The generated packet safety scan fails closed on unsafe persisted content indicators.
- The closeout may state whether the packet is organized enough for a later evaluator, but
  it must not conclude that the underlying data is usable, meaningful, production-ready, or
  high quality.
""",
        encoding="utf-8",
    )


def build_packet(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    policy = PathPolicy()
    db_path = policy.get_db_path()
    commands_checked = [
        run_command([".venv/bin/hb-assistant", "second-brain", "--help"]),
        run_command([".venv/bin/hb-assistant", "second-brain", "data-quality", "--help"]),
        run_command([".venv/bin/hb-assistant", "second-brain", "mcp", "--help"]),
    ]
    conn = sqlite_readonly_connection(db_path)
    try:
        inventory = table_inventory(conn, db_path)
        profiles = field_profiles(conn, inventory["table_list"])
    finally:
        conn.close()

    lineage = source_lineage(inventory)
    review = review_queue_evidence(inventory, profiles)
    financial = financial_evidence(inventory, profiles)
    generated = generated_output_evidence(inventory)
    mcp = mcp_evidence()
    obsidian = obsidian_evidence(policy)
    dictionary = data_dictionary(inventory, profiles)
    base = baseline(policy, db_path, commands_checked)
    linkage = {
        "entity_types_evidence": {
            family: {
                "matching_tables": [t["table"] for t in inventory["table_summaries"] if family in t["source_families"]],
                "record_count": sum(t["row_count"] for t in inventory["table_summaries"] if family in t["source_families"]),
            }
            for family in SOURCE_FAMILIES
        },
        "project_entity_relationship_linkage_evaluated": False,
        "linkage_measurements_only": True,
    }
    completeness = {
        "table_row_counts": {t["table"]: t["row_count"] for t in inventory["table_summaries"]},
        "field_usefulness_indicators": [
            {
                "table": table["table"],
                "field": field["column_name"],
                "indicators": field["field_level_usefulness_indicators"],
            }
            for table in profiles["table_profiles"]
            for field in table["fields"]
        ],
        "operational_unused_indicator_tables": [t["table"] for t in inventory["table_summaries"] if t["row_count"] == 0],
        "data_quality_conclusions_made": False,
    }
    agent_map = {
        "data_consumer_matrix": AGENT_CONSUMER_MATRIX,
        "raw_data_consumed_directly": False,
        "mapping_is_dependency_evidence_only": True,
    }
    evaluator_index: dict[str, Any] = {
        "packet_organized_for_later_evaluation": True,
        "underlying_data_readiness_conclusion": "not_evaluated",
        "evaluator_use_map": EVALUATOR_USE_MAP,
        "data_consumer_matrix": AGENT_CONSUMER_MATRIX,
        "recommended_review_order": PACKET_FILES,
        "stop_conditions_triggered": [],
    }

    payloads = {
        "00-repo-data-baseline": base,
        "01-sqlite-structure-inventory": inventory,
        "02-sqlite-field-profile": profiles,
        "03-source-to-table-lineage": lineage,
        "04-agent-consumption-map": agent_map,
        "05-project-entity-relationship-linkage": linkage,
        "06-data-completeness-freshness-shape": completeness,
        "07-review-queue-and-human-in-loop-evidence": review,
        "08-financial-data-structure-quality-evidence": financial,
        "09-generated-output-structure-quality-evidence": generated,
        "10-mcp-data-exposure-evidence": mcp,
        "11-obsidian-structure-linkage-evidence": obsidian,
        "12-data-dictionary-and-evaluator-index": dictionary,
        "15-evaluator-readiness-index": evaluator_index,
    }
    for slug, payload in payloads.items():
        write_json(output_dir / f"{slug}.json", payload)
        title = slug.replace("-", " ").title()
        sections = []
        if slug in {"12-data-dictionary-and-evaluator-index", "15-evaluator-readiness-index"}:
            sections.append("## Evaluator Use Map\n\n" + json.dumps(EVALUATOR_USE_MAP, indent=2, sort_keys=True))
            sections.append("## Data Consumer Matrix\n\n" + json.dumps(AGENT_CONSUMER_MATRIX, indent=2, sort_keys=True))
        write_md(output_dir / f"{slug}.md", title, payload, sections)

    scan = safety_scan(output_dir)
    write_json(output_dir / "13-proof-packet-safety-scan.json", scan)
    write_md(output_dir / "13-proof-packet-safety-scan.md", "13 Proof Packet Safety Scan", scan)
    if scan["unsafe_findings"]:
        evaluator_index["packet_organized_for_later_evaluation"] = False
        evaluator_index["stop_conditions_triggered"].append("safety_scan_flagged_unsafe_content")
        write_json(output_dir / "15-evaluator-readiness-index.json", evaluator_index)
        write_md(output_dir / "15-evaluator-readiness-index.md", "15 Evaluator Readiness Index", evaluator_index)
        raise StopCondition("Generated evidence packet safety scan flagged unsafe content")

    closeout = {
        "all_generated_proof_files": [f"{slug}.md" for slug in PACKET_FILES]
        + [f"{slug}.json" for slug in PACKET_FILES],
        "commands_run": commands_checked + mcp["cli_help_surfaces_checked"],
        "commands_not_run": [
            "No live endpoint calls.",
            "No MCP workflow dispatch calls.",
            "No Obsidian note writes.",
            "No source-system writeback commands.",
        ],
        "sqlite_proof_status": "read_only_confirmed",
        "obsidian_proof_status": obsidian["status"],
        "source_lineage_proof_status": "measurement_packet_written",
        "agent_consumption_map_status": "dependency_matrix_written",
        "financial_data_proof_status": "structure_and_aggregate_metadata_written",
        "mcp_exposure_proof_status": "registry_and_help_surface_metadata_written",
        "no_writeback_status": "no_writeback_commands_executed",
        "no_raw_data_persistence_status": "safety_scan_passed",
        "safety_scan_result": scan["scan_status"],
        "limitations": scan["limitations"] + [
            "This packet does not perform final data-quality or usefulness evaluation.",
            "Obsidian body references are not inspected to avoid raw note content exposure.",
        ],
        "packet_ready_for_separate_evaluation_session": True,
        "underlying_data_readiness_conclusion": "not_evaluated",
    }
    write_json(output_dir / "14-final-evidence-closeout.json", closeout)
    write_md(output_dir / "14-final-evidence-closeout.md", "14 Final Evidence Closeout", closeout)
    write_json(output_dir / "15-evaluator-readiness-index.json", evaluator_index)
    write_md(
        output_dir / "15-evaluator-readiness-index.md",
        "15 Evaluator Readiness Index",
        evaluator_index,
        [
            "## Evaluator Use Map\n\n" + json.dumps(EVALUATOR_USE_MAP, indent=2, sort_keys=True),
            "## Data Consumer Matrix\n\n" + json.dumps(AGENT_CONSUMER_MATRIX, indent=2, sort_keys=True),
        ],
    )
    return {"output_dir": str(output_dir), "inventory": inventory, "scan": scan, "closeout": closeout}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=EVIDENCE_DIR)
    parser.add_argument("--write-architecture-note", action="store_true")
    args = parser.parse_args(argv)
    if args.write_architecture_note:
        write_architecture_note()
    try:
        result = build_packet(args.output_dir)
    except StopCondition as exc:
        print(json.dumps({"status": "incomplete", "reason": str(exc)}, indent=2), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": "complete",
                "output_dir": result["output_dir"],
                "table_count": result["inventory"]["table_count"],
                "total_row_count": result["inventory"]["total_row_count"],
                "safety_scan": result["scan"]["scan_status"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
