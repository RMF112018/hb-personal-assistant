"""Phase 07D Prompt 02 — V25 cross-source relationship + meeting-prep schema additions.

Proves V25 additively (1) creates the ten 07D substrate tables that ship empty, (2)
enforces the eight no-raw / no-writeback guard columns via CHECK(... = 0) on every
table, (3) enforces the domain CHECKs (confidence_class, promotion_status, mode,
risk_source_class) and the UNIQUE edge keys that make apply() idempotent and dedup-safe,
(4) defaults relationship candidates to review_required, (5) is idempotent, and (6)
leaves V1-V24 intact. No raw body/text/payload, prompt, response, signed/download URL,
or external-writeback value can be persisted.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_V25_TABLES = [
    "cross_source_relationship_candidates",
    "cross_source_relationships",
    "source_evidence_trails",
    "meeting_prep_brief_runs",
    "meeting_prep_brief_sections",
    "project_issue_history_items",
    "project_risk_digest_items",
    "aging_exposure_report_items",
    "cross_source_intelligence_obsidian_runs",
    "phase_07d_validation_runs",
]

# The eight guard columns required by 05_SCHEMA_AND_MIGRATION_PLAN on every 07D table.
_V25_GUARD_COLUMNS = [
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
]


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _names(conn: sqlite3.Connection, kind: str) -> set[str]:
    return {r[0] for r in conn.execute(f"SELECT name FROM sqlite_master WHERE type='{kind}'")}


def _insert_candidate(conn: sqlite3.Connection, candidate_id: str, ref: str = "r1") -> None:
    conn.execute(
        "INSERT INTO cross_source_relationship_candidates "
        "(candidate_id, source_family, source_record_type, source_record_ref, "
        "target_family, target_record_type, target_record_ref, relationship_type, "
        "confidence_score, confidence_class, source_reference_json) "
        "VALUES (?, 'email', 'email_thread', ?, 'procore', 'rfi', 't1', 'references', "
        "0.9, 'deterministic', '{}')",
        (candidate_id, ref),
    )


def test_v25_is_latest_and_creates_substrate_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v25.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION == 25
        conn = sqlite3.connect(str(db))
        tables = _names(conn, "table")
        for t in _V25_TABLES:
            assert t in tables, f"missing 07D table {t}"
            # every 07D table ships empty
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0


def test_v25_every_table_has_eight_guard_columns() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v25.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        for t in _V25_TABLES:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
            for guard in _V25_GUARD_COLUMNS:
                assert guard in cols, f"{t} missing guard column {guard}"


@pytest.mark.parametrize("table", _V25_TABLES)
def test_v25_every_table_declares_all_eight_guard_checks(table: str) -> None:
    """Each 07D table's DDL declares ``CHECK(<guard> = 0)`` for all eight guards."""
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v25.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        for guard in _V25_GUARD_COLUMNS:
            assert f"CHECK({guard} = 0)" in ddl, f"{table} missing CHECK({guard} = 0)"


def test_v25_guard_check_rejects_nonzero_on_valid_row() -> None:
    """A fully valid row with a single guard flipped to 1 raises the guard CHECK."""
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v25.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        # evidence trail: all NOT NULL columns supplied, download_url_persisted = 1
        with pytest.raises(sqlite3.IntegrityError) as exc:
            conn.execute(
                "INSERT INTO source_evidence_trails "
                "(evidence_trail_id, evidence_kind, source_refs_json, confidence_class, "
                "download_url_persisted) VALUES ('e1', 'relationship', '[]', 'deterministic', 1)"
            )
        assert "download_url_persisted = 0" in str(exc.value)
        # the same row with the guard at 0 inserts cleanly
        conn.execute(
            "INSERT INTO source_evidence_trails "
            "(evidence_trail_id, evidence_kind, source_refs_json, confidence_class) "
            "VALUES ('e2', 'relationship', '[]', 'deterministic')"
        )
        assert conn.execute("SELECT COUNT(*) FROM source_evidence_trails").fetchone()[0] == 1
        # candidate row with raw_email_body_persisted = 1 is rejected
        with pytest.raises(sqlite3.IntegrityError) as exc2:
            conn.execute(
                "INSERT INTO cross_source_relationship_candidates "
                "(candidate_id, source_family, source_record_type, source_record_ref, "
                "target_family, target_record_type, target_record_ref, relationship_type, "
                "confidence_score, confidence_class, source_reference_json, "
                "raw_email_body_persisted) "
                "VALUES ('c', 'email', 'x', 'r', 'procore', 'rfi', 't', 'rel', 0.9, "
                "'weak_heuristic', '{}', 1)"
            )
        assert "raw_email_body_persisted = 0" in str(exc2.value)


def test_v25_domain_checks_reject_bad_values() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v25.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        # bad confidence_class on candidates
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO cross_source_relationship_candidates "
                "(candidate_id, source_family, source_record_type, source_record_ref, "
                "target_family, target_record_type, target_record_ref, relationship_type, "
                "confidence_score, confidence_class, source_reference_json) "
                "VALUES ('c', 'email', 'x', 'r', 'procore', 'rfi', 't', 'rel', 0.1, 'bogus', '{}')"
            )
        # bad mode on a run ledger
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO meeting_prep_brief_runs "
                "(brief_run_id, project_key, mode, lookahead_days, status) "
                "VALUES ('b', 'tropical', 'sideways', 7, 'ok')"
            )
        # bad risk_source_class
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO project_risk_digest_items "
                "(risk_digest_id, project_key, risk_indicator_type, risk_source_class, "
                "summary_redacted, confidence_class) "
                "VALUES ('rd', 'tropical', 'schedule', 'made_up', '...', 'deterministic')"
            )


def test_v25_candidate_review_required_defaults_to_one() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v25.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        _insert_candidate(conn, "c1")
        got = conn.execute(
            "SELECT review_required FROM cross_source_relationship_candidates WHERE candidate_id='c1'"
        ).fetchone()[0]
        assert got == 1


def test_v25_unique_edge_key_dedups_candidates() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v25.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        _insert_candidate(conn, "c1", ref="same")
        with pytest.raises(sqlite3.IntegrityError):
            # different PK, identical edge -> UNIQUE(source/target/type) rejects it
            _insert_candidate(conn, "c2", ref="same")


def test_v25_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v25.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert _migrate(db) == LATEST_SCHEMA_VERSION  # second apply is a no-op
        conn = sqlite3.connect(str(db))
        n = conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 25"
        ).fetchone()[0]
        assert n == 1


def test_v25_leaves_prior_versions_intact() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v25.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        tables = _names(conn, "table")
        for t in [
            "source_records",
            "construction_document_cards",
            "construction_document_relationship_candidates",
            "data_quality_gate_results",
            "calendar_event_index",
        ]:
            assert t in tables, f"prior-version table {t} missing after V25"
