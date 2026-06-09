"""Phase 10 V45 — daily-brief pending enrichment consumption tests (raw-free, labeled).

Proves the daily brief surfaces PENDING V45 enrichments clearly labeled "Model-enriched / pending
review", source-linked, with no raw excerpts/URLs/HTML; low-confidence items are labeled or omitted
per policy; reviewed rows are not mislabeled; and a missing/empty enrichment table degrades cleanly.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.daily_brief.email_followup_pending import (
    LOW_CONFIDENCE_LABEL,
    PENDING_LABEL,
    build_pending_email_enrichment_section,
    render_pending_enrichment_markdown,
)
from hb_assistant.construction.store import ConstructionStore


def _seed_enrichment(store: ConstructionStore, *, cid: str, confidence: float, band: str,
                     review_status: str = "pending") -> None:
    store.upsert_email_followup_enrichment(
        enrichment_id=f"enr-{cid}",
        idempotency_key=f"idem-{cid}",
        source_candidate_id=cid,
        source_candidate_type="task",
        raw_excerpt_hash="sha256:abc123",
        enriched_title=f"Send revised RFI for {cid}",
        waiting_state="waiting_on_me",
        assignee_type="me",
        confidence=confidence,
        confidence_band=band,
        input_context_hash="ic",
        output_hash="oc",
        prompt_template_version="email_followup_raw_enrichment.v1",
        watch_item_id=f"watch:{cid}",
        suggested_next_action="Draft and send the revised response.",
        reason_codes=["direct_ask"],
        source_refs=["email_msg:deadbeef", "srh-x"],
        review_status=review_status,
    )


def test_pending_items_are_labeled() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = ConstructionStore(db_path=str(Path(td) / "b.db"))
        _seed_enrichment(store, cid="c1", confidence=0.8, band="high")
        section = build_pending_email_enrichment_section(store)
        assert section["available"] is True
        assert section["count"] == 1
        item = section["items"][0]
        assert item["label"] == PENDING_LABEL
        assert item["enrichment_id"] == "enr-c1"
        assert item["candidate_id"] == "c1"
        assert item["watch_item_id"] == "watch:c1"
        assert item["source_refs"] == ["email_msg:deadbeef", "srh-x"]


def test_low_confidence_labeled_by_default() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = ConstructionStore(db_path=str(Path(td) / "b.db"))
        _seed_enrichment(store, cid="c1", confidence=0.3, band="low")
        section = build_pending_email_enrichment_section(store)
        assert section["count"] == 1
        assert LOW_CONFIDENCE_LABEL in section["items"][0]["label"]
        assert section["items"][0]["label"].startswith(PENDING_LABEL)


def test_low_confidence_omitted_when_policy_omit() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = ConstructionStore(db_path=str(Path(td) / "b.db"))
        _seed_enrichment(store, cid="c1", confidence=0.3, band="low")
        _seed_enrichment(store, cid="c2", confidence=0.9, band="high")
        section = build_pending_email_enrichment_section(store, low_confidence_policy="omit")
        assert section["count"] == 1
        assert section["omitted_low_confidence"] == 1
        assert section["items"][0]["candidate_id"] == "c2"


def test_reviewed_rows_not_mislabeled_as_pending() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = ConstructionStore(db_path=str(Path(td) / "b.db"))
        _seed_enrichment(store, cid="c1", confidence=0.8, band="high", review_status="accepted")
        # default (pending only) → not surfaced
        assert build_pending_email_enrichment_section(store)["count"] == 0
        # include_reviewed → surfaced but NOT labeled pending
        section = build_pending_email_enrichment_section(store, include_reviewed=True)
        assert section["count"] == 1
        assert section["items"][0]["label"] != PENDING_LABEL
        assert "accepted" in section["items"][0]["label"]


def test_no_raw_content_in_section_or_markdown() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = ConstructionStore(db_path=str(Path(td) / "b.db"))
        _seed_enrichment(store, cid="c1", confidence=0.8, band="high")
        section = build_pending_email_enrichment_section(store)
        blob = json.dumps(section)
        for forbidden in ("http://", "https://", "body_html", "raw_prompt", "raw_response", "Bearer "):
            assert forbidden not in blob
        md = render_pending_enrichment_markdown(section)
        assert PENDING_LABEL in md
        assert "enrichment=enr-c1" in md
        for forbidden in ("http://", "https://", "body_html"):
            assert forbidden not in md


def test_empty_table_degrades_cleanly() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = ConstructionStore(db_path=str(Path(td) / "b.db"))  # migrated, no rows
        section = build_pending_email_enrichment_section(store)
        assert section["available"] is True
        assert section["count"] == 0
        assert render_pending_enrichment_markdown(section) == ""


def test_missing_table_degrades_cleanly() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "b.db")
        store = ConstructionStore(db_path=db)
        import sqlite3

        conn = sqlite3.connect(db)
        conn.execute("DROP TABLE email_followup_enrichments")
        conn.commit()
        conn.close()
        section = build_pending_email_enrichment_section(store)
        assert section["available"] is False
        assert section["count"] == 0
        assert "enrichment_unavailable" in section.get("degraded_reason", "")


def test_daily_run_with_email_raw_enrichment_flag() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "b.db")
        store = ConstructionStore(db_path=db)
        _seed_enrichment(store, cid="c1", confidence=0.8, band="high")
        res = runner.invoke(
            app,
            ["second-brain", "daily-run", "run", "--db", db, "--date", "2026-06-02",
             "--with-email-raw-enrichment", "--dry-run", "--json"],
        )
        assert res.exit_code == 0, res.output
        payload = json.loads(res.output)
        assert "email_raw_enrichment" in payload
        section = payload["email_raw_enrichment"]
        assert section["available"] is True
        assert section["count"] == 1
        assert section["items"][0]["label"] == PENDING_LABEL
        for forbidden in ("http://", "https://", "body_html", "raw_prompt"):
            assert forbidden not in res.output


def test_daily_run_without_flag_unchanged() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "b.db")
        ConstructionStore(db_path=db)
        res = runner.invoke(
            app,
            ["second-brain", "daily-run", "run", "--db", db, "--date", "2026-06-02",
             "--dry-run", "--json"],
        )
        assert res.exit_code == 0, res.output
        payload = json.loads(res.output)
        assert "email_raw_enrichment" not in payload
