from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scripts.proofs import procore_null_projection_audit as audit


def _make_db(tmp_path: Path) -> Path:
    db = tmp_path / "audit.sqlite"
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

            CREATE TABLE procore_ep_change_events (
              record_key TEXT PRIMARY KEY,
              endpoint_key TEXT NOT NULL,
              project_key TEXT,
              record_id TEXT,
              amount TEXT,
              mapped_missing_leaf TEXT,
              unmapped_all_null TEXT,
              external_writeback_performed INTEGER,
              parent_record_id TEXT,
              source_quality TEXT
            );

            CREATE TABLE procore_ep_empty (
              empty_business_field TEXT
            );

            CREATE TABLE procore_ep_rfis (
              record_key TEXT PRIMARY KEY,
              ball_in_court TEXT,
              arbitrary_unmapped_null TEXT
            );
            """
        )
        for idx in range(2):
            conn.execute(
                """
                INSERT INTO procore_endpoint_raw_payloads (
                  raw_payload_id, endpoint_key, project_key, payload_json, is_current,
                  raw_procore_payload_persisted, source_quality
                ) VALUES (?, 'change-events', 'tropical', ?, 1, 1, 'live_full_payload')
                """,
                (
                    f"raw-{idx}",
                    json.dumps({"id": idx + 1, "amount": "100.00", "container": {}}),
                ),
            )
            conn.execute(
                """
                INSERT INTO procore_ep_change_events (
                  record_key, endpoint_key, project_key, record_id, amount,
                  mapped_missing_leaf, unmapped_all_null, external_writeback_performed,
                  parent_record_id, source_quality
                ) VALUES (?, 'change-events', 'tropical', ?, NULL, NULL, NULL, 0, NULL, 'live_full_payload')
                """,
                (f"row-{idx}", str(idx + 1)),
            )
            conn.execute(
                """
                INSERT INTO procore_ep_rfis (
                  record_key, ball_in_court, arbitrary_unmapped_null
                ) VALUES (?, NULL, NULL)
                """,
                (f"rfi-{idx}",),
            )
        conn.commit()
    finally:
        conn.close()
    return db


def _install_fake_registry(monkeypatch: Any) -> None:
    plan = SimpleNamespace(
        endpoint_family="change_events",
        primary_table="procore_ep_change_events",
        primary_columns=(
            ("amount", "amount"),
            ("container.leaf", "mapped_missing_leaf"),
        ),
        child_tables=(),
    )
    monkeypatch.setattr(audit.projection_registry, "load_registry", lambda: {"change-events": plan})


def _by_column(payload: dict[str, Any], column: str) -> dict[str, Any]:
    matches = [row for row in payload["columns"] if row["column"] == column]
    assert len(matches) == 1
    return matches[0]


def test_required_root_cause_classes_and_row_context(
    tmp_path: Path, monkeypatch: Any
) -> None:
    _install_fake_registry(monkeypatch)
    payload = audit.audit_database(_make_db(tmp_path))

    amount = _by_column(payload, "amount")
    assert amount["table_total_rows"] == 2
    assert amount["classification"] == "all_null"
    assert amount["root_cause_class"] == audit.ROOT_PATH_PRESENT_NOT_WRITTEN
    assert amount["suspected_projection_defect"] is True
    assert amount["raw_path_presence"] == {
        "endpoint_key": "change-events",
        "json_path": "$.amount",
        "payload_rows_inspected": 2,
        "path_present_count": 2,
        "path_non_empty_count": 2,
        "path_missing_count": 0,
        "parent_path_present_count": 2,
        "source_quality_filter_used": (
            "is_current=1 AND raw_procore_payload_persisted=1 "
            "AND source_quality='live_full_payload'"
        ),
        "raw_payload_values_emitted": False,
    }

    missing_leaf = _by_column(payload, "mapped_missing_leaf")
    assert missing_leaf["root_cause_class"] == audit.ROOT_PATH_ABSENT
    assert missing_leaf["raw_path_presence"]["path_present_count"] == 0
    assert missing_leaf["raw_path_presence"]["parent_path_present_count"] == 2

    unmapped = _by_column(payload, "unmapped_all_null")
    assert unmapped["root_cause_class"] == audit.ROOT_UNMAPPED
    assert unmapped["suspected_projection_defect"] is True

    support = _by_column(payload, "external_writeback_performed")
    assert support["root_cause_class"] == audit.ROOT_SUPPORT
    assert support["suspected_projection_defect"] is False


def test_documented_batch_deferrals_do_not_suppress_arbitrary_unmapped_fields(
    tmp_path: Path, monkeypatch: Any
) -> None:
    _install_fake_registry(monkeypatch)
    payload = audit.audit_database(_make_db(tmp_path))

    reviewed = [
        row
        for row in payload["columns"]
        if row["table"] == "procore_ep_rfis" and row["column"] == "ball_in_court"
    ][0]
    assert reviewed["root_cause_class"] == audit.ROOT_UNMAPPED
    assert reviewed["explicitly_deferred"] is True
    assert reviewed["deferred_batch"] == "Batch B"
    assert reviewed["deferred_disposition"] == (
        "documented_object_container_or_child_field_decomposition"
    )
    assert reviewed["suspected_projection_defect"] is False

    arbitrary = [
        row
        for row in payload["columns"]
        if row["table"] == "procore_ep_rfis" and row["column"] == "arbitrary_unmapped_null"
    ][0]
    assert arbitrary["root_cause_class"] == audit.ROOT_UNMAPPED
    assert arbitrary["explicitly_deferred"] is False
    assert arbitrary["suspected_projection_defect"] is True

    assert payload["summary"]["explicitly_deferred_fields"] >= 1


def test_empty_table_and_body_free_outputs(tmp_path: Path, monkeypatch: Any) -> None:
    _install_fake_registry(monkeypatch)
    payload = audit.audit_database(_make_db(tmp_path))

    empty = [
        row
        for row in payload["columns"]
        if row["table"] == "procore_ep_empty" and row["column"] == "empty_business_field"
    ][0]
    assert empty["table_total_rows"] == 0
    assert empty["root_cause_class"] == audit.ROOT_EMPTY_TABLE
    assert empty["suspected_projection_defect"] is False

    dumped = json.dumps(payload)
    assert "sample_value" not in dumped
    assert "100.00" not in dumped
    assert all(row["raw_payload_values_emitted"] is False for row in payload["columns"])


def test_markdown_closeout_is_exact(tmp_path: Path, monkeypatch: Any) -> None:
    _install_fake_registry(monkeypatch)
    markdown = audit.render_markdown(audit.audit_database(_make_db(tmp_path)))

    assert "## Remediation Not Applied" in markdown
    assert (
        "No schema, registry, migration, projection, scheduled-refresh, live-fetch, "
        "or read-model remediation was applied by this audit."
    ) in markdown
