"""Phase 10 V45 — enrichment engine + persistence tests (offline, synthetic).

Proves eligibility gating (email-source-linked, open), dry-run zero-writes, apply requires a positive
cap and respects it, idempotent re-runs, model-unavailable / missing-raw clean degradation, the
pre-write raw-leak guard, and that persisted V45 rows are review-safe (no raw fields).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.local_ai.email_followup_enrichment import (
    run_email_followup_enrichment,
    select_eligible_candidates,
)
from hb_assistant.construction.second_brain.local_ai.raw_followup_window import (
    build_raw_followup_window,
)
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient
from hb_assistant.construction.store import ConstructionStore

_PRESENT = {"mistral-nemo:12b"}
_BODY = "Please confirm the slab schedule and send the revised submittal by reviewing this."


def _seed_candidate(
    store: ConstructionStore,
    *,
    cid: str,
    msg_hash: str = "mh-shared",
    srh: str = "srh-shared",
    family: str = "email_message",
    status: str = "open",
    with_raw: bool = True,
) -> None:
    store.upsert_task_candidate(
        candidate_id=cid,
        stable_key=f"sk-{cid}",
        title_redacted="Follow up on RFI",
        waiting_state="waiting_on_me",
        safety_category="normal",
    )
    store.insert_accepted_task(
        candidate_id=cid,
        title_redacted="Follow up on RFI",
        waiting_state="waiting_on_me",
        safety_category="normal",
        status=status,
    )
    store.upsert_candidate_source_ref(
        source_ref_id=f"sr-{cid}",
        candidate_type="task",
        candidate_id=cid,
        source_family=family,
        source_ref_hash=srh,
        source_table="email_message_raw_content",
        source_primary_key_hash=msg_hash,
    )
    if with_raw:
        store.upsert_email_message_raw_content(
            raw_email_id=f"raw-{msg_hash}",
            message_id_hash=msg_hash,
            source_ref_hash=srh,
            subject="RFI follow up",
            body_text=_BODY,
            from_address="vendor@example.com",
            received_at_utc="2026-06-01T10:00:00+00:00",
        )


def _mock_output_for(store: ConstructionStore, cid: str, *, reason_codes=None, leak_in_reason=False) -> str:
    """Build a schema-valid mock output whose raw_excerpt_hash matches the engine's window."""
    refs = store.list_candidate_source_refs(candidate_id=cid, candidate_type="task")
    win = build_raw_followup_window(
        candidate_id=cid, candidate_type="task", source_refs=refs, store=store
    )
    rc = reason_codes or ["direct_ask"]
    if leak_in_reason:
        rc = ["see http://leak.example.com/x"]
    return json.dumps(
        {
            "enriched_title": "Send revised RFI response",
            "waiting_state": "waiting_on_me",
            "assignee_type": "me",
            "assignee_display": "",
            "suggested_next_action": "Draft and send the revised response.",
            "due_at_utc": None,
            "confidence": 0.8,
            "reason_codes": rc,
            "cited_source_aliases": [],
            "cited_candidate_ids": [],
            "cited_watch_item_ids": [],
            "raw_excerpt_hash": win.raw_excerpt_hash,
        }
    )


def _store(td: str) -> ConstructionStore:
    return ConstructionStore(db_path=str(Path(td) / "engine.db"))


def test_no_email_refs_means_no_model_call() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store, cid="c1", family="procore_rfi")
        backend = StaticOutputClient("{}")
        out = run_email_followup_enrichment(
            store=store, present_models=_PRESENT, backend=backend, dry_run=True
        )
        assert out["eligible"] == 0
        assert backend.call_count == 0
        assert out["would_persist"] == 0


def test_missing_raw_degrades_without_model_call() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store, cid="c1", with_raw=False)
        backend = StaticOutputClient("{}")
        out = run_email_followup_enrichment(
            store=store, present_models=_PRESENT, backend=backend, dry_run=True
        )
        assert out["eligible"] == 1
        assert backend.call_count == 0
        assert any(s["reason"] == "no_raw_content_available" for s in out["skipped"])
        assert out["would_persist"] == 0


def test_model_unavailable_no_persist() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store, cid="c1")
        backend = StaticOutputClient(_mock_output_for(store, "c1"))
        out = run_email_followup_enrichment(
            store=store, present_models=set(), backend=backend,
            dry_run=False, max_persist=5,
        )
        assert out["model_unavailable"] is True
        assert out["persisted"] == 0
        assert backend.call_count == 0
        assert store.count_email_followup_enrichments() == 0


def test_dry_run_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store, cid="c1")
        out = run_email_followup_enrichment(
            store=store, present_models=_PRESENT,
            backend=StaticOutputClient(_mock_output_for(store, "c1")), dry_run=True,
        )
        assert out["mode"] == "dry_run"
        assert out["would_persist"] == 1
        assert out["persisted"] == 0
        assert store.count_email_followup_enrichments() == 0


def test_apply_requires_positive_cap() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store, cid="c1")
        with pytest.raises(ValueError):
            run_email_followup_enrichment(
                store=store, present_models=_PRESENT,
                backend=StaticOutputClient(_mock_output_for(store, "c1")),
                dry_run=False, max_persist=None,
            )
        with pytest.raises(ValueError):
            run_email_followup_enrichment(
                store=store, present_models=_PRESENT,
                backend=StaticOutputClient(_mock_output_for(store, "c1")),
                dry_run=False, max_persist=0,
            )


def test_apply_respects_cap() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        # 3 candidates sharing one raw email row -> identical window hash (one mock works for all).
        for cid in ("c1", "c2", "c3"):
            _seed_candidate(store, cid=cid)
        out = run_email_followup_enrichment(
            store=store, present_models=_PRESENT,
            backend=StaticOutputClient(_mock_output_for(store, "c1")),
            dry_run=False, max_persist=2,
        )
        assert out["persisted"] == 2
        assert store.count_email_followup_enrichments() == 2


def test_apply_idempotent_no_duplicate() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store, cid="c1")
        mock = _mock_output_for(store, "c1")
        run_email_followup_enrichment(
            store=store, present_models=_PRESENT,
            backend=StaticOutputClient(mock), dry_run=False, max_persist=5,
        )
        assert store.count_email_followup_enrichments() == 1
        run_email_followup_enrichment(
            store=store, present_models=_PRESENT,
            backend=StaticOutputClient(mock), dry_run=False, max_persist=5,
        )
        assert store.count_email_followup_enrichments() == 1  # idempotent


def test_persisted_row_is_review_safe() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store, cid="c1")
        run_email_followup_enrichment(
            store=store, present_models=_PRESENT,
            backend=StaticOutputClient(_mock_output_for(store, "c1")),
            dry_run=False, max_persist=5,
        )
        rows = store.list_email_followup_enrichments()
        assert len(rows) == 1
        row = rows[0]
        assert row["source_candidate_id"] == "c1"
        assert row["review_status"] == "pending"
        assert row["raw_excerpt_hash"].startswith("sha256:")
        blob = json.dumps(row)
        for forbidden in ("body_html", "raw_prompt", "raw_response", _BODY, "http://", "https://"):
            assert forbidden not in blob


def test_raw_leak_guard_blocks_persistence() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store, cid="c1")
        # reason_codes carry a URL: passes the schema (no validator on reason_codes) but the engine's
        # per-field leak guard must block the write.
        out = run_email_followup_enrichment(
            store=store, present_models=_PRESENT,
            backend=StaticOutputClient(_mock_output_for(store, "c1", leak_in_reason=True)),
            dry_run=False, max_persist=5,
        )
        assert out["persisted"] == 0
        assert any(s["reason"] == "raw_leak_detected" for s in out["skipped"])
        assert store.count_email_followup_enrichments() == 0


def test_closed_items_skipped_by_default() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store, cid="c1", status="closed")
        sel = select_eligible_candidates(store=store)
        assert sel == []
        sel_incl = select_eligible_candidates(store=store, include_closed=True)
        assert len(sel_incl) == 1


def test_no_eligible_reports_note() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        out = run_email_followup_enrichment(
            store=store, present_models=_PRESENT, backend=StaticOutputClient("{}"), dry_run=True
        )
        assert out["note"] == "no_eligible_candidates"
        assert out["eligible"] == 0
