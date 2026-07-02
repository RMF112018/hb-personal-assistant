"""Tests for hb-schedule-graph writer apply, idempotency, and manual preservation (Phase 20)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.schedule_note_graph import GRAPH_MANAGED_BEGIN, GRAPH_MANAGED_END
from hb_assistant.obsidian_mcp.schedule_note_graph_writer import (
    apply_schedule_graph_links,
    extract_manual_tail,
    upsert_schedule_graph_block,
)
from hb_assistant.obsidian_mcp.schedule_obsidian_note_writer import apply_schedule_note_write
from hb_assistant.obsidian_mcp.schedule_review_note_generator import MANAGED_END, render_note_markdown


def _payload(**overrides):
    base = {
        "note_type": "schedule_update",
        "project_key": "tropical",
        "project_label": "Tropical Wind",
        "schedule_data_date": "2026-07-03",
        "comparison_basis": "prior_update",
        "comparison_label": "Prior Update",
        "analytics_trust_status": "ready",
        "identity_trust_status": "ready",
        "cpm_trust_status": "ready",
        "quality_trust_status": "ready",
        "as_of": "2026-07-03",
        "safe_links": {},
        "recommended_actions": [],
        "capability_limitations": ["Advisory only."],
        "review_status": {"headline": "Review pending"},
        "quality_controls": {"headline": "Controls available"},
    }
    base.update(overrides)
    return base


def test_upsert_inserts_after_schedule_note_managed_block() -> None:
    note = render_note_markdown(_payload())
    link_lines = [
        "- [[Work/HB Personal Assistant/Schedule Review/Projects/tropical/other|Other]] "
        "— same_project_schedule_note · deterministic · confidence 0.90"
    ]
    updated = upsert_schedule_graph_block(note, link_lines)
    assert note.index(MANAGED_END) < updated.index(GRAPH_MANAGED_BEGIN)
    assert GRAPH_MANAGED_END in updated
    assert "same_project_schedule_note" in updated


def test_apply_idempotent_and_preserves_manual_tail(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    rel = "Work/HB Personal Assistant/Schedule Review/Projects/tropical/note.md"
    apply_schedule_note_write(
        vault_root=vault,
        relative_path=rel,
        payload=_payload(),
        dry_run=False,
    )
    path = vault / rel
    manual = "\n\n## Operator Notes\n\n- Keep this manual note.\n"
    path.write_text(path.read_text(encoding="utf-8") + manual, encoding="utf-8")
    lines = {
        rel: [
            "- [[Work/HB Personal Assistant/Schedule Review/Projects/tropical/other|Other]] "
            "— same_project_schedule_note · deterministic · confidence 0.90"
        ]
    }
    first = apply_schedule_graph_links(vault_root=vault, lines_by_source=lines, dry_run=False)
    assert first[0].action == "updated"
    after_first = path.read_text(encoding="utf-8")
    second = apply_schedule_graph_links(vault_root=vault, lines_by_source=lines, dry_run=False)
    assert second[0].action == "unchanged"
    after_second = path.read_text(encoding="utf-8")
    assert after_first == after_second
    assert "Keep this manual note." in after_second
    assert extract_manual_tail(after_second).strip().endswith("Keep this manual note.")


def test_dry_run_zero_write_attempts(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    rel = "Work/HB Personal Assistant/Schedule Review/Projects/tropical/note.md"
    apply_schedule_note_write(vault_root=vault, relative_path=rel, payload=_payload(), dry_run=False)
    lines = {rel: ["- [[x|X]] — same_project_schedule_note · deterministic · confidence 0.90"]}
    results = apply_schedule_graph_links(vault_root=vault, lines_by_source=lines, dry_run=True)
    assert results[0].action == "planned_insert"
    text = (vault / rel).read_text(encoding="utf-8")
    assert GRAPH_MANAGED_BEGIN not in text


def test_phase19_rerun_preserves_graph_block(tmp_path: Path) -> None:
    """Regression: Phase 19 note writer must not clobber hb-schedule-graph block."""
    vault = tmp_path / "vault"
    rel = "Work/HB Personal Assistant/Schedule Review/Projects/tropical/note.md"
    apply_schedule_note_write(vault_root=vault, relative_path=rel, payload=_payload(), dry_run=False)
    graph_lines = [
        "- [[Work/HB Personal Assistant/Schedule Review/Projects/tropical/other|Other]] "
        "— prior_schedule_update · deterministic · confidence 0.88"
    ]
    apply_schedule_graph_links(
        vault_root=vault,
        lines_by_source={rel: graph_lines},
        dry_run=False,
    )
    path = vault / rel
    before_graph = path.read_text(encoding="utf-8")
    assert GRAPH_MANAGED_BEGIN in before_graph
    graph_section = before_graph.split(GRAPH_MANAGED_BEGIN, 1)[1].split(GRAPH_MANAGED_END, 1)[0]

    updated_payload = _payload(review_status={"headline": "Updated review headline"})
    apply_schedule_note_write(
        vault_root=vault,
        relative_path=rel,
        payload=updated_payload,
        dry_run=False,
    )
    after = path.read_text(encoding="utf-8")
    assert GRAPH_MANAGED_BEGIN in after
    assert GRAPH_MANAGED_END in after
    assert graph_section in after
    assert "Updated review headline" in after
