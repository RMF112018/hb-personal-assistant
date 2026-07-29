"""EventKit source/calendar allowlist binding."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from hb_assistant.apple_mcc.probes.status import ProbeResult, ProbeState

# Default allowlist of source titles (case-sensitive). Prefer live discovery at runtime.
# Calendar capture targets EventKit sources by exact source title.
# iCloud includes the operator's own calendars and shared calendars under that account.
DEFAULT_EVENTKIT_SOURCE_ALLOWLIST: frozenset[str] = frozenset(
    {
        "iCloud",
    }
)
# Optional additional sources (e.g. Exchange/local) — not selected for calendar capture by default.
DEFAULT_EVENTKIT_SOURCE_OPTIONAL: frozenset[str] = frozenset(
    {
        "BF-Personal",
        "On My Mac",
        "Exchange",
        "Google",
        "Other",
    }
)


def resolve_eventkit_sources(
    *,
    sources: Sequence[dict[str, Any]],
    allowlist: frozenset[str] | set[str] | None = None,
) -> ProbeResult:
    """Bind EventKit sources that appear in the allowlist.

    ``sources`` items: {"title": str, "identifier": str, "calendars": [...]}.
    """
    allowed = frozenset(allowlist) if allowlist is not None else DEFAULT_EVENTKIT_SOURCE_ALLOWLIST
    titles = [str(s.get("title", "")) for s in sources]
    matched = [t for t in titles if t in allowed]
    if not titles:
        return ProbeResult(
            domain="eventkit",
            state=ProbeState.MISSING,
            detail="no_sources_enumerated",
            candidates=(),
            metadata={"allowlist": sorted(allowed)},
        )
    if not matched:
        return ProbeResult(
            domain="eventkit",
            state=ProbeState.MISSING,
            detail="no_allowlisted_sources",
            candidates=tuple(titles),
            metadata={"allowlist": sorted(allowed)},
        )
    return ProbeResult(
        domain="eventkit",
        state=ProbeState.OK,
        detail="allowlist_bound",
        selected=",".join(matched),
        candidates=tuple(titles),
        metadata={"matched": matched, "allowlist": sorted(allowed)},
    )


def resolve_eventkit_calendars(
    *,
    calendars: Sequence[dict[str, Any]],
    source_titles_allowed: frozenset[str] | set[str] | None = None,
) -> ProbeResult:
    """Filter calendars whose source title is allowlisted."""
    allowed = (
        frozenset(source_titles_allowed)
        if source_titles_allowed is not None
        else DEFAULT_EVENTKIT_SOURCE_ALLOWLIST
    )
    kept: list[str] = []
    all_titles: list[str] = []
    for c in calendars:
        title = str(c.get("title", ""))
        src = str(c.get("source_title", c.get("source", "")))
        all_titles.append(title)
        if src in allowed:
            kept.append(title)
    if not kept:
        return ProbeResult(
            domain="eventkit_calendars",
            state=ProbeState.MISSING,
            detail="no_allowlisted_calendars",
            candidates=tuple(all_titles),
        )
    return ProbeResult(
        domain="eventkit_calendars",
        state=ProbeState.OK,
        detail="calendars_bound",
        selected=",".join(kept),
        candidates=tuple(all_titles),
        metadata={"bound": kept},
    )
