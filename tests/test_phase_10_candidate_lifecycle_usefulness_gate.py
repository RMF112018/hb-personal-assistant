"""Phase 10 V50 — usefulness-gate lifecycle contradiction tests.

Asserts the lifecycle stage context detects each lifecycle contradiction, the usefulness gate fails
a would-be success when a lifecycle contradiction is present, and the gate is backward-compatible
when no lifecycle_context is provided.
"""

from __future__ import annotations

from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.candidate_lifecycle_daily_brief import (
    lifecycle_stage_context,
)
from hb_assistant.construction.second_brain.local_ai.usefulness_gate import evaluate_usefulness_gate
from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-11T12:00:00Z"


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "t.sqlite"))


def _seed_task(s, cid, ref_hash="h", refs=True):
    s.upsert_task_candidate(candidate_id=cid, stable_key=f"PRJ:task:{cid}", title_redacted="Submit RFI",
                            project_key="PRJ", assignee_class="user", waiting_state="waiting_on_me",
                            safety_category="normal", confidence=0.9, review_status="pending")
    if refs:
        s.upsert_candidate_source_ref(source_ref_id=f"sr-{cid}", candidate_type="task",
                                      candidate_id=cid, source_family="email",
                                      source_ref_hash=ref_hash, source_table="email")


def test_duplicate_inflation_detected(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "a", ref_hash="SAME")
    _seed_task(s, "b", ref_hash="SAME")
    ctx = lifecycle_stage_context(s, now_utc=NOW)
    assert "duplicate_inflation" in ctx["contradictions"]


def test_source_coverage_below_100_detected(tmp_path: Path) -> None:
    s = _store(tmp_path)
    _seed_task(s, "missing", refs=False)  # source_missing actionable row
    ctx = lifecycle_stage_context(s, now_utc=NOW)
    assert "lifecycle_source_ref_coverage_below_100" in ctx["contradictions"]


def test_gate_fails_on_lifecycle_contradiction(tmp_path: Path) -> None:
    s = _store(tmp_path)
    # one useful deterministic section so the non-lifecycle checks pass
    s.insert_daily_brief_action_candidate(brief_date="2026-06-11", section="actions",
                                          title_redacted="Do thing", confidence=0.8,
                                          project_key="PRJ", group_key="g1")
    rid = s.daily_brief_action_candidate_id_for("2026-06-11", "actions", "g1")
    s.upsert_candidate_source_ref(source_ref_id="db1", candidate_type="daily_brief_action",
                                  candidate_id=rid, source_family="email", source_ref_hash="h1",
                                  source_table="t")
    _seed_task(s, "a", ref_hash="SAME")
    _seed_task(s, "b", ref_hash="SAME")  # duplicate inflation
    lifecycle_ctx = lifecycle_stage_context(s, now_utc=NOW)
    res = evaluate_usefulness_gate(store=s, brief_date="2026-06-11", synthesis_present=True,
                                   synthesis_degraded=False, lifecycle_context=lifecycle_ctx)
    assert not res.passed
    assert "duplicate_inflation" in res.failed_reasons


def test_gate_backward_compatible_without_lifecycle_context(tmp_path: Path) -> None:
    s = _store(tmp_path)
    s.insert_daily_brief_action_candidate(brief_date="2026-06-11", section="actions",
                                          title_redacted="Do thing", confidence=0.8,
                                          project_key="PRJ", group_key="g1")
    rid = s.daily_brief_action_candidate_id_for("2026-06-11", "actions", "g1")
    s.upsert_candidate_source_ref(source_ref_id="db1", candidate_type="daily_brief_action",
                                  candidate_id=rid, source_family="email", source_ref_hash="h1",
                                  source_table="t")
    _seed_task(s, "a", ref_hash="SAME")
    _seed_task(s, "b", ref_hash="SAME")
    # No lifecycle_context → lifecycle checks skipped entirely (legacy behavior).
    res = evaluate_usefulness_gate(store=s, brief_date="2026-06-11", synthesis_present=True,
                                   synthesis_degraded=False)
    assert "duplicate_inflation" not in res.failed_reasons
    assert "lifecycle_contradictions" not in res.metrics


def test_accepted_missing_source_contradiction(tmp_path: Path) -> None:
    s = _store(tmp_path)
    # accepted_task whose candidate has NO source refs (candidate seeded for the FK, refs omitted)
    _seed_task(s, "x", refs=False)
    s.insert_accepted_task(candidate_id="x", title_redacted="X", waiting_state="waiting_on_me",
                           safety_category="normal", project_key="PRJ")
    ctx = lifecycle_stage_context(s, now_utc=NOW)
    assert "accepted_actions_missing_source_refs" in ctx["contradictions"]
