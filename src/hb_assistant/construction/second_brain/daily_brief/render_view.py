"""Phase 08B Prompt 01 — deterministic daily-brief render-view builder.

A pure, deterministic builder that turns a (persisted or in-memory) delivery handoff into a
render-ready :class:`DailyBriefRenderView` — the stable contract the future HTML renderer will
consume. It performs no DB access, no model call, and no IO; it never emits HTML (``rendered``
stays False) and carries no raw source content (only the handoff's already-redacted titles +
safe source-ref pairs). Sections are emitted in canonical ``HANDOFF_SECTIONS`` order so the
output is byte-stable across runs.

Prompt 37: what_matters_today is first (from HANDOFF) for exec summary + ranked priorities.
"""

from __future__ import annotations

from .models import (
    HANDOFF_SECTIONS,
    DailyBriefRenderView,
    DeliveryHandoffPayload,
    RenderViewLine,
    RenderViewSection,
)


def build_daily_brief_render_view(
    handoff: DeliveryHandoffPayload,
    *,
    context_quality_class: str = "insufficient",
    generated_utc: str = "",
) -> DailyBriefRenderView:
    """Build a deterministic, no-raw, ``rendered=False`` render view from a delivery handoff.

    Sections follow ``HANDOFF_SECTIONS`` ordering and lines preserve their handoff order.
    ``context_quality_class`` and ``generated_utc`` are passed through (they are not carried on
    the handoff); both default to deterministic, side-effect-free values so the builder is pure.
    """
    sections: list[RenderViewSection] = []
    section_counts: dict[str, int] = {}
    total = 0
    for name in HANDOFF_SECTIONS:
        lines = [
            RenderViewLine(
                title_redacted=line.title_redacted,
                review_tier=line.review_tier,
                source_refs=list(line.source_refs),
            )
            for line in handoff.sections.get(name, [])
        ]
        count = len(lines)
        section_counts[name] = count
        total += count
        sections.append(RenderViewSection(name=name, lines=lines, line_count=count))

    stale_unknown_count = sum(
        1
        for ref in handoff.source_refs
        if str(ref.get("stale_unknown", "")).lower() in ("true", "1")
    )

    return DailyBriefRenderView(
        brief_date=handoff.brief_date,
        brief_run_id=handoff.brief_run_id,
        title_redacted=handoff.notification_summary.title_redacted,
        generated_utc=generated_utc,
        degradation_mode=handoff.degradation_mode,
        context_quality_class=context_quality_class,
        review_tier=handoff.review_tier,
        sections=sections,
        section_counts=section_counts,
        total_line_count=total,
        review_required_count=handoff.notification_summary.review_required_count,
        stale_unknown_count=stale_unknown_count,
        source_ref_count=len(handoff.source_refs),
    )
