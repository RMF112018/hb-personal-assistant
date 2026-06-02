"""Phase 08A Daily Brief Context Builder (daily_brief_agent) — Prompt 11.

Assembles a bounded, source-linked daily-brief **context** package: it retrieves once via
the Prompt-04 Retrieval Broker, assesses it with the Prompt-07 Research Packet Agent
(reusing the same envelope), then deterministically groups items into attention/meeting/
project/warning/review-required cards, a review-load summary, and a structured delivery
handoff input. No model call, no HTML, no notifications, no raw content. Insufficient
context degrades or blocks — it never overstates.
"""

from __future__ import annotations

from typing import Any

from ..research import (
    ResearchPacket,
    ResearchPacketAssessment,
    build_research_packet_from_envelope,
)
from ..retrieval import (
    ALLOWLISTED_SOURCE_FAMILIES,
    RetrievalBroker,
    RetrievalEnvelope,
    RetrievalItem,
)
from .models import (
    HANDOFF_SECTIONS,
    AttentionItemCard,
    DailyBriefContext,
    DeliveryHandoffInput,
    HandoffLine,
    MeetingCard,
    ProjectCard,
    ReviewRequiredCard,
    WarningCard,
)
from .policy import reason_code_for_tier
from .store import write_daily_brief_run
from .triage import build_review_load_status

_MEETING_FAMILY = "meeting_prep_brief_sections"
_PROJECT_FAMILIES = frozenset(
    {
        "project_issue_history_items",
        "project_risk_digest_items",
        "aging_exposure_report_items",
    }
)
_ATTENTION_FAMILIES = frozenset(
    {
        "project_issue_history_items",
        "project_risk_digest_items",
        "aging_exposure_report_items",
        "cross_source_relationships",
    }
)


def _ref(it: RetrievalItem) -> dict[str, str]:
    return {
        "source_family": it.source_family,
        "source_ref": it.source_ref,
        "record_type": it.record_type,
        "review_tier": str(it.review_tier),
    }


def _urgency(it: RetrievalItem) -> str:
    if it.review_required or it.conflict_flags:
        return "high"
    if it.review_tier == 2 or it.stale_unknown_flags:
        return "medium"
    return "low"


def _build_cards(
    items: list[RetrievalItem],
) -> tuple[
    list[AttentionItemCard],
    list[MeetingCard],
    list[ProjectCard],
    list[WarningCard],
    list[ReviewRequiredCard],
]:
    attention: list[AttentionItemCard] = []
    meetings: list[MeetingCard] = []
    review_required: list[ReviewRequiredCard] = []
    warnings: list[WarningCard] = []

    for it in items:
        if it.review_required:
            review_required.append(
                ReviewRequiredCard(
                    title_redacted=it.content_excerpt_redacted or it.record_type,
                    project_key=it.project_key,
                    review_tier=3,
                    review_tier_reason_code=reason_code_for_tier(3),
                    source_refs=[_ref(it)],
                )
            )
        elif it.source_family == _MEETING_FAMILY:
            meetings.append(
                MeetingCard(
                    title_redacted=it.content_excerpt_redacted or it.record_type,
                    project_key=it.project_key,
                    review_tier=it.review_tier,
                    review_tier_reason_code=reason_code_for_tier(it.review_tier),
                    source_refs=[_ref(it)],
                )
            )
        elif it.source_family in _ATTENTION_FAMILIES and it.review_tier in (1, 2):
            attention.append(
                AttentionItemCard(
                    title_redacted=it.content_excerpt_redacted or it.record_type,
                    project_key=it.project_key,
                    review_tier=it.review_tier,
                    review_tier_reason_code=reason_code_for_tier(it.review_tier),
                    confidence_class=it.confidence_class,
                    urgency=_urgency(it),
                    source_refs=[_ref(it)],
                )
            )

        for flag in it.conflict_flags:
            warnings.append(
                WarningCard(
                    warning_class="conflict",
                    summary_redacted=f"{it.source_family}:{flag}",
                    project_key=it.project_key,
                    review_tier=max(it.review_tier, 2),
                    source_refs=[_ref(it)],
                )
            )
        for flag in it.stale_unknown_flags:
            warnings.append(
                WarningCard(
                    warning_class="stale_unknown",
                    summary_redacted=f"{it.source_family}:{flag}",
                    project_key=it.project_key,
                    review_tier=max(it.review_tier, 2),
                    source_refs=[_ref(it)],
                )
            )

    # Per-project rollup over project-bearing families (deterministic by project key).
    by_project: dict[str, list[RetrievalItem]] = {}
    for it in items:
        if it.source_family in _PROJECT_FAMILIES and it.project_key:
            by_project.setdefault(it.project_key, []).append(it)
    projects = [
        ProjectCard(
            project_key=key,
            item_count=len(group),
            review_required_count=sum(1 for g in group if g.review_required),
            stale_unknown_count=sum(1 for g in group if g.stale_unknown_flags),
            max_review_tier=max((g.review_tier for g in group), default=3),
            source_refs=[_ref(g) for g in group],
        )
        for key, group in sorted(by_project.items())
    ]
    return attention, meetings, projects, warnings, review_required


def _build_delivery_handoff(
    *,
    attention: list[AttentionItemCard],
    meetings: list[MeetingCard],
    projects: list[ProjectCard],
    warnings: list[WarningCard],
    review_required: list[ReviewRequiredCard],
    source_refs: list[dict[str, str]],
    review_tier: int,
    degradation_mode: str,
) -> DeliveryHandoffInput:
    sections: dict[str, list[HandoffLine]] = {s: [] for s in HANDOFF_SECTIONS}
    sections["priority_actions"] = [
        HandoffLine(title_redacted=c.title_redacted, review_tier=c.review_tier, source_refs=c.source_refs)
        for c in attention
    ]
    sections["waiting_on"] = [
        HandoffLine(title_redacted=c.summary_redacted, review_tier=c.review_tier, source_refs=c.source_refs)
        for c in warnings
    ]
    sections["meeting_prep"] = [
        HandoffLine(title_redacted=c.title_redacted, review_tier=c.review_tier, source_refs=c.source_refs)
        for c in meetings
    ]
    sections["file_review_queue"] = [
        HandoffLine(title_redacted=c.title_redacted, review_tier=c.review_tier, source_refs=c.source_refs)
        for c in review_required
    ]
    sections["project_signals"] = [
        HandoffLine(
            title_redacted=f"project:{c.project_key} items={c.item_count}",
            review_tier=c.max_review_tier,
            source_refs=c.source_refs,
        )
        for c in projects
    ]
    return DeliveryHandoffInput(
        sections=sections,
        source_refs=source_refs,
        review_tier=review_tier,
        degradation_mode=degradation_mode,
        output_format="structured_data",
        notification_emitted=False,
    )


def _assemble_daily_brief(
    *,
    brief_date: str,
    project_key: str | None = None,
    families: tuple[str, ...] | None = None,
    db_path: str | None = None,
    emit_receipt: bool = False,
) -> tuple[
    DailyBriefContext,
    ResearchPacket,
    ResearchPacketAssessment,
    RetrievalEnvelope,
    str | None,
]:
    """Assemble the daily-brief context (no brief-run persist) from broker + packet.

    Returns (context, packet, assessment, envelope, packet_receipt_id). ``emit_receipt``
    only controls the research-packet receipt; the brief-run row is persisted by the
    caller. Deterministic, read-only.
    """
    requested = tuple(families or ALLOWLISTED_SOURCE_FAMILIES)
    envelope = RetrievalBroker(db_path=db_path).retrieve(
        project_key=project_key, families=requested, emit_receipt=False
    )
    packet, assessment, _retrieval_receipt_id, packet_receipt_id = (
        build_research_packet_from_envelope(
            envelope,
            packet_type="daily_brief",
            requested=requested,
            project_key=project_key,
            db_path=db_path,
            emit_receipt=emit_receipt,
        )
    )

    items = envelope.items
    attention, meetings, projects, warnings, review_required = _build_cards(items)
    source_refs = [_ref(it) for it in items]
    review_load = build_review_load_status(
        items, degradation_mode=packet.degradation_mode, warnings=envelope.coverage_warnings
    )
    handoff = _build_delivery_handoff(
        attention=attention,
        meetings=meetings,
        projects=projects,
        warnings=warnings,
        review_required=review_required,
        source_refs=source_refs,
        review_tier=packet.review_tier,
        degradation_mode=packet.degradation_mode,
    )

    project_count = len({it.project_key for it in items if it.project_key})
    context = DailyBriefContext(
        brief_date=brief_date,
        project_count=project_count,
        source_ref_count=packet.source_ref_count,
        review_required_count=packet.review_required_count,
        stale_unknown_count=packet.stale_unknown_count,
        source_coverage=assessment.source_coverage,
        review_tier_counts=dict(assessment.review_tier_distribution),
        context_quality_class=packet.context_quality_class,
        degradation_mode=packet.degradation_mode,
        review_tier=packet.review_tier,
        review_tier_reason_code=packet.review_tier_reason_code,
        research_packet_id=packet_receipt_id,
        attention_cards=attention,
        meeting_cards=meetings,
        project_cards=projects,
        warning_cards=warnings,
        review_required_cards=review_required,
        review_load=review_load,
        delivery_handoff=handoff,
        source_refs=source_refs,
        warnings=sorted(set(assessment.policy_warnings) | set(envelope.coverage_warnings)),
        status=packet.status,
    )
    return context, packet, assessment, envelope, packet_receipt_id


def build_daily_brief_context(
    *,
    brief_date: str,
    project_key: str | None = None,
    families: tuple[str, ...] | None = None,
    db_path: str | None = None,
    mode: str = "dry_run",
    emit_receipt: bool = False,
) -> DailyBriefContext:
    """Build the daily-brief context from the retrieval broker + research packet.

    Deterministic and read-only. When ``emit_receipt`` is True a metadata-only run is
    persisted to the V26 ``daily_brief_runs`` table and ``brief_run_id`` is populated.
    """
    context, _packet, _assessment, _envelope, _packet_receipt_id = _assemble_daily_brief(
        brief_date=brief_date,
        project_key=project_key,
        families=families,
        db_path=db_path,
        emit_receipt=emit_receipt,
    )
    if emit_receipt:
        context.brief_run_id = write_daily_brief_run(context, mode=mode, db_path=db_path)
    return context


def build_daily_brief_context_builder_proof() -> dict[str, Any]:
    """Deterministic proof for ``daily-brief-context-builder-proof.json`` (temp DB)."""
    import json
    import sqlite3
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    with tempfile.TemporaryDirectory() as tmp:
        seeded = f"{tmp}/seeded.sqlite3"
        store = ConstructionStore(seeded)
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
        store.upsert_cross_source_relationship(
            relationship_id="rel-2",
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
        # A project issue-history item: tier-2 (attention) carrying a stale flag (warning)
        # and a project key (project rollup) — exercises the remaining card kinds.
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
        conn = sqlite3.connect(seeded)
        conn.execute(
            "INSERT INTO long_term_memory_items "
            "(memory_id, memory_type, statement_redacted, project_key, confidence_class, "
            " review_status) VALUES ('mem1','fact','kickoff confirmed','P1','high','accepted')"
        )
        conn.commit()
        conn.close()

        context = build_daily_brief_context(
            brief_date="2026-06-02", project_key="P1", db_path=seeded, emit_receipt=True
        )

        empty = f"{tmp}/empty.sqlite3"
        ConstructionStore(empty)
        blocked = build_daily_brief_context(
            brief_date="2026-06-02", project_key="P1", db_path=empty, emit_receipt=False
        )

        c2 = sqlite3.connect(seeded)
        c2.row_factory = sqlite3.Row
        run_row = dict(c2.execute("SELECT * FROM daily_brief_runs").fetchone())
        ref_count = c2.execute("SELECT COUNT(*) FROM daily_brief_source_refs").fetchone()[0]
        c2.close()

    blob = context.model_dump_json()
    no_raw_content = not any(
        t in blob
        for t in (
            "raw_body", "raw_document_text", "raw_calendar_payload", "raw_prompt",
            "raw_response", "signed_url", "download_url", "secret",
        )
    )
    guards_zero = all(
        run_row[c] == 0
        for c in run_row
        if c.endswith("_persisted") or c == "external_writeback_performed"
    )
    has_coverage_and_tiers = (
        isinstance(context.source_coverage, float) and bool(context.review_tier_counts)
    )
    handoff_source_linked = bool(context.delivery_handoff.source_refs) and all(
        bool(line.source_refs)
        for lines in context.delivery_handoff.sections.values()
        for line in lines
    )
    handoff_structured = (
        context.delivery_handoff.output_format == "structured_data"
        and context.delivery_handoff.notification_emitted is False
        and set(context.delivery_handoff.sections) == set(HANDOFF_SECTIONS)
    )
    cards_present = bool(context.review_required_cards) and bool(context.project_cards)
    meeting_degraded = any(
        w.startswith("no_read_model:meeting_prep_brief_sections") for w in context.warnings
    )

    proof_passed = bool(
        context.brief_run_id
        and has_coverage_and_tiers
        and handoff_source_linked
        and handoff_structured
        and cards_present
        and meeting_degraded
        and no_raw_content
        and guards_zero
        and ref_count == context.source_ref_count
        and blocked.status == "blocked"
        and blocked.degradation_mode == "blocked"
    )
    return {
        "proof": "phase_08a_daily_brief_context_builder",
        "proof_passed": proof_passed,
        "seeded_context": {
            "brief_date": context.brief_date,
            "project_count": context.project_count,
            "source_ref_count": context.source_ref_count,
            "review_required_count": context.review_required_count,
            "stale_unknown_count": context.stale_unknown_count,
            "source_coverage": context.source_coverage,
            "review_tier_counts": context.review_tier_counts,
            "context_quality_class": context.context_quality_class,
            "degradation_mode": context.degradation_mode,
            "attention_cards": len(context.attention_cards),
            "meeting_cards": len(context.meeting_cards),
            "project_cards": len(context.project_cards),
            "warning_cards": len(context.warning_cards),
            "review_required_cards": len(context.review_required_cards),
            "status": context.status,
        },
        "review_load": context.review_load.model_dump(),
        "empty_db_context": {
            "status": blocked.status,
            "degradation_mode": blocked.degradation_mode,
            "context_quality_class": blocked.context_quality_class,
            "source_ref_count": blocked.source_ref_count,
        },
        "context_includes_source_coverage_and_review_tier_counts": has_coverage_and_tiers,
        "delivery_handoff_structured": handoff_structured,
        "delivery_handoff_source_linked": handoff_source_linked,
        "brief_run_persisted": bool(context.brief_run_id),
        "source_refs_persisted": ref_count,
        "guard_columns_zero": guards_zero,
        "no_raw_content": no_raw_content,
        "meeting_source_degrades_gracefully": meeting_degraded,
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "no_html_or_notifications": True,
            "source_references_required": True,
            "synthesis_requires_packet": True,
            "insufficient_context_degrades_not_overstates": True,
            "model_direct_external_api_access": False,
        },
    }
