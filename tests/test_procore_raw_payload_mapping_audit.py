from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scripts.proofs import procore_raw_payload_mapping_audit as audit


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "mapping.sqlite"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(
            """
            CREATE TABLE procore_endpoint_raw_payloads (
              raw_payload_id TEXT PRIMARY KEY,
              endpoint_key TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              is_current INTEGER NOT NULL,
              raw_procore_payload_persisted INTEGER NOT NULL,
              source_quality TEXT NOT NULL
            );

            CREATE TABLE procore_ep_punch_items (
              record_key TEXT PRIMARY KEY,
              closed_at TEXT,
              closed_by TEXT,
              closed_by_id TEXT,
              closed_by_name TEXT,
              closed_by_login TEXT
            );

            CREATE TABLE procore_ep_rfis (
              record_key TEXT PRIMARY KEY,
              ball_in_court TEXT,
              ball_in_court_id TEXT,
              ball_in_court_name TEXT
            );

            CREATE TABLE procore_ep_rfis_assignees (
              record_key TEXT PRIMARY KEY,
              response_required TEXT
            );

            CREATE TABLE procore_ep_budget_detail_rows (
              record_key TEXT PRIMARY KEY,
              actual_cost TEXT
            );
            """
        )
        payloads = {
            "punch-items": {
                "id": 1,
                "closed_at": "2026-06-01T12:00:00Z",
                "closed_by": {"id": 7, "name": "Synthetic Reviewer", "login": "reviewer@example.invalid"},
            },
            "rfis": {
                "id": 2,
                "ball_in_court": {"id": 8, "name": "Synthetic Assignee"},
                "assignees": [{"id": 9, "response_required": True}],
            },
            "budget-detail-rows": {"id": 3, "name": "Synthetic Budget Row"},
        }
        for endpoint, payload in payloads.items():
            conn.execute(
                """
                INSERT INTO procore_endpoint_raw_payloads (
                  raw_payload_id, endpoint_key, payload_json, is_current,
                  raw_procore_payload_persisted, source_quality
                ) VALUES (?, ?, ?, 1, 1, 'live_full_payload')
                """,
                (f"raw-{endpoint}", endpoint, json.dumps(payload)),
            )
        conn.commit()
    finally:
        conn.close()
    return db


def _current_audit(tmp_path: Path) -> Path:
    rows = [
        ("procore_ep_punch_items", "closed_at", "all_null", "TEXT", 1),
        ("procore_ep_rfis", "ball_in_court", "all_null", "TEXT", 1),
        ("procore_ep_rfis_assignees", "response_required", "all_null", "TEXT", 1),
        ("procore_ep_budget_detail_rows", "actual_cost", "all_null", "TEXT", 1),
    ]
    payload = {
        "columns": [
            {
                "table": table,
                "column": column,
                "classification": classification,
                "declared_type": declared_type,
                "root_cause_class": "schema_column_not_in_projection_registry",
                "suspected_projection_defect": True,
                "table_total_rows": total,
                "total_rows": total,
                "null_rows": total,
                "null_rate": 1.0,
                "explicitly_deferred": False,
            }
            for table, column, classification, declared_type, total in rows
        ]
    }
    path = tmp_path / "current-audit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _install_registry(monkeypatch: Any) -> None:
    plans = {
        "punch-items": SimpleNamespace(
            endpoint_family="punch-items",
            primary_table="procore_ep_punch_items",
            primary_columns=(),
            child_tables=(),
        ),
        "rfis": SimpleNamespace(
            endpoint_family="rfis",
            primary_table="procore_ep_rfis",
            primary_columns=(),
            child_tables=(
                SimpleNamespace(
                    table="procore_ep_rfis_assignees",
                    array_path="$.assignees",
                    columns=(),
                ),
            ),
        ),
        "budget-detail-rows": SimpleNamespace(
            endpoint_family="budget-detail",
            primary_table="procore_ep_budget_detail_rows",
            primary_columns=(),
            child_tables=(),
        ),
    }
    monkeypatch.setattr(audit.projection_registry, "load_registry", lambda: plans)


def _by_column(payload: dict[str, Any], table: str, column: str) -> dict[str, Any]:
    matches = [
        row for row in payload["fields"] if row["table"] == table and row["column"] == column
    ]
    assert len(matches) == 1
    return matches[0]


def test_source_path_audit_is_body_free_and_classifies_mapping_shapes(
    tmp_path: Path, monkeypatch: Any
) -> None:
    _install_registry(monkeypatch)
    payload = audit.audit_source_paths(
        db_path=_db(tmp_path),
        current_audit_json=_current_audit(tmp_path),
        strict=True,
    )

    closed_at = _by_column(payload, "procore_ep_punch_items", "closed_at")
    assert closed_at["recommended_mapping"] == "map_scalar_path"
    assert closed_at["confidence"] == "high"
    assert any(
        check["json_path"] == "$.closed_at" and check["path_non_empty_count"] == 1
        for check in closed_at["candidate_json_paths_checked"]
    )

    ball_in_court = _by_column(payload, "procore_ep_rfis", "ball_in_court")
    assert ball_in_court["recommended_mapping"] == "deprecation_candidate"
    assert ball_in_court["classification"] == "object_container_requires_decomposition"

    child = _by_column(payload, "procore_ep_rfis_assignees", "response_required")
    assert child["recommended_mapping"] == "map_child_table"
    assert any(
        check["json_path"] == "$.assignees[].response_required"
        and check["path_non_empty_count"] == 1
        for check in child["candidate_json_paths_checked"]
    )

    budget = _by_column(payload, "procore_ep_budget_detail_rows", "actual_cost")
    assert budget["recommended_mapping"] == "leave_unmapped_source_absent"
    assert budget["classification"] == "source_absent_in_current_payloads"

    dumped = json.dumps(payload)
    assert "Synthetic Reviewer" not in dumped
    assert "reviewer@example.invalid" not in dumped
    assert "sample_value" not in dumped
    assert payload["summary"]["raw_payload_values_emitted"] is False
