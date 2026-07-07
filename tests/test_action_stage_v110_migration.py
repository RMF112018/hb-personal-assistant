"""N8C-19 — V110 action-stage migration: additive, idempotent, head at LATEST, prior V100–V109 rows/tables
survive, the fixed no-execution / staged-only / preserve-review-state policy is pinned by CHECK, items are
pinned to not_executed / external_system=none / external_ref NULL, staged_state is candidate/blocked only,
citations require ≥1 provenance anchor, and there is NO execution/dispatch/external-delivery column."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_STAGE_TABLES = {
    "assistant_action_stages",
    "assistant_action_stage_items",
    "assistant_action_stage_citations",
    "assistant_action_stage_receipts",
    "assistant_action_stage_events",
}


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def test_head_is_at_least_110(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    assert _migrate(db) == LATEST_SCHEMA_VERSION
    assert LATEST_SCHEMA_VERSION >= 110


def test_five_stage_tables_created(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'assistant_action_stage%'")}
    assert tables == _STAGE_TABLES


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    assert _migrate(db) == LATEST_SCHEMA_VERSION
    assert _migrate(db) == LATEST_SCHEMA_VERSION
    with sqlite3.connect(db) as c:
        row = c.execute("SELECT name FROM schema_migrations WHERE version=110").fetchone()
    assert row[0] == "v110_assistant_action_stage"


def test_prior_v100_v110_versions_survive(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        versions = {r[0] for r in c.execute(
            "SELECT version FROM schema_migrations WHERE version BETWEEN 100 AND 110")}
    assert set(range(100, 111)) <= versions


def test_prior_v108_v109_tables_survive(tmp_path: Path) -> None:
    # The V110 additive migration must not drop or rewrite the N8C-14 draft or N8C-18 feedback tables it reads.
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "assistant_answer_drafts" in names
    assert "assistant_feedback_records" in names and "assistant_feedback_recommendations" in names


def test_stage_policy_check_rejects_execution(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_action_stages "
                  "(stage_id, stage_type, execution_policy) VALUES ('x','mixed_actions','executed')")


def test_stage_review_policy_pinned(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_action_stages "
                  "(stage_id, stage_type, review_policy) VALUES ('x','mixed_actions','apply_disposition')")


def test_item_execution_status_pinned_not_executed(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_action_stage_items "
                  "(stage_item_id, stage_id, action_kind, execution_status) "
                  "VALUES ('i','s','review_candidate','executed')")


def test_item_external_system_pinned_none(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_action_stage_items "
                  "(stage_item_id, stage_id, action_kind, external_system) "
                  "VALUES ('i','s','review_candidate','slack')")


def test_item_external_ref_must_be_null(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_action_stage_items "
                  "(stage_item_id, stage_id, action_kind, external_ref) "
                  "VALUES ('i','s','review_candidate','https://external')")


def test_item_staged_state_cannot_be_active(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_action_stage_items "
                  "(stage_item_id, stage_id, action_kind, staged_state) "
                  "VALUES ('i','s','review_candidate','active')")


def test_item_requires_operator_review_pinned(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_action_stage_items "
                  "(stage_item_id, stage_id, action_kind, requires_operator_review) "
                  "VALUES ('i','s','review_candidate',0)")


def test_citation_requires_provenance_anchor(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_action_stage_citations "
                  "(stage_citation_id, stage_id, stage_item_id) VALUES ('c','s','i')")


def test_no_finality_or_dispatch_columns(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    forbidden = {"sent", "scheduled", "completed", "executed_at", "dispatched", "emailed", "delivered",
                 "n8d_job_id", "external_task_id", "reminder_id", "calendar_event_id"}
    with sqlite3.connect(db) as c:
        for table in _STAGE_TABLES:
            cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
            assert not (forbidden & cols), (table, forbidden & cols)
