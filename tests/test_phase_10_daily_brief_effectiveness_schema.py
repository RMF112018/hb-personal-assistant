"""Phase 10 V52 — effectiveness telemetry schema/migration tests.

Covers: migration applies to V52 and is idempotent (prior versions preserved); all 6 telemetry
tables present with the 13 guard columns; guard CHECK enforcement; no destructive change; and the
V52 guard/schema-status builder enumerates every table (refinement #5).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.local_ai.schema import (
    PHASE_10_GUARD_COLUMNS,
    PHASE_10_V52_TABLES,
    build_phase_10_v52_schema_status_report,
)
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_V52_TABLES = [
    "daily_brief_exposure_events",
    "daily_brief_item_outcome_events",
    "ranking_policy_eval_runs",
    "ranking_policy_eval_items",
    "model_profile_eval_results",
    "brief_effectiveness_rollups",
]


def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "t.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def test_migration_applies_v52_with_all_tables(tmp_path: Path) -> None:
    db = _db(tmp_path)
    assert LATEST_SCHEMA_VERSION >= 52
    conn = sqlite3.connect(db)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = [t for t in _V52_TABLES if t not in names]
    assert missing == []
    # V51 + V50 tables coexist (additive only).
    assert "daily_brief_ranked_candidates" in names
    assert "candidate_lifecycle_events" in names


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION  # second apply is a no-op
    conn = sqlite3.connect(db)
    for v in (52, 53):
        n = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = ?", (v,)).fetchone()[0]
        assert n == 1


_OLD_V52_EVAL_ITEMS_DDL = (
    "CREATE TABLE ranking_policy_eval_items ("
    "eval_run_id TEXT NOT NULL, daily_brief_action_candidate_id TEXT NOT NULL, rank_position INTEGER,"
    "section_key TEXT, candidate_family TEXT, source_family TEXT, project_key TEXT,"
    "deterministic_score REAL, feedback_score REAL, model_advisory_score REAL, final_score REAL,"
    "model_advisory_used INTEGER NOT NULL DEFAULT 0, outcome_type TEXT, outcome_weight REAL,"
    "outcome_lag_hours REAL, source_ref_count INTEGER NOT NULL DEFAULT 0, eval_notes_json TEXT,"
    "created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
    + ",".join(f"{g} INTEGER NOT NULL DEFAULT 0 CHECK({g}=0)" for g in PHASE_10_GUARD_COLUMNS)
    + ", PRIMARY KEY (eval_run_id, daily_brief_action_candidate_id))"
)


def test_v53_reconcile_adds_ranking_run_id_and_preserves_rows(tmp_path: Path) -> None:
    # Simulate a DB migrated to the ORIGINAL V52 shape (eval_items without ranking_run_id), as an
    # editable-install runner could have produced, then confirm V53 reconciles it non-destructively.
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE ranking_policy_eval_items")
    conn.execute(_OLD_V52_EVAL_ITEMS_DDL)
    conn.execute(
        "INSERT INTO ranking_policy_eval_items "
        "(eval_run_id, daily_brief_action_candidate_id, rank_position, outcome_type) "
        "VALUES ('rpe:x','cand1',1,'accepted')"
    )
    conn.execute("DELETE FROM schema_migrations WHERE version = 53")
    conn.commit()
    conn.close()

    SQLiteMigrator(db_path=db).apply()  # reconcile

    conn = sqlite3.connect(db)
    info = list(conn.execute("PRAGMA table_info(ranking_policy_eval_items)"))
    cols = {r[1] for r in info}
    pk = sorted(r[1] for r in info if r[5] > 0)
    assert "ranking_run_id" in cols
    assert pk == ["daily_brief_action_candidate_id", "eval_run_id", "ranking_run_id"]
    # Legacy row preserved, backfilled with ranking_run_id='unknown' (no data loss).
    row = conn.execute(
        "SELECT eval_run_id, ranking_run_id, daily_brief_action_candidate_id FROM ranking_policy_eval_items"
    ).fetchone()
    assert row == ("rpe:x", "unknown", "cand1")
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    # Idempotent: a re-apply leaves it untouched.
    SQLiteMigrator(db_path=db).apply()
    assert conn.execute("SELECT COUNT(*) FROM ranking_policy_eval_items").fetchone()[0] == 1


def test_every_v52_table_has_thirteen_guard_columns(tmp_path: Path) -> None:
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    assert len(PHASE_10_GUARD_COLUMNS) == 13
    for table in _V52_TABLES:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        missing = [g for g in PHASE_10_GUARD_COLUMNS if g not in cols]
        assert missing == [], f"{table} missing {missing}"


def test_guard_check_is_enforced(tmp_path: Path) -> None:
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO brief_effectiveness_rollups "
            "(rollup_id, scope, scope_key, window_start, window_end, raw_prompt_persisted) "
            "VALUES ('x','daily','k','2026-06-01','2026-06-01',1)"
        )


def test_eval_items_carry_ranking_run_id_in_pk(tmp_path: Path) -> None:
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    info = list(conn.execute("PRAGMA table_info(ranking_policy_eval_items)"))
    cols = {r[1] for r in info}
    assert "ranking_run_id" in cols
    pk = sorted(r[1] for r in info if r[5] > 0)  # r[5] = pk position (>0 means part of PK)
    assert pk == ["daily_brief_action_candidate_id", "eval_run_id", "ranking_run_id"]


def test_v52_schema_status_report_lists_all_tables(tmp_path: Path) -> None:
    db = _db(tmp_path)
    report = build_phase_10_v52_schema_status_report(db_path=db)
    assert report["overall_status"] == "ready"
    assert report["all_tables_present"] is True
    assert report["all_guards_present"] is True
    assert report["guard_sum"] == 0
    reported = {t["table_name"] for t in report["tables"]}
    assert reported == set(PHASE_10_V52_TABLES) == set(_V52_TABLES)


def test_no_destructive_schema_change(tmp_path: Path) -> None:
    # The migrator only ever creates V52 objects with IF NOT EXISTS — no DROP/destructive ALTER.
    statements = "\n".join(SQLiteMigrator.V52_STATEMENTS)
    lowered = statements.lower()
    assert "drop table" not in lowered
    assert "drop column" not in lowered
    assert " rename to" not in lowered
    assert lowered.count("create table if not exists") == 6
