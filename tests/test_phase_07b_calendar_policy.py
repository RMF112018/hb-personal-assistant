"""Phase 07B Prompt 02 — calendar/email policy seeds, contracts, and registry helpers.

Proves the read-only YAML policy seeds and JSON contracts load and validate (with
their safety invariants enforced), and that the calendar source-registry repository
helpers round-trip and reject any non-read-only write.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.calendar import (
    load_calendar_project_match_contract,
    load_calendar_source_policy,
    load_email_thread_summary_contract,
    load_email_thread_summary_policy,
    load_meeting_email_relationship_candidate_contract,
    load_review_required_rules,
)
from hb_assistant.construction.calendar.policy import (
    CalendarSourceDefaults,
    EmailThreadSummaryDefaults,
)
from hb_assistant.construction.store import ConstructionStore


def test_calendar_source_policy_loads_and_is_read_only() -> None:
    policy = load_calendar_source_policy()
    assert policy.version == "phase07b-calendar-source-policy-v1"
    assert policy.defaults.read_only is True
    assert policy.defaults.persist_event_body is False
    assert policy.defaults.persist_join_url is False
    assert any(s.source_id == "primary_calendar" for s in policy.sources)


def test_email_thread_summary_policy_no_raw_persistence() -> None:
    policy = load_email_thread_summary_policy()
    assert policy.defaults.summary_mode == "metadata_only"
    assert policy.defaults.persist_decrypted_body is False
    assert policy.defaults.persist_raw_prompt is False
    assert policy.defaults.persist_raw_response is False


def test_review_rules_load_with_prohibitions() -> None:
    rules = load_review_required_rules()
    assert rules.rules, "expected at least one review rule"
    assert rules.prohibited.auto_promote_model_only is True
    assert rules.prohibited.persist_raw_body is True


def test_policy_validators_reject_unsafe_values() -> None:
    with pytest.raises(ValueError):
        CalendarSourceDefaults(read_only=False)
    with pytest.raises(ValueError):
        CalendarSourceDefaults(persist_event_body=True)
    with pytest.raises(ValueError):
        EmailThreadSummaryDefaults(persist_raw_prompt=True)


def test_json_contracts_load_and_disable_auto_promotion() -> None:
    match = load_calendar_project_match_contract()
    assert match["auto_promotion_allowed"] is False
    assert "forbidden_persistence" in match

    summary = load_email_thread_summary_contract()
    assert summary["default_mode"] == "metadata_only"
    assert "raw_body" in summary["forbidden_persistence"]

    candidate = load_meeting_email_relationship_candidate_contract()
    assert candidate["auto_promotion_allowed"] is False
    assert "review_required_classes" in candidate


def test_calendar_source_location_helper_round_trip_and_guard() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "reg.db"
        store = ConstructionStore(str(db))
        store.upsert_calendar_source_location(
            source_id="primary_calendar",
            mailbox_owner_hash="OWNERHASH",
            calendar_role="primary",
            policy_id="default_calendar_readonly",
        )
        store.upsert_calendar_sync_state(source_id="primary_calendar", sync_status="pending")
        conn = sqlite3.connect(str(db))
        row = conn.execute(
            "SELECT source_id, read_only, calendar_role FROM calendar_source_locations"
        ).fetchone()
        assert row == ("primary_calendar", 1, "primary")
        state = conn.execute("SELECT source_id, sync_status FROM calendar_sync_state").fetchone()
        assert state == ("primary_calendar", "pending")
        # read-only guard rejects any writeback-capable source
        with pytest.raises(ValueError):
            store.upsert_calendar_source_location(
                source_id="x", mailbox_owner_hash="H", read_only=False
            )
