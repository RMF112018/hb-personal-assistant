"""Calendar event normalization."""

from __future__ import annotations

from datetime import datetime, timezone


def to_utc_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_subject(subject: str | None) -> str:
    return (subject or "").strip()
