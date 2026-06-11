"""Projection completeness matrix gate (Pass 1, Prompt 04A/04C).

Proves the mechanical completeness gate: for every source family with raw rows, unmapped
primary + nested business fields are zero (or carry a justified exclusion); the gate FAILS
closed when a novel business JSON key is observed but not in the registry; policy/system
exclusions are explicit and reasoned; and the emitted matrix/coverage carry field names +
counts only (no raw values).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.email_calendar import projection_engine as eng
from hb_assistant.construction.email_calendar import projection_matrix as matrix
from hb_assistant.construction.email_calendar import projection_registry as reg
from hb_assistant.construction.store.repositories import ConstructionStore


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "ec.sqlite"))


def _seed_full(store: ConstructionStore) -> None:
    store.upsert_email_message_raw_content(
        raw_email_id="raw:m1",
        message_id_hash="mh1",
        subject="s",
        body_text="b",
        from_address="a@hb.com",
        to_recipients_json=json.dumps([{"name": "B", "address": "b@x.com"}]),
        attachment_metadata_json=json.dumps([{"name": "f.pdf", "contentType": "x", "id": "a1"}]),
        source_quality="graph_full_body",
    )
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id="raw:e1",
        graph_event_id_hash="g1",
        body_text="agenda",
        attendees_json=json.dumps(
            [{"type": "required", "status": "none", "name": "B", "address": "b@x.com"}]
        ),
        recurrence_json=json.dumps(
            {
                "pattern": {"type": "daily", "interval": 1},
                "range": {"type": "noEnd", "startDate": "2026-01-01"},
            }
        ),
        source_quality="graph_full_event_body",
        raw_sidecar_json=json.dumps({"isAllDay": False, "categories": ["x"]}),
    )


def test_coverage_zero_unmapped_for_fixtures(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_full(store)
    conn = sqlite3.connect(store._db_path)
    cov = matrix.compute_coverage(conn)
    assert cov["ok"]
    assert cov["total_unmapped_business_fields"] == 0
    for fam in cov["families"]:
        if fam["raw_parent_rows"] > 0:
            assert fam["unmapped_primary_business_fields"] == 0
            assert fam["unmapped_nested_business_fields"] == 0
            assert fam["observed_nested_arrays_without_child_table_or_mapped_sidecar"] == 0
            assert fam["status"] in (matrix.STATUS_COMPLETE, matrix.STATUS_COMPLETE_WITH_EXCLUSIONS)


def test_gate_fails_on_unmapped_nested_key(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # inject a novel business key into the attendees array
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id="raw:e2",
        graph_event_id_hash="g2",
        body_text="a",
        attendees_json=json.dumps(
            [
                {
                    "type": "required",
                    "status": "none",
                    "name": "Z",
                    "address": "z@x.com",
                    "totally_unknown_business_key": "surprise",
                }
            ]
        ),
        source_quality="graph_full_event_body",
    )
    conn = sqlite3.connect(store._db_path)
    cov = matrix.compute_coverage(conn)
    assert cov["ok"] is False
    assert cov["total_unmapped_business_fields"] > 0
    cal = next(f for f in cov["families"] if f["source_family"] == "calendar_event")
    assert cal["status"] == matrix.STATUS_FAILED_UNMAPPED
    assert any("totally_unknown_business_key" in s for s in cal["unmapped_nested_samples"])


def test_enforce_mode_raises_on_unmapped(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id="raw:e2",
        graph_event_id_hash="g2",
        body_text="a",
        attendees_json=json.dumps([{"type": "x", "novel_unknown_key": 1}]),
        source_quality="graph_full_event_body",
    )
    with pytest.raises(eng.UnknownProjectionPath):
        eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)


def test_join_url_exclusion_is_explicit_and_reasoned(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_full(store)
    conn = sqlite3.connect(store._db_path)
    rows = matrix.matrix_rows_for_db(conn)
    join = [r for r in rows if r.raw_column_or_json_path == "join_url"]
    assert join, "join_url must appear in the matrix"
    assert join[0].destination_kind == reg.EXCLUDED_POLICY_BLOCKED
    assert "join_url_policy" in join[0].exclusion_reason


def test_system_columns_excluded_with_reason(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_full(store)
    conn = sqlite3.connect(store._db_path)
    rows = matrix.matrix_rows_for_db(conn)
    payload_hash = [
        r
        for r in rows
        if r.raw_column_or_json_path == "payload_hash"
        and r.source_table == "email_message_raw_content"
    ]
    assert payload_hash and payload_hash[0].destination_kind == reg.EXCLUDED_NON_BUSINESS
    assert payload_hash[0].exclusion_reason


def test_matrix_csv_header_matches_template(tmp_path: Path) -> None:
    # the package template CSV header the evidence must conform to
    expected = [
        "source_family",
        "source_table",
        "raw_column_or_json_path",
        "observed_type",
        "cardinality",
        "occurrence_count",
        "non_null_count",
        "empty_count",
        "business_category",
        "destination_kind",
        "destination_table",
        "destination_column",
        "extraction_strategy",
        "exclusion_reason",
        "status",
    ]
    assert expected == matrix.MATRIX_CSV_HEADER


def test_inventory_and_coverage_emit_names_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.upsert_email_message_raw_content(
        raw_email_id="raw:m1",
        message_id_hash="mh1",
        body_text="SECRET_BODY_zzz",
        source_quality="graph_full_body",
    )
    inv = eng.inventory(db_path=store._db_path)
    cov = eng.coverage(db_path=store._db_path)
    blob = json.dumps([inv, cov])
    assert "SECRET_BODY_zzz" not in blob
    # the inventory rows are field paths, not values
    assert inv["header"] == matrix.MATRIX_CSV_HEADER


def test_registry_covers_all_three_families() -> None:
    assert set(reg.SOURCE_FAMILIES) == {"email_message", "email_thread", "calendar_event"}
    for plan in reg.PLANS.values():
        assert plan.structured_table
        assert plan.required_structured_columns()
