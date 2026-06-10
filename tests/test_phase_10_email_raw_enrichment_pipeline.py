"""Phase 10 V45 — email raw enrichment daily-run apply STAGE (offline, synthetic).

Proves the bounded daily-run stage wrapper: dry-run persists nothing, apply requires a positive cap
and respects it, re-runs are idempotent, the local-model-unavailable path degrades cleanly, persisted
rows keep the guard columns zero, and the stage receipt is raw-free.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.daily_run import (
    _run_email_raw_enrichment_stage,
)
from hb_assistant.construction.second_brain.local_ai.raw_followup_window import (
    build_raw_followup_window,
)
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.connection import get_connection

_PRESENT = {"mistral-nemo:12b"}
_BODY = "Please confirm the slab schedule and send the revised submittal."
_GUARDS = (
    "raw_email_body_persisted", "raw_document_text_persisted", "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted", "raw_prompt_persisted", "raw_response_persisted",
    "signed_url_persisted", "download_url_persisted", "external_writeback_performed",
    "graph_writeback_performed", "procore_writeback_performed",
)


def _store(td: str) -> ConstructionStore:
    return ConstructionStore(db_path=str(Path(td) / "stage.db"))


def _seed(store: ConstructionStore, *, cid: str, msg: str = "mh-shared", srh: str = "srh-shared") -> None:
    # Candidates share one raw email row (shared msg/srh) → identical windows → one mock matches all.
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
        source_family="email_message", source_ref_hash=srh,
        source_table="email_message_raw_content", source_primary_key_hash=msg,
    )
    store.upsert_email_message_raw_content(
        raw_email_id=f"raw-{msg}", message_id_hash=msg, source_ref_hash=srh,
        subject="RFI follow up", body_text=_BODY, from_address="vendor@example.com",
        received_at_utc="2026-06-01T10:00:00+00:00",
    )


def _mock_for(store: ConstructionStore, cid: str) -> str:
    refs = store.list_candidate_source_refs(candidate_id=cid, candidate_type="task")
    win = build_raw_followup_window(candidate_id=cid, candidate_type="task", source_refs=refs, store=store)
    return json.dumps({
        "enriched_title": "Send revised RFI response", "waiting_state": "waiting_on_me",
        "assignee_type": "me", "assignee_display": "", "suggested_next_action": "Draft and send.",
        "due_at_utc": None, "confidence": 0.8, "reason_codes": ["direct_ask"],
        "cited_source_aliases": [], "cited_candidate_ids": [], "cited_watch_item_ids": [],
        "raw_excerpt_hash": win.raw_excerpt_hash,
    })


def _guard_sums(store: ConstructionStore) -> int:
    conn = get_connection(store._db_path)
    cols = ", ".join(f"COALESCE(SUM({c}),0)" for c in _GUARDS)
    row = conn.execute(f"SELECT {cols} FROM email_followup_enrichments").fetchone()
    return sum(int(v) for v in row)


def test_dry_run_persists_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed(store, cid="c1")
        r = _run_email_raw_enrichment_stage(
            store=store, now_utc="2026-06-09T05:00:00-04:00", enabled=True, dry_run=True,
            max_persist=5, backend=StaticOutputClient(_mock_for(store, "c1")), present_models=_PRESENT,
        )
        assert r["stage"] == "email_followup_raw_enrichment"
        assert r["would_persist"] == 1
        assert r["persisted"] == 0
        assert store.count_email_followup_enrichments() == 0


def test_disabled_skips() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed(store, cid="c1")
        r = _run_email_raw_enrichment_stage(
            store=store, now_utc="x", enabled=False, dry_run=False, max_persist=5,
        )
        assert r["status"] == "skipped"
        assert r["degraded_reason"] == "disabled"


def test_apply_cap_respected_and_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        for cid in ("c1", "c2", "c3"):
            _seed(store, cid=cid)
        # Cap at 2 with 3 eligible → exactly 2 persisted.
        r = _run_email_raw_enrichment_stage(
            store=store, now_utc="2026-06-09T05:00:00-04:00", enabled=True, dry_run=False,
            max_persist=2, backend=StaticOutputClient(_mock_for(store, "c1")), present_models=_PRESENT,
        )
        assert r["status"] == "ok"
        assert r["persisted"] == 2
        assert store.count_email_followup_enrichments() == 2
        # Idempotent re-run of the same two does not duplicate.
        before = store.count_email_followup_enrichments()
        _run_email_raw_enrichment_stage(
            store=store, now_utc="2026-06-09T05:00:00-04:00", enabled=True, dry_run=False,
            max_persist=2, backend=StaticOutputClient(_mock_for(store, "c1")), present_models=_PRESENT,
        )
        assert store.count_email_followup_enrichments() == before
        assert _guard_sums(store) == 0


def test_model_unavailable_degrades_without_persist() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed(store, cid="c1")
        r = _run_email_raw_enrichment_stage(
            store=store, now_utc="2026-06-09T05:00:00-04:00", enabled=True, dry_run=False,
            max_persist=5, backend=StaticOutputClient(_mock_for(store, "c1")), present_models=set(),
        )
        assert r["status"] == "degraded"
        assert r["persisted"] == 0
        assert store.count_email_followup_enrichments() == 0


def test_receipt_is_raw_free() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed(store, cid="c1")
        r = _run_email_raw_enrichment_stage(
            store=store, now_utc="2026-06-09T05:00:00-04:00", enabled=True, dry_run=False,
            max_persist=5, backend=StaticOutputClient(_mock_for(store, "c1")), present_models=_PRESENT,
        )
        blob = json.dumps(r)
        assert "slab schedule" not in blob
        assert "vendor@example.com" not in blob
