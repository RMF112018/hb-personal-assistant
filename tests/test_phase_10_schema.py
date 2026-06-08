"""Phase 10 Prompt 02 — V41 additive migration + schema-status tests.

Covers: migration applies to V41 and is idempotent (prior versions preserved); all 21 tables
present with the 13 guard columns; guard CHECK enforcement; `ai_job_queue` environment isolation;
stale-schema fail-closed; contract↔schema guard parity; and the read-only status builder/CLI.
No Ollama, no network — additive schema only.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai.contracts import load_all_phase_10_contracts
from hb_assistant.construction.second_brain.local_ai.schema import (
    PHASE_10_GUARD_COLUMNS,
    PHASE_10_V41_TABLES,
    build_phase_10_schema_status_report,
)
from hb_assistant.construction.second_brain.phase_09_schema import PHASE_09_V38_TABLES
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

runner = CliRunner()


def _migrated_db(td: str) -> str:
    db = Path(td) / "v41.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------
def test_migration_applies_v41_with_all_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        assert LATEST_SCHEMA_VERSION >= 41  # V41 action tables coexist with later versions (e.g. V42 raw)
        conn = sqlite3.connect(db)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        missing = [t for t in PHASE_10_V41_TABLES if t not in names]
        assert missing == []
        assert len(PHASE_10_V41_TABLES) == 21


def test_migration_idempotent_and_preserves_prior_versions() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v41.db"
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION  # idempotent
        conn = sqlite3.connect(str(db))
        n41 = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=41").fetchone()[0]
        assert n41 == 1
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        # V40 + a Phase 09 (V38/39) table still present — additive only.
        assert "construction_project_keyword_registry" in names
        assert PHASE_09_V38_TABLES[0] in names


def test_every_table_has_thirteen_guard_columns() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        try:
            for table in PHASE_10_V41_TABLES:
                cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
                missing = [g for g in PHASE_10_GUARD_COLUMNS if g not in cols]
                assert missing == [], f"{table} missing {missing}"
        finally:
            conn.close()
        assert len(PHASE_10_GUARD_COLUMNS) == 13


def test_v43_candidate_review_columns_present() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        try:

            def cols(table: str) -> set[str]:
                return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}

            review_cols = {
                "snoozed_until_utc",
                "reviewed_utc",
                "reviewed_by",
                "review_note_redacted",
            }
            for table in ("task_candidates", "commitment_candidates"):
                assert review_cols <= cols(table), f"{table} missing V43 review columns"
            assert {"changes_json_redacted", "snoozed_until_utc", "reviewer_ref"} <= cols(
                "candidate_review_events"
            )
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Guard CHECK enforcement + environment isolation
# ---------------------------------------------------------------------------
def test_guard_check_rejects_nonzero() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO task_candidates (candidate_id, stable_key, title_redacted,"
                    " assignee_class, urgency, waiting_state, safety_category, confidence,"
                    " recommended_next_action, raw_prompt_persisted)"
                    " VALUES ('c1','k1','t','user','normal','unknown','normal',0.5,'review',1)"
                )
        finally:
            conn.close()


def test_ai_job_queue_environment_isolation() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        try:

            def _insert(job_id: str, env: str) -> None:
                conn.execute(
                    "INSERT INTO ai_job_queue (job_id, environment, job_type, status,"
                    " idempotency_key) VALUES (?,?,?,?,?)",
                    (job_id, env, "extract_email_tasks", "queued", "key-1"),
                )

            # Same (job_type, idempotency_key) in different environments both insert.
            _insert("j-dev", "dev")
            _insert("j-prod", "production")
            # Duplicate within the same environment violates the UNIQUE constraint.
            with pytest.raises(sqlite3.IntegrityError):
                _insert("j-dev-2", "dev")
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Schema-status report
# ---------------------------------------------------------------------------
def test_schema_status_ready() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        report = build_phase_10_schema_status_report(db_path=db)
        assert report["overall_status"] == "ready"
        assert report["schema_version"] == LATEST_SCHEMA_VERSION
        assert report["all_tables_present"] is True
        assert report["all_guards_present"] is True
        assert report["guard_sum"] == 0
        assert report["read_only"] is True
        assert report["makes_determination"] is False
        assert report["phase_10_table_count"] == 21


def test_schema_status_stale_not_ready() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        report = build_phase_10_schema_status_report(db_path=str(db))
        assert report["schema_ready"] is False
        assert report["overall_status"] == "not_ready"
        assert report["all_tables_present"] is False


def test_schema_status_does_not_mutate_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        before = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        conn.close()
        build_phase_10_schema_status_report(db_path=db)
        conn = sqlite3.connect(db)
        after = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        conn.close()
        assert before == after


def test_schema_status_writes_evidence(tmp_path) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        report = build_phase_10_schema_status_report(
            db_path=db, evidence_dir=str(tmp_path), write_evidence=True
        )
        assert report["overall_status"] == "ready"
        assert (tmp_path / "02-schema-v41-proof.json").exists()
        assert (tmp_path / "02-schema-v41-proof.md").exists()


# ---------------------------------------------------------------------------
# Contract <-> schema parity (ties Prompt 01 to Prompt 02)
# ---------------------------------------------------------------------------
def test_contract_guard_columns_match_schema() -> None:
    contracts = load_all_phase_10_contracts()
    checked = 0
    for name, body in contracts.items():
        guard_cols = body.get("guard_columns")
        if guard_cols is None:
            continue  # the action-candidate JSON Schema has no guard_columns list
        assert guard_cols == PHASE_10_GUARD_COLUMNS, name
        checked += 1
    assert checked >= 9  # all contracts except the JSON-Schema candidate output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def test_cli_schema_status_ready_exit_zero() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        result = runner.invoke(app, ["phase-10", "schema-status", "--db", db, "--json"])
        assert result.exit_code == 0, result.output
        assert '"overall_status": "ready"' in result.output


def test_cli_schema_status_stale_exit_three() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        result = runner.invoke(app, ["phase-10", "schema-status", "--db", str(db), "--json"])
        assert result.exit_code == 3
