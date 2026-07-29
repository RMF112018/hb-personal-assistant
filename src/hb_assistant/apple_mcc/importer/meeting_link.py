"""Meeting email ↔ calendar linkage helpers."""

from __future__ import annotations

import re

JOIN_URL_RE = re.compile(r"https?://[^\s<>\"]+", re.I)


def extract_join_urls(text: str | None) -> list[str]:
    if not text:
        return []
    return JOIN_URL_RE.findall(text)


def score_meeting_email_link(*, email_subject: str | None, event_subject: str | None) -> float:
    if not email_subject or not event_subject:
        return 0.0
    a = email_subject.strip().lower()
    b = event_subject.strip().lower()
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.7
    return 0.0
