"""Phase 07D Prompt 08 — review-controlled risk-digest materialization (V25).

Covers the four risk_source_class passes (source_stated / inferred_candidate / review_required /
model_proposed), review-required category flagging, empty no-op, no-raw-content, idempotency,
dry-run, and status coverage over project_risk_digest_items.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.risk_digest import (
    RiskDigestBuilder,
    project_risk_digest_status,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_LEAK = re.compile(
    r"https?://|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|BEGIN:V|-----BEGIN|Bearer |eyJ", re.IGNORECASE
)
_GUARDS = (
    "raw_email_body_persisted", "raw_document_text_persisted",
    "raw_calendar_payload_persisted", "raw_prompt_persisted", "raw_response_persisted",
    "signed_url_persisted", "download_url_persisted", "external_writeback_performed",
)


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_riskdigest_")
    os.close(fd)
    SQLiteMigrator(db_path=db).apply()
    return db


def _signal(db: str, aid: str, signal_type: str, endpoint: str) -> None:
    raw = sqlite3.connect(db)
    try:
        raw.execute(
            "INSERT INTO procore_action_signals "
            "(action_signal_id, project_key, record_key, endpoint_id, signal_type, signal_status, "
            " importance, title_redacted, first_detected_at_utc, last_seen_at_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                aid, "tropical", f"tropical|{endpoint}||1", endpoint, signal_type, "open",
                "medium", "[redacted]", "2026-05-29T00:00:00Z", "2026-05-29T00:00:00Z",
            ),
        )
        raw.commit()
    finally:
        raw.close()


def _issue(store: ConstructionStore, fid: str, *, status: str, age: int, kind: str = "rfis") -> None:
    store.upsert_project_issue_history_item(
        issue_family_id=fid, project_key="tropical", status=status,
        source_families_json=json.dumps(["procore"]), confidence_class="deterministic",
        issue_kind=kind, age_days=age, evidence_trail_id="et_" + fid,
    )


def _cand(store: ConstructionStore, cid: str, **over: object) -> None:
    kw: dict = {
        "candidate_id": cid,
        "source_family": "email",
        "source_record_type": "email_message",
        "source_record_ref": "m_" + cid,
        "target_family": "project",
        "target_record_type": "project",
        "target_record_ref": "p_" + cid,
        "relationship_type": "financial_keyword_in_preview",
        "confidence_score": 0.5,
        "confidence_class": "weak_heuristic",
        "source_reference_json": json.dumps({"x": cid}),
        "review_required": True,
        "project_key": "tropical",
        "evidence_trail_id": "et_" + cid,
    }
    kw.update(over)
    store.upsert_cross_source_relationship_candidate(**kw)  # type: ignore[arg-type]


def _items(store: ConstructionStore) -> dict[str, dict]:
    return {i["risk_indicator_type"]: i for i in store.list_project_risk_digest_items()}


def _assert_guards_zero(db: str) -> None:
    raw = sqlite3.connect(db)
    try:
        cols = ", ".join(_GUARDS)
        for row in raw.execute(f"SELECT {cols} FROM project_risk_digest_items"):
            assert set(row) <= {0}, "project_risk_digest_items has a non-zero guard column"
    finally:
        raw.close()


# ---------------------------------------------------------------------------


def test_source_stated_from_action_signals() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _signal(db, "a1", "invoice_payment_due", "invoices")
        _signal(db, "a2", "invoice_payment_due", "invoices")
        _signal(db, "a3", "meeting_topic_open_high_priority", "meetings")
        report = RiskDigestBuilder(store).build(dry_run=False)
        assert report["ok"] is True
        items = _items(store)
        fin = items["invoice_payment_due"]
        assert fin["risk_source_class"] == "source_stated"
        assert fin["confidence_class"] == "deterministic"
        assert fin["review_required"] is True  # financial category
        assert json.loads(fin["summary_redacted"])["count"] == 2
        # a non-review category indicator is not auto-flagged
        assert items["meeting_topic_open_high_priority"]["review_required"] is False
        _assert_guards_zero(db)
    finally:
        Path(db).unlink(missing_ok=True)


def test_inferred_candidate_from_issue_history() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _issue(store, "i1", status="overdue", age=90)
        _issue(store, "i2", status="open", age=120, kind="submittals")  # aged open
        _issue(store, "i3", status="approved", age=5)  # not risk-bearing
        RiskDigestBuilder(store).build(dry_run=False)
        items = _items(store)
        assert items["overdue_issue"]["risk_source_class"] == "inferred_candidate"
        assert items["overdue_issue"]["confidence_class"] == "strong_heuristic"
        assert "aging_open_issue" in items
        assert "approved_issue" not in items
    finally:
        Path(db).unlink(missing_ok=True)


def test_review_required_and_model_proposed_relationships() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(store, "c1")  # weak/review-required financial keyword
        _cand(store, "c2", sensitive_high_impact=True, relationship_type="claim_notice",
              confidence_class="strong_heuristic")
        _cand(store, "c3", model_proposed=True, confidence_class="model_proposed",
              relationship_type="email_topic_inference", review_required=True)
        RiskDigestBuilder(store).build(dry_run=False)
        items = _items(store)
        assert items["financial_keyword_in_preview"]["risk_source_class"] == "review_required"
        assert items["financial_keyword_in_preview"]["review_required"] is True
        assert items["sensitive_high_impact_relationship"]["risk_source_class"] == "review_required"
        model = items["email_topic_inference"]
        assert model["risk_source_class"] == "model_proposed"
        assert model["confidence_class"] == "model_proposed"
        assert model["review_required"] is True  # model is never auto-promoted
    finally:
        Path(db).unlink(missing_ok=True)


def test_empty_substrate_writes_no_items() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        report = RiskDigestBuilder(store).build(dry_run=False)
        assert report["summary"]["items_written"] == 0
        assert store.count_project_risk_digest_items() == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_no_raw_content() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _signal(db, "a1", "invoice_payment_due", "invoices")
        _issue(store, "i1", status="void", age=70)
        _cand(store, "c1")
        RiskDigestBuilder(store).build(dry_run=False)
        blob = json.dumps(store.list_project_risk_digest_items(), default=str)
        assert _LEAK.search(blob) is None
        # the seeded action-signal title_redacted placeholder must not be pulled through
        assert "[redacted]" not in blob
    finally:
        Path(db).unlink(missing_ok=True)


def test_idempotent_apply() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _signal(db, "a1", "invoice_payment_due", "invoices")
        _issue(store, "i1", status="overdue", age=90)
        _cand(store, "c1")
        builder = RiskDigestBuilder(store)
        builder.build(dry_run=False)
        n = store.count_project_risk_digest_items()
        builder.build(dry_run=False)
        assert store.count_project_risk_digest_items() == n
        _assert_guards_zero(db)
    finally:
        Path(db).unlink(missing_ok=True)


def test_dry_run_writes_nothing() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _signal(db, "a1", "invoice_payment_due", "invoices")
        report = RiskDigestBuilder(store).build(dry_run=True)
        assert report["mode"] == "dry_run"
        assert report["summary"]["items_planned"] == 1
        assert report["summary"]["items_written"] == 0
        assert store.count_project_risk_digest_items() == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_status_reports_coverage() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _signal(db, "a1", "invoice_payment_due", "invoices")
        _issue(store, "i1", status="overdue", age=90)
        _cand(store, "c1")
        RiskDigestBuilder(store).build(dry_run=False)
        status = project_risk_digest_status(store)
        assert status["ok"] is True
        assert status["summary"]["items"] == 3
        assert set(status["summary"]["by_risk_source_class"]) == {
            "source_stated", "inferred_candidate", "review_required"
        }
        assert status["summary"]["review_required"] == 3
    finally:
        Path(db).unlink(missing_ok=True)
