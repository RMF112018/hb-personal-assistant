"""Phase 06 Prompt 08A — V12 encrypted-body schema + repository + vault round-trip.

Uses synthetic text only; no real email body plaintext appears anywhere.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.store import ConstructionStore
from hb_assistant.security.text_vault import decrypt_text, encrypt_text
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_SYNTHETIC = "Synthetic non-sensitive body text for testing only."


def _tmp_db() -> str:
    return str(Path(tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False).name))


def _store_with_message(db: str) -> ConstructionStore:
    store = ConstructionStore(db)
    store.upsert_email_source_location(
        source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F"
    )
    store.upsert_email_message(message_id="m1", thread_key="t", source_id="sx")
    return store


def test_v12_applies_and_creates_vault_table() -> None:
    db = _tmp_db()
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
    conn = sqlite3.connect(db)
    try:
        assert (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE name='email_message_body_vault_refs'"
            ).fetchone()
            is not None
        )
        cols = {r[1] for r in conn.execute("PRAGMA table_info(email_message_body_vault_refs)")}
    finally:
        conn.close()
    # No plaintext column of any kind.
    forbidden = {"body_plaintext", "raw_body", "body_html", "body_content", "body_text", "content"}
    assert not (cols & forbidden), f"forbidden plaintext columns: {cols & forbidden}"
    assert "encrypted_full_body_ref" in cols


@pytest.mark.parametrize(
    "column",
    [
        "plaintext_persisted",
        "obsidian_body_persisted",
        "evidence_body_persisted",
        "log_body_persisted",
    ],
)
def test_check_constraints_reject_body_persistence_flags(column: str) -> None:
    db = _tmp_db()
    SQLiteMigrator(db_path=db).apply()
    conn = sqlite3.connect(db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO email_message_body_vault_refs "
                f"(message_id, body_hash, body_length, encrypted_full_body_ref, extraction_policy, {column}) "
                f"VALUES ('m', 'h', 5, 'ref', 'encrypted_text_vault', 1)"
            )
    finally:
        conn.close()


def test_repository_stores_ref_metadata_only() -> None:
    db = _tmp_db()
    store = _store_with_message(db)
    store.upsert_email_body_vault_ref(
        message_id="m1",
        encrypted_full_body_ref="deadbeef",
        body_hash="a" * 64,
        body_length=51,
        extraction_policy="encrypted_text_vault",
        body_content_type="text",
        review_required=True,
        sensitivity_classification="contracts",
    )
    rec = store.get_email_body_vault_ref("m1")
    assert rec is not None
    assert rec["encrypted_full_body_ref"] == "deadbeef"
    assert rec["body_length"] == 51
    assert rec["plaintext_persisted"] is False
    assert rec["review_required"] is True
    assert rec["sensitivity_classification"] == "contracts"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"encrypted_full_body_ref": ""},
        {"body_hash": ""},
        {"body_length": 0},
        {"body_length": -1},
    ],
)
def test_repository_rejects_invalid_inputs(kwargs: dict) -> None:
    db = _tmp_db()
    store = _store_with_message(db)
    base = {
        "message_id": "m1",
        "encrypted_full_body_ref": "ref",
        "body_hash": "h",
        "body_length": 10,
        "extraction_policy": "encrypted_text_vault",
    }
    base.update(kwargs)
    with pytest.raises(ValueError):
        store.upsert_email_body_vault_ref(**base)


def test_repository_is_idempotent() -> None:
    db = _tmp_db()
    store = _store_with_message(db)
    for _ in range(2):
        store.upsert_email_body_vault_ref(
            message_id="m1",
            encrypted_full_body_ref="r",
            body_hash="h" * 64,
            body_length=10,
            extraction_policy="encrypted_text_vault",
        )
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM email_message_body_vault_refs").fetchone()[0] == 1
    finally:
        conn.close()


def test_vault_round_trip_with_synthetic_text() -> None:
    # Synthetic text only; mirrors tests/test_text_vault.py (writes under the
    # resolved app-support vault, never the repo).
    from hb_assistant.config.path_policy import PathPolicy

    ref = encrypt_text(_SYNTHETIC)
    assert ref is not None
    assert decrypt_text(ref) == _SYNTHETIC
    assert encrypt_text(_SYNTHETIC) == ref  # deterministic
    blob = PathPolicy().get_app_support() / "security" / "text-vault" / f"{ref}.enc"
    assert blob.exists()
    assert _SYNTHETIC.encode("utf-8") not in blob.read_bytes()  # ciphertext != plaintext
