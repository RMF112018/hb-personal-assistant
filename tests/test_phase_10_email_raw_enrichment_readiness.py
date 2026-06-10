"""Phase 10 V45 — email raw enrichment readiness/eligibility funnel (offline, synthetic, raw-free).

Proves each no-op reason code is reported, eligible rows are counted, already-enriched rows are
excluded, the local-model-unavailable gate is explicit, and the report carries no raw content.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.email_followup_readiness import (
    build_email_followup_enrichment_readiness,
)
from hb_assistant.construction.store import ConstructionStore

_PRESENT = {"mistral-nemo:12b"}
_BODY = "Please confirm the slab schedule and send the revised submittal."


def _store(td: str) -> ConstructionStore:
    return ConstructionStore(db_path=str(Path(td) / "readiness.db"))


def _seed(
    store: ConstructionStore, *, cid: str, family: str = "email_message",
    with_raw: bool = True, with_refs: bool = True, msg: str = "mh", srh: str = "srh",
) -> None:
    store.upsert_task_candidate(
        candidate_id=cid, stable_key=f"sk-{cid}", title_redacted="Follow up on RFI",
        waiting_state="waiting_on_me", safety_category="normal",
    )
    store.insert_accepted_task(
        candidate_id=cid, title_redacted="Follow up on RFI", waiting_state="waiting_on_me",
        safety_category="normal", status="open",
    )
    if with_refs:
        store.upsert_candidate_source_ref(
            source_ref_id=f"sr-{cid}", candidate_type="task", candidate_id=cid,
            source_family=family, source_ref_hash=f"{srh}-{cid}",
            source_table="email_message_raw_content", source_primary_key_hash=f"{msg}-{cid}",
        )
    if with_raw:
        store.upsert_email_message_raw_content(
            raw_email_id=f"raw-{msg}-{cid}", message_id_hash=f"{msg}-{cid}",
            source_ref_hash=f"{srh}-{cid}", subject="RFI follow up", body_text=_BODY,
            from_address="vendor@example.com", received_at_utc="2026-06-01T10:00:00+00:00",
        )


def test_no_accepted_items() -> None:
    with tempfile.TemporaryDirectory() as td:
        r = build_email_followup_enrichment_readiness(store=_store(td), present_models=_PRESENT)
        assert r["accepted_total"] == 0
        assert r["eligible_for_raw_enrichment"] == 0


def test_no_source_refs_reason() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed(store, cid="c1", with_refs=False, with_raw=False)
        r = build_email_followup_enrichment_readiness(store=store, present_models=_PRESENT)
        assert r["skipped_by_reason"]["no_candidate_source_refs"] == 1


def test_non_email_refs_reason() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed(store, cid="c1", family="procore_rfi", with_raw=False)
        r = build_email_followup_enrichment_readiness(store=store, present_models=_PRESENT)
        assert r["skipped_by_reason"]["no_email_source_ref"] == 1


def test_email_refs_but_no_raw_reason() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed(store, cid="c1", with_raw=False)
        r = build_email_followup_enrichment_readiness(store=store, present_models=_PRESENT)
        assert r["accepted_with_email_source_refs"] == 1
        assert r["skipped_by_reason"]["no_raw_email_content"] == 1


def test_eligible_when_email_raw_and_model_present() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed(store, cid="c1")
        r = build_email_followup_enrichment_readiness(store=store, present_models=_PRESENT)
        assert r["accepted_with_raw_email_content"] == 1
        assert r["eligible_for_raw_enrichment"] == 1
        assert r["local_model_available"] is True
        assert "c1" in r["sample_eligible_candidate_ids"]


def test_already_pending_excluded() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed(store, cid="c1")
        store.upsert_email_followup_enrichment(
            enrichment_id="e1", idempotency_key="i1", source_candidate_id="c1",
            source_candidate_type="task", raw_excerpt_hash="sha256:x", enriched_title="t",
            waiting_state="waiting_on_me", assignee_type="me", confidence=0.8,
            confidence_band="high", input_context_hash="ic", output_hash="oc",
            prompt_template_version="email_followup_raw_enrichment.v1", review_status="pending",
        )
        r = build_email_followup_enrichment_readiness(store=store, present_models=_PRESENT)
        assert r["already_enriched_pending"] == 1
        assert r["skipped_by_reason"]["already_pending"] == 1
        assert r["eligible_for_raw_enrichment"] == 0


def test_local_model_unavailable_gate() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed(store, cid="c1")
        r = build_email_followup_enrichment_readiness(store=store, present_models=None)
        assert r["local_model_available"] is False
        assert r["skipped_by_reason"]["local_model_unavailable"] == 1
        assert r["eligible_for_raw_enrichment"] == 0


def test_report_is_raw_free() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed(store, cid="c1")
        r = build_email_followup_enrichment_readiness(store=store, present_models=_PRESENT)
        blob = json.dumps(r)
        assert "slab schedule" not in blob  # raw body never surfaces
        assert "vendor@example.com" not in blob
        for forbidden in ("http://", "https://", "Bearer ", "<html"):
            assert forbidden not in blob
        assert r["guardrails"]["no_raw_body_loaded"] is True
