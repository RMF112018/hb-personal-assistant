"""Live pilot dry-run scaffold (no source mutation)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LivePilotPlan:
    source_mutation: bool = False
    redacted: bool = True
    dry_run: bool = True


def plan_live_pilot() -> LivePilotPlan:
    return LivePilotPlan()
