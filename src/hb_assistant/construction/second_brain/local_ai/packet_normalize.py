"""Phase 10A — model-packet normalization & redaction.

Turns raw email/calendar bodies (mostly HTML in dev) into bounded, clean, redacted *model text* for
action-extraction packets. The full HTML, join URLs, and full attendee arrays stay in the raw V42
tables; model packets carry only normalized text + compact metadata.

Public helpers:
- ``normalize_model_text(body_text, body_html, *, max_chars)`` → (text, meta): HTML→text fallback,
  Teams boilerplate strip, join-URL / Meeting ID / Passcode / dial-in redaction, whitespace collapse,
  bounded truncation with a ``[truncated]`` marker.
- ``has_join_url(...)`` → bool metadata (the URL itself is never emitted).
- ``summarize_attendees(attendees, *, user_domains)`` → compact ``{attendee_count, user_is_attendee,
  participant_domains}`` (no large attendee arrays in packets).
"""

from __future__ import annotations

import re
from typing import Any, Optional

from hb_assistant.procore.normalizers.financial import html_to_text

# Minimum "strong" plain-text length; below this (with HTML present) we prefer the HTML→text body.
_WEAK_TEXT_CHARS = 16
_TRUNCATED_MARKER = "…[truncated]"

# Redaction patterns for join artifacts (removed from model text; never emitted).
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MEETING_ID_RE = re.compile(r"meeting id:\s*[\d\s]+", re.IGNORECASE)
_PASSCODE_RE = re.compile(r"(passcode|password|conference id):\s*\S+", re.IGNORECASE)
_DIALIN_RE = re.compile(
    r"(dial[- ]?in|phone conference id|call in|tel:)\s*[:+]?[\d\s().+-]{6,}", re.IGNORECASE
)
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
_DIVIDER_RE = re.compile(r"[_*=–—-]{6,}")

# Microsoft Teams / Outlook meeting boilerplate phrases stripped from model text.
_TEAMS_BOILERPLATE = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"microsoft teams (meeting|need help\?)",
        r"join on your computer,? mobile app,? or room device",
        r"join (the meeting now|with a video conferencing device)",
        r"meeting options\b",
        r"learn more\b",
        r"organizer'?s meeting options",
        r"for organizers:.*",
        r"download teams\b",
        r"join on the web instead",
        r"video conferencing device\b",
        r"\bteams\.microsoft\.com\b",
    )
)
_JOIN_URL_HINT_RE = re.compile(
    r"(teams\.microsoft\.com/l/meetup-join|/meetup-join/|aka\.ms/joinmeeting|zoom\.us/j/|"
    r"webex\.com|join the meeting now|click here to join)",
    re.IGNORECASE,
)


def _is_weak(text: Optional[str]) -> bool:
    return not text or len(text.strip()) < _WEAK_TEXT_CHARS


def normalize_model_text(
    body_text: Optional[str], body_html: Optional[str], *, max_chars: int
) -> tuple[str, dict[str, Any]]:
    """Return (bounded clean model text, normalization metadata).

    Uses ``body_text`` when it is strong; otherwise derives text from ``body_html``. Strips Teams
    boilerplate and redacts join URLs / Meeting IDs / Passcodes / dial-in numbers / divider lines, then
    collapses whitespace and truncates to ``max_chars``. Raw HTML is never emitted.
    """
    used_html = False
    text = body_text or ""
    if _is_weak(body_text) and body_html:
        text = html_to_text(body_html)
        used_html = True

    # Redact join artifacts FIRST, while URLs are still intact single tokens (before boilerplate
    # phrase-stripping could fragment a teams.microsoft.com/... link into an un-maskable remnant).
    redacted = False
    for pat in (_URL_RE, _MEETING_ID_RE, _PASSCODE_RE, _DIALIN_RE, _PHONE_RE):
        new = pat.sub(" ", text)
        if new != text:
            redacted = True
            text = new

    boilerplate = False
    for pat in _TEAMS_BOILERPLATE:
        new = pat.sub(" ", text)
        if new != text:
            boilerplate = True
            text = new

    text = _DIVIDER_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()

    truncated = False
    if len(text) > max_chars:
        text = text[: max(0, max_chars - len(_TRUNCATED_MARKER))].rstrip() + _TRUNCATED_MARKER
        truncated = True

    meta = {
        "body_html_included": False,
        "derived_from_html": used_html,
        "teams_boilerplate_stripped": boilerplate,
        "redacted_join_artifacts": redacted,
        "truncated": truncated,
        "char_count": len(text),
    }
    return text, meta


def has_join_url(
    *,
    join_url: Optional[str] = None,
    online_meeting_provider: Optional[str] = None,
    raw_text: Optional[str] = None,
) -> bool:
    """True when the source had a join link/provider — metadata only; the URL is never emitted."""
    if join_url and str(join_url).strip():
        return True
    if online_meeting_provider and str(online_meeting_provider).strip():
        return True
    return bool(raw_text and _JOIN_URL_HINT_RE.search(raw_text))


def _attendee_domain(att: Any) -> Optional[str]:
    if isinstance(att, dict):
        dom = att.get("attendee_domain") or att.get("domain")
        if dom:
            return str(dom).lower()
        addr = att.get("email") or att.get("address") or att.get("emailAddress")
        if isinstance(addr, dict):
            addr = addr.get("address")
        if isinstance(addr, str) and "@" in addr:
            return addr.split("@", 1)[1].lower()
    elif isinstance(att, str) and "@" in att:
        return att.split("@", 1)[1].lower()
    return None


def summarize_attendees(
    attendees: Any, *, user_domains: tuple[str, ...] = ()
) -> dict[str, Any]:
    """Compact attendee metadata — count, participant domains, whether the user attends.

    Replaces the full attendee array; no names/emails/large lists flow into the model packet.
    """
    items = attendees if isinstance(attendees, list) else []
    domains = sorted({d for a in items if (d := _attendee_domain(a))})
    user_doms = {d.lower() for d in user_domains}
    user_is_attendee = any(d in user_doms for d in domains)
    return {
        "attendee_count": len(items),
        "user_is_attendee": user_is_attendee,
        "participant_domains": domains[:20],
    }
