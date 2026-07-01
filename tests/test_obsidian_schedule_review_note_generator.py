"""Tests for schedule_review_note_generator."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.schedule_review_note_generator import (
    assert_note_safe,
    note_filename,
    note_relative_path,
    render_note_markdown,
)


def _sample_payload() -> dict:
    return {
        "note_type": "schedule_update",
        "project_key": "tropical",
        "project_label": "Tropical Wind",
        "schedule_data_date": "2026-07-01",
        "comparison_basis": "prior_update",
        "comparison_label": "Prior update",
        "analytics_trust_status": "degraded",
        "identity_trust_status": "trusted",
        "cpm_trust_status": "degraded",
        "quality_trust_status": "unavailable",
        "review_status": {"pm_summary": "Schedule review items are queued for operator review."},
        "quality_controls": {"headline": "Quality controls unavailable for this snapshot."},
        "recommended_actions": ["Review preview cues and persisted items."],
        "safe_links": {"schedule_hub": "/projects/tropical/schedule"},
        "capability_limitations": ["Sequence cues are advisory."],
        "body_markdown": "## Headline\nSample body",
        "as_of": "2026-07-03",
        "generation_mode": "deterministic",
    }


def test_render_note_markdown_is_deterministic() -> None:
    payload = _sample_payload()
    first = render_note_markdown(payload)
    second = render_note_markdown(payload)
    assert first == second


def test_render_note_markdown_has_required_sections() -> None:
    md = render_note_markdown(_sample_payload())
    for section in (
        "## Summary",
        "## Trust Posture",
        "## Comparison Basis",
        "## Schedule Quality Controls",
        "## Review Status",
        "## Recommended Follow-Up",
        "## Links",
        "## Capability Limitations",
        "<!-- hb-schedule-note:begin managed -->",
    ):
        assert section in md


def test_note_paths_are_stable() -> None:
    payload = _sample_payload()
    assert note_relative_path(payload).startswith("Work/HB Personal Assistant/Schedule Review/Projects/")
    assert note_filename(payload).endswith(".md")


def test_assert_note_safe_rejects_forbidden_language() -> None:
    payload = _sample_payload()
    md = render_note_markdown(payload) + "\nThe subcontractor is liable for this delay.\n"
    try:
        assert_note_safe(md)
        raised = False
    except ValueError:
        raised = True
    assert raised
