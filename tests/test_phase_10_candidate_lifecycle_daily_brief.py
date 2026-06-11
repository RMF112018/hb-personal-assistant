"""Phase 10 V50 — daily-brief lifecycle integration tests.

Asserts: rejected/suppressed/merged duplicates are absent from the normal brief; a snoozed item is
absent before its return date and returns on it; accepted appears in the accepted/open section; a
stale accepted item appears as stale; project-review-required is visible; source-ref-missing rows
are withheld; the rendered markdown passes a no-raw-leak scan.
"""

from __future__ import annotations

from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import candidate_lifecycle as lc
from hb_assistant.construction.second_brain.local_ai.candidate_lifecycle_daily_brief import (
    build_daily_brief_lifecycle_view,
    render_daily_brief_lifecycle_markdown,
)
from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-11T12:00:00Z"
_FORBIDDEN = ("raw_body", "body_html", "body_text", "signed_url", "download_url", "join_url",
              "token", "secret", "bearer", "http://", "https://", "@example", "<html")


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


def test_rejected_suppressed_merged_absent_from_normal_view(tmp_path: Path) -> None:
    s = _store(tmp_path)
    for c in ("rej", "sup", "mga", "mgb"):
        _seed_task(s, c)
    lc.reject(s, subject_type="task_candidate", subject_id="rej", reason="not_actionable", now_utc=NOW)
    lc.suppress(s, scope="candidate", subject_type="task_candidate", subject_id="sup",
                reason="recurring_false_positive", now_utc=NOW)
    lc.merge(s, source_subject_type="task_candidate", source_subject_id="mgb",
             target_subject_type="task_candidate", target_subject_id="mga", reason="same_source",
             now_utc=NOW)
    view = build_daily_brief_lifecycle_view(s, now_utc=NOW)
    shown = {r["subject_id"] for sec in view["sections"].values() for r in sec}
    assert "rej" not in shown and "sup" not in shown and "mgb" not in shown
    assert view["hidden_counts"]["rejected"] == 1
    assert view["hidden_counts"]["suppressed"] == 1
    assert view["hidden_counts"]["merged"] == 1


def test_snooze_absent_then_returns(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "t1")
    lc.snooze(s, subject_type="task_candidate", subject_id="t1", until="2026-06-20T00:00:00Z",
              now_utc=NOW)
    before = build_daily_brief_lifecycle_view(s, now_utc=NOW)
    assert before["hidden_counts"]["snoozed_future"] == 1
    shown_before = {r["subject_id"] for sec in before["sections"].values() for r in sec}
    assert "t1" not in shown_before
    after = build_daily_brief_lifecycle_view(s, now_utc="2026-06-21T00:00:00Z")
    shown_after = {r["subject_id"] for sec in after["sections"].values() for r in sec}
    assert "t1" in shown_after
    assert after["snoozed_returning_count"] == 1


def test_accepted_and_stale_visible_distinctly(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "acc")
    lc.accept(s, subject_type="task_candidate", subject_id="acc", now_utc=NOW)
    lc.promote(s, subject_type="task_candidate", subject_id="acc", now_utc=NOW)
    # stale accepted task: accepted 20+ days before "now" (candidate must exist for the FK)
    _seed_task(s, "old")
    s.insert_accepted_task(candidate_id="old", title_redacted="Old task", waiting_state="waiting_on_me",
                           safety_category="normal", project_key="PRJ", accepted_utc="2026-05-10T00:00:00Z")
    view = build_daily_brief_lifecycle_view(s, now_utc=NOW)
    assert view["section_counts"]["accepted_actions"] >= 1
    assert view["section_counts"]["stale_actions"] >= 1


def test_project_review_and_source_missing_surfaced(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "pr", proj=None)
    _seed_task(s, "sm", refs=False)
    view = build_daily_brief_lifecycle_view(s, now_utc=NOW)
    assert view["section_counts"]["project_review_required"] == 1
    assert view["section_counts"]["source_missing_withheld"] == 1


def test_rendered_markdown_raw_free(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "t1")
    md = render_daily_brief_lifecycle_markdown(build_daily_brief_lifecycle_view(s, now_utc=NOW))
    low = md.lower()
    for f in _FORBIDDEN:
        assert f not in low, f
