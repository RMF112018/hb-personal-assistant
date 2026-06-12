"""Phase 10 (251) — user-facing daily-brief render / assembly tests.

Proves the render path consumes the V51 assembly overlay and emits polished, raw-safe, operator-
facing Markdown: Top Priorities first, Procore aggregated, calendar safe-labelled, email/follow-up
always represented, and zero internal artifacts. Pure presentation helpers are unit-tested directly;
the render integration test drives the real ranking/assembly pipeline over a seeded temp DB.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.local_ai import (
    run_candidate_ranking_and_assembly,
)
from hb_assistant.construction.second_brain.local_ai import (
    daily_brief_presentation as P,
)
from hb_assistant.construction.second_brain.local_ai.daily_brief_candidate_writer import (
    persist_candidate_with_refs,
)
from hb_assistant.construction.second_brain.local_ai.daily_brief_render import render_daily_brief
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

BRIEF_DATE = "2026-06-12"
NOW = "2026-06-12T12:00:00+00:00"

# Tokens that must never appear in user-facing Markdown.
FORBIDDEN = (
    "id:dbac",
    "dbac-",
    "rel-",
    "__needs_review__",
    "__internal_",
    "[redacted:",
    "next:review",
    "candidate_id",
    "section_key",
)


# --------------------------------------------------------------------------------------------
# Pure presentation helpers
# --------------------------------------------------------------------------------------------


def test_safe_calendar_label_maps_sentinels() -> None:
    assert P.safe_calendar_label("__internal_time_off__") == "Internal calendar block"
    assert P.safe_calendar_label("__needs_review__") == "Calendar item needing project review"
    assert P.safe_calendar_label("Tropical") == "Project meeting — Tropical"
    assert P.safe_calendar_label(None) == "Calendar item — project TBD"
    assert P.safe_calendar_label("") == "Calendar item — project TBD"


def test_project_label_drops_sentinels() -> None:
    assert P.project_label("Tropical") == "Tropical"
    assert P.project_label("__needs_review__") is None
    assert P.project_label(None) is None


def test_parse_and_cta_for_procore_signal() -> None:
    why, st = P.parse_procore_signal("Financially material: invoice_payment_due")
    assert why == "Financially material"
    assert st == "invoice_payment_due"
    assert P.cta_for_signal("invoice_payment_due").startswith("Review payment status")
    assert P.cta_for_signal("rfi_cost_impact_flagged").startswith("Confirm pricing exposure")
    # Unknown signal still gets a concrete CTA, never a blank or next:review.
    assert P.cta_for_signal("unknown_signal")
    assert "next:review" not in P.cta_for_signal("unknown_signal")


def test_aggregate_procore_collapses_duplicates_and_caps() -> None:
    items = (
        [{"project_key": "Tropical", "title_redacted": "x: invoice_payment_due"}] * 22
        + [{"project_key": "Tropical", "title_redacted": "x: invoice_approved_not_paid"}] * 10
        + [{"project_key": "Alton", "title_redacted": "x: rfi_cost_impact_flagged"}] * 2
    )
    lines = P.aggregate_procore_lines(items)
    # 34 Tropical rows + 2 Alton rows collapse to exactly 2 project lines.
    assert len(lines) == 2
    assert lines[0].startswith("- Tropical —")
    assert "22 payment-due invoice signals" in lines[0]
    assert "10 approved-not-paid invoice signals" in lines[0]
    assert lines[1].startswith("- Alton —")
    for ln in lines:
        for tok in FORBIDDEN:
            assert tok not in ln


def test_email_followup_gap_card_uses_count() -> None:
    card = P.email_followup_gap_card(281)
    assert len(card) == 1
    assert "281 email thread summaries" in card[0]
    assert "follow-up watch" in card[0]
    empty = P.email_followup_gap_card(0)
    assert "No email follow-up candidates" in empty[0]


def test_calendar_metadata_normalizes_location() -> None:
    meta = P.calendar_metadata("7 attendees · 2 domains · online")
    assert meta == "7 attendees / 2 domains / online"
    meta2 = P.calendar_metadata("3 attendees · 1 domains · in_person_or_unspecified")
    assert "in person / TBD" in meta2


def test_assert_clean_display_rejects_artifacts() -> None:
    for bad in (
        "- id:dbac-0011",
        "- project:__needs_review__",
        "- next:review",
        "- visit https://example.com",
        "- mail a@b.com",
        "- [redacted:deadbeef]",
    ):
        with pytest.raises(ValueError):
            P.assert_clean_display(bad)
    # A clean line passes.
    P.assert_clean_display("- Tropical — payment-due invoice signal. Review payment status.")


def test_render_data_gap_lines_polished() -> None:
    lines = P.render_data_gap_lines("source_missing_withheld=3;model_layer=withheld")
    blob = "\n".join(lines)
    assert "3 item(s) withheld" in blob
    assert "deterministic ranking is authoritative" in blob
    assert "model_layer" not in blob  # the raw key=value is never echoed verbatim


# --------------------------------------------------------------------------------------------
# Render integration over the real ranking/assembly pipeline
# --------------------------------------------------------------------------------------------


def _seed_store(db: str, *, with_email_task: bool, with_email_summary: bool = False) -> ConstructionStore:
    """Seed procore + calendar (+ optional email task / summary) candidates and run the overlay."""
    SQLiteMigrator(db_path=db).apply()
    store = ConstructionStore(db_path=db)

    # Procore: many per-signal candidates, one dominant project + signal type (tests aggregation).
    for i in range(22):
        persist_candidate_with_refs(
            store,
            brief_date=BRIEF_DATE,
            section="procore",
            title_redacted="Financially material: invoice_payment_due",
            confidence=0.8,
            group_key=f"sig-pd-{i}",
            source_refs=[{"source_family": "procore_action_signals", "source_ref": f"sig-pd-{i}"}],
            project_key="Tropical",
            priority=10,
            reason_redacted="Financially material",
            recommended_next_action="review",
        )
    for i in range(10):
        persist_candidate_with_refs(
            store,
            brief_date=BRIEF_DATE,
            section="procore",
            title_redacted="Financially material: invoice_approved_not_paid",
            confidence=0.7,
            group_key=f"sig-anp-{i}",
            source_refs=[{"source_family": "procore_action_signals", "source_ref": f"sig-anp-{i}"}],
            project_key="Tropical",
            priority=20,
            reason_redacted="Financially material",
            recommended_next_action="review",
        )

    # Calendar: a __needs_review__ sentinel candidate with a redacted-hash title.
    persist_candidate_with_refs(
        store,
        brief_date=BRIEF_DATE,
        section="calendar",
        title_redacted="[redacted:149058e0c7f9d3ff]",
        confidence=0.5,
        group_key="cal-1",
        source_refs=[{"source_family": "calendar_event_raw_content", "source_ref": "cal-1"}],
        project_key="__needs_review__",
        priority=30,
        reason_redacted="7 attendees · 2 domains · online",
        recommended_next_action="review",
    )

    if with_email_task:
        store.upsert_task_candidate(
            candidate_id="t1",
            stable_key="PRJ:t1",
            title_redacted="Reply to owner on schedule question",
            project_key="Tropical",
            confidence=0.9,
            review_status="pending",
        )
        store.upsert_candidate_source_ref(
            source_ref_id="sr-t1",
            candidate_type="task",
            candidate_id="t1",
            source_family="email",
            source_ref_hash="h-t1",
        )

    if with_email_summary:
        store.upsert_email_thread_summary(
            thread_key="th-1",
            project_key="Tropical",
            message_count=4,
            summary_redacted="metadata only",
        )

    run_candidate_ranking_and_assembly(
        store=store,
        brief_date=BRIEF_DATE,
        now_utc=NOW,
        use_model=False,
        include_similarity=True,
        dry_run=False,
        max_persist=1000,
    )
    return store


def test_render_consumes_overlay_and_is_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "brief.db")
        store = _seed_store(db, with_email_task=True)
        payload = render_daily_brief(store=store, brief_date=BRIEF_DATE)

        assert payload["used_assembly_overlay"] is True
        md = payload["markdown"]

        # Overlay-driven ordering: Top Priorities heading appears, before review/data-gap sections.
        assert "## Top Priorities" in md
        if "## Needs Review / Decisions" in md:
            assert md.index("## Top Priorities") < md.index("## Needs Review / Decisions")

        # No internal artifacts anywhere in the user-facing Markdown.
        for tok in FORBIDDEN:
            assert tok not in md, f"forbidden token {tok!r} leaked into brief"

        # Procore aggregated, not dumped: the bulk of 32 per-signal candidates collapse to a small
        # number of project-level lines carrying signal-type counts (exact counts depend on which
        # rows the ranking pulled into Top Priorities; deterministic counts are unit-tested above).
        assert "## Procore Financial / Project Signals" in md
        assert "invoice signals" in md
        procore_block = md.split("## Procore Financial / Project Signals", 1)[1]
        assert procore_block.count("\n- ") <= 4, "procore section must aggregate, not dump"

        # Calendar safe label replaced the hash/sentinel.
        assert "Calendar item needing project review" in md or "## Calendar Prep" in md

        # A concrete CTA replaced the blanket next:review.
        assert "Review payment status and confirm next payment action." in md


def test_render_email_followup_gap_card_when_empty() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "brief.db")
        store = _seed_store(db, with_email_task=False, with_email_summary=True)
        payload = render_daily_brief(store=store, brief_date=BRIEF_DATE)
        md = payload["markdown"]
        assert "## Email / Follow-up" in md
        assert "Email follow-up unavailable" in md
        assert "email thread summar" in md  # summary/summaries — count-agnostic
        for tok in FORBIDDEN:
            assert tok not in md


def test_render_empty_date_is_clean_no_candidates() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "brief.db")
        SQLiteMigrator(db_path=db).apply()
        store = ConstructionStore(db_path=db)
        payload = render_daily_brief(store=store, brief_date=BRIEF_DATE)
        md = payload["markdown"]
        assert "No review candidates for this date" in md
        for tok in FORBIDDEN:
            assert tok not in md
