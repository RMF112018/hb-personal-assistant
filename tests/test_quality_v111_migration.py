"""N8C-20 — V111 quality/evaluation migration: additive, idempotent, head at LATEST, prior V100–V110
rows/tables survive, the fixed no-execution / evaluate-only / advisory-review-loop policy is pinned by CHECK,
finding_type / severity / status / event_type CHECKs accept-reject, and there is NO repair / execution /
review-disposition column anywhere."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_QUALITY_TABLES = {
    "assistant_quality_runs",
    "assistant_quality_findings",
    "assistant_quality_targets",
    "assistant_quality_receipts",
    "assistant_quality_events",
}


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def test_head_is_at_least_111(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    assert _migrate(db) == LATEST_SCHEMA_VERSION
    assert LATEST_SCHEMA_VERSION >= 111


def test_five_quality_tables_created(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'assistant_quality%'")}
    assert tables == _QUALITY_TABLES


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    assert _migrate(db) == LATEST_SCHEMA_VERSION
    assert _migrate(db) == LATEST_SCHEMA_VERSION
    with sqlite3.connect(db) as c:
        row = c.execute("SELECT name FROM schema_migrations WHERE version=111").fetchone()
    assert row[0] == "v111_assistant_quality"


def test_prior_v100_v111_versions_survive(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        versions = {r[0] for r in c.execute(
            "SELECT version FROM schema_migrations WHERE version BETWEEN 100 AND 111")}
    assert set(range(100, 112)) <= versions


def test_prior_v108_v110_tables_survive(tmp_path: Path) -> None:
    # The V111 additive migration must not drop or rewrite the N8C-14 draft / N8C-18 feedback / N8C-19
    # action-stage tables it reads.
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "assistant_answer_drafts" in names
    assert "assistant_feedback_records" in names and "assistant_feedback_recommendations" in names
    assert "assistant_action_stages" in names and "assistant_action_stage_items" in names


def test_run_action_policy_pinned_no_execution(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_quality_runs "
                  "(quality_run_id, target_kind, target_id, action_policy) "
                  "VALUES ('x','feedback','f1','execute')")


def test_run_execution_policy_pinned_evaluate_only(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_quality_runs "
                  "(quality_run_id, target_kind, target_id, execution_policy) "
                  "VALUES ('x','feedback','f1','executed')")


def test_run_review_policy_pinned_advisory(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_quality_runs "
                  "(quality_run_id, target_kind, target_id, review_policy) "
                  "VALUES ('x','feedback','f1','apply_disposition')")


def test_run_requires_operator_review_pinned(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_quality_runs "
                  "(quality_run_id, target_kind, target_id, requires_operator_review) "
                  "VALUES ('x','feedback','f1',0)")


def test_run_status_check_rejects_unknown(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_quality_runs "
                  "(quality_run_id, target_kind, target_id, status) "
                  "VALUES ('x','feedback','f1','applied')")


def test_run_target_kind_check_rejects_unknown(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_quality_runs "
                  "(quality_run_id, target_kind, target_id) VALUES ('x','not_a_kind','f1')")


def test_finding_type_check_rejects_unknown(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_quality_findings "
                  "(finding_id, quality_run_id, finding_type) VALUES ('f','r','auto_repaired')")


def test_finding_severity_check_rejects_unknown(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_quality_findings "
                  "(finding_id, quality_run_id, finding_type, severity) "
                  "VALUES ('f','r','missing_citation','fatal')")


def test_finding_execution_policy_pinned(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_quality_findings "
                  "(finding_id, quality_run_id, finding_type, execution_policy) "
                  "VALUES ('f','r','missing_citation','executed')")


def test_event_type_check_rejects_repair(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_quality_events "
                  "(event_id, quality_run_id, event_type) VALUES ('e','r','repaired')")


def test_accepts_valid_advisory_finding(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO assistant_quality_runs (quality_run_id, target_kind, target_id) "
                  "VALUES ('r','feedback','f1')")
        c.execute("INSERT INTO assistant_quality_findings "
                  "(finding_id, quality_run_id, finding_type, severity) "
                  "VALUES ('f','r','missing_citation','warn')")
        row = c.execute("SELECT action_policy, execution_policy, review_policy, requires_operator_review "
                        "FROM assistant_quality_findings WHERE finding_id='f'").fetchone()
    assert row == ("no_execution", "evaluate_only", "advisory_review_loop", 1)


def test_no_repair_execution_or_disposition_columns(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    forbidden = {"repaired", "repaired_at", "executed", "executed_at", "applied", "applied_at", "sent",
                 "dispatched", "accepted", "rejected", "deferred", "disposed", "disposition",
                 "n8d_job_id", "external_task_id", "reminder_id", "calendar_event_id"}
    with sqlite3.connect(db) as c:
        for table in _QUALITY_TABLES:
            cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
            assert not (forbidden & cols), (table, forbidden & cols)
