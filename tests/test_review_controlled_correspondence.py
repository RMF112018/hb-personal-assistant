"""Phase 07B Prompt 09 — review-controlled correspondence intelligence (read-only).

Proves: the builder aggregates project thread summaries + the open review queue into
redacted previews and category-level review warnings; warnings carry the registry's
evidence-safe metadata and "not a determination" framing; previews never leak raw
subject/address/body; the report is advisory (read_only, persisted False); and running it
performs no SQLite writes.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from hb_assistant.construction.correspondence import CorrespondenceReviewBuilder
from hb_assistant.construction.store import ConstructionStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _tmp_db() -> str:
    return str(Path(tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False).name))


def _seed(db: str) -> ConstructionStore:
    store = ConstructionStore(db)
    store.upsert_email_source_location(
        source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F"
    )
    now = _now_iso()
    for mid, tk in (("m1", "T1"), ("m2", "T1"), ("m3", "T2")):
        store.upsert_email_message(
            message_id=mid, thread_key=tk, source_id="sx", received_datetime=now
        )
    store.upsert_email_thread_summary(
        thread_key="T1", project_key="tropical", message_count=2,
        first_message_datetime=now, last_message_datetime=now,
        summary_redacted="thread: 2 message(s), 2 participant(s)",
        summary_policy="metadata_only", review_required=True,
    )
    store.upsert_email_thread_summary(
        thread_key="T2", project_key="tropical", message_count=1,
        first_message_datetime=now, last_message_datetime=now,
        summary_redacted="thread: 1 message(s), 1 participant(s)",
        summary_policy="metadata_only", review_required=False,
    )
    # Open review queue: two contracts (medium) + one claims (high).
    store.enqueue_email_review_item(
        review_id="r1", message_id="m1", category="contracts", sensitivity="medium",
        reason="sensitive_category:contracts", suggested_action="route_to_review",
        confidence=0.9, project_key="tropical",
    )
    store.enqueue_email_review_item(
        review_id="r2", message_id="m2", category="contracts", sensitivity="medium",
        reason="sensitive_category:contracts", suggested_action="route_to_review",
        confidence=0.9, project_key="tropical",
    )
    store.enqueue_email_review_item(
        review_id="r3", message_id="m3", category="claims", sensitivity="high",
        reason="sensitive_category:claims", suggested_action="route_to_review_no_determination",
        confidence=0.9, project_key="tropical",
    )
    return store


def test_report_aggregates_threads_and_warnings() -> None:
    db = _tmp_db()
    store = _seed(db)
    report = CorrespondenceReviewBuilder(store).review(
        project_key="tropical", lookback_days=3650
    )
    assert report.threads_total == 2
    assert report.threads_review_required == 1
    assert report.review_queue_open == 3
    assert report.read_only is True
    assert report.persisted is False
    assert "not determinations" in report.disclaimer

    by_cat = {w.category: w for w in report.warnings}
    assert set(by_cat) == {"contracts", "claims"}
    assert by_cat["contracts"].open_item_count == 2
    assert by_cat["claims"].open_item_count == 1
    assert by_cat["claims"].sensitivity_level == "high"
    assert "not a determination" in by_cat["claims"].evidence_safe_explanation
    # High-sensitivity warnings sort first.
    assert report.warnings[0].category == "claims"


def test_previews_are_redacted_and_capped() -> None:
    db = _tmp_db()
    store = _seed(db)
    report = CorrespondenceReviewBuilder(store).review(
        project_key="tropical", lookback_days=3650, max_previews=1
    )
    assert len(report.previews) == 1  # capped
    p = report.previews[0]
    # thread_ref is a hash, not the raw thread_key.
    assert p.thread_ref not in {"T1", "T2"}
    assert len(p.thread_ref) == 16
    blob = json.dumps(report.model_dump())
    assert "@" not in blob
    assert "http" not in blob
    # The raw thread_key must not leak into the preview ref or summary.
    assert p.thread_ref not in {"T1", "T2"}
    assert "T1" not in (p.summary_redacted or "") and "T2" not in (p.summary_redacted or "")


def test_review_makes_no_writes() -> None:
    db = _tmp_db()
    store = _seed(db)

    def _counts() -> tuple[int, int]:
        conn = sqlite3.connect(db)
        try:
            t = conn.execute("SELECT COUNT(*) FROM email_thread_summaries").fetchone()[0]
            q = conn.execute("SELECT COUNT(*) FROM email_review_queue").fetchone()[0]
        finally:
            conn.close()
        return t, q

    before = _counts()
    CorrespondenceReviewBuilder(store).review(project_key="tropical", lookback_days=3650)
    assert _counts() == before


def test_lookback_excludes_old_threads() -> None:
    db = _tmp_db()
    store = _seed(db)
    store.upsert_email_thread_summary(
        thread_key="T_OLD", project_key="tropical", message_count=1,
        first_message_datetime="2020-01-01T00:00:00+00:00",
        last_message_datetime="2020-01-01T00:00:00+00:00",
        summary_redacted="old thread", summary_policy="metadata_only",
    )
    recent = CorrespondenceReviewBuilder(store).review(project_key="tropical", lookback_days=30)
    assert recent.threads_total == 2  # T_OLD excluded by lookback
    wide = CorrespondenceReviewBuilder(store).review(project_key="tropical", lookback_days=3650)
    assert wide.threads_total == 3
