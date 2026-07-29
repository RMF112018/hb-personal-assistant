"""EventKit source/calendar allowlist tests."""

from __future__ import annotations

from hb_assistant.apple_mcc.probes.eventkit_source import (
    resolve_eventkit_calendars,
    resolve_eventkit_sources,
)
from hb_assistant.apple_mcc.probes.status import ProbeState


def test_eventkit_source_calendar_allowlist() -> None:
    sources = [
        {"title": "iCloud", "identifier": "icloud"},
        {"title": "Untrusted", "identifier": "x"},
    ]
    r = resolve_eventkit_sources(sources=sources)
    assert r.state is ProbeState.OK
    assert "iCloud" in (r.selected or "")


def test_eventkit_no_allowlisted() -> None:
    r = resolve_eventkit_sources(sources=[{"title": "Random", "identifier": "r"}])
    assert r.state is ProbeState.MISSING


def test_eventkit_calendars_bound() -> None:
    cals = [
        {"title": "Home", "source_title": "iCloud"},
        {"title": "Spam", "source_title": "Untrusted"},
    ]
    r = resolve_eventkit_calendars(calendars=cals)
    assert r.state is ProbeState.OK
    assert "Home" in (r.selected or "")
