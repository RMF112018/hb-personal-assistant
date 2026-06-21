"""Phase 08A Prompt 02 — V26 second-brain runtime schema additions.

Proves V26 additively (1) creates the 21 second-brain substrate tables that ship empty,
(2) declares + enforces the no-raw / no-writeback guard `CHECK(col = 0)` columns that each
table carries (guard sets vary per table and are derived from the DDL), (3) enforces the
review-tier `CHECK(review_tier IN (1,2,3))` and the operator-preference UNIQUE key,
(4) defaults research packets to the most-conservative Tier 3 + pending_review,
(5) is idempotent, and (6) leaves V1-V25 intact. It also proves the lifecycle contract
classifies every V26 table as operational_empty_expected (none unmapped) at count 142
(141 through V26 + the V27 daily_brief_handoff_lines table).
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.data_quality import build_table_inventory_report
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_V26_TABLES = [
    "second_brain_runtime_config_receipts",
    "obsidian_index_manifests",
    "obsidian_index_entries",
    "retrieval_query_receipts",
    "retrieval_context_refs",
    "query_tool_receipts",
    "interactive_chat_sessions",
    "interactive_chat_message_receipts",
    "long_term_memory_items",
    "long_term_memory_source_refs",
    "long_term_memory_quality_signals",
    "memory_update_candidates",
    "memory_update_reviews",
    "second_brain_research_packets",
    "second_brain_evaluation_runs",
    "second_brain_operator_feedback",
    "second_brain_operator_preference_profiles",
    "daily_brief_runs",
    "daily_brief_source_refs",
    "launchd_schedule_previews",
    "phase_08a_validation_runs",
]

# Any column whose name implies it could carry raw content / writeback / arbitrary SQL
# MUST be guarded with CHECK(col = 0). This is the canonical guard-name set used across
# the V26 tables (each table declares the subset relevant to what it can hold).
_GUARD_NAME_RE = re.compile(
    r"(raw_email_body_persisted|raw_document_text_persisted|raw_calendar_payload_persisted|"
    r"raw_prompt_persisted|raw_response_persisted|retrieved_context_persisted|"
    r"signed_url_persisted|download_url_persisted|arbitrary_sql_allowed|"
    r"external_writeback_performed)"
)


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _names(conn: sqlite3.Connection, kind: str) -> set[str]:
    return {r[0] for r in conn.execute(f"SELECT name FROM sqlite_master WHERE type='{kind}'")}


def _ddl(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    assert row is not None, f"missing table {table}"
    return str(row[0])


def _guard_columns(ddl: str) -> set[str]:
    return set(_GUARD_NAME_RE.findall(ddl))


def test_v26_is_latest_and_creates_substrate_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v26.db"
        # V26 ships through the head schema (>= 26); forward bumps add tables, never remove.
        assert _migrate(db) == LATEST_SCHEMA_VERSION >= 26
        conn = sqlite3.connect(str(db))
        tables = _names(conn, "table")
        for t in _V26_TABLES:
            assert t in tables, f"missing V26 table {t}"
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0


def test_v26_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v26.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        conn = sqlite3.connect(str(db))
        n = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 26").fetchone()[0]
        assert n == 1


_V27_TABLES = ["daily_brief_handoff_lines"]


def test_v27_creates_handoff_lines_table_with_guards() -> None:
    """V27 additively creates the durable daily_brief_handoff_lines table (ships empty),
    declaring the canonical no-raw / no-writeback guard CHECK(col = 0) columns."""
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v27.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        for t in _V27_TABLES:
            assert t in _names(conn, "table"), f"missing V27 table {t}"
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
        guards = _guard_columns(_ddl(conn, "daily_brief_handoff_lines"))
        for col in (
            "raw_email_body_persisted",
            "raw_document_text_persisted",
            "raw_calendar_payload_persisted",
            "raw_prompt_persisted",
            "raw_response_persisted",
            "retrieved_context_persisted",
            "signed_url_persisted",
            "download_url_persisted",
            "external_writeback_performed",
        ):
            assert col in guards, f"missing guard column {col}"
        # The guard CHECK(col = 0) is enforced: a nonzero write is rejected.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO daily_brief_handoff_lines "
                "(line_id, brief_run_id, section, line_index, title_redacted, "
                " external_writeback_performed) VALUES ('l1','r1','priority_actions',0,'t',1)"
            )


def test_v27_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v27.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        conn = sqlite3.connect(str(db))
        n = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 27").fetchone()[0]
        assert n == 1


@pytest.mark.parametrize("table", _V26_TABLES)
def test_v26_guard_columns_declare_check_zero(table: str) -> None:
    """Every guard-named column on each table is declared CHECK(col = 0)."""
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v26.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        ddl = _ddl(conn, table)
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        # Any guard-named column present must carry the CHECK(... = 0) clause.
        for guard in _guard_columns(ddl):
            assert guard in cols
            assert f"CHECK({guard} = 0)" in ddl, f"{table}.{guard} missing CHECK(=0)"


def test_v26_output_tables_carry_guards() -> None:
    """Tables that can hold summaries/receipts carry at least one guard column."""
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v26.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        for t in (
            "second_brain_runtime_config_receipts",
            "retrieval_query_receipts",
            "second_brain_research_packets",
            "second_brain_evaluation_runs",
            "daily_brief_runs",
            "long_term_memory_items",
            "memory_update_candidates",
            "query_tool_receipts",
            "phase_08a_validation_runs",
        ):
            assert _guard_columns(_ddl(conn, t)), f"{t} declares no guard column"


def test_v26_guard_check_rejects_nonzero() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v26.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        with pytest.raises(sqlite3.IntegrityError) as exc:
            conn.execute(
                "INSERT INTO daily_brief_runs "
                "(brief_run_id, brief_date, mode, status, raw_prompt_persisted) "
                "VALUES ('b1', '2026-06-02', 'dry_run', 'ok', 1)"
            )
        assert "raw_prompt_persisted = 0" in str(exc.value)


def test_v26_review_tier_check_constrains_values() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v26.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        # Tier 4 rejected.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO second_brain_research_packets "
                "(packet_id, mode, topic_hash, status, review_tier) "
                "VALUES ('p1', 'dry_run', 'h1', 'ok', 4)"
            )
        # Tier 2 accepted.
        conn.execute(
            "INSERT INTO second_brain_research_packets "
            "(packet_id, mode, topic_hash, status, review_tier) "
            "VALUES ('p2', 'dry_run', 'h2', 'ok', 2)"
        )


def test_v26_research_packet_defaults_to_tier3_pending_review() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v26.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        conn.execute(
            "INSERT INTO second_brain_research_packets "
            "(packet_id, mode, topic_hash, status) VALUES ('p3', 'dry_run', 'h3', 'ok')"
        )
        tier, status, advisory = conn.execute(
            "SELECT review_tier, review_status, advisory_classification "
            "FROM second_brain_research_packets WHERE packet_id='p3'"
        ).fetchone()
        assert tier == 3 and status == "pending_review" and advisory == "advisory"


def test_v26_memory_candidates_default_review_required() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v26.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        conn.execute(
            "INSERT INTO memory_update_candidates "
            "(candidate_id, proposed_memory_type, statement_redacted, confidence_class, "
            "source_refs_json, status) VALUES ('c1', 'fact', '<redacted>', 'model_proposed', "
            "'[]', 'proposed')"
        )
        rr = conn.execute(
            "SELECT review_required FROM memory_update_candidates WHERE candidate_id='c1'"
        ).fetchone()[0]
        assert rr == 1


def test_v26_preference_profile_unique_key() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v26.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        ins = (
            "INSERT INTO second_brain_operator_preference_profiles "
            "(preference_id, scope, scope_key, preference_key) VALUES (?, 'project', 'tropical', 'tone')"
        )
        conn.execute(ins, ("pref1",))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(ins, ("pref2",))


def test_v26_leaves_prior_versions_intact() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v26.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        tables = _names(conn, "table")
        for t in (
            "schema_migrations",
            "construction_document_cards",
            "cross_source_relationship_candidates",
            "meeting_prep_brief_runs",
            "phase_07d_validation_runs",
        ):
            assert t in tables, f"prior-version table {t} missing after V26"


def test_v26_tables_classified_in_lifecycle_contract() -> None:
    """The inventory classifies every V26 table operational_empty_expected, none unmapped."""
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v26.db"
        _migrate(db)
        report = build_table_inventory_report(db_path=str(db))
        assert report["contract_table_count"] == 399  # Phase 4: +8 v61 external-forecast tables (was 391)
        by_name = {t["table_name"]: t for t in report["tables"]}
        for t in _V26_TABLES:
            assert t in by_name, f"{t} absent from live inventory"
            assert by_name[t]["lifecycle_status"] == "operational_empty_expected"
            assert by_name[t].get("source") == "contract"
        assert report["reconciliation"]["in_db_not_in_contract"] == []
