from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from scripts.proofs import procore_budget_financial_source_path_triage as triage


def _make_db(tmp_path: Path) -> Path:
    db = tmp_path / "triage.sqlite"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(
            """
            CREATE TABLE procore_endpoint_raw_payloads (
              raw_payload_id TEXT PRIMARY KEY,
              endpoint_key TEXT NOT NULL,
              project_key TEXT,
              payload_json TEXT NOT NULL,
              is_current INTEGER NOT NULL,
              raw_procore_payload_persisted INTEGER NOT NULL,
              source_quality TEXT NOT NULL
            );

            CREATE TABLE procore_ep_budget_detail_rows (
              record_key TEXT PRIMARY KEY,
              project_key TEXT,
              actual_cost TEXT,
              cost_type TEXT,
              cost_type_id TEXT,
              line_item_type_id TEXT
            );

            CREATE TABLE procore_ep_budget_detail_row_cells (
              cell_key TEXT PRIMARY KEY,
              project_key TEXT,
              is_current INTEGER NOT NULL,
              column_name TEXT,
              column_label TEXT,
              field_path TEXT,
              value_decimal_text TEXT,
              currency_iso_code TEXT
            );

            CREATE TABLE procore_ep_change_events_change_items (
              record_key TEXT PRIMARY KEY,
              project_key TEXT,
              cost_impact_contract_confirmed TEXT,
              cost_impact_vendor_confirmed TEXT
            );
            """
        )
        for idx in range(2):
            conn.execute(
                """
                INSERT INTO procore_ep_budget_detail_rows
                  (record_key, project_key, actual_cost, cost_type, cost_type_id, line_item_type_id)
                VALUES (?, 'tropical', NULL, NULL, NULL, NULL)
                """,
                (f"budget-row-{idx}",),
            )
        conn.execute(
            """
            INSERT INTO procore_ep_budget_detail_row_cells (
              cell_key, project_key, is_current, column_name, column_label, field_path,
              value_decimal_text, currency_iso_code
            ) VALUES ('cell-1', 'tropical', 1, 'actual_cost', 'Actual Cost', 'actual_cost',
              '100.00', NULL)
            """
        )
        for idx in range(2):
            conn.execute(
                """
                INSERT INTO procore_ep_change_events_change_items (
                  record_key, project_key, cost_impact_contract_confirmed,
                  cost_impact_vendor_confirmed
                ) VALUES (?, 'tropical', NULL, NULL)
                """,
                (f"change-item-{idx}",),
            )
        conn.execute(
            """
            INSERT INTO procore_endpoint_raw_payloads (
              raw_payload_id, endpoint_key, project_key, payload_json, is_current,
              raw_procore_payload_persisted, source_quality
            ) VALUES ('raw-budget-1', 'budget-detail-rows', 'tropical', ?, 1, 1,
              'live_full_payload')
            """,
            (
                json.dumps(
                    {
                        "id": "row-1",
                        "cost_type": {"id": 3, "abbreviation": "MAT"},
                        "line_item_type_id": 3,
                        "custom_budget_modification": "do not confuse",
                    }
                ),
            ),
        )
        conn.execute(
            """
            INSERT INTO procore_endpoint_raw_payloads (
              raw_payload_id, endpoint_key, project_key, payload_json, is_current,
              raw_procore_payload_persisted, source_quality
            ) VALUES ('raw-change-1', 'change-events', 'tropical', ?, 1, 1,
              'live_full_payload')
            """,
            (
                json.dumps(
                    {
                        "id": "ce-1",
                        "change_items": [
                            {
                                "id": "ci-1",
                                "cost_impact": {"contract_confirmed": True},
                                "budget_impact": {
                                    "budget_modification": {
                                        "amount": "999.99",
                                        "description": "must not leak",
                                    }
                                },
                            }
                        ],
                    }
                ),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return db


def _audit_json(tmp_path: Path) -> Path:
    path = tmp_path / "audit.json"
    columns: list[dict[str, Any]] = []
    for target in triage.TARGETS:
        columns.append(
            {
                "table": target.table,
                "column": target.column,
                "null_rate": 1.0,
                "root_cause_class": "schema_column_not_in_projection_registry",
                "classification": "all_null",
            }
        )
    path.write_text(json.dumps({"columns": columns}))
    return path


def _by_column(payload: dict[str, Any], column: str) -> dict[str, Any]:
    matches = [row for row in payload["target_fields"] if row["column"] == column]
    assert len(matches) == 1
    return matches[0]


def test_body_free_output_and_allowed_next_actions(tmp_path: Path) -> None:
    payload = triage.triage_database(_make_db(tmp_path), audit_json=_audit_json(tmp_path))
    dumped = json.dumps(payload)

    assert "sample_value" not in dumped
    assert "999.99" not in dumped
    assert "100.00" not in dumped
    assert "must not leak" not in dumped
    assert "custom_budget_modification" not in dumped
    assert all(
        row["next_action"] in triage.NEXT_ACTIONS for row in payload["target_fields"]
    )
    assert all(row["raw_payload_values_emitted"] is False for row in payload["target_fields"])


def test_budget_detail_distinguishes_row_source_from_dynamic_cell(tmp_path: Path) -> None:
    payload = triage.triage_database(_make_db(tmp_path), audit_json=_audit_json(tmp_path))

    actual_cost = _by_column(payload, "actual_cost")
    assert actual_cost["classification"] == triage.CLASS_DYNAMIC_CELL
    assert actual_cost["next_action"] == "no_action_dynamic_cell_already_handled"
    assert actual_cost["dynamic_cell_evidence"]["matching_cell_rows"] == 1
    assert actual_cost["path_checks"][0]["path_present_count"] == 0

    cost_type = _by_column(payload, "cost_type")
    assert cost_type["classification"] == triage.CLASS_ROW_SOURCE
    assert cost_type["next_action"] == "approve_mapping_patch_next"
    assert cost_type["path_checks"][0]["path_non_empty_count"] == 1

    line_item = _by_column(payload, "line_item_type_id")
    assert line_item["classification"] == triage.CLASS_ROW_SOURCE
    assert line_item["next_action"] == "approve_mapping_patch_next"


def test_change_event_confirmation_paths_are_not_budget_modification(tmp_path: Path) -> None:
    payload = triage.triage_database(_make_db(tmp_path), audit_json=_audit_json(tmp_path))

    contract = _by_column(payload, "cost_impact_contract_confirmed")
    assert contract["classification"] == triage.CLASS_ROW_SOURCE
    assert contract["next_action"] == "approve_mapping_patch_next"
    checked_paths = {check["json_path"] for check in contract["path_checks"]}
    assert "$.change_items[].cost_impact.contract_confirmed" in checked_paths
    assert all("budget_modification" not in path for path in checked_paths)

    vendor = _by_column(payload, "cost_impact_vendor_confirmed")
    assert vendor["classification"] == triage.CLASS_SCHEMA_ARTIFACT
    assert vendor["next_action"] == "document_schema_artifact"
    checked_paths = {check["json_path"] for check in vendor["path_checks"]}
    assert all("budget_modification" not in path for path in checked_paths)


def test_markdown_closeout_states_no_remediation(tmp_path: Path) -> None:
    payload = triage.triage_database(_make_db(tmp_path), audit_json=_audit_json(tmp_path))
    markdown = triage.render_markdown(payload)

    assert "No remediation was applied; null projection counts were intentionally unchanged." in markdown
    assert "No live calls were made." in markdown
    assert "SourceRefreshOrchestrator" in markdown
