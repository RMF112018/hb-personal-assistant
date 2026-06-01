"""Phase 07C Prompt 02 — V24 document intelligence schema additions.

Proves V24 additively (1) extends the existing empty V5 ``construction_document_cards``
via ALTER ADD COLUMN with the canonical ``document_card_id`` identity + UNIQUE INDEX and
the no-raw guard columns, (2) creates the five document satellite tables with their guard
CHECKs and indexes, (3) is idempotent, and (4) leaves V1-V23 intact. No raw-text /
signed-URL / download-URL / external-writeback value can be persisted.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_V24_SATELLITE_TABLES = [
    "construction_document_classification_candidates",
    "construction_document_project_match_candidates",
    "construction_document_relationship_candidates",
    "construction_document_intelligence_previews",
    "construction_document_projection_runs",
]

_V24_NEW_CARD_COLUMNS = [
    "document_card_id",
    "drive_id_hash",
    "drive_item_id_hash",
    "project_number_hash",
    "title_hash",
    "title_redacted",
    "file_extension",
    "mime_type",
    "size_class",
    "source_path_hash",
    "source_path_token_hashes_json",
    "last_modified_datetime",
    "source_reference_json",
    "review_status",
    "review_required",
    "review_reasons_json",
    "extraction_eligibility",
    "confidence_class",
    "guardrail_flags_json",
    "raw_document_text_persisted",
    "raw_payload_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "source_file_copied_to_vault",
    "external_writeback_performed",
]

_V24_GUARD_COLUMNS = [
    "raw_document_text_persisted",
    "raw_payload_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "source_file_copied_to_vault",
    "external_writeback_performed",
]

_V24_INDEXES = [
    "ux_document_cards_document_card_id",
    "ix_document_cards_project_type",
    "ix_document_cards_source",
    "ix_document_cards_review",
    "ix_document_relationship_candidates_target",
]


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _names(conn: sqlite3.Connection, kind: str) -> set[str]:
    return {r[0] for r in conn.execute(f"SELECT name FROM sqlite_master WHERE type='{kind}'")}


def test_v24_is_latest_and_creates_document_schema() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v24.db"
        # V24 is additive; later migrations (e.g. V25 Phase 07D) advance LATEST, so we
        # assert the migration reaches LATEST and the V24 document schema is present below.
        assert _migrate(db) == LATEST_SCHEMA_VERSION >= 24
        conn = sqlite3.connect(str(db))

        tables = _names(conn, "table")
        for t in _V24_SATELLITE_TABLES:
            assert t in tables, f"missing satellite table {t}"

        card_cols = {r[1] for r in conn.execute("PRAGMA table_info(construction_document_cards)")}
        for c in _V24_NEW_CARD_COLUMNS:
            assert c in card_cols, f"missing card column {c}"
        # the legacy V5 PK is retained untouched
        assert "card_id" in card_cols

        indexes = _names(conn, "index")
        for ix in _V24_INDEXES:
            assert ix in indexes, f"missing index {ix}"


def test_v24_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v24.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert _migrate(db) == LATEST_SCHEMA_VERSION  # second apply is a no-op
        conn = sqlite3.connect(str(db))
        n = conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 24"
        ).fetchone()[0]
        assert n == 1


@pytest.mark.parametrize("guard", _V24_GUARD_COLUMNS)
def test_v24_card_guard_columns_reject_nonzero(guard: str) -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v24.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO construction_document_cards (card_id, source_id, {guard}) "
                "VALUES ('c1', 's1', 1)"
            )


def test_v24_satellite_guard_rejects_external_writeback() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v24.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO construction_document_projection_runs "
                "(run_id, mode, status, external_writeback_performed) VALUES ('r1', 'dry', 'ok', 1)"
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO construction_document_classification_candidates "
                "(candidate_id, document_card_id, document_type, classifier_name, signal_class, "
                "confidence, confidence_class, raw_document_text_persisted) "
                "VALUES ('x', 'd', 'rfi', 'clf', 'heuristic', 0.5, 'weak_heuristic', 1)"
            )


def test_v24_leaves_prior_versions_intact() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v24.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        tables = _names(conn, "table")
        # representative V1/V5/V20/V23 tables must still be present
        for t in [
            "source_records",
            "construction_document_cards",
            "data_quality_gate_results",
            "calendar_event_index",
        ]:
            assert t in tables, f"prior-version table {t} missing after V24"
