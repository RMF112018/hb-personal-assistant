"""Phase 07B calendar + email-thread intelligence foundation.

Read-only policy loaders and JSON contract loaders for the additive V23 schema
(calendar source registry, event index, project-match and meeting/email
relationship candidates, and email-thread summary materialization receipts).
Ingestion, matching, and summarization logic land in later 07B prompts.
"""

from __future__ import annotations

from .contracts import (
    load_calendar_project_match_contract,
    load_email_thread_summary_contract,
    load_meeting_email_relationship_candidate_contract,
)
from .policy import (
    CalendarSourcePolicy,
    EmailThreadSummaryPolicy,
    ReviewRequiredRules,
    load_calendar_source_policy,
    load_email_thread_summary_policy,
    load_review_required_rules,
)

__all__ = [
    "CalendarSourcePolicy",
    "EmailThreadSummaryPolicy",
    "ReviewRequiredRules",
    "load_calendar_source_policy",
    "load_email_thread_summary_policy",
    "load_review_required_rules",
    "load_calendar_project_match_contract",
    "load_email_thread_summary_contract",
    "load_meeting_email_relationship_candidate_contract",
]
