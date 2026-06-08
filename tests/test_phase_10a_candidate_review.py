"""Phase 10A — candidate review service layer.

Covers list/show/summary/accept/ignore/reject/snooze/edit/export over persisted
V41/V43 candidate rows: status transitions, V43 lifecycle columns, the corrected
candidate_review_events audit insert, ignore->suppressed normalization, edit diff
+ source-ref immutability, enum validation, and no-raw output guarantees.
No Ollama, no network — local DB only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.local_ai.candidate_review import (
    accept_candidate,
    edit_candidate,
    export_review_queue,
    ignore_candidate,
    list_review_candidates,
    reject_candidate,
    review_summary,
    show_review_candidate,
    snooze_candidate,
)
from hb_assistant.construction.store import ConstructionStore

_FORBIDDEN_KEYS = {
    "raw_body",
    "body",
    "body_text",
    "prompt",
    "response",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "token",
    "secret",
}


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "review.db"))


def _seed_task(store: ConstructionStore, pk: str, cid: str = "task-001") -> str:
    store.upsert_task_candidate(
        candidate_id=cid,
        stable_key=f"{pk}:task:{cid}",
        title_redacted="Submit foundation inspection report",
        project_key=pk,
        assignee_class="unknown",
        urgency="high",
        waiting_state="unknown",
        safety_category="normal",
        confidence=0.9,
        reason_redacted="Explicit ask in thread.",
        recommended_next_action="review",
        review_status="pending",
    )
    store.upsert_candidate_source_ref(
        source_ref_id=f"sr-{cid}",
        candidate_type="task",
        candidate_id=cid,
        source_family="email_message_raw_content",
        source_ref_hash="hash-abc",
        source_table="email_message_raw_content",
        source_primary_key_hash="hash-abc",
        evidence_redacted="Submit foundation inspection report",
    )
    return cid


def _seed_commitment(store: ConstructionStore, pk: str, cid: str = "comm-001") -> str:
    store.upsert_commitment_candidate(
        candidate_id=cid,
        stable_key=f"{pk}:commitment:{cid}",
        title_redacted="Vendor will deliver shop drawings",
        project_key=pk,
        commitment_actor_class="other",
        urgency="normal",
        waiting_state="waiting_on_others",
        safety_category="normal",
        confidence=0.8,
        reason_redacted="Promise in thread.",
        recommended_next_action="review",
        review_status="pending",
    )
    return cid


def _audit_rows(store: ConstructionStore, candidate_id: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(store._db_path))
    conn.row_factory = sqlite3.Row
    try:
        return list(
            conn.execute(
                "SELECT * FROM candidate_review_events WHERE candidate_id = ? ORDER BY created_utc",
                (candidate_id,),
            )
        )
    finally:
        conn.close()


def _assert_no_forbidden_keys(obj: object) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in _FORBIDDEN_KEYS, f"forbidden key {k!r} present"
            _assert_no_forbidden_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            _assert_no_forbidden_keys(item)


# ---------------------------------------------------------------------------
# Read-only
# ---------------------------------------------------------------------------
def test_summary_counts(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    _seed_task(s, pk)
    _seed_commitment(s, pk)
    rep = review_summary(s, project_key=pk)
    assert rep["ok"] is True
    assert rep["task"]["pending"] == 1
    assert rep["task"]["total"] == 1
    assert rep["commitment"]["pending"] == 1
    assert rep["combined"]["pending"] == 2
    assert rep["combined"]["total"] == 2


def test_list_and_status_filter_and_enum_reject(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    _seed_commitment(s, pk)
    out = list_review_candidates(s, project_key=pk)
    assert out["count"] == 2
    assert {c["candidate_type"] for c in out["candidates"]} == {"task", "commitment"}

    accept_candidate(s, candidate_id=tid, candidate_type="task")
    accepted = list_review_candidates(s, status="accepted", project_key=pk)
    assert accepted["count"] == 1
    assert accepted["candidates"][0]["candidate_id"] == tid

    with pytest.raises(ValueError):
        list_review_candidates(s, status="ignored")  # not a valid stored status


def test_show_found_and_not_found_with_source_refs(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    shown = show_review_candidate(s, candidate_id=tid)
    assert shown["ok"] is True
    assert shown["candidate_type"] == "task"
    assert shown["candidate"]["candidate_id"] == tid
    assert len(shown["source_refs"]) == 1
    assert shown["source_refs"][0]["source_ref_hash"] == "hash-abc"

    missing = show_review_candidate(s, candidate_id="nope")
    assert missing["ok"] is False
    assert missing["error"] == "candidate_not_found"


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------
def test_accept_sets_lifecycle_columns_and_audit(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    res = accept_candidate(
        s, candidate_id=tid, candidate_type="task", reviewer="bobby", note="looks right"
    )
    assert res["ok"] is True
    assert res["prior_review_status"] == "pending"
    assert res["new_review_status"] == "accepted"
    assert res["review_event_id"]

    row = [r for r in s.list_task_candidates(project_key=pk) if r["candidate_id"] == tid][0]
    assert row["review_status"] == "accepted"
    assert row["reviewed_by"] == "bobby"
    assert row["reviewed_utc"]
    assert row["review_note_redacted"] == "looks right"

    audits = _audit_rows(s, tid)
    assert len(audits) == 1
    assert audits[0]["action"] == "accept"
    assert audits[0]["prior_status"] == "pending"
    assert audits[0]["new_status"] == "accepted"
    assert audits[0]["reviewer_ref"] == "bobby"
    assert audits[0]["user_note_redacted"] == "looks right"


def test_reject_and_missing_candidate(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    res = reject_candidate(s, candidate_id=tid, candidate_type="task", note="bad extraction")
    assert res["new_review_status"] == "rejected"

    missing = reject_candidate(s, candidate_id="ghost", candidate_type="task")
    assert missing["ok"] is False
    assert missing["error"] == "candidate_not_found"


def test_ignore_normalizes_to_suppressed(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    res = ignore_candidate(s, candidate_id=tid, candidate_type="task")
    assert res["action"] == "ignore"
    assert res["new_review_status"] == "suppressed"
    row = [r for r in s.list_task_candidates(project_key=pk) if r["candidate_id"] == tid][0]
    assert row["review_status"] == "suppressed"
    assert _audit_rows(s, tid)[0]["action"] == "ignore"


def test_snooze_persists_until_and_rejects_bad_timestamp(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    cid = _seed_commitment(s, pk)
    until = "2026-06-12T09:00:00-04:00"
    res = snooze_candidate(s, candidate_id=cid, candidate_type="commitment", until=until)
    assert res["new_review_status"] == "snoozed"
    assert res["snoozed_until_utc"] == until
    row = [r for r in s.list_commitment_candidates(project_key=pk) if r["candidate_id"] == cid][0]
    assert row["review_status"] == "snoozed"
    assert row["snoozed_until_utc"] == until
    assert _audit_rows(s, cid)[0]["snoozed_until_utc"] == until

    with pytest.raises(ValueError):
        snooze_candidate(s, candidate_id=cid, candidate_type="commitment", until="not-a-date")


def test_edit_updates_fields_records_diff_preserves_refs_and_status(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    res = edit_candidate(
        s,
        candidate_id=tid,
        candidate_type="task",
        title="Submit revised inspection report",
        assignee="user",
        waiting_state="waiting_on_me",
    )
    assert res["ok"] is True
    assert res["review_status"] == "pending"  # edit does not change review decision
    assert res["changes"]["assignee_class"] == {"from": "unknown", "to": "user"}

    row = [r for r in s.list_task_candidates(project_key=pk) if r["candidate_id"] == tid][0]
    assert row["title_redacted"] == "Submit revised inspection report"
    assert row["assignee_class"] == "user"
    assert row["waiting_state"] == "waiting_on_me"
    assert row["review_status"] == "pending"

    # source refs untouched
    refs = s.list_candidate_source_refs(candidate_id=tid)
    assert len(refs) == 1 and refs[0]["source_ref_hash"] == "hash-abc"

    audit = _audit_rows(s, tid)[0]
    assert audit["action"] == "edit"
    assert audit["changes_json_redacted"] and "assignee_class" in audit["changes_json_redacted"]


def test_edit_validates_enums_and_no_edits(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    with pytest.raises(ValueError):
        edit_candidate(s, candidate_id=tid, candidate_type="task", assignee="nobody")
    with pytest.raises(ValueError):
        edit_candidate(s, candidate_id=tid, candidate_type="task", waiting_state="someday")
    none = edit_candidate(s, candidate_id=tid, candidate_type="task")
    assert none["ok"] is False and none["error"] == "no_edits"


def test_edit_commitment_maps_actor_class(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    cid = _seed_commitment(s, pk)
    res = edit_candidate(s, candidate_id=cid, candidate_type="commitment", assignee="user")
    assert res["changes"]["commitment_actor_class"] == {"from": "other", "to": "user"}
    row = [r for r in s.list_commitment_candidates(project_key=pk) if r["candidate_id"] == cid][0]
    assert row["commitment_actor_class"] == "user"


# ---------------------------------------------------------------------------
# Export + no-raw guarantee
# ---------------------------------------------------------------------------
def test_export_returns_safe_items_with_refs(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    _seed_task(s, pk)
    _seed_commitment(s, pk)
    out = export_review_queue(s, project_key=pk)
    assert out["count"] == 2
    assert all("source_refs" in it for it in out["items"])
    with pytest.raises(ValueError):
        export_review_queue(s, status="bogus")


def test_no_forbidden_keys_in_any_output(tmp_path: Path) -> None:
    s = _store(tmp_path)
    pk = "PRJ-1"
    tid = _seed_task(s, pk)
    _seed_commitment(s, pk)
    _assert_no_forbidden_keys(review_summary(s, project_key=pk))
    _assert_no_forbidden_keys(list_review_candidates(s, project_key=pk))
    _assert_no_forbidden_keys(show_review_candidate(s, candidate_id=tid))
    _assert_no_forbidden_keys(accept_candidate(s, candidate_id=tid, candidate_type="task"))
    _assert_no_forbidden_keys(export_review_queue(s, project_key=pk))
