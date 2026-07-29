"""EventKit calendar collector (fixture-friendly)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hb_assistant.apple_mcc.probes.eventkit_source import resolve_eventkit_sources


@dataclass
class CalendarCollectPlan:
    sources: list[str]
    limit: int


def plan_collect(*, sources: list[dict], limit: int = 100) -> CalendarCollectPlan:
    r = resolve_eventkit_sources(sources=sources)
    if not r.ok:
        raise RuntimeError(f"eventkit_not_bound:{r.state.value}")
    return CalendarCollectPlan(sources=(r.selected or "").split(","), limit=limit)


def load_ics_fixture(path: Path) -> str:
    return path.read_text(encoding="utf-8")
