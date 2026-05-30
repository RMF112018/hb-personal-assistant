"""Phase 06 Prompt 08A — encrypted body capture during indexing.

Synthetic bodies only. Proves capture encrypts + stores ref (no plaintext in DB),
routes sensitive bodies to review, honors the run cap, and that dry-run fetches
nothing.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from hb_assistant.construction.email import EmailMessageIndexer
from hb_assistant.construction.email import message_indexer as mi
from hb_assistant.construction.policy import load_email_intelligence_active_policy
from hb_assistant.construction.store import ConstructionStore

_OWNER = "bobby@example.com"
_SYNTHETIC_BODY = "SYNTHETIC subcontract agreement body — confidential — for tests only."


def _msg(mid: str) -> dict[str, Any]:
    return {
        "id": mid,
        "subject": "doc",
        "conversationId": "c1",
        "internetMessageId": f"<{mid}@x>",
        "from": {"emailAddress": {"address": "gc@vendor.com"}},
        "toRecipients": [{"emailAddress": {"address": _OWNER}}],
        "ccRecipients": [],
        "bccRecipients": [],
        "receivedDateTime": "2026-05-20T10:00:00Z",
        "hasAttachments": False,
        "bodyPreview": "see doc",
    }


class FakeReader:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self._messages = messages
        self.body_calls: list[str] = []

    def get_me(self) -> dict[str, Any]:
        return {"userPrincipalName": _OWNER}

    def list_messages(self, *, folder_id=None, top=50, received_after=None, max_items=None) -> list[dict[str, Any]]:
        return self._messages[:max_items] if max_items else list(self._messages)

    def list_attachment_metadata(self, message_id: str) -> list[dict[str, Any]]:
        return []

    def get_message_body(self, message_id: str) -> dict[str, Any]:
        self.body_calls.append(message_id)
        return {
            "id": message_id,
            "internetMessageId": f"<{message_id}@x>",
            "conversationId": "c1",
            "body": {"contentType": "text", "content": _SYNTHETIC_BODY},
        }


def _tmp_db() -> str:
    return str(Path(tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False).name))


def _store_with_inbox(db: str) -> ConstructionStore:
    store = ConstructionStore(db)
    store.upsert_email_source_location(
        source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F", include_in_sync=True
    )
    return store


def test_capture_encrypts_and_stores_ref_only() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader([_msg("m1")])
    result = EmailMessageIndexer(reader, store).index(
        project_key="tropical", lookback_days=30, include_encrypted_body=True
    )
    assert result.body_capture_enabled is True
    assert result.bodies_encrypted == 1
    assert result.plaintext_persisted is False
    assert reader.body_calls == ["m1"]

    rec = store.get_email_body_vault_ref("m1")
    assert rec is not None
    assert rec["encrypted_full_body_ref"]
    assert rec["body_length"] == len(_SYNTHETIC_BODY)
    assert rec["review_required"] is True  # "agreement"/"confidential" → sensitive
    assert rec["plaintext_persisted"] is False

    # No plaintext anywhere in the DB.
    conn = sqlite3.connect(db)
    try:
        dump = " ".join(
            " ".join(str(c) for c in row)
            for tbl in ("email_message_body_vault_refs", "email_messages", "email_processing_receipts")
            for row in conn.execute(f"SELECT * FROM {tbl}")
        )
    finally:
        conn.close()
    assert "SYNTHETIC subcontract" not in dump


def test_dry_run_fetches_no_body_and_reports_eligibility() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    # dry-run needs folders present (it does not self-heal); seed handled above.
    reader = FakeReader([_msg("m1"), _msg("m2")])
    result = EmailMessageIndexer(reader, store).index(
        project_key="tropical", lookback_days=30, include_encrypted_body=True, dry_run=True
    )
    assert reader.body_calls == []  # no body fetched in dry-run
    assert result.bodies_encrypted == 0
    assert result.body_capture_enabled is True
    assert result.bodies_eligible == 2
    assert _count(db) == 0


def test_disabled_without_flag() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader([_msg("m1")])
    result = EmailMessageIndexer(reader, store).index(project_key="tropical", lookback_days=30)
    assert result.body_capture_enabled is False
    assert reader.body_calls == []
    assert _count(db) == 0


def test_run_cap_is_honored(monkeypatch) -> None:
    # Force a tiny per-run cap via the policy loader the indexer uses.
    base = load_email_intelligence_active_policy()
    capped = base.model_copy(update={"max_full_body_fetch_per_run": 2})
    monkeypatch.setattr(mi, "load_email_intelligence_active_policy", lambda *a, **k: capped)

    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader([_msg(f"m{i}") for i in range(5)])
    result = EmailMessageIndexer(reader, store).index(
        project_key="tropical", lookback_days=30, include_encrypted_body=True
    )
    assert result.bodies_encrypted == 2  # capped
    assert len(reader.body_calls) == 2
    assert _count(db) == 2


def _count(db: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM email_message_body_vault_refs").fetchone()[0]
    finally:
        conn.close()
