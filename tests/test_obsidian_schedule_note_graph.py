"""Tests for schedule note graph discovery and deterministic candidates (Phase 20)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.schedule_note_graph import (
    GRAPH_MANAGED_BEGIN,
    GRAPH_MANAGED_END,
    ScheduleGraphNoteFact,
    assert_report_paths_safe,
    build_schedule_graph_candidates,
    build_schedule_wiki_link,
    discover_safe_source_cards,
    discover_schedule_notes,
    graph_block_entries,
    render_graph_link_lines,
    tag_recommendations,
)
from hb_assistant.obsidian_mcp.schedule_review_note_generator import (
    MANAGED_BEGIN,
    MANAGED_END,
    render_note_markdown,
)


def _minimal_payload(**overrides):
    base = {
        "note_type": "schedule_update",
        "project_key": "tropical",
        "project_label": "Tropical Wind",
        "schedule_data_date": "2026-07-01",
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


def _write_note(vault: Path, rel: str, payload: dict) -> None:
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_note_markdown(payload), encoding="utf-8")


def test_discover_schedule_notes_filters_type_and_prefix(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    rel = "Work/HB Personal Assistant/Schedule Review/Projects/tropical/2026-07-01 - Tropical - Schedule Comparison - Prior Update.md"
    _write_note(vault, rel, _minimal_payload())
    _write_note(vault, "other/random.md", _minimal_payload())
    facts = discover_schedule_notes(vault, project_key="tropical")
    assert len(facts) == 1
    assert facts[0].note_type == "schedule_update"
    assert facts[0].project_key == "tropical"


def test_build_candidates_same_project_and_prior_update(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    rel_a = "Work/HB Personal Assistant/Schedule Review/Projects/tropical/a.md"
    rel_b = "Work/HB Personal Assistant/Schedule Review/Projects/tropical/b.md"
    _write_note(
        vault,
        rel_a,
        _minimal_payload(schedule_data_date="2026-07-01", comparison_basis="baseline_a"),
    )
    _write_note(
        vault,
        rel_b,
        _minimal_payload(schedule_data_date="2026-07-08", comparison_basis="baseline_b"),
    )
    facts = discover_schedule_notes(vault, project_key="tropical")
    candidates = build_schedule_graph_candidates(facts)
    rel_types = {c.relationship_type for c in candidates}
    assert "same_project_schedule_note" in rel_types
    assert "prior_schedule_update" in rel_types


def test_source_card_candidates_optional_and_conservative(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    note_rel = "Work/HB Personal Assistant/Schedule Review/Projects/tropical/note.md"
    _write_note(vault, note_rel, _minimal_payload())
    card_rel = "Source Notes/Work/Tropical Schedule__abc123.md"
    card_path = vault / card_rel
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(
        "---\n"
        "note_type: source_card\n"
        "generation_status: generated\n"
        "project_key: tropical\n"
        "document_type: schedule\n"
        "title: Tropical Schedule Baseline\n"
        "---\n\n# Tropical Schedule Baseline\n",
        encoding="utf-8",
    )
    facts = discover_schedule_notes(vault, project_key="tropical")
    cards = discover_safe_source_cards(vault, project_key="tropical")
    assert len(cards) == 1
    candidates = build_schedule_graph_candidates(facts, source_cards=cards)
    sc = [c for c in candidates if c.relationship_type == "schedule_note_to_safe_source_card"]
    assert len(sc) == 1
    assert sc[0].recommended is False


def test_report_path_qa_rejects_absolute_paths() -> None:
    with pytest.raises(ValueError, match="report_path_leak"):
        assert_report_paths_safe({"note": "/Users/bobbyfetting/secret.md"})


def test_build_schedule_wiki_link_rejects_traversal() -> None:
    with pytest.raises(ValueError, match="path_traversal"):
        build_schedule_wiki_link("../escape.md", "Bad")


def test_tag_recommendations_report_only() -> None:
    fact = ScheduleGraphNoteFact(
        note_rel_path="Work/HB Personal Assistant/Schedule Review/Projects/tropical/x.md",
        note_title="Title",
        note_type="schedule_update",
        project_key="tropical",
        project_label="Tropical",
        schedule_data_date="2026-07-01",
        comparison_basis="prior",
        trust_statuses={"analytics": "ready", "identity": "ready", "cpm": "ready", "quality": "ready"},
        review_status={},
        tags=("#schedule-review",),
    )
    rec = tag_recommendations([fact])
    assert "#schedule-review" in rec[fact.note_rel_path]


def test_render_graph_link_lines_use_note_titles(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    rel_a = "Work/HB Personal Assistant/Schedule Review/Projects/tropical/a.md"
    rel_b = "Work/HB Personal Assistant/Schedule Review/Projects/tropical/b.md"
    _write_note(vault, rel_a, _minimal_payload(schedule_data_date="2026-07-01"))
    _write_note(vault, rel_b, _minimal_payload(schedule_data_date="2026-07-08"))
    facts = discover_schedule_notes(vault, project_key="tropical")
    candidates = build_schedule_graph_candidates(facts)
    lines = render_graph_link_lines(candidates, {f.note_rel_path: f for f in facts})
    assert rel_a in lines or rel_b in lines
    joined = "\n".join(sum(lines.values(), []))
    assert "[[Work/HB Personal Assistant/Schedule Review/Projects/tropical/" in joined


def test_graph_block_entries_parser() -> None:
    text = (
        f"{MANAGED_BEGIN}\nbody\n{MANAGED_END}\n\n"
        f"{GRAPH_MANAGED_BEGIN}\n- [[a|A]]\n{GRAPH_MANAGED_END}\n"
    )
    entries = graph_block_entries(text)
    assert entries == ["- [[a|A]]"]
