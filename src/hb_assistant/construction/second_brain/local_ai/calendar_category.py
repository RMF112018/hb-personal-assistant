"""Phase 10 — deterministic calendar *category* resolution (advisory, no writeback).

Adds the project/internal/needs-review *category* dimension that the daily-brief usefulness substrate
needs, on top of the existing, well-tested project alias resolver. This module is a thin
classification layer: the **project arm delegates entirely to**
:func:`project_aliases.resolve_project_alias` (it never re-implements alias matching), and the
needs-review arm reuses :func:`project_aliases.candidate_tokens`. It only adds deterministic
internal classification (company / training / time-off) and a review-safe fallback *around* that.

Categories (:data:`CalendarCategory`):
- ``project``          — an alias resolved to a canonical HB ``project_key`` (high confidence).
- ``internal_company`` — company/admin events (financial forecast, leadership, all-hands…).
- ``internal_training``— training / learning / certification.
- ``internal_time_off``— PTO / OOO / vacation / leave.
- ``needs_review``     — project-looking text that did NOT resolve to a known alias (low confidence,
  routed to review; never forced into a project fact).
- ``unknown``          — no project signal and no internal signal.

A resolved ``project_key`` is the canonical key for ``project``; otherwise a review-safe sentinel
(``__internal_company__`` / ``__internal_training__`` / ``__internal_time_off__`` /
``__needs_review__`` / ``__unassigned__``) so downstream sections can group internal vs project vs
review separately. Pure + deterministic: no DB, no clock, no model, no writeback; redacted text only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .project_aliases import candidate_tokens, resolve_project_alias

CalendarCategory = Literal[
    "project",
    "internal_company",
    "internal_training",
    "internal_time_off",
    "needs_review",
    "unknown",
]

# Category sentinels stored in daily_brief_action_candidates.project_key when there is no real key.
SENTINEL_BY_CATEGORY: dict[str, str] = {
    "internal_company": "__internal_company__",
    "internal_training": "__internal_training__",
    "internal_time_off": "__internal_time_off__",
    "needs_review": "__needs_review__",
    "unknown": "__unassigned__",
}

# Personal time signals (PTO / OOO / vacation / leave).
_TIME_OFF_RE = re.compile(
    r"\b(pto|ooo|out of office|out-of-office|vacation|holiday|day off|leave|sick)\b",
    re.IGNORECASE,
)
# Training / learning / development.
_TRAINING_RE = re.compile(
    r"\b(training|lma training|learning|workshop|certification|webinar|onboarding|"
    r"lunch ?& ?learn|course)\b",
    re.IGNORECASE,
)
# Company / admin / leadership (internal, non-project). "forecast" covers the audit's
# "Project Financial Forecasts" (a company finance ritual, not a project meeting).
_COMPANY_RE = re.compile(
    r"\b(financial forecasts?|forecasts?|all[- ]?hands|town hall|company meeting|leadership|"
    r"board meeting|quarterly review|qbr|staff meeting|admin|payroll|benefits|hr\b|"
    r"performance review|annual review)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CalendarResolution:
    """Deterministic category resolution for a single calendar event."""

    project_key: str
    category: CalendarCategory
    confidence: float
    matched_alias: str | None
    needs_review: bool
    reason: str


def resolve_calendar_category(
    *,
    subject: str | None,
    location: str | None = None,
    organizer_domain: str | None = None,
    attendees: int = 0,
    indexed_project_key: str | None = None,
) -> CalendarResolution:
    """Resolve a calendar event's category + project key (deterministic; redacted inputs only).

    Precedence: a pre-indexed project key (trusted) → project-alias match (delegated) → internal
    time-off → internal training → internal company → project-looking-but-unresolved (needs review)
    → unknown. Never forces a low-confidence project mapping (those become ``needs_review``).
    """
    text = " ".join(p for p in (subject, location) if p).strip()

    # 1. A project key already assigned upstream (index) is authoritative.
    if indexed_project_key and not indexed_project_key.startswith("__"):
        return CalendarResolution(
            project_key=indexed_project_key,
            category="project",
            confidence=1.0,
            matched_alias=None,
            needs_review=False,
            reason="indexed_project_key",
        )

    # 2. Project alias — delegate to the single canonical matcher (no duplicate alias logic).
    key, alias = resolve_project_alias(subject, location)
    if key:
        return CalendarResolution(
            project_key=key,
            category="project",
            confidence=0.95,
            matched_alias=alias,
            needs_review=False,
            reason=f"alias:{alias}",
        )

    # 3. Internal buckets (deterministic keywords). Time-off first (most specific personal signal),
    #    then training, then company/admin.
    if _TIME_OFF_RE.search(text):
        return _internal("internal_time_off", "time_off_keyword")
    if _TRAINING_RE.search(text):
        return _internal("internal_training", "training_keyword")
    if _COMPANY_RE.search(text):
        return _internal("internal_company", "company_keyword")

    # 4. Project-looking but unresolved → review-safe (never invent a project).
    if candidate_tokens(subject) or candidate_tokens(location):
        return CalendarResolution(
            project_key=SENTINEL_BY_CATEGORY["needs_review"],
            category="needs_review",
            confidence=0.2,
            matched_alias=None,
            needs_review=True,
            reason="unresolved_project_like_token",
        )

    # 5. Nothing actionable.
    return CalendarResolution(
        project_key=SENTINEL_BY_CATEGORY["unknown"],
        category="unknown",
        confidence=0.0,
        matched_alias=None,
        needs_review=False,
        reason="no_project_or_internal_signal",
    )


def _internal(category: CalendarCategory, reason: str) -> CalendarResolution:
    return CalendarResolution(
        project_key=SENTINEL_BY_CATEGORY[category],
        category=category,
        confidence=0.6,
        matched_alias=None,
        needs_review=False,
        reason=reason,
    )
