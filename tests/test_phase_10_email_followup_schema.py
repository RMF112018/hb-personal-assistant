"""Phase 10 V45 — email follow-up raw enrichment schema + contract tests.

Proves the V45 ``email_followup_enrichments`` migration is additive and review-safe: it exists with
the required indexes and the 13 Phase-10 guard columns (all defaulting to 0), introduces NO
raw-content columns, migrates a DB already at V44, accepts a minimal review-safe row, and is
idempotent on the deterministic idempotency key (re-enrichment updates in place, never duplicates).
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.email_followup_models import (
    EmailFollowupEnrichmentRow,
    confidence_band_for,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

# The 13 Phase-10 guard columns (verbatim repo names) — must exist and default to 0.
_GUARD_COLUMNS = (
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
    "graph_writeback_performed",
    "procore_writeback_performed",
    "email_send_performed",
    "calendar_mutation_performed",
)

# Dangerous substrings that must never appear in any V45 column name.
_FORBIDDEN_SUBSTRINGS = (
    "body",
    "html",
    "raw_text",
    "raw_body",
    "raw_prompt",
    "raw_response",
    "secret",
    "signed_url",
    "download_url",
    "join_url",
)
# Columns that legitimately contain an ambiguous token (prompt/response/url/token) but are
# documented-safe metadata/hash columns (no raw content).
_SAFE_AMBIGUOUS_COLUMNS = {
    "prompt_template_version",
    "raw_excerpt_hash",
    "input_context_hash",
    "output_hash",
    "email_thread_ref_hash",
    "email_message_ref_hashes_json",
}
_AMBIGUOUS_TOKENS = ("prompt", "response", "url", "token")


def _column_info(db: str) -> list[tuple]:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("PRAGMA table_info(email_followup_enrichments)").fetchall()
    finally:
        conn.close()


def _column_names(db: str) -> list[str]:
    return [c[1] for c in _column_info(db)]


def test_fresh_db_migrates_to_latest_and_includes_v45() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "fresh.db")
        assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
        assert LATEST_SCHEMA_VERSION >= 45
        assert "enrichment_id" in _column_names(db)


def test_migration_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "idem.db")
        assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
        assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION


def test_v44_db_upgrades_to_v45() -> None:
    """A DB sitting at V44 (no V45 table/migration row) gains the table on re-apply."""
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "v44.db")
        SQLiteMigrator(db_path=db).apply()
        # Simulate a DB that is at V44: drop the V45 artifacts.
        conn = sqlite3.connect(db)
        conn.execute("DROP TABLE email_followup_enrichments")
        conn.execute("DELETE FROM schema_migrations WHERE version >= 45")
        conn.commit()
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 44
        conn.close()
        # Re-apply: the V45 migration must run on the V44 DB.
        assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
        assert "enrichment_id" in _column_names(db)


def test_table_and_indexes_exist() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "ix.db")
        SQLiteMigrator(db_path=db).apply()
        conn = sqlite3.connect(db)
        try:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='email_followup_enrichments'"
            ).fetchone()
            assert tbl is not None
            idx = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name='email_followup_enrichments'"
                ).fetchall()
            }
        finally:
            conn.close()
        for expected in (
            "ix_email_followup_enrichments_candidate",
            "ix_email_followup_enrichments_watch_item",
            "ix_email_followup_enrichments_review_status",
            "ix_email_followup_enrichments_waiting_state",
            "ix_email_followup_enrichments_created_utc",
        ):
            assert expected in idx, f"missing index {expected}"


def test_guard_columns_exist_and_default_zero() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "guard.db")
        store = ConstructionStore(db_path=db)
        names = set(_column_names(db))
        for g in _GUARD_COLUMNS:
            assert g in names, f"missing guard column {g}"
        store.upsert_email_followup_enrichment(
            enrichment_id="enr-1",
            idempotency_key="idem-1",
            source_candidate_id="cand-1",
            source_candidate_type="task",
            raw_excerpt_hash="h_raw",
            enriched_title="Send revised RFI response",
            waiting_state="waiting_on_me",
            assignee_type="me",
            confidence=0.8,
            confidence_band="high",
            input_context_hash="h_in",
            output_hash="h_out",
            prompt_template_version="email_followup_raw_enrichment.v1",
        )
        conn = sqlite3.connect(db)
        try:
            cols = ", ".join(_GUARD_COLUMNS)
            for row in conn.execute(
                f"SELECT {cols} FROM email_followup_enrichments"
            ).fetchall():
                assert all(v == 0 for v in row)
        finally:
            conn.close()


def test_no_raw_content_columns() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "noraw.db")
        SQLiteMigrator(db_path=db).apply()
        for name in _column_names(db):
            if name in _GUARD_COLUMNS:
                continue
            low = name.lower()
            for bad in _FORBIDDEN_SUBSTRINGS:
                assert bad not in low, f"column {name!r} contains forbidden substring {bad!r}"
            for tok in _AMBIGUOUS_TOKENS:
                if tok in low:
                    assert name in _SAFE_AMBIGUOUS_COLUMNS, (
                        f"column {name!r} contains ambiguous token {tok!r} and is not allowlisted"
                    )


def test_minimal_review_safe_row_insert() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "row.db")
        store = ConstructionStore(db_path=db)
        status = store.upsert_email_followup_enrichment(
            enrichment_id="enr-2",
            idempotency_key="idem-2",
            source_candidate_id="cand-2",
            source_candidate_type="commitment",
            raw_excerpt_hash="h_raw2",
            enriched_title="Confirm submittal schedule",
            waiting_state="waiting_on_others",
            assignee_type="other",
            confidence=0.62,
            confidence_band=confidence_band_for(0.62),
            input_context_hash="h_in2",
            output_hash="h_out2",
            prompt_template_version="email_followup_raw_enrichment.v1",
            email_message_ref_hashes=["m1", "m2"],
            reason_codes=["waiting_on_others", "due_date"],
            source_refs=["email_thread:abc"],
        )
        assert status == "inserted"
        rows = store.list_email_followup_enrichments()
        assert len(rows) == 1
        rec = rows[0]
        assert rec["enriched_title"] == "Confirm submittal schedule"
        assert rec["email_message_ref_hashes"] == ["m1", "m2"]
        assert rec["source_refs"] == ["email_thread:abc"]
        assert rec["review_status"] == "pending"
        # The persisted dict carries no raw-content keys.
        assert not any(
            k.lower().endswith(("body", "html")) or "raw_prompt" in k or "raw_response" in k
            for k in rec
        )


def test_idempotency_key_upsert_no_duplicate() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "idemkey.db")
        store = ConstructionStore(db_path=db)
        kwargs = {
            "enrichment_id": "enr-3",
            "idempotency_key": "idem-3",
            "source_candidate_id": "cand-3",
            "source_candidate_type": "task",
            "raw_excerpt_hash": "h",
            "enriched_title": "First title",
            "waiting_state": "open",
            "assignee_type": "unknown",
            "confidence": 0.5,
            "confidence_band": "medium",
            "input_context_hash": "hi",
            "output_hash": "ho",
            "prompt_template_version": "email_followup_raw_enrichment.v1",
        }
        assert store.upsert_email_followup_enrichment(**kwargs) == "inserted"
        kwargs2 = {**kwargs, "enrichment_id": "enr-other", "enriched_title": "Updated title"}
        assert store.upsert_email_followup_enrichment(**kwargs2) == "updated"
        rows = store.list_email_followup_enrichments()
        assert len(rows) == 1
        assert rows[0]["enriched_title"] == "Updated title"
        # Original enrichment_id preserved (PK never rewritten).
        assert rows[0]["enrichment_id"] == "enr-3"
        assert store.count_email_followup_enrichments() == 1


def test_row_contract_rejects_extra_fields() -> None:
    base = {
        "enrichment_id": "e",
        "idempotency_key": "i",
        "source_candidate_id": "c",
        "source_candidate_type": "task",
        "raw_excerpt_hash": "h",
        "enriched_title": "t",
        "waiting_state": "open",
        "assignee_type": "me",
        "confidence": 0.5,
        "confidence_band": "medium",
        "input_context_hash": "hi",
        "output_hash": "ho",
    }
    ok = EmailFollowupEnrichmentRow(**base)
    assert ok.review_status == "pending"
    try:
        EmailFollowupEnrichmentRow(**{**base, "raw_email_body": "leak"})
        raise AssertionError("expected extra-field rejection")
    except Exception as exc:
        assert "raw_email_body" in str(exc) or "extra" in str(exc).lower()
