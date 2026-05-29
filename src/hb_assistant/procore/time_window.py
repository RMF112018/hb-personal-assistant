"""Relative-time parsing for the local query commands.

Turns operator phrases (``"48 hours ago"``, ``"7 days ago"``) and ISO timestamps
into a normalized ISO-8601 UTC string suitable for the history/timeline/change
``since_utc`` / ``until_utc`` filters. Pure: ``now`` is injected so the parse is
deterministic and testable.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_REL_RE = re.compile(r"^\s*(\d+)\s+(minute|hour|day|week)s?\s+ago\s*$", re.IGNORECASE)
_UNIT_SECONDS = {"minute": 60, "hour": 3600, "day": 86400, "week": 604800}


def parse_since(value: str, *, now: datetime) -> str:
    """Return an ISO-8601 UTC timestamp for ``value``.

    Accepts ``"N minutes|hours|days|weeks ago"`` (relative to ``now``) or an ISO
    timestamp (normalized to UTC; a trailing ``Z`` is accepted). Raises
    ``ValueError`` on anything else.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("empty time value")

    match = _REL_RE.match(value)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        moment = now - timedelta(seconds=amount * _UNIT_SECONDS[unit])
        return _to_utc_iso(moment)

    iso_candidate = value.strip()
    if iso_candidate.endswith(("Z", "z")):
        iso_candidate = iso_candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(iso_candidate)
    except ValueError as exc:
        raise ValueError(f"unparseable time value: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return _to_utc_iso(parsed)


def _to_utc_iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = ["parse_since"]
