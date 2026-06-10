"""Phase 10 — daily-run surface convergence for the V45 pending email follow-up section.

Proves the raw-free pending-enrichment section converges onto the FINAL daily-run surfaces:

* it appears in the browser HTML card and in the Obsidian markdown when pending review-safe rows
  exist — deterministically, WITHOUT model synthesis (``synthesize_brief=False``);
* it is absent (clean-degraded) when there are no pending rows;
* it survives the degraded synthesis path (the HTML renderer emits the card before the brief body);
* the redacted status file carries only counts/labels for it (no row-level content); and
* the rendered HTML stays egress-clean.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.daily_brief.email_followup_pending import (
    PENDING_LABEL,
    build_pending_email_enrichment_section,
)
from hb_assistant.construction.second_brain.local_ai.daily_run import run_daily_local_agent
from hb_assistant.construction.second_brain.local_ai.daily_run_html import (
    render_daily_run_html,
    scan_daily_run_html,
)
from hb_assistant.construction.store import ConstructionStore


def _seed(store: ConstructionStore, *, cid: str, confidence: float = 0.82, band: str = "high") -> None:
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
        review_status="pending",
    )


def _run(store: ConstructionStore, td: Path, db_path: str) -> dict:
    return run_daily_local_agent(
        store=store,
        now_utc="2026-06-09T05:00:00-04:00",  # a weekday
        db_path=db_path,
        dry_run=False,
        weekdays_only=True,
        synthesize_brief=False,  # deterministic — no model required
        generate_browser=True,
        browser_output_dir=str(td / "html"),
        status_dir=str(td / "status"),
    )


def test_seeded_pending_section_converges_to_browser_and_status() -> None:
    with tempfile.TemporaryDirectory() as t:
        td = Path(t)
        db_path = str(td / "b.db")
        store = ConstructionStore(db_path=db_path)
        _seed(store, cid="c1")
        _seed(store, cid="c2")
        res = _run(store, td, db_path)

        # Status carries the redacted pending summary (counts/labels only).
        assert res["pending_followup"]["available"] is True
        assert res["pending_followup"]["count"] == 2
        assert "items" not in res["pending_followup"]

        # The browser HTML card is present and egress-clean.
        html_files = list((td / "html").glob("daily-brief-*.html"))
        assert html_files, "expected a dated browser HTML artifact"
        html = html_files[0].read_text(encoding="utf-8")
        assert PENDING_LABEL in html
        assert "Send revised RFI for c1" in html
        assert scan_daily_run_html(html) == []

        # The latest status file mirrors the redacted summary (no row content).
        status = json.loads((td / "status" / "latest-status.json").read_text(encoding="utf-8"))
        assert status["pending_followup"]["count"] == 2
        assert "Send revised RFI" not in json.dumps(status)


def test_no_pending_rows_section_absent() -> None:
    with tempfile.TemporaryDirectory() as t:
        td = Path(t)
        db_path = str(td / "b.db")
        store = ConstructionStore(db_path=db_path)
        res = _run(store, td, db_path)
        assert res["pending_followup"]["count"] == 0
        for f in (td / "html").glob("daily-brief-*.html"):
            assert PENDING_LABEL not in f.read_text(encoding="utf-8")


def test_pending_card_survives_degraded_synthesis_path() -> None:
    with tempfile.TemporaryDirectory() as t:
        store = ConstructionStore(db_path=str(Path(t) / "b.db"))
        _seed(store, cid="c9")
        section = build_pending_email_enrichment_section(store)
        html = render_daily_run_html(
            brief_date="2026-06-09",
            status="partial",
            sections=[],
            summary={"rendered": 0},
            warnings=["synthesis_degraded: model_unavailable"],
            generated_label="2026-06-09T05:00:00-04:00",
            degraded=True,
            model_metadata={"degraded_reason": "model_unavailable"},
            pending_followup=section,
        )
        assert PENDING_LABEL in html  # card emitted even on the degraded path
        assert "Send revised RFI for c9" in html
        assert scan_daily_run_html(html) == []
