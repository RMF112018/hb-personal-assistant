"""Phase 10 V50 — duplicate group key, merge, and suppression tests.

Asserts: duplicate group key is deterministic across replay and raw-free; a merged source becomes
``merged`` (hidden from default, visible with include_hidden) with refs preserved; replaying a
merge is a no-op; group-level suppression hides future same-group items but keeps them retrievable.
"""

from __future__ import annotations

from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import candidate_lifecycle as lc
from hb_assistant.construction.second_brain.local_ai.candidate_lifecycle_duplicates import (
    duplicate_group_key,
)
from hb_assistant.construction.second_brain.local_ai.candidate_lifecycle_read_model import (
    build_review_queue,
)
from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-11T12:00:00Z"


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "t.sqlite"))


def _seed_task(s, cid, ref_hash, proj="PRJ"):
    s.upsert_task_candidate(candidate_id=cid, stable_key=f"{proj}:task:{cid}",
                            title_redacted="Submit RFI", project_key=proj, assignee_class="user",
                            waiting_state="waiting_on_me", safety_category="normal",
                            confidence=0.9, review_status="pending")
    s.upsert_candidate_source_ref(source_ref_id=f"sr-{cid}", candidate_type="task",
                                  candidate_id=cid, source_family="email", source_ref_hash=ref_hash,
                                  source_table="email")


def test_group_key_deterministic_and_raw_free() -> None:
    refs = [{"source_family": "email", "source_ref_hash": "abc"}]
    k1 = duplicate_group_key(subject_type="task_candidate", subject_id="t1", source_refs=refs)
    k2 = duplicate_group_key(subject_type="task_candidate", subject_id="t1", source_refs=refs)
    assert k1 == k2 == "src:email:abc"
    # title-based fallback hashes the already-redacted title, never emits raw text
    k3 = duplicate_group_key(subject_type="task_candidate", subject_id="t2", family="task",
                             project_key="PRJ", title_redacted="Confidential subject line",
                             due_bucket="today")
    assert "Confidential" not in k3
    assert k3.startswith("ttl:task:PRJ:")


def test_same_source_candidates_share_group(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "a", "SAME")
    _seed_task(s, "b", "SAME")
    rows = {r["subject_id"]: r for r in build_review_queue(s, now_utc=NOW)["rows"]}
    assert rows["a"]["duplicate_group_key"] == rows["b"]["duplicate_group_key"]


def test_merge_hides_source_preserves_refs_idempotent(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "a", "HA")
    _seed_task(s, "b", "HB")
    r1 = lc.merge(s, source_subject_type="task_candidate", source_subject_id="b",
                  target_subject_type="task_candidate", target_subject_id="a",
                  reason="same_title_project_due", now_utc=NOW)
    assert r1["status"] == "merged"
    # replay = no-op (idempotent link + event)
    r2 = lc.merge(s, source_subject_type="task_candidate", source_subject_id="b",
                  target_subject_type="task_candidate", target_subject_id="a",
                  reason="same_title_project_due", now_utc=NOW)
    assert r2["status"] == "already_merged"
    assert len(s.list_merge_links()) == 1
    # source hidden from default, visible + merged with include_hidden
    assert all(rr["subject_id"] != "b" for rr in build_review_queue(s, now_utc=NOW)["rows"])
    full = build_review_queue(s, now_utc=NOW, include_hidden=True)["rows"]
    assert next(rr for rr in full if rr["subject_id"] == "b")["lifecycle_state"] == lc.STATE_MERGED
    # source refs preserved (still queryable)
    assert s.list_candidate_source_refs(candidate_type="task", candidate_id="b")


def test_group_suppression_hides_future_members(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "a", "GRP")
    gk = next(r["duplicate_group_key"] for r in build_review_queue(s, now_utc=NOW)["rows"]
              if r["subject_id"] == "a")
    lc.suppress(s, scope="group", reason="recurring_false_positive",
                duplicate_group_key_value=gk, now_utc=NOW)
    # a new same-group candidate arrives later
    _seed_task(s, "b", "GRP")
    default_ids = {r["subject_id"] for r in build_review_queue(s, now_utc=NOW)["rows"]}
    assert "a" not in default_ids and "b" not in default_ids
    # still retrievable as suppressed via include_hidden
    full = {r["subject_id"]: r["lifecycle_state"] for r in
            build_review_queue(s, now_utc=NOW, include_hidden=True)["rows"]}
    assert full["a"] == lc.STATE_SUPPRESSED
    assert full["b"] == lc.STATE_SUPPRESSED


def test_suppression_reversible(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "a", "REV")
    gk = next(r["duplicate_group_key"] for r in build_review_queue(s, now_utc=NOW)["rows"])
    lc.suppress(s, scope="group", reason="recurring_false_positive",
                duplicate_group_key_value=gk, now_utc=NOW)
    # flip the rule off (reversible, auditable; same idempotency key)
    s.upsert_suppression_rule(idempotency_key=f"suppress:group:{gk}:recurring_false_positive",
                              scope="group", reason_code="recurring_false_positive",
                              duplicate_group_key=gk, active=False)
    ids = {r["subject_id"] for r in build_review_queue(s, now_utc=NOW)["rows"]}
    assert "a" in ids
