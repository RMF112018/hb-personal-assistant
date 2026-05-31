"""Tests for V20 additive data-quality schema (Prompt 01).

Covers:
- Tables and indexes are created.
- Prior schema (V1-V19) is preserved.
- Migration is idempotent.
- CHECK guardrails reject raw_body_persisted / full_text_persisted / external_writeback_performed = 1.
- Basic round-trips via ConstructionStore adapters.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator


def _migrate(db_path: str | Path) -> int:
    return SQLiteMigrator(db_path=str(db_path)).apply()


def _get_tables_and_indexes(db_path: str | Path) -> tuple[set[str], set[str]]:
    conn = sqlite3.connect(str(db_path))
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'"
        )}
        indexes = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        )}
        return tables, indexes
    finally:
        conn.close()


_V20_TABLES = {
    "construction_data_quality_runs",
    "construction_table_lifecycle_registry",
    "source_system_record_map",
    "relationship_resolution_queue",
    "project_source_coverage_mart",
    "data_quality_gate_results",
}

_V20_INDEXES = {
    "ix_source_record_map_project_system",
    "ix_source_record_map_source_key",
    "ix_source_record_map_type_status",
    "ix_relationship_resolution_status_confidence",
    "ix_relationship_resolution_from",
    "ix_relationship_resolution_to",
    "ix_project_source_coverage_project_domain",
    "ix_data_quality_gate_results_run_status",
}


def test_v20_applies_and_creates_tables_and_indexes() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v20.db"
        version = _migrate(db)
        assert version == 20
        tables, indexes = _get_tables_and_indexes(db)
        assert not (_V20_TABLES - tables), f"V20 tables missing: {sorted(_V20_TABLES - tables)}"
        assert not (_V20_INDEXES - indexes), f"V20 indexes missing: {sorted(_V20_INDEXES - indexes)}"


def test_v20_preserves_all_prior_tables_and_views() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v20.db"
        _migrate(db)
        tables, _ = _get_tables_and_indexes(db)
        # Spot-check core prior tables from V1, V5, V6, V7, V10, V11 etc.
        assert "source_records" in tables  # V1
        assert "construction_drive_items" in tables  # V5
        assert "procore_live_records" in tables  # V6
        assert "procore_action_signals" in tables  # V7
        assert "email_messages" in tables  # V11
        assert "construction_file_extraction_runs" in tables  # V19
        # Views from V7
        assert "v_procore_open_action_signals" in tables
        assert "v_procore_inspection_unanswered_items" in tables


def test_v20_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v20.db"
        v1 = _migrate(db)
        v2 = _migrate(db)
        assert v1 == 20 and v2 == 20
        # schema_migrations should have exactly one row for v20
        conn = sqlite3.connect(str(db))
        try:
            cur = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 20")
            assert cur.fetchone()[0] == 1
        finally:
            conn.close()


@pytest.mark.parametrize("flag_col", ["raw_body_persisted", "external_writeback_performed"])
def test_data_quality_runs_check_rejects_bad_flags(flag_col: str) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v20.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    f"INSERT INTO construction_data_quality_runs (run_id, phase, started_utc, status, {flag_col}) VALUES ('r1','p','2026-05-31','ok',1)"
                )
        finally:
            conn.close()


def test_source_system_record_map_check_rejects_raw_and_full_text() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v20.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO source_system_record_map (canonical_record_id, source_system, source_table, source_primary_key, confidence_class, raw_body_persisted) "
                    "VALUES ('canon1','procore','procore_live_records','123','deterministic',1)"
                )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO source_system_record_map (canonical_record_id, source_system, source_table, source_primary_key, confidence_class, full_text_persisted) "
                    "VALUES ('canon2','email','email_messages','msg-1','heuristic',1)"
                )
        finally:
            conn.close()


def test_relationship_resolution_queue_check_rejects_full_text() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v20.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO relationship_resolution_queue (relationship_id, from_source_system, relationship_type, relationship_status, confidence_class, full_text_persisted) "
                    "VALUES ('rel1','procore','same_project','candidate','heuristic',1)"
                )
        finally:
            conn.close()


def test_construction_store_adapters_round_trip_and_enforce_flags() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v20.db"
        _migrate(db)
        store = ConstructionStore(db_path=str(db))

        # data quality run
        store.insert_data_quality_run(run_id="dq-run-1", phase="07A", started_utc="2026-05-31T05:00:00Z", status="ok", schema_version=20)
        # table lifecycle
        store.upsert_table_lifecycle_registry({
            "table_name": "source_system_record_map",
            "table_family": "data_quality_v20",
            "lifecycle_status": "operational_populated",
            "expected_population_status": "populated",
        })
        # source record (adapter must force flags=0 even if caller tries bad value)
        with pytest.raises(ValueError, match="raw_body_persisted must be False"):
            store.upsert_source_system_record({
                "canonical_record_id": "c1",
                "source_system": "procore",
                "source_table": "procore_live_records",
                "source_primary_key": "2525840-123",
                "confidence_class": "deterministic",
                "raw_body_persisted": 1,
            })
        canon = store.upsert_source_system_record({
            "canonical_record_id": "c1",
            "source_system": "procore",
            "source_table": "procore_live_records",
            "source_primary_key": "2525840-123",
            "confidence_class": "deterministic",
            "project_key": "tropical",
        })
        assert canon == "c1"

        # relationship
        store.insert_relationship_resolution_candidate({
            "relationship_id": "r1",
            "from_source_system": "procore",
            "relationship_type": "same_project",
            "relationship_status": "candidate",
            "confidence_class": "heuristic",
        })

        # coverage + gate
        store.upsert_project_source_coverage({
            "coverage_id": "cov-tropical-procore",
            "run_id": "dq-run-1",
            "project_key": "tropical",
            "source_domain": "procore",
            "quality_status": "partial",
        })
        store.insert_data_quality_gate_result({
            "gate_result_id": "g1",
            "run_id": "dq-run-1",
            "gate_name": "identity_population",
            "gate_status": "pass",
            "blocking": 0,
        })

        # verify via direct query (light)
        conn = sqlite3.connect(str(db))
        try:
            assert conn.execute("SELECT COUNT(*) FROM construction_data_quality_runs WHERE run_id='dq-run-1'").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM source_system_record_map WHERE canonical_record_id='c1'").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM relationship_resolution_queue WHERE relationship_id='r1'").fetchone()[0] == 1
        finally:
            conn.close()


def test_construction_agent_validate_reports_v20() -> None:
    # Indirect: after migration the validate command (invoked in CI) must report 20.
    # We just ensure the migrator reports 20; full CLI exercised in the proof run.
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v20.db"
        assert _migrate(db) == 20
