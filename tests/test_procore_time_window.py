"""Phase 04B relative-time parsing tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hb_assistant.procore.time_window import parse_since

_NOW = datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("48 hours ago", "2026-05-27T12:00:00Z"),
        ("7 days ago", "2026-05-22T12:00:00Z"),
        ("30 minutes ago", "2026-05-29T11:30:00Z"),
        ("2 weeks ago", "2026-05-15T12:00:00Z"),
        ("1 day ago", "2026-05-28T12:00:00Z"),
        ("2026-05-01T00:00:00Z", "2026-05-01T00:00:00Z"),
        ("2026-05-01", "2026-05-01T00:00:00Z"),
        ("2026-05-01T06:00:00+06:00", "2026-05-01T00:00:00Z"),
    ],
)
def test_parse_since_valid(value: str, expected: str) -> None:
    assert parse_since(value, now=_NOW) == expected


@pytest.mark.parametrize("value", ["", "   ", "yesterday", "soon", "5 fortnights ago", "ago 3 days"])
def test_parse_since_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        parse_since(value, now=_NOW)
