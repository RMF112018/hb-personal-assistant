"""Shared deterministic seeding helpers for the Phase 10 V52 effectiveness telemetry tests.

Not a test module. Seeds source-linked candidates with varied V50 lifecycle dispositions, runs the
V51 ranking/assembly overlay to populate the ranked/assembly rows, and returns an isolated
``ConstructionStore`` so each test exercises the V52 telemetry layer over a known, raw-free fixture.
"""

from __future__ import annotations

from typing import Optional

from hb_assistant.construction.second_brain.local_ai import run_candidate_ranking_and_assembly
from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-11T12:00:00+00:00"
BRIEF_DATE = "2026-06-11"
# A reference "now" well past the 72h ignored-lag window, so open items resolve to ``ignored``.
EVAL_NOW = "2026-06-30T00:00:00+00:00"
WINDOW_START = "2026-06-01"
WINDOW_END = "2026-06-30"


def _task(
    store: ConstructionStore,
    cid: str,
    *,
    refs: bool = True,
    source_family: str = "email",
    review_status: str = "pending",
    project_key: Optional[str] = "PRJ-A",
    confidence: float = 0.6,
) -> None:
    store.upsert_task_candidate(
        candidate_id=cid,
        stable_key=f"PRJ:{cid}",
        title_redacted=f"Task {cid}",
        project_key=project_key,
        confidence=confidence,
        review_status=review_status,
    )
    if refs:
        store.upsert_candidate_source_ref(
            source_ref_id=f"sr-{cid}",
            candidate_type="task",
            candidate_id=cid,
            source_family=source_family,
            source_ref_hash=f"h-{cid}",
        )


def _event(
    store: ConstructionStore,
    cid: str,
    *,
    event_type: str,
    new_state: str,
    until: Optional[str] = None,
) -> None:
    store.insert_lifecycle_event(
        idempotency_key=f"{event_type}:{cid}",
        subject_type="task_candidate",
        subject_id=cid,
        event_type=event_type,
        new_state=new_state,
        effective_until_utc=until,
    )


def seed_effectiveness_store(db: str, *, now: str = NOW) -> ConstructionStore:
    """Seed surfaced candidates, run the V51 overlay, THEN disposition them. Returns the store.

    Mirrors the real flow: the brief surfaces pending (review-required) items first, and the operator
    accepts/rejects/snoozes them afterwards. Outcomes represented: accepted, rejected, snoozed,
    ignored (open + aged past lag), plus a Procore-family rejected item for the noise evaluator.
    """
    store = ConstructionStore(db_path=db)
    for cid, source_family, project in (
        ("e_acc", "email", "PRJ-A"),
        ("e_rej", "email", "PRJ-A"),
        ("e_snz", "email", "PRJ-A"),
        ("e_ign", "email", "PRJ-A"),
        ("e_proc", "procore", "PRJ-B"),
    ):
        _task(store, cid, source_family=source_family, project_key=project, review_status="pending")

    # Surface them in the brief (V51 ranks only visible/surfaced candidates).
    run_candidate_ranking_and_assembly(
        store=store,
        brief_date=BRIEF_DATE,
        now_utc=now,
        use_model=False,
        include_similarity=True,
        dry_run=False,
        max_persist=1000,
    )

    # Operator dispositions AFTER exposure (e_ign is left open → ignored once aged past the lag).
    _event(store, "e_acc", event_type="accept", new_state="accepted")
    _event(store, "e_rej", event_type="reject", new_state="rejected")
    _event(
        store, "e_snz", event_type="snooze", new_state="snoozed", until="2026-12-31T00:00:00+00:00"
    )
    _event(store, "e_proc", event_type="reject", new_state="rejected")
    return store
