"""Phase 08B Prompt 01 — durable delivery-handoff recovery + render-view contract.

Proves (1) the structured delivery handoff is durably persisted on ``--emit-receipt`` and
can be reconstructed faithfully after a fresh connection (process-exit recovery), (2) the
dry-run / no-emit path persists nothing, (3) the deterministic render-view builder is stable,
carries no raw content, and never renders HTML, and (4) the new V27 table's guard columns
stay zero. Covers success, blocked, stale, and dry-run paths.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.daily_brief import (
    build_daily_brief_render_view,
    read_daily_brief_handoff,
    run_daily_brief,
)
from hb_assistant.construction.second_brain.daily_brief.models import HANDOFF_SECTIONS
from hb_assistant.construction.second_brain.reasoning import MockClaudeAdapter
from hb_assistant.construction.store import ConstructionStore

_FORBIDDEN = (
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "secret",
)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "handoff.sqlite")


def _seed(db_path: str, *, stale: bool = False) -> None:
    store = ConstructionStore(db_path)
    store.upsert_cross_source_relationship(
        relationship_id="rel-1",
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
    store.upsert_project_issue_history_item(
        issue_family_id="iss-1",
        project_key="P1",
        status="open",
        source_families_json=json.dumps(["procore"]),
        confidence_class="medium",
        issue_kind="rfi",
        age_days=30,
        review_required=False,
        stale_unknown_flags_json=json.dumps(["stale_status"]) if stale else json.dumps([]),
    )


def _run(db_path: str, vault: Path, *, mode: str = "apply", emit: bool = True):
    return run_daily_brief(
        brief_date="2026-06-02",
        project_key="P1",
        db_path=db_path,
        mode=mode,
        adapter=MockClaudeAdapter(),
        emit_receipt=emit,
        vault_brief_dir=str(vault),
    )


def _section_shape(handoff) -> dict:
    return {
        name: [(ln.title_redacted, ln.review_tier, ln.source_refs) for ln in lines]
        for name, lines in handoff.sections.items()
    }


def test_emit_persists_handoff_lines(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    result = _run(db_path, tmp_path / "v", emit=True)
    conn = sqlite3.connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM daily_brief_handoff_lines").fetchone()[0]
    assert n > 0
    # Every persisted line belongs to the run and uses a canonical section.
    rows = conn.execute("SELECT brief_run_id, section FROM daily_brief_handoff_lines").fetchall()
    assert all(r[0] == result.brief_run_id for r in rows)
    assert all(r[1] in HANDOFF_SECTIONS for r in rows)


def test_dry_run_persists_no_handoff_lines(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    _run(db_path, tmp_path / "v", mode="dry_run", emit=False)
    conn = sqlite3.connect(db_path)
    # The table exists (migration runs) but no row is written without emit_receipt.
    n = conn.execute("SELECT COUNT(*) FROM daily_brief_handoff_lines").fetchone()[0]
    assert n == 0


def test_durable_roundtrip_after_fresh_connection(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    result = _run(db_path, tmp_path / "v", emit=True)
    in_memory = result.delivery_handoff
    # Reconstruct from persisted rows only (new connection inside read_daily_brief_handoff).
    recon = read_daily_brief_handoff(result.brief_run_id, db_path=db_path)
    assert recon is not None
    # The structured sections (lost before this change) round-trip exactly.
    assert _section_shape(recon) == _section_shape(in_memory)
    # Durable source-ref identity is preserved (family + ref).
    assert [(r["source_family"], r["source_ref"]) for r in recon.source_refs] == [
        (r["source_family"], r["source_ref"]) for r in in_memory.source_refs
    ]
    # Reconstruction satisfies the safe-handoff invariants.
    assert recon.local_only is True
    assert recon.external_delivery_performed is False
    assert recon.notification_summary.emitted is False
    assert recon.html_rendering.rendered is False


def test_reconstruct_unknown_run_returns_none(db_path: str) -> None:
    assert read_daily_brief_handoff("does-not-exist", db_path=db_path) is None


def test_render_view_is_deterministic_and_ordered(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    result = _run(db_path, tmp_path / "v", emit=True)
    recon = read_daily_brief_handoff(result.brief_run_id, db_path=db_path)
    v1 = build_daily_brief_render_view(recon)
    v2 = build_daily_brief_render_view(recon)
    assert v1.model_dump_json() == v2.model_dump_json()
    assert [s.name for s in v1.sections] == list(HANDOFF_SECTIONS)
    assert v1.total_line_count == sum(s.line_count for s in v1.sections)
    assert v1.format == "render_view"
    assert v1.rendered is False


def test_render_view_rejects_rendered_true(tmp_path: Path, db_path: str) -> None:
    from hb_assistant.construction.second_brain.daily_brief.models import DailyBriefRenderView

    with pytest.raises(ValueError):
        DailyBriefRenderView(brief_date="2026-06-02", rendered=True)


def test_no_raw_content_in_persisted_lines_and_render_view(tmp_path: Path, db_path: str) -> None:
    _seed(db_path, stale=True)
    result = _run(db_path, tmp_path / "v", emit=True)
    conn = sqlite3.connect(db_path)
    persisted = " ".join(
        str(r[0]) for r in conn.execute("SELECT source_refs_json FROM daily_brief_handoff_lines")
    )
    recon = read_daily_brief_handoff(result.brief_run_id, db_path=db_path)
    view_blob = build_daily_brief_render_view(recon).model_dump_json()
    for forbidden in _FORBIDDEN:
        assert forbidden not in persisted
        assert forbidden not in view_blob


def test_handoff_line_guard_columns_zero(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    _run(db_path, tmp_path / "v", emit=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM daily_brief_handoff_lines").fetchall()
    assert rows
    for row in rows:
        for col, value in dict(row).items():
            if col.endswith("_persisted") or col == "external_writeback_performed":
                assert value == 0, f"guard {col} must be 0"


def test_blocked_run_reconstructs_with_empty_sections(tmp_path: Path, db_path: str) -> None:
    # Empty store -> evaluation fails -> apply blocked, persisted as dry_run with no lines.
    ConstructionStore(db_path)
    result = _run(db_path, tmp_path / "v", emit=True)
    assert result.applied is False
    assert result.apply_blocked_reason == "evaluation_failed"
    recon = read_daily_brief_handoff(result.brief_run_id, db_path=db_path)
    assert recon is not None
    assert all(len(lines) == 0 for lines in recon.sections.values())
    # A render view still builds deterministically for a blocked brief.
    view = build_daily_brief_render_view(recon)
    assert view.total_line_count == 0
    assert view.rendered is False
