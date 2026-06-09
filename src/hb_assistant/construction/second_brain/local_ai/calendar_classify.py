"""Phase 10 correction — deterministic calendar event classification (pre-model noise filter).

Classifies each calendar event into one of four value tiers from already-redacted fields only
(title, location, attendee count, online flag, project assignment, proximity). This runs BEFORE the
local-model synthesis packet is built so obvious low-value items are demoted/excluded and the model
only ever sees meetings worth prepping for (amendment: pre-model calendar filtering).

Tiers (``CalendarClass``):
- ``requires_prep`` — a prep keyword (OAC, RFI, submittal, kickoff, bid, inspection…) or a
  near-term project meeting that needs work before it.
- ``key_meeting``  — a project meeting with real attendance but no explicit prep signal.
- ``fyi``         — routine syncs/standups/all-hands with no project or prep value (demoted).
- ``excluded``    — PTO/OOO, IT maintenance, lunch-only, placeholders/holds, zero-attendee or
  malformed entries (suppressed from the brief body).

Pure + deterministic: no DB, no clock, no model, no writeback. Operates on redacted text only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CalendarClass = Literal["requires_prep", "key_meeting", "fyi", "excluded"]

# Visible tiers (rendered in the brief); ``fyi`` is demoted, ``excluded`` is suppressed by default.
VISIBLE_CLASSES: frozenset[str] = frozenset({"requires_prep", "key_meeting"})

# Prep-worthy construction-meeting signals — these promote to requires_prep even if recurring.
_PREP_PATTERNS = re.compile(
    r"\b("
    r"oac|owner[- ]architect|pre[- ]?con(?:struction)?|kick[- ]?off|buyout|bid\b|"
    r"rfi|submittal|coordination|schedule review|closeout|punch|inspection|"
    r"walk(?:through| )|interview|negotiation|preconstruction|design review|"
    r"budget review|gmp|change order|owner meeting|subcontractor"
    r")\b",
    re.IGNORECASE,
)

# Out-of-office / personal-time signals — excluded as noise.
_OOO_PATTERNS = re.compile(
    r"\b(pto|ooo|out of office|out-of-office|vacation|holiday|day off|leave|sick)\b",
    re.IGNORECASE,
)

# IT / system maintenance reminders — excluded as noise.
_IT_PATTERNS = re.compile(
    r"\b(it maintenance|maintenance window|system update|patch(?:ing)?|server|outage|upgrade window)\b",
    re.IGNORECASE,
)

# Placeholder / hold / tentative blocks — excluded as noise.
_HOLD_PATTERNS = re.compile(
    r"\b(hold|placeholder|do not book|tentative|block(?:ed)?|reserved|tbd)\b", re.IGNORECASE
)

# Lunch-only entries — excluded unless they carry a project/prep signal (handled by ordering).
_LUNCH_PATTERNS = re.compile(r"\b(lunch|coffee|happy hour|birthday|celebration)\b", re.IGNORECASE)

# Routine low-signal syncs — demoted to FYI when no project/prep signal is present.
_ROUTINE_PATTERNS = re.compile(
    r"\b(huddle|stand[- ]?up|all[- ]?hands|check[- ]?in|sync|weekly sync|daily sync|town hall|1[: ]?1|one[- ]?on[- ]?one)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CalendarClassification:
    """Deterministic classification of a single calendar event."""

    klass: CalendarClass
    reason_code: str

    @property
    def visible(self) -> bool:
        return self.klass in VISIBLE_CLASSES


def classify_calendar_event(
    *,
    title: str | None,
    location: str | None = None,
    attendee_count: int = 0,
    is_online: bool = False,
    has_project: bool = False,
    days_until: float = 0.0,
) -> CalendarClassification:
    """Classify one event into a value tier (deterministic; redacted inputs only).

    Order of precedence: malformed/noise exclusions → prep keywords (always promote) → routine syncs
    (demote when no project) → project meetings (key) → default FYI.
    """
    text = " ".join(p for p in (title, location) if p).strip()

    # 1. Malformed / zero-signal entries.
    if not (title or "").strip():
        return CalendarClassification("excluded", "malformed_no_title")

    # 2. Personal time / IT maintenance / holds — pure noise.
    if _OOO_PATTERNS.search(text):
        return CalendarClassification("excluded", "out_of_office")
    if _IT_PATTERNS.search(text):
        return CalendarClassification("excluded", "it_maintenance")
    if _HOLD_PATTERNS.search(text) and not has_project and not _PREP_PATTERNS.search(text):
        return CalendarClassification("excluded", "placeholder_hold")

    # 3. Prep keywords always win (a "weekly OAC" is recurring but still needs prep).
    if _PREP_PATTERNS.search(text):
        return CalendarClassification("requires_prep", "prep_keyword")

    # 4. Lunch / social-only with no project → noise.
    if _LUNCH_PATTERNS.search(text) and not has_project:
        return CalendarClassification("excluded", "social_only")

    # 5. Zero-attendee entries with no project → noise.
    if attendee_count <= 0 and not has_project:
        return CalendarClassification("excluded", "no_attendees")

    # 6. Routine syncs with no project → FYI (demoted, not excluded).
    if _ROUTINE_PATTERNS.search(text) and not has_project:
        return CalendarClassification("fyi", "routine_sync")

    # 7. Project meetings with real attendance → key meeting (or near-term).
    if has_project and attendee_count >= 2:
        return CalendarClassification("key_meeting", "project_meeting")
    if has_project and days_until <= 1.0:
        return CalendarClassification("key_meeting", "near_term_project")

    # 8. Anything else is low-signal FYI.
    return CalendarClassification("fyi", "low_signal")
