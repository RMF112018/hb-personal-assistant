"""Phase 06 Prompt 09 — email relationship candidate builder (local-only).

Proves candidates are generated for project / Procore / calendar / financial signals,
that candidates are NOT determinations (confidence + review + "possible" evidence),
that file candidates are counted not duplicated, and that runs are idempotent.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.email import RelationshipCandidateBuilder
from hb_assistant.construction.store import ConstructionStore


def _tmp_db() -> str:
    return str(Path(tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False).name))


def _seed(db: str, *, with_financials: bool = False) -> ConstructionStore:
    store = ConstructionStore(db)
    store.upsert_email_source_location(
        source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F"
    )
    rows = [
        ("m1", "vendor.com", "Tropical schedule update for the team"),  # plain project
        ("m2", "procore.com", "New RFI 12 response submitted for review"),  # procore notification
        ("m3", "vendor.com", "Accepted: Tropical OAC meeting when: 2pm where: Teams"),  # meeting
        ("m4", "vendor.com", "Please find the attached pay application g702 invoice"),  # financial
    ]
    for mid, dom, preview in rows:
        store.upsert_email_message(
            message_id=mid,
            thread_key="t" + mid,
            source_id="sx",
            sender_domain=dom,
            received_datetime="2026-05-20T10:00:00Z",
            body_preview_excerpt_redacted=preview,
        )
        store.upsert_email_project_match(
            match_id="pm-" + mid,
            message_id=mid,
            match_signal="project_name_in_subject",
            confidence=0.8,
            project_key="tropical",
            project_number="23-435-01",
        )
    # an existing Prompt-08 file candidate on m4
    store.upsert_email_message_attachment(
        attachment_key="m4:a1", message_id="m4", name_hash="nh", content_type="application/pdf"
    )
    store.upsert_email_relationship_candidate(
        candidate_id="m4:fn",
        message_id="m4",
        candidate_type="sharepoint_drive_item",
        match_signal="attachment_filename",
        confidence=0.5,
        project_key="tropical",
        target_table="construction_drive_items",
        target_key="nh",
    )
    if with_financials:
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO procore_financial_contracts "
            "(record_key, project_key, endpoint_id, contract_id, contract_family, "
            " raw_body_persisted, redaction_applied) "
            "VALUES ('rk1', 'tropical', 'prime-contracts', 'c1', 'prime', 0, 1)"
        )
        conn.commit()
        conn.close()
    return store


def test_generates_project_procore_and_calendar_candidates() -> None:
    db = _tmp_db()
    store = _seed(db)
    report = RelationshipCandidateBuilder(store).build(
        project_key="tropical", lookback_days=30, dry_run=False
    )

    assert report.messages_considered == 4
    bt = report.candidates_by_type
    assert bt["project"] == 4  # one per matched message
    assert bt["procore_rfi"] == 1  # procore notification with "rfi"
    assert bt["calendar_event"] == 1  # meeting pattern
    assert report.file_candidates_existing == 1  # the Prompt-08 file candidate, counted
    # candidates are not determinations
    assert "not determinations" in report.disclaimer
    for c in report.samples:
        assert c.evidence_redacted.startswith("possible ")
        assert 0.0 <= c.confidence <= 1.0


def test_financial_candidate_only_when_available_and_routes_review() -> None:
    db = _tmp_db()
    store = _seed(db, with_financials=True)
    report = RelationshipCandidateBuilder(store).build(
        project_key="tropical", lookback_days=30, dry_run=False
    )
    fin = [
        c
        for c in store.list_email_relationship_candidates(project_key="tropical")
        if c["candidate_type"]
        in ("procore_payment_application", "procore_invoice", "procore_contract")
    ]
    assert fin, "expected a financial candidate when financials are available"
    assert all(c["review_required"] for c in fin)  # financial routes to review
    assert report.procore_available.get("financial_contracts") == 1


def test_no_financial_candidate_when_unavailable() -> None:
    db = _tmp_db()
    store = _seed(db, with_financials=False)
    RelationshipCandidateBuilder(store).build(
        project_key="tropical", lookback_days=30, dry_run=False
    )
    fin = [
        c
        for c in store.list_email_relationship_candidates(project_key="tropical")
        if c["candidate_type"].startswith("procore_") and c["candidate_type"] != "procore_rfi"
    ]
    assert not fin


def test_dry_run_persists_nothing() -> None:
    db = _tmp_db()
    store = _seed(db)
    report = RelationshipCandidateBuilder(store).build(
        project_key="tropical", lookback_days=30, dry_run=True
    )
    assert report.persisted is False
    assert report.candidates_generated > 0
    conn = sqlite3.connect(db)
    try:
        # only the pre-seeded Prompt-08 file candidate exists; nothing new persisted
        n = conn.execute("SELECT COUNT(*) FROM email_relationship_candidates").fetchone()[0]
    finally:
        conn.close()
    assert n == 1


def test_idempotent_recommit() -> None:
    db = _tmp_db()
    store = _seed(db)
    b = RelationshipCandidateBuilder(store)
    b.build(project_key="tropical", lookback_days=30, dry_run=False)
    conn = sqlite3.connect(db)
    first = conn.execute("SELECT COUNT(*) FROM email_relationship_candidates").fetchone()[0]
    conn.close()
    b.build(project_key="tropical", lookback_days=30, dry_run=False)
    conn = sqlite3.connect(db)
    second = conn.execute("SELECT COUNT(*) FROM email_relationship_candidates").fetchone()[0]
    conn.close()
    assert second == first  # deterministic candidate_id upserts


def test_lookback_excludes_old_messages() -> None:
    db = _tmp_db()
    store = ConstructionStore(db)
    store.upsert_email_source_location(
        source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F"
    )
    store.upsert_email_message(
        message_id="old",
        thread_key="t",
        source_id="sx",
        sender_domain="vendor.com",
        received_datetime="2020-01-01T00:00:00Z",
        body_preview_excerpt_redacted="old tropical mail",
    )
    store.upsert_email_project_match(
        match_id="pm-old",
        message_id="old",
        match_signal="x",
        confidence=0.8,
        project_key="tropical",
    )
    report = RelationshipCandidateBuilder(store).build(
        project_key="tropical", lookback_days=30, dry_run=True
    )
    assert report.messages_considered == 0
