"""Shared deterministic seeding helpers for the Phase 10 V51 ranking/assembly tests.

Not a test module (no ``test_`` prefix). Seeds source-linked candidate/accepted/lifecycle rows into
an isolated ``ConstructionStore`` so each test exercises the V50 read model + V51 overlay over a
known, raw-free fixture set.
"""

from __future__ import annotations

from typing import Optional

from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-11T12:00:00+00:00"
BRIEF_DATE = "2026-06-11"
_ACCEPTED_UTC = "2026-06-10T00:00:00+00:00"


def accept_task(
    store: ConstructionStore,
    cid: str,
    *,
    waiting: str = "unknown",
    project_key: Optional[str] = "PRJ-A",
    due_at_utc: Optional[str] = None,
    refs: bool = True,
    title: Optional[str] = None,
    confidence: float = 0.8,
) -> None:
    """Seed a source-linked accepted task (the brief's primary surfaced family)."""
    store.upsert_task_candidate(
        candidate_id=cid,
        stable_key=f"PRJ:{cid}",
        title_redacted=title or f"Task {cid}",
        project_key=project_key,
        waiting_state=waiting,
        due_at_utc=due_at_utc,
        confidence=confidence,
        review_status="accepted",
    )
    if refs:
        store.upsert_candidate_source_ref(
            source_ref_id=f"sr-{cid}",
            candidate_type="task",
            candidate_id=cid,
            source_family="email",
            source_ref_hash=f"h-{cid}",
        )
    store.insert_accepted_task(
        candidate_id=cid,
        title_redacted=title or f"Task {cid}",
        waiting_state=waiting,
        safety_category="normal",
        project_key=project_key,
        due_at_utc=due_at_utc,
        accepted_utc=_ACCEPTED_UTC,
    )


def pending_candidate(
    store: ConstructionStore,
    cid: str,
    *,
    review_status: str = "pending",
    project_key: Optional[str] = "PRJ-A",
    confidence: float = 0.5,
    refs: bool = True,
    title: Optional[str] = None,
) -> None:
    """Seed a task candidate in a given review_status (pending/rejected/snoozed/suppressed)."""
    store.upsert_task_candidate(
        candidate_id=cid,
        stable_key=f"PRJ:{cid}",
        title_redacted=title or f"Candidate {cid}",
        project_key=project_key,
        confidence=confidence,
        review_status=review_status,
    )
    if refs:
        store.upsert_candidate_source_ref(
            source_ref_id=f"sr-{cid}",
            candidate_type="task",
            candidate_id=cid,
            source_family="email",
            source_ref_hash=f"h-{cid}",
        )


def snooze_future(
    store: ConstructionStore, cid: str, *, until: str = "2026-12-31T00:00:00+00:00"
) -> None:
    """Seed a candidate snoozed into the future via the V50 lifecycle overlay (hidden from brief)."""
    pending_candidate(store, cid, review_status="pending")
    store.insert_lifecycle_event(
        idempotency_key=f"snooze:{cid}",
        subject_type="task_candidate",
        subject_id=cid,
        event_type="snooze",
        new_state="snoozed",
        effective_until_utc=until,
    )


def seed_ranking_store(db: str) -> ConstructionStore:
    """Seed the default ranking fixture: three source-linked accepted tasks (varied signals)."""
    store = ConstructionStore(db_path=db)
    accept_task(store, "t1", waiting="waiting_on_me", project_key="PRJ-A")
    accept_task(
        store, "t2", waiting="unknown", project_key="PRJ-B", due_at_utc="2026-06-09T00:00:00+00:00"
    )
    accept_task(store, "t3", waiting="waiting_on_others", project_key="PRJ-C")
    return store
