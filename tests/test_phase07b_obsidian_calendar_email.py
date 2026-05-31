"""Phase 07B Prompt 10 — marker-bounded Obsidian calendar/email register (redacted).

Proves: a single grouped register note per project (not one-per-item); dry-run writes
nothing; apply writes a marker-bounded note that passes the secret scanner and contains no
raw subject/address/URL/calendar tokens; and re-apply replaces only the marker-bounded
region while preserving surrounding user text.

The autouse `isolated_hb_pa_config` conftest fixture points the vault at a per-test tmp dir,
so these writes never touch the real Obsidian vault.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from hb_assistant.construction.calendar_email_obsidian import CalendarEmailObsidianProjector
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.procore_no_writeback_proof import _scan_text_for_secrets

_MARKER_START = "<!-- HB-CALENDAR-EMAIL-REGISTER:START -->"
_MARKER_END = "<!-- HB-CALENDAR-EMAIL-REGISTER:END -->"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _seed(tmp_path: Path) -> ConstructionStore:
    store = ConstructionStore(str(tmp_path / "db.sqlite"))
    store.upsert_calendar_source_location(source_id="primary_calendar", mailbox_owner_hash="owner")
    store.upsert_email_source_location(
        source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F"
    )
    now = _now_iso()
    store.upsert_calendar_event_index(
        event_index_id="E1", source_id="primary_calendar", graph_event_id_hash="g1",
        start_datetime_utc=now, end_datetime_utc=now, organizer_domain="vendor.com",
        review_required=True,
    )
    for mid, tk in (("m1", "T1"), ("m2", "T2")):
        store.upsert_email_message(message_id=mid, thread_key=tk, source_id="sx",
                                   received_datetime=now)
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
    store.enqueue_email_review_item(
        review_id="r1", message_id="m1", category="contracts", sensitivity="medium",
        reason="sensitive_category:contracts", suggested_action="route_to_review",
        confidence=0.9, project_key="tropical",
    )
    store.upsert_meeting_email_relationship_candidate(
        candidate_id="c1", event_index_id="E1", thread_key_hash="abc123def456",
        project_key="tropical", candidate_type="time_and_domain",
        source_reference_json=json.dumps(
            {"event_index_id": "E1", "thread_key_hash": "abc123def456",
             "event_start_utc": now, "event_end_utc": now}
        ),
        confidence=0.8, confidence_class="strong", review_required=False,
    )
    return store


def test_dry_run_plans_one_note_and_writes_nothing(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    report = CalendarEmailObsidianProjector(store).project(project_key="tropical", dry_run=True)
    assert report.notes_planned == 1  # one grouped register, not one-per-item
    assert report.notes_written == 0
    assert report.plaintext_written is False
    assert report.threads_referenced == 2
    assert report.candidates_referenced == 1
    assert not Path(report.paths[0]).exists()


def test_apply_writes_marker_bounded_redacted_note(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    report = CalendarEmailObsidianProjector(store).project(project_key="tropical", dry_run=False)
    assert report.notes_written == 1
    path = Path(report.paths[0])
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert _MARKER_START in text and _MARKER_END in text
    assert "Calendar & Email Register" in text
    # No raw values / secrets.
    assert _scan_text_for_secrets(text) == []
    low = text.lower()
    for token in ("@", "http", "begin:vevent", "join url", "-----original message-----"):
        assert token not in low
    # Previews/candidates render hashes, not raw thread keys.
    from hb_assistant.normalize.redaction import hash_value

    assert "abc123def456" in text  # candidate thread_key_hash (already a hash)
    assert hash_value("T1") in text  # preview thread_ref is the hashed thread_key


def test_reapply_preserves_user_text_outside_markers(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    projector = CalendarEmailObsidianProjector(store)
    path = Path(projector.project(project_key="tropical", dry_run=False).paths[0])

    user_top = "# My own notes\n\nKeep this paragraph.\n"
    user_bottom = "\nFooter the user wrote.\n"
    body = path.read_text(encoding="utf-8")
    inner = body[body.index(_MARKER_START):body.index(_MARKER_END) + len(_MARKER_END)]
    path.write_text(user_top + inner + user_bottom, encoding="utf-8")

    projector.project(project_key="tropical", dry_run=False)
    text2 = path.read_text(encoding="utf-8")
    assert "Keep this paragraph." in text2
    assert "Footer the user wrote." in text2
    assert text2.count(_MARKER_START) == 1  # markers not duplicated
    assert _scan_text_for_secrets(text2) == []
