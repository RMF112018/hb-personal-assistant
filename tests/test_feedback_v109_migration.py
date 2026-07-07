"""N8C-18 — V109 feedback migration: additive, idempotent, head at LATEST, prior V100–V108 rows/tables
survive, the fixed no-execution / feedback-only / advisory-review-loop policy is pinned by CHECK, targets
require a target_id, and there is NO action-stage table and NO finality/execution/disposition column."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_FEEDBACK_TABLES = {
    "assistant_feedback_records",
    "assistant_feedback_targets",
    "assistant_feedback_recommendations",
    "assistant_feedback_receipts",
    "assistant_feedback_events",
}


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def test_head_is_at_least_109(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    assert _migrate(db) == LATEST_SCHEMA_VERSION
    assert LATEST_SCHEMA_VERSION >= 109


def test_five_feedback_tables_created(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'assistant_feedback%'")}
    assert tables == _FEEDBACK_TABLES


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    assert _migrate(db) == LATEST_SCHEMA_VERSION
    assert _migrate(db) == LATEST_SCHEMA_VERSION  # re-apply is a no-op
    with sqlite3.connect(db) as c:
        row = c.execute("SELECT name FROM schema_migrations WHERE version=109").fetchone()
    assert row[0] == "v109_assistant_feedback"


def test_prior_v100_v108_versions_survive(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        versions = {r[0] for r in c.execute(
            "SELECT version FROM schema_migrations WHERE version BETWEEN 100 AND 109")}
    assert {100, 101, 102, 103, 104, 105, 106, 107, 108, 109} <= versions


def test_prior_v108_draft_tables_survive(tmp_path: Path) -> None:
    # The V109 additive migration must not drop or rewrite the N8C-14 answer-draft tables it reads from.
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'assistant_answer_draft%'")}
    assert "assistant_answer_drafts" in tables and "assistant_answer_draft_citations" in tables


def test_policy_check_rejects_execution_claim(tmp_path: Path) -> None:
    # A feedback record can never claim execution: action_policy is pinned to 'no_execution' by CHECK.
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_feedback_records "
                  "(feedback_id, feedback_type, action_policy) VALUES ('x','useful','execute')")


def test_policy_check_rejects_review_disposition_policy(tmp_path: Path) -> None:
    # review_policy is pinned to 'advisory_review_loop' — a row can never assert it applies a disposition.
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_feedback_records "
                  "(feedback_id, feedback_type, review_policy) VALUES ('x','useful','apply_disposition')")


def test_requires_operator_review_pinned_to_one(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_feedback_records "
                  "(feedback_id, feedback_type, requires_operator_review) VALUES ('x','useful',0)")


def test_feedback_type_check_rejects_unknown(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_feedback_records "
                  "(feedback_id, feedback_type) VALUES ('x','accepted')")


def test_target_requires_target_id(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_feedback_targets "
                  "(feedback_target_id, feedback_id, target_kind, target_id) "
                  "VALUES ('t','f','open_loop',NULL)")


def test_recommendation_policy_pinned(tmp_path: Path) -> None:
    # A recommendation is advisory-only: review_policy CHECK forbids any disposition-applying value.
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_feedback_recommendations "
                  "(recommendation_id, feedback_id, recommendation_type, review_policy) "
                  "VALUES ('r','f','suggest_review','accept')")


def test_no_action_stage_tables(tmp_path: Path) -> None:
    # N8C-18 is feedback-only. Action staging is a SEPARATE later phase (N8C-19); no such table here.
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'assistant_action%'")}
    assert tables == set()


def test_no_finality_or_disposition_columns_on_feedback_tables(tmp_path: Path) -> None:
    # No column may express an applied review disposition, an execution, or a dispatched action.
    db = tmp_path / "h.db"
    _migrate(db)
    forbidden = {"accepted", "rejected", "deferred", "disposed", "disposition", "executed",
                 "execution_status", "sent", "scheduled", "external_ref", "external_system",
                 "dispatched", "final_answer", "answer_text"}
    with sqlite3.connect(db) as c:
        for table in _FEEDBACK_TABLES:
            cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
            assert not (forbidden & cols), (table, forbidden & cols)
