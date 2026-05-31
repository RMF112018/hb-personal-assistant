"""Phase 07B cross-domain relationship candidate builders (local-only, candidates only).

Builders here link records across already-ingested domains (e.g. calendar events ↔ email
threads) into review-routed candidate rows. They are read-only with respect to every
external system and never auto-promote: every row is written with
``promotion_status='candidate'``.
"""

from __future__ import annotations

from .meeting_email_candidates import (
    MeetingEmailCandidateBuilder,
    MeetingEmailCandidateReport,
    MeetingEmailCandidateSample,
)

__all__ = [
    "MeetingEmailCandidateBuilder",
    "MeetingEmailCandidateReport",
    "MeetingEmailCandidateSample",
]
