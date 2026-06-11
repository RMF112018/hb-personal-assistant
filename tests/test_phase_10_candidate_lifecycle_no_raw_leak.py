"""Phase 10 V50 — no-raw-leak hardening tests.

Adversarially embeds raw-content patterns (URL, signed URL w/ token, bearer token, email, HTML
tag, join URL, Procore blob marker) into candidate redacted fields AND an operator note, then
asserts NONE of those dangerous patterns appear in the review-queue JSON, lifecycle operation
JSON, feedback JSON, rendered daily-brief markdown, or the lifecycle event log. The lifecycle layer
defensively re-scrubs already-redacted DB text at the read-model boundary and scrubs operator notes
before storage, so no raw URL/token/email/HTML can reach a lifecycle output.
"""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import candidate_lifecycle as lc
from hb_assistant.construction.second_brain.local_ai.candidate_lifecycle_daily_brief import (
    build_daily_brief_lifecycle_view,
    render_daily_brief_lifecycle_markdown,
)
from hb_assistant.construction.second_brain.local_ai.candidate_lifecycle_feedback import (
    build_feedback_summary,
)
from hb_assistant.construction.second_brain.local_ai.candidate_lifecycle_read_model import (
    build_review_queue,
)
from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-11T12:00:00Z"

# Adversarial raw content the lifecycle layer must never re-emit.
_RAW = (
    "https://teams.microsoft.com/l/JOIN https://x.invalid/p/SIGNED?token=SECRET "
    "Bearer ABC123 victim@example.invalid <p>HTML</p> PROCORE_BLOB"
)
# Dangerous patterns that must be absent from every lifecycle surface.
_FORBIDDEN = ("https://", "http://", "teams.microsoft.com", "token=", "bearer ", "secret",
              "@example.invalid", "<p>", "</p>", "x.invalid")


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "t.sqlite"))


def _scan(text: str, label: str) -> None:
    low = text.lower()
    for bad in _FORBIDDEN:
        assert bad.lower() not in low, f"raw pattern {bad!r} leaked in {label}"


def test_no_raw_patterns_in_any_lifecycle_surface(tmp_path: Path) -> None:
    s = _store(tmp_path)
    # Candidate whose "redacted" fields adversarially carry raw patterns (simulating an upstream
    # redaction gap the lifecycle layer must still defend against).
    s.upsert_task_candidate(candidate_id="t1", stable_key="PRJ:task:t1", title_redacted=_RAW,
                            project_key="PRJ", assignee_class="user", waiting_state="waiting_on_me",
                            safety_category="normal", confidence=0.9, review_status="pending",
                            reason_redacted=_RAW, recommended_next_action=_RAW)
    s.upsert_candidate_source_ref(source_ref_id="sr1", candidate_type="task", candidate_id="t1",
                                  source_family="email", source_ref_hash="h1", source_table="email")
    # Operator note carrying raw patterns must be scrubbed before storage.
    lc.accept(s, subject_type="task_candidate", subject_id="t1", now_utc=NOW, note=_RAW)
    op = lc.reject(s, subject_type="task_candidate", subject_id="t1", reason="other",
                   now_utc=NOW, note=_RAW)

    _scan(json.dumps(build_review_queue(s, now_utc=NOW, include_hidden=True)), "review_queue")
    _scan(json.dumps(op), "operation_json")
    _scan(json.dumps(build_feedback_summary(s, now_utc=NOW)), "feedback")
    _scan(render_daily_brief_lifecycle_markdown(
        build_daily_brief_lifecycle_view(s, now_utc=NOW)), "daily_brief_markdown")
    _scan(json.dumps(
        s.list_lifecycle_events(subject_type="task_candidate", subject_id="t1")), "lifecycle_events")


def test_scrub_note_strips_dangerous_patterns() -> None:
    out = lc.scrub_note(
        "see https://x.example/a?token=abc and a@b.com Bearer XYZ <script>x</script>"
    )
    low = (out or "").lower()
    assert "https://" not in low
    assert "@b.com" not in low
    assert "bearer xyz" not in low
    assert "<script>" not in low


def test_scrub_note_keeps_safe_text() -> None:
    # A benign operator note survives (scrubbing must not delete legitimate content).
    out = lc.scrub_note("follow up before Friday handoff")
    assert out == "follow up before Friday handoff"
