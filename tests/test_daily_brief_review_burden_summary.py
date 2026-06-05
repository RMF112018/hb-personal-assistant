"""Daily brief renders review exceptions summary (capped) + batched note, not full itemized queue of thousands."""

from hb_assistant.construction.second_brain.daily_brief.models import (
    DailyBriefContext,
    ReviewLoadStatus,
)
from hb_assistant.construction.second_brain.daily_brief.output import render_brief_markdown


def test_daily_brief_review_output_is_summary_first_and_capped():
    ctx = DailyBriefContext(
        brief_date="2026-06-05",
        project_count=1,
        source_ref_count=10,
        review_required_count=2,
        review_required_cards=[],  # no cards -> no item spam
        what_matters_today=[],  # Prompt 37 field (default empty ok for this summary test)
        review_load=ReviewLoadStatus(total_review_items=1000, tier_3_count=5),
    )
    md = render_brief_markdown(ctx)
    assert "Review exceptions" in md
    assert "Batched/suppressed" in md
    assert "File Review Queue (mandatory review)" not in md  # we replaced the header
    assert "Recommended: run `hb-assistant second-brain review burden" in md
    # Prompt 37: what matters present (empty case shows fallback)
    assert "## What Matters Today" in md
    # No thousands of lines (non-spam preserved)
    assert md.count("\n") < 200
