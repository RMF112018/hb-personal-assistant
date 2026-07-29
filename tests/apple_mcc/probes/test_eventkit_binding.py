"""EventKit source/calendar allowlist tests."""

from __future__ import annotations

from hb_assistant.apple_mcc.probes.eventkit_source import (
    DEFAULT_EVENTKIT_SOURCE_ALLOWLIST,
    resolve_eventkit_calendars,
    resolve_eventkit_sources,
)
from hb_assistant.apple_mcc.probes.status import ProbeState


def test_default_allowlist_is_icloud() -> None:
    assert DEFAULT_EVENTKIT_SOURCE_ALLOWLIST == frozenset({"iCloud"})


def test_eventkit_source_calendar_allowlist() -> None:
    sources = [
        {"title": "iCloud", "identifier": "icloud"},
        {"title": "BF-Personal", "identifier": "bf"},
        {"title": "Untrusted", "identifier": "x"},
    ]
    r = resolve_eventkit_sources(sources=sources)
    assert r.state is ProbeState.OK
    assert r.selected == "iCloud"
    assert "BF-Personal" not in (r.selected or "")


def test_eventkit_no_allowlisted() -> None:
    r = resolve_eventkit_sources(sources=[{"title": "Random", "identifier": "r"}])
    assert r.state is ProbeState.MISSING


def test_eventkit_calendars_bound_all_icloud_including_shared() -> None:
    """All calendars under iCloud source bind; non-iCloud excluded."""
    cals = [
        {"title": "Personal", "source_title": "iCloud"},
        {"title": "Family", "source_title": "iCloud"},  # shared family calendar
        {"title": "Family Bills Calendar", "source_title": "iCloud"},
        {"title": "Pestle", "source_title": "iCloud"},
        {"title": "Calendar", "source_title": "BF-Personal"},
        {"title": "US Holidays", "source_title": "Subscribed Calendars"},
    ]
    r = resolve_eventkit_calendars(calendars=cals)
    assert r.state is ProbeState.OK
    selected = set((r.selected or "").split(","))
    assert selected == {"Personal", "Family", "Family Bills Calendar", "Pestle"}
    assert "Calendar" not in selected  # BF-Personal not default
    assert "US Holidays" not in selected
