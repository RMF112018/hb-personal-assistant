"""Phase 10 — cross-candidate daily-run integration (offline, synthetic, fully injected models).

Proves ONE daily-run apply converges all three candidates: the V45 email raw enrichment stage
persists a review-safe pending row, the converged Model Enriched Intelligence section consumes it the
same run alongside source-linked advisory bullets, the browser surface renders the exact label, the
status is raw-free, and the V45 guard columns stay zero. No live model is used (both paths injected).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.daily_run import run_daily_local_agent
from hb_assistant.construction.second_brain.local_ai.raw_followup_window import (
    build_raw_followup_window,
)
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.connection import get_connection

_PRESENT = {"mistral-nemo:12b"}
_BRIEF_DATE = "2026-06-09"  # a weekday
_WEEKDAY = "2026-06-09T05:00:00-04:00"
_BODY = "Please confirm the slab schedule and send the revised submittal."
_GUARDS = (
    "raw_email_body_persisted", "raw_document_text_persisted", "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted", "raw_prompt_persisted", "raw_response_persisted",
    "signed_url_persisted", "download_url_persisted", "external_writeback_performed",
    "graph_writeback_performed", "procore_writeback_performed",
)


def _seed_email_candidate(store: ConstructionStore, *, cid: str) -> None:
    store.upsert_task_candidate(
        candidate_id=cid, stable_key=f"sk-{cid}", title_redacted="Follow up on RFI",
        waiting_state="waiting_on_me", safety_category="normal",
    )
    store.insert_accepted_task(
        candidate_id=cid, title_redacted="Follow up on RFI", waiting_state="waiting_on_me",
        safety_category="normal", status="open",
    )
    store.upsert_candidate_source_ref(
        source_ref_id=f"sr-{cid}", candidate_type="task", candidate_id=cid,
        source_family="email_message", source_ref_hash=f"srh-{cid}",
        source_table="email_message_raw_content", source_primary_key_hash=f"mh-{cid}",
    )
    store.upsert_email_message_raw_content(
        raw_email_id=f"raw-{cid}", message_id_hash=f"mh-{cid}", source_ref_hash=f"srh-{cid}",
        subject="RFI follow up", body_text=_BODY, from_address="vendor@example.com",
        received_at_utc="2026-06-01T10:00:00+00:00",
    )


def _email_mock(store: ConstructionStore, cid: str) -> str:
    refs = store.list_candidate_source_refs(candidate_id=cid, candidate_type="task")
    win = build_raw_followup_window(candidate_id=cid, candidate_type="task", source_refs=refs, store=store)
    return json.dumps({
        "enriched_title": "Send revised RFI response", "waiting_state": "waiting_on_me",
        "assignee_type": "me", "assignee_display": "", "suggested_next_action": "Draft and send.",
        "due_at_utc": None, "confidence": 0.8, "reason_codes": ["direct_ask"],
        "cited_source_aliases": [], "cited_candidate_ids": [], "cited_watch_item_ids": [],
        "raw_excerpt_hash": win.raw_excerpt_hash,
    })


def _mei_mock() -> str:
    return json.dumps({
        "executive_catchup": ["One advisory item today."],
        "top_priorities": [{"text": "Respond to the RFI", "source_ids": ["c1"],
                            "confidence": 0.9, "reason_code": "due_today"}],
        "open_loops": [], "waiting_on_me": [], "waiting_on_others": [],
        "meeting_prep": [], "project_risk": [],
    })


def _guard_sums(store: ConstructionStore) -> int:
    conn = get_connection(store._db_path)
    cols = ", ".join(f"COALESCE(SUM({c}),0)" for c in _GUARDS)
    row = conn.execute(f"SELECT {cols} FROM email_followup_enrichments").fetchone()
    return sum(int(v) for v in row)


def test_one_daily_run_converges_all_three_candidates() -> None:
    with tempfile.TemporaryDirectory() as t:
        td = Path(t)
        db_path = str(td / "integration.db")
        store = ConstructionStore(db_path=db_path)
        _seed_email_candidate(store, cid="cmail")
        # A daily-brief action candidate so the advisory adapter has something to cite (alias c1).
        store.insert_daily_brief_action_candidate(
            brief_date=_BRIEF_DATE, section="actions", title_redacted="Respond to the RFI",
            confidence=0.8, project_key="P1", recommended_next_action="Send the response",
        )

        res = run_daily_local_agent(
            store=store, now_utc=_WEEKDAY, db_path=db_path, dry_run=False, weekdays_only=True,
            synthesize_brief=False, generate_browser=True,
            browser_output_dir=str(td / "html"), status_dir=str(td / "status"),
            model_enriched_intelligence=True, model_enriched_backend=StaticOutputClient(_mei_mock()),
            email_raw_enrichment=True, email_raw_enrichment_max_persist=5,
            email_raw_enrichment_backend=StaticOutputClient(_email_mock(store, "cmail")),
            email_raw_enrichment_present_models=_PRESENT,
        )

        # 1. The email raw enrichment stage ran and persisted a review-safe pending row.
        stage = res["email_raw_enrichment_stage"]
        assert stage["stage"] == "email_followup_raw_enrichment"
        assert stage["persisted"] >= 1

        # 2. Model Enriched Intelligence is enabled, available, and consumed the pending row.
        mei = res["model_enriched_intelligence"]
        assert mei["enabled"] is True
        assert mei["available"] is True
        assert mei["label"] == "Model Enriched Intelligence"
        assert mei["bullets_kept"] >= 1
        assert mei["pending_followup_count"] >= 1

        # 3. The browser surface renders the one exact-label section.
        html_files = list((td / "html").glob("daily-brief-*.html"))
        assert html_files
        html = html_files[0].read_text(encoding="utf-8")
        assert "Model Enriched Intelligence" in html

        # 4. Guard columns stay zero; status is raw-free.
        assert _guard_sums(store) == 0
        status_blob = (td / "status" / "latest-status.json").read_text(encoding="utf-8")
        assert "slab schedule" not in status_blob
        assert "vendor@example.com" not in status_blob
        assert json.loads(status_blob)["model_enriched_intelligence"]["available"] is True
