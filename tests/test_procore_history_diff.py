"""Unit tests for the Phase 04B canonical-diff engine + change classification."""

from __future__ import annotations

from hb_assistant.store.procore_history import (
    ChangeEvent,
    compute_canonical_hash,
    diff_canonical_records,
)


def _by_path(events: list[ChangeEvent]) -> dict[str, ChangeEvent]:
    return {e.field_path: e for e in events}


def test_canonical_hash_is_order_independent() -> None:
    a = compute_canonical_hash({"b": 2, "a": 1})
    b = compute_canonical_hash({"a": 1, "b": 2})
    assert a == b
    assert a != compute_canonical_hash({"a": 1, "b": 3})


def test_scalar_changes_classify_to_required_categories() -> None:
    prev = {
        "status": "open",
        "due_date": "2026-01-01",
        "assignee_id": 42,
        "ball_in_court_id": 7,
        "cost_impact": "none",
        "schedule_impact_days": 0,
        "priority": "low",
    }
    cur = {
        "status": "closed",
        "due_date": "2026-02-01",
        "assignee_id": 43,
        "ball_in_court_id": 8,
        "cost_impact": "yes",
        "schedule_impact_days": 5,
        "priority": "high",
    }
    cats = {p: e.change_category for p, e in _by_path(diff_canonical_records(prev, cur)).items()}
    assert cats["status"] == "closed"
    assert cats["due_date"] == "due_date_changed"
    assert cats["assignee_id"] == "assignee_changed"
    assert cats["ball_in_court_id"] == "ball_in_court_changed"
    assert cats["cost_impact"] == "cost_impact_changed"
    assert cats["schedule_impact_days"] == "schedule_impact_changed"
    assert cats["priority"] == "priority_changed"


def test_status_reopened_detected() -> None:
    cats = {
        e.field_path: e.change_category
        for e in diff_canonical_records({"status": "closed"}, {"status": "open"})
    }
    assert cats["status"] == "reopened"


def test_became_overdue_detected() -> None:
    cats = {
        e.field_path: e.change_category
        for e in diff_canonical_records({"overdue": False}, {"overdue": True})
    }
    assert cats["overdue"] == "became_overdue"


def test_nested_dict_change_uses_dotted_path() -> None:
    prev = {"entities": {"location": {"id": 1, "name": "A"}}}
    cur = {"entities": {"location": {"id": 1, "name": "B"}}}
    paths = {e.field_path for e in diff_canonical_records(prev, cur)}
    assert "entities.location.name" in paths


def test_arrays_with_stable_ids_diffed_by_id() -> None:
    prev = {"entities": {"attachments": {"count": 0, "items": []}}}
    cur = {
        "entities": {
            "attachments": {
                "count": 1,
                "items": [{"id": 7, "filename_summary": {"hash_prefix": "f"}}],
            }
        }
    }
    events = _by_path(diff_canonical_records(prev, cur))
    # count bump -> attachment_added; new keyed list element -> added at items[id=7]
    assert events["entities.attachments.count"].change_category == "attachment_added"
    assert "entities.attachments.items[id=7]" in events
    assert events["entities.attachments.items[id=7]"].change_type == "added"


def test_response_added_via_count() -> None:
    cats = {
        e.field_path: e.change_category
        for e in diff_canonical_records({"responses_count": 1}, {"responses_count": 3})
    }
    assert cats["responses_count"] == "response_added"


def test_summary_and_long_values_are_hash_only() -> None:
    prev = {
        "comment_summary": {"type": "string", "length": 5, "hash_prefix": "aaa"},
        "blob": "x" * 200,
    }
    cur = {
        "comment_summary": {"type": "string", "length": 9, "hash_prefix": "bbb"},
        "blob": "y" * 200,
    }
    events = _by_path(diff_canonical_records(prev, cur))
    cs = events["comment_summary"]
    assert cs.change_category == "text_changed"
    # The hash-only block carries no raw value, only a hash.
    assert cs.old_value_redacted is None and cs.new_value_redacted is None
    assert cs.old_value_hash and cs.new_value_hash
    blob = events["blob"]
    assert blob.old_value_redacted is None and blob.new_value_redacted is None
    assert blob.old_value_hash and blob.new_value_hash


def test_short_scalar_values_are_kept_verbatim() -> None:
    ev = _by_path(diff_canonical_records({"status": "open"}, {"status": "closed"}))["status"]
    assert ev.old_value_redacted == "open"
    assert ev.new_value_redacted == "closed"


def test_inspection_item_categories() -> None:
    prev = {"responded_with": "yes", "is_unanswered": False, "is_deficient": False}
    cur = {"responded_with": "no", "is_unanswered": True, "is_deficient": True}
    cats = {e.field_path: e.change_category for e in diff_canonical_records(prev, cur)}
    assert cats["responded_with"] == "inspection_item_response_changed"
    assert cats["is_unanswered"] == "inspection_item_became_unanswered"
    assert cats["is_deficient"] == "inspection_item_became_deficient"


def test_significant_flags_drive_timeline_selection() -> None:
    events = diff_canonical_records(
        {"status": "open", "priority": "low"}, {"status": "closed", "priority": "high"}
    )
    sig = {e.change_category: e.significant for e in events}
    assert sig["closed"] is True
    assert sig["priority_changed"] is False
