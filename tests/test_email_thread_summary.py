"""Phase 07B Prompt 07 — Email thread summary materialization (local-only, redacted).

Proves: metadata-only summaries persist + upsert idempotently; dry-run persists nothing;
sensitive/high-impact threads route to review; the controlled body-context policy uses
decrypted bodies in-memory only (never persisted, gated by the flag AND policy); and the
per-run audit receipt records counts with the raw-persistence guard columns at 0.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from hb_assistant.construction.calendar.policy import (
    EmailThreadSummaryDefaults,
    EmailThreadSummaryPolicy,
)
from hb_assistant.construction.email.thread_summary import EmailThreadSummaryMaterializer
from hb_assistant.construction.store import ConstructionStore

# A distinctive plaintext token encrypted as a body; must never leak into any artifact.
_SECRET_BODY = "SECRET_BODY_TOKEN_zzz change order pricing detail that must stay encrypted"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _tmp_db() -> str:
    return str(Path(tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False).name))


def _store(db: str) -> ConstructionStore:
    store = ConstructionStore(db)
    store.upsert_email_source_location(
        source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F"
    )
    return store


def _add(
    store: ConstructionStore,
    mid: str,
    *,
    thread_key: str,
    preview: str,
    sender_hash: str = "sender-a",
    confidence: float = 0.95,
) -> None:
    store.upsert_email_message(
        message_id=mid,
        thread_key=thread_key,
        source_id="sx",
        sender_address_hash=sender_hash,
        sender_domain="vendor.com",
        subject_redacted="[redacted:abc123]",
        body_preview_excerpt_redacted=preview,
        received_datetime=_now_iso(),
    )
    store.upsert_email_project_match(
        match_id="pm-" + mid,
        message_id=mid,
        match_signal="project_name_in_subject",
        confidence=confidence,
        project_key="tropical",
        project_number="23-435-01",
    )


def _allow_body_policy() -> EmailThreadSummaryPolicy:
    return EmailThreadSummaryPolicy(
        version="test-policy-v1",
        defaults=EmailThreadSummaryDefaults(allow_encrypted_body_context=True),
    )


# --- metadata-only materialization ------------------------------------------------


def test_metadata_only_summary_persists_and_is_idempotent() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", thread_key="t1", preview="weekly recap and progress photos")
    _add(store, "m2", thread_key="t1", preview="more progress photos", sender_hash="sender-b")

    report = EmailThreadSummaryMaterializer(store).materialize(
        project_key="tropical", lookback_days=60, dry_run=False
    )
    assert report.threads_considered == 1
    assert report.threads_summarized == 1
    assert report.review_required_count == 0
    assert report.persisted is True

    rec = store.get_email_thread_summary("t1")
    assert rec is not None
    assert rec["message_count"] == 2
    assert rec["review_required"] is False
    assert rec["summary_policy"] == "metadata_only"
    # Metadata-only: the redacted subject/preview text must not be embedded.
    assert "[redacted:abc123]" not in (rec["summary_redacted"] or "")
    assert "progress photos" not in (rec["summary_redacted"] or "")
    assert isinstance(rec["participants_hash"], list)
    assert sorted(rec["participants_hash"]) == ["sender-a", "sender-b"]

    # Re-run upserts in place — no duplicate thread row.
    EmailThreadSummaryMaterializer(store).materialize(
        project_key="tropical", lookback_days=60, dry_run=False
    )
    assert len(store.list_email_thread_summaries(project_key="tropical")) == 1


def test_dry_run_persists_nothing() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", thread_key="t1", preview="attached change order ZZZUNIQUE")

    report = EmailThreadSummaryMaterializer(store).materialize(
        project_key="tropical", lookback_days=60, dry_run=True
    )
    assert report.persisted is False
    assert report.run_id is None
    conn = sqlite3.connect(db)
    try:
        n = conn.execute("SELECT COUNT(*) FROM email_thread_summaries").fetchone()[0]
        q = conn.execute("SELECT COUNT(*) FROM email_review_queue").fetchone()[0]
        r = conn.execute(
            "SELECT COUNT(*) FROM email_thread_summary_materialization_runs"
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 0
    assert q == 0
    assert r == 0


def test_sensitive_thread_routes_to_review_without_leaking_preview() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", thread_key="t1", preview="attached change order ZZZUNIQUE pricing")

    report = EmailThreadSummaryMaterializer(store).materialize(
        project_key="tropical", lookback_days=60, dry_run=False
    )
    assert report.review_required_count == 1

    rec = store.get_email_thread_summary("t1")
    assert rec is not None
    assert rec["review_required"] is True
    # The category id may appear; the raw preview token must not.
    assert "ZZZUNIQUE" not in (rec["summary_redacted"] or "")
    assert "change_orders" in (rec["summary_redacted"] or "")
    assert store.count_email_review_queue(project_key="tropical", status="open") >= 1


def test_run_receipt_recorded_with_guard_columns_zero() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", thread_key="t1", preview="weekly recap")
    EmailThreadSummaryMaterializer(store).materialize(
        project_key="tropical", lookback_days=60, dry_run=False
    )
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT status, threads_summarized, raw_body_persisted, raw_prompt_persisted, "
            "raw_response_persisted, external_writeback_performed "
            "FROM email_thread_summary_materialization_runs"
        ).fetchall()
    finally:
        conn.close()
    assert len(row) == 1
    status, summarized, rb, rp, rr, ew = row[0]
    assert status == "completed"
    assert summarized == 1
    assert (rb, rp, rr, ew) == (0, 0, 0, 0)


# --- controlled body-context policy ----------------------------------------------


def test_body_context_routes_only_when_flag_and_policy_allow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path))
    from hb_assistant.security.text_vault import encrypt_text

    db = str(tmp_path / "db.sqlite")
    store = _store(db)
    # Subject/preview are benign — the sensitivity term lives ONLY in the encrypted body.
    _add(store, "m1", thread_key="t1", preview="weekly recap and progress photos")
    ref = encrypt_text(_SECRET_BODY)
    assert ref is not None
    store.upsert_email_body_vault_ref(
        message_id="m1",
        encrypted_full_body_ref=ref,
        body_hash="bh",
        body_length=len(_SECRET_BODY),
        extraction_policy="encrypted_text_vault",
    )

    # Without body context: no sensitive term visible → no review.
    no_body = EmailThreadSummaryMaterializer(store).materialize(
        project_key="tropical", lookback_days=60, dry_run=False,
        use_encrypted_body_context=True,  # flag on, but default policy disallows
    )
    assert no_body.review_required_count == 0
    assert no_body.encrypted_body_context_used_count == 0

    # With body context allowed by policy: the body term drives routing.
    with_body = EmailThreadSummaryMaterializer(store, policy=_allow_body_policy()).materialize(
        project_key="tropical", lookback_days=60, dry_run=False,
        use_encrypted_body_context=True,
    )
    assert with_body.review_required_count == 1
    assert with_body.encrypted_body_context_used_count == 1

    rec = store.get_email_thread_summary("t1")
    assert rec is not None
    assert rec["review_required"] is True
    # The decrypted body token must never appear in any persisted/returned artifact.
    assert _SECRET_BODY not in json.dumps(with_body.model_dump())
    assert _SECRET_BODY not in json.dumps(rec)
    for item in store.list_email_review_queue(project_key="tropical", status=None):
        assert _SECRET_BODY not in json.dumps(item)
    # And it never reached the SQLite file as plaintext.
    assert _SECRET_BODY.encode("utf-8") not in Path(db).read_bytes()


def test_get_and_list_round_trip() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", thread_key="t1", preview="weekly recap")
    EmailThreadSummaryMaterializer(store).materialize(
        project_key="tropical", lookback_days=60, dry_run=False
    )
    listed = store.list_email_thread_summaries(project_key="tropical")
    assert isinstance(listed, list)
    assert len(listed) == 1
    assert listed[0]["thread_key"] == "t1"
    assert store.list_email_thread_summaries(review_required=True) == []
