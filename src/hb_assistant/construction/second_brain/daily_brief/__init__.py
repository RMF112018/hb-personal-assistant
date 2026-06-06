"""Phase 08A Daily Brief Context Builder (daily_brief_agent) + Review Triage Agent — Prompt 11.

The context builder turns broker-retrieved, packet-assessed context into bounded,
source-linked cards (attention/meeting/project/warning/review-required), a review-load
summary, and a structured delivery handoff input — never HTML, never a notification. The
review triage agent summarizes review load grouped by tier, source, project, and urgency.
Deterministic, local-first, read-only, metadata-only persistence (reuses V26
``daily_brief_runs``); insufficient context degrades or blocks (never overstates).
"""

from __future__ import annotations

from .context import build_daily_brief_context, build_daily_brief_context_builder_proof
from .generate import (
    build_daily_brief_agent_proof,
    build_daily_brief_delivery_handoff_proof,
    run_daily_brief,
)
from .mcp_handoff_status import build_daily_brief_mcp_handoff_status, handoff_present
from .models import (
    AttentionItemCard,
    DailyBriefContext,
    DailyBriefRenderView,
    DailyBriefResult,
    DeliveryHandoffInput,
    DeliveryHandoffPayload,
    HandoffLine,
    HtmlRenderingData,
    LaunchdSchedulePreview,
    MeetingCard,
    NotificationSummary,
    ProjectCard,
    RenderViewLine,
    RenderViewSection,
    ReviewLoadStatus,
    ReviewRequiredCard,
    WarningCard,
)
from .output import render_brief_markdown, resolve_brief_path, write_brief_output
from .output_receipt import (
    RenderedOutputReceiptError,
    build_daily_brief_rendered_output_receipt_proof,
    build_rendered_brief_receipt,
    build_trusted_packet_receipt,
    import_rendered_brief,
)
from .packet import (
    DailyBriefPacketError,
    build_daily_brief_packet,
    build_daily_brief_packet_proof,
    build_daily_brief_packet_v2,
    build_daily_brief_packet_v2_proof,
    load_daily_brief_packet_v2_contract,
)
from .policy import (
    DailyBriefPolicyError,
    load_daily_brief_policy_seed,
    reason_code_for_tier,
    validate_daily_brief_policy,
)
from .render_view import build_daily_brief_render_view
from .rendered_quality import (
    RenderedBriefQualityError,
    build_daily_brief_rendered_quality_proof,
    validate_rendered_brief,
)
from .scheduling import build_daily_brief_schedule_preview, build_launchd_schedule_proof
from .store import (
    read_daily_brief_handoff,
    read_latest_daily_brief_runs,
    read_latest_launchd_schedule_previews,
    write_daily_brief_handoff_lines,
    write_daily_brief_run,
    write_launchd_schedule_preview,
)
from .triage import (
    ReviewTriageAgent,
    build_review_load_status,
    build_review_triage_agent_proof,
)

__all__ = [
    "AttentionItemCard",
    "DailyBriefContext",
    "DailyBriefRenderView",
    "DailyBriefResult",
    "DeliveryHandoffInput",
    "DeliveryHandoffPayload",
    "HandoffLine",
    "HtmlRenderingData",
    "LaunchdSchedulePreview",
    "MeetingCard",
    "NotificationSummary",
    "ProjectCard",
    "RenderViewLine",
    "RenderViewSection",
    "ReviewLoadStatus",
    "ReviewRequiredCard",
    "WarningCard",
    "build_daily_brief_context",
    "build_daily_brief_context_builder_proof",
    "build_daily_brief_agent_proof",
    "build_daily_brief_delivery_handoff_proof",
    "build_daily_brief_render_view",
    "build_daily_brief_schedule_preview",
    "build_launchd_schedule_proof",
    "run_daily_brief",
    "render_brief_markdown",
    "resolve_brief_path",
    "write_brief_output",
    "DailyBriefPacketError",
    "build_daily_brief_packet",
    "build_daily_brief_packet_proof",
    "build_daily_brief_packet_v2",
    "build_daily_brief_packet_v2_proof",
    "load_daily_brief_packet_v2_contract",
    "RenderedBriefQualityError",
    "build_daily_brief_rendered_quality_proof",
    "validate_rendered_brief",
    "RenderedOutputReceiptError",
    "build_daily_brief_rendered_output_receipt_proof",
    "build_rendered_brief_receipt",
    "build_trusted_packet_receipt",
    "import_rendered_brief",
    "build_daily_brief_mcp_handoff_status",
    "handoff_present",
    "DailyBriefPolicyError",
    "load_daily_brief_policy_seed",
    "reason_code_for_tier",
    "validate_daily_brief_policy",
    "read_daily_brief_handoff",
    "read_latest_daily_brief_runs",
    "read_latest_launchd_schedule_previews",
    "write_daily_brief_handoff_lines",
    "write_daily_brief_run",
    "write_launchd_schedule_preview",
    "ReviewTriageAgent",
    "build_review_load_status",
    "build_review_triage_agent_proof",
]
