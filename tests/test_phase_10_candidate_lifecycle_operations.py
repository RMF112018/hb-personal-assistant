"""Phase 10 V50 — candidate disposition operation tests.

Asserts accept/reject/snooze/close/reopen/suppress are idempotent; snooze hides before the
return date and returns on/after it; rejected/suppressed are hidden from the default queue but
visible with include_hidden; a source-missing actionable candidate cannot be accepted; operation
JSON is raw-free.
"""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import candidate_lifecycle as lc
from hb_assistant.construction.second_brain.local_ai.candidate_lifecycle_read_model import (
    build_review_queue,
)
from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-11T12:00:00Z"

_FORBIDDEN = ("raw_body", "body_html", "body_text", "signed_url", "download_url", "join_url",
              "token", "secret", "bearer", "authorization", "http://", "https://", "@example")


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "t.sqlite"))


def _seed_task(s, cid, conf=0.9, proj="PRJ", refs=True):
    s.upsert_task_candidate(candidate_id=cid, stable_key=f"{proj}:task:{cid}",
                            title_redacted="Submit RFI", project_key=proj, assignee_class="user",
                            waiting_state="waiting_on_me", safety_category="normal",
                            confidence=conf, review_status="pending")
    if refs:
        s.upsert_candidate_source_ref(source_ref_id=f"sr-{cid}", candidate_type="task",
                                      candidate_id=cid, source_family="email",
                                      source_ref_hash=f"h-{cid}", source_table="email")


def _state(s, sid, now=NOW):
    rows = build_review_queue(s, now_utc=now, include_hidden=True)["rows"]
    return next((r["lifecycle_state"] for r in rows if r["subject_id"] == sid), None)


def test_accept_idempotent(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "t1")
    r1 = lc.accept(s, subject_type="task_candidate", subject_id="t1", now_utc=NOW)
    r2 = lc.accept(s, subject_type="task_candidate", subject_id="t1", now_utc=NOW)
    assert r1["status"] == "accepted"
    assert r2["status"] == "already_accepted"
    assert len(s.list_lifecycle_events(subject_type="task_candidate", subject_id="t1")) == 1


def test_reject_idempotent_and_hidden(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "t1")
    lc.reject(s, subject_type="task_candidate", subject_id="t1", reason="not_actionable", now_utc=NOW)
    again = lc.reject(s, subject_type="task_candidate", subject_id="t1", reason="not_actionable",
                      now_utc=NOW)
    assert again["status"] == "already_rejected"
    assert all(r["subject_id"] != "t1" for r in build_review_queue(s, now_utc=NOW)["rows"])


def test_snooze_hides_then_returns(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "t1")
    lc.snooze(s, subject_type="task_candidate", subject_id="t1", until="2026-06-20T00:00:00Z",
              now_utc=NOW)
    # before return date: hidden from default
    assert all(r["subject_id"] != "t1" for r in build_review_queue(s, now_utc=NOW)["rows"])
    assert _state(s, "t1", NOW) == lc.STATE_SNOOZED
    # on/after return date: visible again (returned snooze -> needs_review)
    after = "2026-06-21T00:00:00Z"
    vis = build_review_queue(s, now_utc=after)["rows"]
    assert any(r["subject_id"] == "t1" for r in vis)
    assert _state(s, "t1", after) == lc.STATE_NEEDS_REVIEW


def test_close_reopen_idempotent(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "t1")
    assert lc.close(s, subject_type="task_candidate", subject_id="t1", now_utc=NOW)["status"] == "closed"
    assert lc.close(s, subject_type="task_candidate", subject_id="t1", now_utc=NOW)["status"] == "already_closed"
    assert _state(s, "t1") == lc.STATE_CLOSED
    assert lc.reopen(s, subject_type="task_candidate", subject_id="t1", now_utc=NOW)["status"] == "reopened"
    assert _state(s, "t1") == lc.STATE_NEEDS_REVIEW
    assert lc.reopen(s, subject_type="task_candidate", subject_id="t1", now_utc=NOW)["status"] == "already_open"


def test_accept_blocked_when_source_missing(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "t1", refs=False)
    r = lc.accept(s, subject_type="task_candidate", subject_id="t1", now_utc=NOW)
    assert r["status"] == "accept_blocked_source_missing"
    # review_status unchanged (still pending) — no silent acceptance
    assert s.get_task_candidate("t1")["review_status"] == "pending"
    assert _state(s, "t1") == lc.STATE_SOURCE_MISSING


def test_promote_blocked_when_source_missing(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "t1", refs=False)
    r = lc.promote(s, subject_type="task_candidate", subject_id="t1", now_utc=NOW)
    assert r["promotion_status"] == "promotion_blocked_source_missing"
    assert s.list_accepted_tasks() == []


def test_suppress_does_not_delete_and_hides(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "t1")
    r = lc.suppress(s, scope="candidate", subject_type="task_candidate", subject_id="t1",
                    reason="recurring_false_positive", now_utc=NOW)
    assert r["status"] == "suppressed"
    # candidate row still exists (not deleted)
    assert s.get_task_candidate("t1") is not None
    assert all(rr["subject_id"] != "t1" for rr in build_review_queue(s, now_utc=NOW)["rows"])
    assert _state(s, "t1") == lc.STATE_SUPPRESSED


def test_operation_json_is_raw_free(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "t1")
    blob = json.dumps([
        lc.accept(s, subject_type="task_candidate", subject_id="t1", now_utc=NOW,
                  note="see https://evil.example/x?token=abc and bob@example.com"),
        lc.reject(s, subject_type="task_candidate", subject_id="t1", reason="other", now_utc=NOW,
                  note="Bearer SECRET123"),
    ]).lower()
    for f in _FORBIDDEN:
        assert f not in blob, f


def test_unknown_subject_type_invalid(tmp_path: Path) -> None:
    s = _store(tmp_path)
    try:
        lc.accept(s, subject_type="bogus", subject_id="x", now_utc=NOW)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
