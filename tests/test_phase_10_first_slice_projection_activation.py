"""Phase 10 first slice — daily-brief raw-projection activation, substrate, and contradiction gates.

Covers the integration layer that turns the V49 raw/structured substrate into a source-linked,
gated, operator-useful daily brief:

- ``projection_activation.run_email_calendar_projection_stage`` — dry-run writes nothing; apply
  projects structured rows + receipts; a no-raw DB is honest; receipts carry counts only.
- pipeline insertion — the projection stage runs first, does not count toward candidate caps.
- ``email_followup_readiness.classify_email_followup_data_gap`` — data_gap / populated / no_source /
  not_configured.
- calendar prefers the V49 structured substrate for project resolution.
- usefulness gate contradiction checks — source rows exist but candidates empty → degraded;
  backward-compatible when no stage_context is supplied.

All assertions are counts/statuses only; a body sentinel must never appear in any receipt.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.email_calendar import projection_engine as eng
from hb_assistant.construction.second_brain.local_ai import projection_activation
from hb_assistant.construction.second_brain.local_ai.calendar_prep import (
    build_calendar_prep_candidates,
)
from hb_assistant.construction.second_brain.local_ai.email_followup_readiness import (
    classify_email_followup_data_gap,
)
from hb_assistant.construction.second_brain.local_ai.pipeline import (
    STAGE_ORDER,
    run_local_agent_pipeline,
)
from hb_assistant.construction.second_brain.local_ai.usefulness_gate import (
    evaluate_usefulness_gate,
)
from hb_assistant.construction.store import ConstructionStore

BODY = "FIRST_SLICE_BODY_SENTINEL"
AGENDA = "FIRST_SLICE_AGENDA_SENTINEL"
JOIN = "https://teams.microsoft.com/l/FIRST_SLICE_JOIN_SENTINEL"


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "fs.sqlite"))


def _count(store: ConstructionStore, table: str) -> int:
    conn = sqlite3.connect(store._db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


def _seed_email(store: ConstructionStore) -> None:
    store.upsert_email_message_raw_content(
        raw_email_id="raw:m1",
        message_id_hash="mh1",
        conversation_id_hash="ch1",
        project_key="proj-a",
        subject="Kickoff agenda",
        body_text=BODY,
        body_html=f"<p>{BODY}</p>",
        from_name="Alice",
        from_address="alice@hb.com",
        to_recipients_json=json.dumps([{"name": "Bob", "address": "bob@sub.com"}]),
        has_attachments=0,
        source_quality="graph_full_body",
    )


def _seed_calendar(store: ConstructionStore, *, event_index_id: str = "evt-1") -> None:
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id="raw:e1",
        graph_event_id_hash="gh1",
        event_index_id=event_index_id,
        project_key=None,
        subject="HB-1234 OAC meeting",
        body_text=AGENDA,
        body_html=f"<p>{AGENDA}</p>",
        location_display="Trailer",
        organizer_name="Owner",
        organizer_email="owner@hb.com",
        attendees_json="[]",
        join_url=JOIN,
        start_datetime_utc="2026-06-09T15:00:00+00:00",
        end_datetime_utc="2026-06-09T16:00:00+00:00",
        source_quality="graph_full_event_body",
    )


# --------------------------------------------------------------------------- projection activation


def test_projection_dry_run_writes_nothing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_email(store)
    _seed_calendar(store)
    before = _count(store, "email_raw_message_structured")
    receipt = projection_activation.run_email_calendar_projection_stage(
        db_path=store._db_path, apply=False
    )
    assert receipt["mode"] == "dry_run"
    assert receipt["status"] in ("ok", "no_raw_rows")
    assert _count(store, "email_raw_message_structured") == before  # no writes
    assert _count(store, "email_calendar_projection_runs") == 0


def test_projection_apply_writes_structured_and_receipts(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_email(store)
    _seed_calendar(store)
    receipt = projection_activation.run_email_calendar_projection_stage(
        db_path=store._db_path, apply=True
    )
    assert receipt["mode"] == "apply"
    assert receipt["status"] == "ok"
    assert receipt["ok"] is True
    assert _count(store, "email_raw_message_structured") >= 1
    assert _count(store, "calendar_raw_event_structured") >= 1
    assert _count(store, "email_calendar_projection_runs") >= 1
    assert _count(store, "email_calendar_projection_coverage") >= 1
    assert receipt["projection_coverage_status"] == "complete"
    assert receipt["total_unmapped_business_fields"] == 0


def test_projection_no_raw_rows_is_honest_non_failure(tmp_path: Path) -> None:
    store = _store(tmp_path)  # migrated but empty
    receipt = projection_activation.run_email_calendar_projection_stage(
        db_path=store._db_path, apply=True
    )
    assert receipt["status"] == "no_raw_rows"
    assert receipt["ok"] is True


def test_projection_receipt_emits_no_raw_values(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_email(store)
    _seed_calendar(store)
    receipt = projection_activation.run_email_calendar_projection_stage(
        db_path=store._db_path, apply=True
    )
    blob = json.dumps(receipt)
    for sentinel in (BODY, AGENDA, JOIN):
        assert sentinel not in blob
    assert receipt["guardrails"]["emits_values"] is False


def test_projection_unmapped_family_degrades_without_partial(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_email(store)
    # Inject a novel business column on the raw table so the completeness matrix sees an unmapped
    # field; live mode must degrade (never raise, never partially project).
    conn = sqlite3.connect(store._db_path)
    conn.execute("ALTER TABLE email_message_raw_content ADD COLUMN novel_business_field TEXT")
    conn.execute("UPDATE email_message_raw_content SET novel_business_field = 'x'")
    conn.commit()
    conn.close()
    receipt = projection_activation.run_email_calendar_projection_stage(
        db_path=store._db_path, apply=True, mode=eng.MODE_LIVE
    )
    assert receipt["status"] == "failed"
    assert receipt["ok"] is False
    assert any("email_message" in r for r in receipt["degraded_reason"])


# --------------------------------------------------------------------------- pipeline insertion


def test_projection_stage_runs_first_and_not_capped(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_email(store)
    _seed_calendar(store)
    assert STAGE_ORDER[0] == "email_calendar_projection"
    result = run_local_agent_pipeline(
        store=store,
        now_utc="2026-06-09T08:00:00+00:00",
        db_path=store._db_path,
        dry_run=False,
        max_persist_per_stage=5,
        max_total_persist=10,
        lookahead_days=14,
    )
    stages = result["stages"]
    assert stages[0]["stage"] == "email_calendar_projection"
    assert stages[0]["projection_status"] in ("ok", "no_raw_rows", "degraded")
    # Projection is not a candidate write — it must not consume the persist budget.
    assert stages[0]["persisted"] == 0
    assert stages[0]["would_persist"] == 0
    # Apply projected structured rows in the same run.
    assert _count(store, "email_raw_message_structured") >= 1


# --------------------------------------------------------------------------- email/follow-up data gap


def test_data_gap_when_email_exists_but_followup_empty() -> None:
    out = classify_email_followup_data_gap(
        {"email_message_raw_content": 405, "email_raw_message_structured": 405}
    )
    assert out["status"] == "data_gap"
    assert out["data_gap_card"] is not None
    assert out["source_rows"] == 810


def test_populated_when_followup_layer_has_rows() -> None:
    out = classify_email_followup_data_gap(
        {"email_message_raw_content": 405, "follow_up_watch_items": 3}
    )
    assert out["status"] == "populated"
    assert out["data_gap_card"] is None


def test_not_configured_when_nothing_present() -> None:
    assert classify_email_followup_data_gap({})["status"] == "not_configured"


# --------------------------------------------------------------------------- structured substrate


def test_calendar_prefers_structured_substrate(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_calendar(store, event_index_id="evt-struct")
    # Mirror the raw event into the legacy calendar_event_index so the windowed reader returns it.
    conn = sqlite3.connect(store._db_path)
    conn.execute(
        """INSERT INTO calendar_event_index
           (event_index_id, source_id, graph_event_id_hash, subject_redacted, location_redacted,
            organizer_domain, start_datetime_utc, end_datetime_utc, is_online_meeting)
           VALUES (?, 'src1', ?, ?, ?, ?, ?, ?, ?)""",
        (
            "evt-struct",
            "gh1",
            "[redacted]",
            "[redacted]",
            "hb.com",
            "2026-06-09T15:00:00+00:00",
            "2026-06-09T16:00:00+00:00",
            0,
        ),
    )
    conn.commit()
    conn.close()
    # Project so the structured table is populated.
    projection_activation.run_email_calendar_projection_stage(db_path=store._db_path, apply=True)
    out = build_calendar_prep_candidates(
        store=store,
        now_utc="2026-06-08T08:00:00+00:00",
        db_path=store._db_path,
        dry_run=True,
        lookahead_days=7,
    )
    substrate = out["summary"]["subject_substrate"]
    assert substrate["structured"] >= 1
    assert substrate["raw_landing"] == 0


# --------------------------------------------------------------------------- usefulness contradictions


class _EmptyStore:
    def list_daily_brief_action_candidates(self, **_: object) -> list:
        return []

    def list_candidate_source_refs(self, **_: object) -> list:
        return []


def _gate(stage_context: dict | None):
    return evaluate_usefulness_gate(
        store=_EmptyStore(),
        brief_date="2026-06-09",
        synthesis_present=False,
        synthesis_degraded=False,
        stage_context=stage_context,
    )


def test_contradiction_calendar_window_nonempty_but_no_candidates() -> None:
    res = _gate({"calendar": {"events_in_window": 5, "would_persist": 5}})
    assert "calendar_window_nonempty_but_no_candidates" in res.failed_reasons
    assert res.passed is False


def test_contradiction_procore_promotable_but_no_candidates() -> None:
    res = _gate({"procore": {"total_open_signals": 100, "promoted_count": 40}})
    assert "procore_promotable_but_no_candidates" in res.failed_reasons


def test_contradiction_email_rows_but_empty_followup_no_data_gap() -> None:
    res = _gate({"email_followup": {"source_rows": 800, "status": "no_card"}})
    assert "email_rows_but_empty_followup_no_data_gap" in res.failed_reasons


def test_data_gap_ack_suppresses_followup_contradiction() -> None:
    res = _gate({"email_followup": {"source_rows": 800, "status": "data_gap"}})
    assert "email_rows_but_empty_followup_no_data_gap" not in res.failed_reasons


def test_no_stage_context_is_backward_compatible() -> None:
    # Without stage_context the source-row contradiction checks must not fire.
    res = _gate(None)
    for reason in (
        "calendar_window_nonempty_but_no_candidates",
        "procore_promotable_but_no_candidates",
        "email_rows_but_empty_followup_no_data_gap",
    ):
        assert reason not in res.failed_reasons
