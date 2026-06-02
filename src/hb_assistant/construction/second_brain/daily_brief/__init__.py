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
from .models import (
    AttentionItemCard,
    DailyBriefContext,
    DeliveryHandoffInput,
    HandoffLine,
    MeetingCard,
    ProjectCard,
    ReviewLoadStatus,
    ReviewRequiredCard,
    WarningCard,
)
from .policy import (
    DailyBriefPolicyError,
    load_daily_brief_policy_seed,
    reason_code_for_tier,
    validate_daily_brief_policy,
)
from .store import read_latest_daily_brief_runs, write_daily_brief_run
from .triage import (
    ReviewTriageAgent,
    build_review_load_status,
    build_review_triage_agent_proof,
)

__all__ = [
    "AttentionItemCard",
    "DailyBriefContext",
    "DeliveryHandoffInput",
    "HandoffLine",
    "MeetingCard",
    "ProjectCard",
    "ReviewLoadStatus",
    "ReviewRequiredCard",
    "WarningCard",
    "build_daily_brief_context",
    "build_daily_brief_context_builder_proof",
    "DailyBriefPolicyError",
    "load_daily_brief_policy_seed",
    "reason_code_for_tier",
    "validate_daily_brief_policy",
    "read_latest_daily_brief_runs",
    "write_daily_brief_run",
    "ReviewTriageAgent",
    "build_review_load_status",
    "build_review_triage_agent_proof",
]
