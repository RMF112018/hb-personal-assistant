"""Phase 06 Prompt 10 — email review routing + encrypted-body eligibility (local-only).

Proves sensitive + low-confidence project matches route to review, encrypted-body
eligibility honors policy + folder + per-run caps, plaintext body is never marked
allowed, dry-run persists nothing, and routing is idempotent.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.email.review_router import ReviewRouter
from hb_assistant.construction.policy.email_active import (
    load_email_intelligence_active_policy,
)
from hb_assistant.construction.store import ConstructionStore


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
    preview: str,
    *,
    confidence: float = 0.95,
    source_id: str = "sx",
) -> None:
    store.upsert_email_message(
        message_id=mid,
        thread_key="t" + mid,
        source_id=source_id,
        sender_domain="vendor.com",
        received_datetime="2026-05-20T10:00:00Z",
        body_preview_excerpt_redacted=preview,
    )
    store.upsert_email_project_match(
        match_id="pm-" + mid,
        message_id=mid,
        match_signal="project_name_in_subject",
        confidence=confidence,
        project_key="tropical",
        project_number="23-435-01",
    )


def test_sensitive_category_routes_to_review() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "Please review the attached change order for pricing", confidence=0.95)
    report = ReviewRouter(store).route(project_key="tropical", lookback_days=30, dry_run=False)
    assert report.messages_considered == 1
    assert report.routed_to_review == 1
    queue = store.list_email_review_queue(project_key="tropical", status="open")
    cats = {row["category"] for row in queue}
    assert "change_orders" in cats
    row = next(r for r in queue if r["category"] == "change_orders")
    assert row["body_capture_eligible"] is True
    assert row["encrypted_body_capture_allowed"] is True
    assert row["review_required_before_body_use"] is True
    assert row["body_capture_decision_json"]


def test_low_confidence_routes_to_review() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "weekly site walk recap and progress photos", confidence=0.60)
    report = ReviewRouter(store).route(project_key="tropical", lookback_days=30, dry_run=False)
    assert report.routed_to_review == 1
    queue = store.list_email_review_queue(project_key="tropical", status="open")
    assert any(r["category"] == "low_confidence_project_match" for r in queue)


def test_high_confidence_non_sensitive_not_routed() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "weekly site walk recap and progress photos", confidence=0.95)
    report = ReviewRouter(store).route(project_key="tropical", lookback_days=30, dry_run=False)
    assert report.messages_considered == 1
    assert report.routed_to_review == 0
    assert store.count_email_review_queue(project_key="tropical", status="open") == 0
    # still eligible for encrypted body capture (no review gate triggered)
    assert report.body_capture_eligible_count == 1
    assert report.encrypted_body_storage_eligible_count == 1


def test_encrypted_storage_only_when_policy_permits() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "weekly recap and progress photos", confidence=0.95)
    policy = load_email_intelligence_active_policy().model_copy(
        update={"full_body_storage_allowed": False}
    )
    report = ReviewRouter(store, policy=policy).route(
        project_key="tropical", lookback_days=30, dry_run=True
    )
    assert report.body_capture_eligible_count == 0
    assert report.encrypted_body_storage_eligible_count == 0
    assert all(s.encrypted_storage_mode == "not_allowed" for s in report.samples)


def test_excluded_folder_not_eligible() -> None:
    db = _tmp_db()
    store = ConstructionStore(db)
    store.upsert_email_source_location(
        source_id="sxdel",
        mailbox_owner_hash="h",
        folder_role="deleted",
        folder_id="D",
        include_in_sync=False,
    )
    _add(store, "m1", "weekly recap and progress photos", confidence=0.95, source_id="sxdel")
    report = ReviewRouter(store).route(project_key="tropical", lookback_days=30, dry_run=True)
    assert report.body_capture_eligible_count == 0
    assert all(not s.body_capture_eligible for s in report.samples)


def test_per_run_cap_bounds_body_capture() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "weekly recap photos one", confidence=0.95)
    _add(store, "m2", "weekly recap photos two", confidence=0.95)
    policy = load_email_intelligence_active_policy().model_copy(
        update={"max_full_body_fetch_per_run": 1}
    )
    report = ReviewRouter(store, policy=policy).route(
        project_key="tropical", lookback_days=30, dry_run=True
    )
    assert report.messages_considered == 2
    assert report.body_capture_eligible_count == 1  # capped at one per run


def test_lookback_excludes_old_messages() -> None:
    db = _tmp_db()
    store = _store(db)
    store.upsert_email_message(
        message_id="old",
        thread_key="t",
        source_id="sx",
        sender_domain="vendor.com",
        received_datetime="2020-01-01T00:00:00Z",
        body_preview_excerpt_redacted="old change order",
    )
    store.upsert_email_project_match(
        match_id="pm-old",
        message_id="old",
        match_signal="x",
        confidence=0.95,
        project_key="tropical",
    )
    report = ReviewRouter(store).route(project_key="tropical", lookback_days=30, dry_run=True)
    assert report.messages_considered == 0


def test_dry_run_persists_nothing() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "attached change order and invoice", confidence=0.95)
    report = ReviewRouter(store).route(project_key="tropical", lookback_days=30, dry_run=True)
    assert report.persisted is False
    assert report.routed_to_review == 1
    conn = sqlite3.connect(db)
    try:
        n = conn.execute("SELECT COUNT(*) FROM email_review_queue").fetchone()[0]
    finally:
        conn.close()
    assert n == 0


def test_plaintext_never_marked_allowed() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "attached change order", confidence=0.95)
    report = ReviewRouter(store).route(project_key="tropical", lookback_days=30, dry_run=False)
    assert all(s.plaintext_body_persistence_allowed is False for s in report.samples)
    for row in store.list_email_review_queue(project_key="tropical", status="open"):
        decision = row["body_capture_decision_json"] or ""
        assert "plaintext" not in decision.lower()


def test_idempotent_recommit() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "attached change order and invoice", confidence=0.95)
    router = ReviewRouter(store)
    router.route(project_key="tropical", lookback_days=30, dry_run=False)
    first = store.count_email_review_queue(project_key="tropical", status=None)
    router.route(project_key="tropical", lookback_days=30, dry_run=False)
    second = store.count_email_review_queue(project_key="tropical", status=None)
    assert second == first
