"""Phase 06 Prompt 11 — V14 advisory email-classification read model.

Proves V14 adds email_model_classifications additively (V1-V13 preserved), that the
CHECK constraints reject loosened advisory/plaintext/raw-prompt/raw-response flags, that
no plaintext-body column exists, and that the store upsert/get/list helpers round-trip and
upsert idempotently on (message_id, model_name, schema_version).
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def test_v14_applies_and_is_idempotent() -> None:
    db = _temp_db()
    assert _migrate(db) == 14
    assert _migrate(db) == 14
    conn = sqlite3.connect(str(db))
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "email_model_classifications" in tables
        # V1-V13 anchors preserved.
        assert {"email_review_queue", "email_message_body_vault_refs", "email_messages"} <= tables
        count = conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 14"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1


@pytest.mark.parametrize(
    "column,value",
    [
        ("advisory_only", 0),
        ("plaintext_body_persisted", 1),
        ("raw_prompt_persisted", 1),
        ("raw_response_persisted", 1),
    ],
)
def test_check_rejects_loosened_flag(column: str, value: int) -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO email_model_classifications "
                f"(classification_id, message_id, model_name, schema_version, "
                f"classification_status, {column}) "
                f"VALUES ('c1', 'm1', 'mistral', 'v1', 'valid', {value})"
            )
    finally:
        conn.close()


def test_no_plaintext_body_column() -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(email_model_classifications)")}
    finally:
        conn.close()
    forbidden = {"body", "body_text", "body_html", "raw_email", "plain_text",
                 "raw_prompt", "raw_response", "prompt", "response"}
    assert not (cols & forbidden), f"forbidden columns present: {cols & forbidden}"


def _store_with_message() -> tuple[ConstructionStore, str]:
    store = ConstructionStore(str(_temp_db()))
    store.upsert_email_source_location(
        source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F"
    )
    store.upsert_email_message(message_id="m1", thread_key="t1", source_id="sx")
    return store, "m1"


def test_upsert_get_list_round_trip_and_idempotent() -> None:
    store, mid = _store_with_message()
    store.upsert_email_model_classification(
        classification_id="c1",
        message_id=mid,
        model_name="mistral",
        schema_version="phase06-email-ollama-v1",
        classification_status="valid",
        project_key="tropical",
        project_match_confidence=0.8,
        topic_labels=["schedule"],
        relationship_candidates=[{"candidate_type": "procore_rfi", "target_hint": "12", "confidence": 0.7}],
        risk_flags=["delay"],
        sensitive_categories=["contracts"],
        review_required=True,
        review_reasons=["sensitive_category:contracts"],
    )
    got = store.get_email_model_classification(
        message_id=mid, model_name="mistral", schema_version="phase06-email-ollama-v1"
    )
    assert got is not None
    assert got["topic_labels"] == ["schedule"]
    assert got["risk_flags"] == ["delay"]
    assert got["review_required"] is True
    assert got["advisory_only"] is True
    assert got["plaintext_body_persisted"] is False
    # Re-upsert (same unique key) updates in place — no duplicate row.
    store.upsert_email_model_classification(
        classification_id="c1",
        message_id=mid,
        model_name="mistral",
        schema_version="phase06-email-ollama-v1",
        classification_status="valid",
        topic_labels=["budget"],
        review_required=False,
    )
    listed = store.list_email_model_classifications(project_key="tropical")
    assert len(list(store.list_email_model_classifications(message_id=mid))) == 1
    again = store.get_email_model_classification(
        message_id=mid, model_name="mistral", schema_version="phase06-email-ollama-v1"
    )
    assert again is not None
    assert again["topic_labels"] == ["budget"]
    assert store.list_email_model_classifications(review_required=True) == [] or all(
        r["review_required"] for r in store.list_email_model_classifications(review_required=True)
    )
    assert isinstance(listed, list)
