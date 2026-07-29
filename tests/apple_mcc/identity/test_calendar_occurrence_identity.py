"""Calendar occurrence identity tests."""

from __future__ import annotations

from hb_assistant.apple_mcc.identity.calendar_revision import (
    apple_absent_graph_event_id_hash,
    calendar_raw_snapshot_id,
    calendar_revision_key,
    occurrence_key,
    source_locator_hash,
    calendar_locator_hash,
)


def test_occurrence_key_stable() -> None:
    src = source_locator_hash("iCloud")
    cal = calendar_locator_hash(src, "cal-1")
    o1 = occurrence_key(cal, ical_uid="UID1", ek_event_id="ek1", start_utc="2026-01-01T10:00:00Z")
    o2 = occurrence_key(cal, ical_uid="UID1", ek_event_id="ek2", start_utc="2026-01-01T10:00:00Z")
    assert o1 == o2


def test_revision_and_snapshot() -> None:
    occ = "ab" * 32
    rev = calendar_revision_key(occ, "cd" * 32)
    snap = calendar_raw_snapshot_id(rev)
    assert len(snap) == 64
    absent = apple_absent_graph_event_id_hash("11" * 32)
    assert len(absent) == 64
