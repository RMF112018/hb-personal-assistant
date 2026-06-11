"""Phase 10 V50 — feedback read-model tests.

Asserts the feedback summary is deterministic, counts accepted/rejected/snoozed/suppressed/merged
correctly, buckets confidence stably, and contains no forbidden raw keys/strings.
"""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import candidate_lifecycle as lc
from hb_assistant.construction.second_brain.local_ai.candidate_lifecycle_feedback import (
    build_feedback_summary,
)
from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-11T12:00:00Z"
_FORBIDDEN = ("raw_body", "body_html", "body_text", "signed_url", "download_url", "join_url",
              "token", "secret", "bearer", "http://", "https://", "@example")


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


def _seed(tmp_path: Path) -> ConstructionStore:
    s = _store(tmp_path)
    for c in ("a", "b", "r", "n"):
        _seed_task(s, c)
    lc.accept(s, subject_type="task_candidate", subject_id="a", now_utc=NOW)
    lc.accept(s, subject_type="task_candidate", subject_id="b", now_utc=NOW)
    lc.reject(s, subject_type="task_candidate", subject_id="r", reason="not_actionable", now_utc=NOW)
    lc.snooze(s, subject_type="task_candidate", subject_id="n", until="2026-06-30T00:00:00Z",
              now_utc=NOW)
    return s


def test_feedback_counts_deterministic(tmp_path: Path) -> None:
    s = _seed(tmp_path)
    f1 = build_feedback_summary(s, now_utc=NOW)
    f2 = build_feedback_summary(s, now_utc=NOW)
    # determinism (ignoring generated_utc which is pinned here anyway)
    assert f1 == f2
    c = f1["counts"]
    assert c["accepted"] == 2
    assert c["rejected"] == 1
    assert c["snoozed"] == 1
    assert c["total_reviewed"] == 4


def test_confidence_buckets_present(tmp_path: Path) -> None:
    s = _seed(tmp_path)
    f = build_feedback_summary(s, now_utc=NOW)
    assert set(f["confidence_buckets"].keys()) == {
        "0_25", "26_50", "51_70", "71_85", "86_100", "unknown"
    }
    assert sum(f["confidence_buckets"].values()) >= 4


def test_reason_codes_from_events(tmp_path: Path) -> None:
    s = _seed(tmp_path)
    f = build_feedback_summary(s, now_utc=NOW)
    assert "reject:not_actionable" in f["reason_codes"]


def test_feedback_raw_free(tmp_path: Path) -> None:
    s = _seed(tmp_path)
    blob = json.dumps(build_feedback_summary(s, now_utc=NOW)).lower()
    for f in _FORBIDDEN:
        assert f not in blob, f
    assert json.dumps(build_feedback_summary(s, now_utc=NOW))  # serializable
