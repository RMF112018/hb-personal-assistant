"""Phase 08A Prompt 11 — Daily Brief Context Builder (daily_brief_agent)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.daily_brief import (
    build_daily_brief_context,
    build_daily_brief_context_builder_proof,
    read_latest_daily_brief_runs,
)
from hb_assistant.construction.store import ConstructionStore


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "brief.sqlite")


def _seed(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_cross_source_relationship(
        relationship_id="rel-ok",
        source_family="email",
        source_record_type="message",
        source_record_ref="m1",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi1",
        relationship_type="references",
        confidence_class="human_promoted",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=False,
    )
    store.upsert_cross_source_relationship(
        relationship_id="rel-review",
        source_family="email",
        source_record_type="message",
        source_record_ref="m2",
        target_family="financial",
        target_record_type="invoice",
        target_record_ref="inv1",
        relationship_type="references",
        confidence_class="model_proposed",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=True,
    )
    store.upsert_project_issue_history_item(
        issue_family_id="iss-1",
        project_key="P1",
        status="open",
        source_families_json=json.dumps(["procore"]),
        confidence_class="medium",
        issue_kind="rfi",
        age_days=30,
        review_required=False,
        stale_unknown_flags_json=json.dumps(["stale_status"]),
    )


def test_context_includes_source_coverage_and_review_tier_counts(db_path: str) -> None:
    _seed(db_path)
    ctx = build_daily_brief_context(
        brief_date="2026-06-02", project_key="P1", db_path=db_path, emit_receipt=False
    )
    assert isinstance(ctx.source_coverage, float)
    assert ctx.review_tier_counts  # validation requirement
    assert set(ctx.review_tier_counts) == {"1", "2", "3"}
    assert ctx.source_ref_count >= 3
    assert ctx.review_required_count >= 1


def test_context_builds_all_card_kinds(db_path: str) -> None:
    _seed(db_path)
    ctx = build_daily_brief_context(
        brief_date="2026-06-02", project_key="P1", db_path=db_path, emit_receipt=False
    )
    assert ctx.review_required_cards  # tier-3 relationship
    assert ctx.attention_cards  # tier-2 issue
    assert ctx.project_cards  # project rollup
    assert ctx.warning_cards  # stale flag
    # Prompt 37: what matters summary + ranked projects (may be empty in minimal seed but shape present)
    assert hasattr(ctx, "what_matters_today")
    assert isinstance(ctx.what_matters_today, list)
    # project_cards may be re-ranked by composite (review_exc + stale + exposure + recency)
    assert isinstance(ctx.project_cards, list)
    # meeting_prep_brief_sections is reader-backed but not project-scoped, so a project-scoped brief
    # surfaces no meeting cards (graceful empty) with an empty-read-model coverage warning (no longer
    # a no_read_model warning).
    assert ctx.meeting_cards == []
    assert not any(w.startswith("no_read_model:meeting_prep_brief_sections") for w in ctx.warnings)
    assert any(
        w.startswith("empty_read_model:meeting_prep_brief_sections") for w in ctx.warnings
    )


def test_delivery_handoff_structured_and_source_linked(db_path: str) -> None:
    _seed(db_path)
    ctx = build_daily_brief_context(
        brief_date="2026-06-02", project_key="P1", db_path=db_path, emit_receipt=False
    )
    handoff = ctx.delivery_handoff
    assert handoff.output_format == "structured_data"
    assert handoff.notification_emitted is False
    assert handoff.source_refs  # source-linked
    # Prompt 37: what_matters_today section present (first) and source linked overall
    assert "what_matters_today" in handoff.sections
    # Every emitted handoff line carries its own source refs (except what_matters_today aggregate summary bullets, which are derived and carry none; their contributing cards do).
    for sec_name, lines in handoff.sections.items():
        for line in lines:
            if sec_name == "what_matters_today":
                continue
            assert line.source_refs


def test_empty_db_blocks_not_overstates(db_path: str) -> None:
    ConstructionStore(db_path)  # migrate only, no seed
    ctx = build_daily_brief_context(
        brief_date="2026-06-02", project_key="P1", db_path=db_path, emit_receipt=False
    )
    assert ctx.status == "blocked"
    assert ctx.degradation_mode == "blocked"
    assert ctx.context_quality_class == "insufficient"
    assert ctx.source_ref_count == 0


def test_emit_persists_run_with_guards_zero(db_path: str) -> None:
    _seed(db_path)
    ctx = build_daily_brief_context(
        brief_date="2026-06-02", project_key="P1", db_path=db_path, emit_receipt=True
    )
    assert ctx.brief_run_id

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM daily_brief_runs").fetchone())
    ref_count = conn.execute("SELECT COUNT(*) FROM daily_brief_source_refs").fetchone()[0]
    conn.close()

    assert row["mode"] == "dry_run"
    assert row["output_path_redacted"] is None
    assert row["output_path_hash"] is None
    guards = [c for c in row if c.endswith("_persisted")] + ["external_writeback_performed"]
    for col in guards:
        assert row[col] == 0, f"guard {col} must be 0"
    assert ref_count == ctx.source_ref_count

    latest = read_latest_daily_brief_runs(db_path=db_path)
    assert latest and latest[0]["brief_run_id"] == ctx.brief_run_id


def test_output_carries_no_raw_content(db_path: str) -> None:
    _seed(db_path)
    ctx = build_daily_brief_context(
        brief_date="2026-06-02", project_key="P1", db_path=db_path, emit_receipt=False
    )
    blob = ctx.model_dump_json()
    for forbidden in (
        "signed_url",
        "download_url",
        "raw_body",
        "raw_prompt",
        "raw_response",
        "secret",
    ):
        assert forbidden not in blob


def test_context_builder_proof_passes() -> None:
    proof = build_daily_brief_context_builder_proof()
    assert proof["proof_passed"] is True
    assert proof["guard_columns_zero"] is True
    assert proof["no_raw_content"] is True
    assert proof["context_includes_source_coverage_and_review_tier_counts"] is True
    assert proof["delivery_handoff_source_linked"] is True
    assert proof["empty_db_context"]["status"] == "blocked"
