"""Phase 10A — deterministic email↔calendar relationship scoring."""

from __future__ import annotations

from hb_assistant.construction.second_brain.local_ai import score_email_calendar_relationship
from hb_assistant.construction.second_brain.local_ai.contracts import load_phase_10_contract
from hb_assistant.construction.second_brain.local_ai.relationship_scoring import (
    MODERATE_THRESHOLD,
    STRONG_THRESHOLD,
)


def _thread(*, project="HILL", subject="Hilltop RFI 42 coordination meeting",
            body="Lets meet about RFI 42 at the coordination meeting.",
            sender="pm@sub.com", to=("bob@hbcd.com",), when="2026-06-07T12:00:00+00:00") -> dict:
    return {
        "thread_ref": "t1", "project_key": project, "thread_subject": subject,
        "messages": [{"id": "m1", "subject": subject, "from_address": sender,
                      "to_recipients": list(to), "body_text": body, "sent_at_utc": when}],
    }


def _event(*, project="HILL", subject="Hilltop RFI 42 coordination meeting", body="Discuss RFI 42",
           organizer="pm@sub.com", attendees=("bob@hbcd.com",),
           start="2026-06-08T09:00:00+00:00") -> dict:
    return {
        "event_index_id": "e1", "project_key": project, "subject": subject, "body_text": body,
        "organizer_email": organizer, "attendees": [{"email": a} for a in attendees],
        "start_datetime_utc": start,
    }


def test_strong_relationship_when_title_ref_participant_time_align() -> None:
    rel = score_email_calendar_relationship(_thread(), _event())
    assert rel["confidence"] >= STRONG_THRESHOLD
    assert rel["relationship_class"] == "strong"
    assert rel["may_combine"] is True
    assert "participant_overlap" in rel["reason_codes"]
    assert "shared_record_reference" in rel["reason_codes"]
    assert "time_proximity" in rel["reason_codes"]


def test_same_project_only_is_weak() -> None:
    rel = score_email_calendar_relationship(
        _thread(subject="Lunch", body="sandwiches", sender="x@a.com", to=("y@b.com",),
                when="2026-01-01T00:00:00+00:00"),
        _event(subject="Budget", body="numbers", organizer="z@c.com", attendees=("w@d.com",)),
    )
    assert rel["confidence"] < MODERATE_THRESHOLD
    assert rel["relationship_class"] == "weak"
    assert rel["may_combine"] is False
    assert rel["reason_codes"] == ["same_project"]


def test_generic_title_is_penalized() -> None:
    thread = _thread(subject="Hilltop RFI coordination", body="meeting about RFI 42")
    specific = score_email_calendar_relationship(
        thread, _event(subject="Hilltop RFI coordination")
    )
    generic = score_email_calendar_relationship(
        thread, _event(subject="Meeting")  # generic title → penalized + loses subject overlap
    )
    assert "generic_title_penalty" in generic["score_components"]
    assert generic["confidence"] < specific["confidence"]


def test_moderate_relationship_marks_review_required() -> None:
    # Build a link that lands in [0.55, 0.80): same project + participant + time + generic-title penalty.
    rel = score_email_calendar_relationship(
        _thread(subject="Coordination", body="meeting today"),
        _event(subject="Meeting"),
    )
    assert MODERATE_THRESHOLD <= rel["confidence"] < STRONG_THRESHOLD
    assert rel["relationship_class"] == "moderate"
    assert rel["review_required"] is True


def test_participant_overlap_alone_is_weak_no_anchor() -> None:
    # Same internal participants, but different projects, no time proximity, no subject/record overlap.
    rel = score_email_calendar_relationship(
        _thread(project="A", subject="Lunch", body="sandwiches", sender="bob@hbcd.com",
                to=("pm@hbcd.com",), when="2026-01-01T00:00:00+00:00"),
        _event(project="B", subject="Budget", body="numbers", organizer="bob@hbcd.com",
               attendees=("pm@hbcd.com",), start="2026-06-08T09:00:00+00:00"),
    )
    assert rel["anchor_present"] is False
    assert rel["confidence"] < MODERATE_THRESHOLD
    assert rel["relationship_class"] == "weak"
    assert rel["may_combine"] is False


def test_generic_shared_term_without_identifier_is_weak() -> None:
    # "proposal" shared but no specific identifier, different projects, no participant/time/subject anchor.
    rel = score_email_calendar_relationship(
        _thread(project="A", subject="Proposal notes", body="the proposal looks fine",
                sender="x@a.com", to=("y@a.com",), when="2026-01-01T00:00:00+00:00"),
        _event(project="B", subject="Proposal items", body="proposal", organizer="z@c.com",
               attendees=("w@d.com",), start="2026-06-08T09:00:00+00:00"),
    )
    assert "shared_record_reference" not in rel["score_components"]
    assert rel["relationship_class"] == "weak"


def test_specific_record_identifier_is_anchor() -> None:
    rel = score_email_calendar_relationship(
        _thread(project="A", subject="notes", body="please review RFI 42 markups",
                sender="x@a.com", to=("y@a.com",), when="2026-01-01T00:00:00+00:00"),
        _event(project="B", subject="site walk", body="RFI 42 discussion", organizer="z@c.com",
               attendees=("w@d.com",), start="2026-06-08T09:00:00+00:00"),
    )
    assert "shared_record_reference" in rel["reason_codes"]
    assert rel["anchor_present"] is True


def test_contract_module_parity() -> None:
    contract = load_phase_10_contract("relationship_candidate_contract")
    assert contract["confidence_thresholds"]["strong"] == STRONG_THRESHOLD
    assert contract["confidence_thresholds"]["moderate"] == MODERATE_THRESHOLD
    # Every reason code the scorer can emit is declared in the contract.
    rel = score_email_calendar_relationship(_thread(), _event())
    declared = set(contract["email_calendar_reason_codes"])
    assert set(rel["reason_codes"]) <= declared
    assert set(rel["score_components"]) <= set(contract["email_calendar_score_components"])
