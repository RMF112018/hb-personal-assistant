"""Source-quality vocabulary + deterministic precedence for email/calendar raw content.

Mirrors the Procore ``structured_analytics`` precedence discipline (higher rank wins; a
lower-quality record must never downgrade a higher-quality one) but with the email/calendar
source-quality vocabulary the package mandates.

These helpers are pure and value-free: they classify from *presence* of body fields, never
from body content, so they are safe to use in receipts/logs.
"""

from __future__ import annotations

# Email source-quality values (Prompt 01).
EMAIL_FULL_BODY = "graph_full_body"
EMAIL_PREVIEW_ONLY = "graph_body_preview_only"
EMAIL_REDACTED_LEGACY = "redacted_legacy_projection"
EMAIL_METADATA_ONLY = "metadata_only"

# Calendar source-quality values (Prompt 01). Full-event body has its own label; the
# remaining three labels are shared with email so consumers reason about one ladder.
CALENDAR_FULL_BODY = "graph_full_event_body"
CALENDAR_PREVIEW_ONLY = "graph_body_preview_only"
CALENDAR_REDACTED_LEGACY = "redacted_legacy_projection"
CALENDAR_METADATA_ONLY = "metadata_only"

EMAIL_SOURCE_QUALITY_VALUES = frozenset(
    {EMAIL_FULL_BODY, EMAIL_PREVIEW_ONLY, EMAIL_REDACTED_LEGACY, EMAIL_METADATA_ONLY}
)
CALENDAR_SOURCE_QUALITY_VALUES = frozenset(
    {CALENDAR_FULL_BODY, CALENDAR_PREVIEW_ONLY, CALENDAR_REDACTED_LEGACY, CALENDAR_METADATA_ONLY}
)

# Deterministic precedence. Equal rank => idempotent overwrite; a strictly lower rank must
# never overwrite local-private body/event content (downgrade prevention).
SOURCE_QUALITY_RANK: dict[str, int] = {
    EMAIL_FULL_BODY: 100,
    CALENDAR_FULL_BODY: 100,
    EMAIL_PREVIEW_ONLY: 70,
    CALENDAR_PREVIEW_ONLY: 70,  # same string as EMAIL_PREVIEW_ONLY; listed for clarity
    EMAIL_REDACTED_LEGACY: 20,
    EMAIL_METADATA_ONLY: 0,
}


def rank(source_quality: str | None) -> int:
    """Return the precedence rank for a source-quality label (unknown => 0)."""
    return SOURCE_QUALITY_RANK.get(source_quality or "", 0)


def _has_text(value: str | None) -> bool:
    return bool(value is not None and str(value).strip() != "")


def classify_email(
    *, body_text: str | None, body_html: str | None, body_preview: str | None
) -> str:
    """Classify an email raw row from body-field presence only."""
    if _has_text(body_text) or _has_text(body_html):
        return EMAIL_FULL_BODY
    if _has_text(body_preview):
        return EMAIL_PREVIEW_ONLY
    return EMAIL_METADATA_ONLY


def classify_calendar(
    *, body_text: str | None, body_html: str | None, body_preview: str | None
) -> str:
    """Classify a calendar raw row from body-field presence only."""
    if _has_text(body_text) or _has_text(body_html):
        return CALENDAR_FULL_BODY
    if _has_text(body_preview):
        return CALENDAR_PREVIEW_ONLY
    return CALENDAR_METADATA_ONLY


def classify_thread(member_qualities: list[str]) -> str:
    """Roll a thread's source-quality up from its member messages (best member wins)."""
    best = EMAIL_METADATA_ONLY
    for q in member_qualities:
        if rank(q) > rank(best):
            # Threads use the email ladder; normalise a calendar full-body label away.
            best = EMAIL_FULL_BODY if q == CALENDAR_FULL_BODY else q
    return best


# SQL fragment that ranks a source-quality column inline, used by precedence-aware upserts
# so a lower-quality row can never downgrade local-private body content at the data layer.
def rank_case_sql(column_expr: str) -> str:
    """Return a SQL CASE expression mapping ``column_expr`` to its precedence rank."""
    return (
        "CASE {c} "
        "WHEN '{full}' THEN 100 "
        "WHEN '{cal_full}' THEN 100 "
        "WHEN '{preview}' THEN 70 "
        "WHEN '{legacy}' THEN 20 "
        "ELSE 0 END"
    ).format(
        c=column_expr,
        full=EMAIL_FULL_BODY,
        cal_full=CALENDAR_FULL_BODY,
        preview=EMAIL_PREVIEW_ONLY,
        legacy=EMAIL_REDACTED_LEGACY,
    )


# Apple local capture source-quality values (MCC).
APPLE_MAIL_FULL = "apple_mail_full_mime"
APPLE_MAIL_PREVIEW = "apple_mail_preview"
APPLE_EVENTKIT_FULL = "apple_eventkit_full"
APPLE_EVENTKIT_META = "apple_eventkit_metadata"
CNCONTACT_FULL = "cncontact_full"
CNCONTACT_PARTIAL = "cncontact_partial"

APPLE_SOURCE_QUALITY_VALUES = frozenset(
    {
        APPLE_MAIL_FULL,
        APPLE_MAIL_PREVIEW,
        APPLE_EVENTKIT_FULL,
        APPLE_EVENTKIT_META,
        CNCONTACT_FULL,
        CNCONTACT_PARTIAL,
    }
)

# Extend rank ladder (higher wins). Keep graph full at 100; apple full at 95.
SOURCE_QUALITY_RANK.update(
    {
        APPLE_MAIL_FULL: 95,
        APPLE_EVENTKIT_FULL: 95,
        CNCONTACT_FULL: 95,
        APPLE_MAIL_PREVIEW: 65,
        APPLE_EVENTKIT_META: 40,
        CNCONTACT_PARTIAL: 50,
    }
)
