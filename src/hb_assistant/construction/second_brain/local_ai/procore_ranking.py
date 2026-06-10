"""Phase 10 — deterministic Procore signal ranking + aggregate suppression (daily-brief usefulness).

Turns the flat list of open Procore action signals into a *ranked* executive selection plus a
*suppressed-backlog* diagnostic, so the daily brief surfaces a handful of source-linked, "why-today"
rows instead of giant unranked aggregate counts (the audit found 5,866 open signals, 0 due-soon,
3,592 aggregate-sludge rows dominating the brief).

Promotion (a signal has a clear "why today") when ANY of: overdue, due-soon, newly observed
(recent / since last successful brief), source-change-linked, financially material, or
high/critical importance. Suppression otherwise — and ``*_closed`` / semantically-resolved signals
(e.g. ``observation_closed``) are suppressed up-front and never surface as an open action.

Pure + deterministic: ``now_utc`` (and optional ``last_success_utc``) are passed in (no clock read).
Inputs are safe enums/ids/timestamps + the opaque ``owner_entity_key`` / ``source_change_event_id``
used ONLY to derive booleans — the raw values never leave this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

# Importance → base score (lower-importance medium/low only surface with another "why today").
_IMPORTANCE_SCORE = {"critical": 30, "high": 20, "medium": 5, "low": 0}

# Score weights for the "why today" signals.
_W_OVERDUE = 50
_W_DUE_SOON = 30
_W_FINANCIAL = 25
_W_SOURCE_CHANGE = 20
_W_RECENT = 15
_W_OWNER = 10

_DUE_SOON_DAYS = 7
_RECENT_DAYS = 7


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_semantically_closed(signal_type: str) -> bool:
    st = signal_type.lower()
    return st.endswith("_closed") or "resolved" in st or st.endswith("_complete")


@dataclass(frozen=True)
class RankedSignal:
    action_signal_id: str
    project_key: str
    signal_type: str
    importance: str
    rank_score: float
    promoted: bool
    why_today: str
    suppression_reason: Optional[str]
    is_aggregate_sludge: bool
    is_semantically_actionable: bool
    source_change_linked: bool
    recent: bool
    due_soon: bool
    overdue: bool
    owner_linked: bool
    financial_materiality: bool
    priority: int
    rank_reasons: list[str] = field(default_factory=list)


def _financial(signal_type: str, dimensions: tuple[str, ...]) -> bool:
    if "cost_exposure" in dimensions:
        return True
    st = signal_type.lower()
    return any(k in st for k in ("cost", "budget", "payment", "invoice", "retainage", "financial"))


def rank_one(
    signal: dict[str, Any],
    *,
    now_dt: Optional[datetime],
    recent_floor: Optional[datetime],
    dimensions: tuple[str, ...],
) -> RankedSignal:
    """Rank a single signal (deterministic)."""
    st = str(signal.get("signal_type") or "")
    importance = str(signal.get("importance") or "medium").lower()
    owner_linked = bool(signal.get("owner_entity_key"))
    source_change_linked = bool(signal.get("source_change_event_id"))
    due = _parse_dt(signal.get("due_at_utc"))
    first_seen = _parse_dt(signal.get("first_detected_at_utc"))

    overdue = bool(due and now_dt and due < now_dt)
    due_soon = bool(due and now_dt and now_dt <= due <= now_dt + timedelta(days=_DUE_SOON_DAYS))
    recent = bool(first_seen and recent_floor and first_seen >= recent_floor)
    financial = _financial(st, dimensions)
    semantically_closed = _is_semantically_closed(st)
    is_actionable = not semantically_closed

    reasons: list[str] = []
    score = float(_IMPORTANCE_SCORE.get(importance, 5))
    if overdue:
        score += _W_OVERDUE
        reasons.append("overdue")
    if due_soon:
        score += _W_DUE_SOON
        reasons.append("due_soon")
    if financial:
        score += _W_FINANCIAL
        reasons.append("financial_materiality")
    if source_change_linked:
        score += _W_SOURCE_CHANGE
        reasons.append("source_change_linked")
    if recent:
        score += _W_RECENT
        reasons.append("recent")
    if owner_linked:
        score += _W_OWNER
        reasons.append("owner_linked")
    if importance in ("high", "critical"):
        reasons.append(importance)

    # Promotion: a clear "why today" OR high/critical importance — but NEVER a closed/resolved signal.
    has_why_today = bool(
        overdue or due_soon or recent or source_change_linked or financial
        or importance in ("high", "critical")
    )
    promoted = is_actionable and has_why_today

    if not is_actionable:
        suppression_reason: Optional[str] = "semantically_closed"
        is_sludge = False
        why_today = ""
    elif promoted:
        suppression_reason = None
        is_sludge = False
        why_today = _why_today(overdue, due_soon, recent, source_change_linked, financial, importance)
    else:
        suppression_reason = "no_why_today_stale_backlog"
        # Aggregate sludge: no urgency, no owner, no change link → pure backlog count.
        is_sludge = not (owner_linked or source_change_linked)
        why_today = ""

    # Priority band (lower = surfaced first).
    if overdue or due_soon:
        priority = 10
    elif importance in ("high", "critical") or financial:
        priority = 30
    else:
        priority = 60

    return RankedSignal(
        action_signal_id=str(signal.get("action_signal_id") or ""),
        project_key=str(signal.get("project_key") or ""),
        signal_type=st,
        importance=importance,
        rank_score=score,
        promoted=promoted,
        why_today=why_today,
        suppression_reason=suppression_reason,
        is_aggregate_sludge=is_sludge,
        is_semantically_actionable=is_actionable,
        source_change_linked=source_change_linked,
        recent=recent,
        due_soon=due_soon,
        overdue=overdue,
        owner_linked=owner_linked,
        financial_materiality=financial,
        priority=priority,
        rank_reasons=reasons,
    )


def _why_today(
    overdue: bool,
    due_soon: bool,
    recent: bool,
    source_change_linked: bool,
    financial: bool,
    importance: str,
) -> str:
    if overdue:
        return "Overdue — past its due date"
    if due_soon:
        return "Due soon"
    if source_change_linked:
        return "Recently changed"
    if financial:
        return "Financially material"
    if recent:
        return "Newly observed"
    if importance in ("high", "critical"):
        return f"{importance.capitalize()} importance"
    return "Open action"


def rank_procore_signals(
    signals: list[dict[str, Any]],
    *,
    now_utc: str,
    last_success_utc: Optional[str] = None,
    dimensions_for: Any = None,
) -> list[RankedSignal]:
    """Rank a list of open Procore signals; returns RankedSignals (deterministic order by score desc).

    ``dimensions_for(signal_type) -> list[str]`` is injected (defaults to the project-health keyword
    map) so financial materiality reuses the existing classification rather than re-implementing it.
    ``recent`` is measured against ``last_success_utc`` when supplied (newly observed since the last
    successful brief), else a rolling ``_RECENT_DAYS`` window.
    """
    now_dt = _parse_dt(now_utc)
    last_dt = _parse_dt(last_success_utc) if last_success_utc else None
    recent_floor = last_dt or (now_dt - timedelta(days=_RECENT_DAYS) if now_dt else None)

    if dimensions_for is None:
        from .procore_digest import _dimensions_for_signal as dimensions_for  # reuse, no dup

    ranked = [
        rank_one(
            s,
            now_dt=now_dt,
            recent_floor=recent_floor,
            dimensions=tuple(dimensions_for(str(s.get("signal_type") or ""))),
        )
        for s in signals
    ]
    # Deterministic: score desc, then priority asc, then id for stable ties.
    ranked.sort(key=lambda r: (-r.rank_score, r.priority, r.action_signal_id))
    return ranked
