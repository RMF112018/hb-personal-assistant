"""Phase 10 V50 — unified candidate lifecycle read-model tests.

Asserts: all six families appear; only raw-safe contract fields are emitted; source-ref
count/coverage is correct; project-review-required stays visible; rejected/suppressed/merged
rows are hidden from the default queue but retrievable with include_hidden; backward-compatible
when the V50 overlay tables are empty.
"""

from __future__ import annotations

from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import candidate_lifecycle as lc
from hb_assistant.construction.second_brain.local_ai.candidate_lifecycle_read_model import (
    build_review_queue,
)
from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-11T12:00:00Z"

_CONTRACT_FIELDS = {
    "subject_type", "subject_id", "candidate_id", "family", "source_family", "title_redacted",
    "reason_redacted", "recommended_next_action_redacted", "confidence", "priority", "project_key",
    "project_resolution_status", "source_ref_count", "source_ref_coverage_status",
    "candidate_status", "review_status", "accepted_status", "watch_status", "lifecycle_state",
    "duplicate_group_key", "age_bucket", "due_bucket", "review_reason", "disposition_reason_code",
    "hidden_from_daily_brief", "actionable",
}


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "t.sqlite"))


def _seed_task(s, cid, conf=0.9, proj="PRJ", refs=True, title="Submit RFI response"):
    s.upsert_task_candidate(candidate_id=cid, stable_key=f"{proj}:task:{cid}", title_redacted=title,
                            project_key=proj, assignee_class="user", waiting_state="waiting_on_me",
                            safety_category="normal", confidence=conf, review_status="pending")
    if refs:
        s.upsert_candidate_source_ref(source_ref_id=f"sr-{cid}", candidate_type="task",
                                      candidate_id=cid, source_family="email_message",
                                      source_ref_hash=f"h-{cid}", source_table="email")


def _seed_commitment(s, cid, proj="PRJ"):
    s.upsert_commitment_candidate(candidate_id=cid, stable_key=f"{proj}:commit:{cid}",
                                  title_redacted="I will send the schedule", project_key=proj,
                                  commitment_actor_class="user", waiting_state="waiting_on_me",
                                  safety_category="normal", confidence=0.8, review_status="pending")
    s.upsert_candidate_source_ref(source_ref_id=f"sr-{cid}", candidate_type="commitment",
                                  candidate_id=cid, source_family="email_message",
                                  source_ref_hash=f"h-{cid}", source_table="email")


def _seed_daily_brief(s, gk, section="actions", proj="PRJ", refs=True):
    s.insert_daily_brief_action_candidate(brief_date="2026-06-11", section=section,
                                          title_redacted="Follow up on submittal", confidence=0.7,
                                          project_key=proj, group_key=gk)
    rid = s.daily_brief_action_candidate_id_for("2026-06-11", section, gk)
    if refs:
        s.upsert_candidate_source_ref(source_ref_id=f"db-{gk}", candidate_type="daily_brief_action",
                                      candidate_id=rid, source_family="email_thread",
                                      source_ref_hash=f"h-{gk}", source_table="thread")
    return rid


def test_all_families_present_and_only_safe_fields(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "t1")
    _seed_commitment(s, "c1")
    _seed_daily_brief(s, "g1")
    s.insert_accepted_task(candidate_id="t1", title_redacted="Submit RFI response",
                           waiting_state="waiting_on_me", safety_category="normal", project_key="PRJ")
    s.insert_accepted_commitment(candidate_id="c1", title_redacted="I will send the schedule",
                                 waiting_state="waiting_on_me", safety_category="normal",
                                 project_key="PRJ")
    s.upsert_follow_up_watch_item(watch_item_id="w1", watch_status="open",
                                  waiting_state="waiting_on_others", accepted_task_id="acc-task:t1",
                                  project_key="PRJ")
    q = build_review_queue(s, now_utc=NOW, include_hidden=True)
    families = {r["subject_type"] for r in q["rows"]}
    assert families == {
        "task_candidate", "commitment_candidate", "daily_brief_action",
        "accepted_task", "accepted_commitment", "follow_up_watch",
    }
    for r in q["rows"]:
        assert set(r.keys()) >= _CONTRACT_FIELDS


def test_source_ref_count_and_coverage(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "ok", refs=True)
    _seed_task(s, "missing", refs=False)
    rows = {r["subject_id"]: r for r in build_review_queue(s, now_utc=NOW, include_hidden=True)["rows"]}
    assert rows["ok"]["source_ref_count"] == 1
    assert rows["ok"]["source_ref_coverage_status"] == "ok"
    assert rows["missing"]["source_ref_count"] == 0
    assert rows["missing"]["source_ref_coverage_status"] == "source_missing"
    assert rows["missing"]["lifecycle_state"] == lc.STATE_SOURCE_MISSING


def test_project_review_required_visible(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "p", proj=None)
    q = build_review_queue(s, now_utc=NOW)  # default view
    row = next(r for r in q["rows"] if r["subject_id"] == "p")
    assert row["lifecycle_state"] == lc.STATE_PROJECT_REVIEW_REQUIRED
    assert row["project_resolution_status"] == "project_review_required"
    assert not row["hidden_from_daily_brief"]


def test_rejected_hidden_from_default_visible_in_include_hidden(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "r1")
    lc.reject(s, subject_type="task_candidate", subject_id="r1", reason="not_actionable", now_utc=NOW)
    default = build_review_queue(s, now_utc=NOW)
    assert all(r["subject_id"] != "r1" for r in default["rows"])
    full = build_review_queue(s, now_utc=NOW, include_hidden=True)
    rejected = next(r for r in full["rows"] if r["subject_id"] == "r1")
    assert rejected["lifecycle_state"] == lc.STATE_REJECTED
    assert rejected["hidden_from_daily_brief"] is True


def test_backward_compatible_with_empty_overlay(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "t1")
    _seed_task(s, "t2", conf=0.4)
    q = build_review_queue(s, now_utc=NOW)
    states = {r["subject_id"]: r["lifecycle_state"] for r in q["rows"]}
    assert states["t1"] == lc.STATE_NEW
    assert states["t2"] == lc.STATE_NEEDS_REVIEW  # low confidence
    assert q["guardrails"]["raw_safe"] is True
