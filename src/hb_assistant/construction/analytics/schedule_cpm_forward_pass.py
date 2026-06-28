"""CPM forward pass foundation: deterministic early start / early finish computation.

PHASE 2 SCOPE — FORWARD PASS ONLY. Over the Phase 1 verified acyclic graph this module
computes application-owned early start (ES) and early finish (EF) for each activity,
honoring FS/SS/FF/SF relationships and normalized lag. It is a pure computation layer:
it takes plain activity/relationship dicts plus the Phase 1 ``GraphBuildResult`` and a
schedule-start anchor, and returns typed result objects. It executes NO SQL.

It deliberately does NOT compute a backward pass, late dates, float (total/free/
interfering/independent), the longest path, or the critical path. It NEVER reads or
overwrites source-export fields (source early/late dates, source total float, derived
float, source_critical_flag, source_driving_path_flag, is_critical) — duration comes only
from the duration fields, and ordering only from the graph.

DATE MODEL (Phase 2 simplification): all timing is computed as continuous day-offsets from
the anchor (day 0 = anchor), where durations and lags are normalized to working-day-
equivalent days via the existing ``schedule_quality_normalization`` helpers. The numeric
offsets are authoritative. A convenience ISO datetime is derived as ``anchor +
timedelta(days=offset)`` using CALENDAR-day addition — there is no weekend/holiday/calendar
engine in this phase (none exists in-repo). Offsets are the source of truth; ISO dates are
a view.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .schedule_cpm_graph import (
    DIAG_CYCLE,
    DIAG_MISSING_PREDECESSOR,
    DIAG_MISSING_SUCCESSOR,
    DIAG_SELF_RELATIONSHIP,
    GraphBuildResult,
)
from .schedule_quality_normalization import (
    DEFAULT_HOURS_PER_DAY,
    calendar_hours_per_day,
    normalize_duration_days,
    normalize_lag_result,
)

SUPPORTED_RELATIONSHIP_TYPES: frozenset[str] = frozenset({"FS", "SS", "FF", "SF"})

# Diagnostics that genuinely corrupt the logic graph and make a forward pass untrustworthy.
# Duplicate and unsupported-relationship-type diagnostics are NON-fatal: they are recorded
# but handled per-relationship below, because real schedules routinely contain them and
# blocking the whole run would be more misleading than computing the orderable graph.
FATAL_GRAPH_DIAGNOSTICS: frozenset[str] = frozenset(
    {
        DIAG_CYCLE,
        DIAG_MISSING_PREDECESSOR,
        DIAG_MISSING_SUCCESSOR,
        DIAG_SELF_RELATIONSHIP,
    }
)

# Run-level status.
RUN_FORWARD_PASS_ONLY = "forward_pass_only"
RUN_BLOCKED = "blocked"

# Block reasons.
BLOCK_GRAPH_DIAGNOSTIC = "blocked_by_graph_diagnostic"
BLOCK_MISSING_ANCHOR = "missing_start_anchor"

# Per-activity forward_pass_status.
ACT_COMPUTED = "computed"
ACT_MISSING_DURATION = "missing_duration"

# Per-relationship relationship_calc_status.
REL_COMPUTED = "computed"
REL_UNSUPPORTED_TYPE = "unsupported_relationship_type"
REL_UNSUPPORTED_LAG_UNIT = "unsupported_lag_unit"
REL_LAG_UNPARSEABLE = "lag_unparseable"
REL_BLOCKED_PRED_NO_FINISH = "blocked_predecessor_no_finish"
REL_SUCCESSOR_DURATION_UNKNOWN = "successor_duration_unknown"

_OFFSET_DECIMALS = 6


@dataclass
class ForwardPassActivity:
    activity_id: str
    activity_name: str | None
    topological_index: int
    early_start_offset_days: float | None
    early_finish_offset_days: float | None
    computed_early_start: str | None
    computed_early_finish: str | None
    duration_value: float | None
    duration_unit: str
    duration_source: str
    predecessor_count: int
    successor_count: int
    forward_pass_status: str
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ForwardPassRelationship:
    relationship_row_id: Any
    relationship_ref: str
    predecessor_activity_id: str
    successor_activity_id: str
    relationship_type: str | None
    lag_value: Any
    lag_unit: Any
    normalized_lag_days: float | None
    predecessor_early_start_offset: float | None
    predecessor_early_finish_offset: float | None
    candidate_successor_early_start_offset: float | None
    relationship_calc_status: str
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ForwardPassResult:
    run_status: str
    block_reason: str | None
    anchor_iso: str | None
    anchor_source: str | None
    node_count: int
    edge_count: int
    diagnostic_count: int
    computed_activity_count: int
    blocked_activity_count: int
    activities: list[ForwardPassActivity] = field(default_factory=list)
    relationships: list[ForwardPassRelationship] = field(default_factory=list)
    # Always forward_pass — never a full CPM engine.
    calculation_type: str = "forward_pass"
    cpm_recalculation_status: str = RUN_FORWARD_PASS_ONLY


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, _OFFSET_DECIMALS)


def _iso_from_offset(anchor: datetime, offset: float | None) -> str | None:
    if offset is None:
        return None
    return (anchor + timedelta(days=offset)).isoformat()


def _ref(pred: str, succ: str, rel_type: str | None) -> str:
    base = f"{pred}->{succ}"
    return f"{base} ({rel_type})" if rel_type else base


def _resolve_duration_days(
    activity: dict[str, Any], hours_per_day: float
) -> tuple[float | None, str]:
    """Deterministic duration precedence (working-day-equivalent days).

    1. Milestone (``is_milestone``) -> 0.0 (source ``milestone``).
    2. ``duration_original`` normalized via the schedule_quality_normalization helper.
    3. else ``duration_remaining`` normalized.
    4. else None -> missing.

    Never infers duration from early/late dates, float, or critical/driving-path flags.
    """
    if activity.get("is_milestone"):
        return 0.0, "milestone"
    unit = activity.get("duration_unit")
    original = normalize_duration_days(
        duration_value=activity.get("duration_original"),
        duration_unit=unit,
        hours_per_day=hours_per_day,
    )
    if original is not None:
        return original, "duration_original"
    remaining = normalize_duration_days(
        duration_value=activity.get("duration_remaining"),
        duration_unit=unit,
        hours_per_day=hours_per_day,
    )
    if remaining is not None:
        return remaining, "duration_remaining"
    return None, "missing"


def _normalize_lag(
    relationship: dict[str, Any], hours_per_day: float
) -> tuple[float | None, str | None, dict[str, Any]]:
    """Return (normalized_lag_days, status_override, notes).

    status_override is a relationship_calc_status to force, or None to keep computing.
    Missing/empty lag is treated as zero (XER/XML emit "0"); non-empty unparseable lag is
    flagged and excluded; an unknown but numeric unit is flagged unsupported but still
    applied as days so the constraint is not silently dropped.
    """
    raw_value = relationship.get("lag_value")
    raw_unit = relationship.get("lag_unit")
    if raw_value is None or str(raw_value).strip() == "":
        return 0.0, None, {"lag": "missing_assumed_zero"}
    result = normalize_lag_result(raw_value, raw_unit, hours_per_day=hours_per_day)
    if result.conversion_status == "unparseable":
        return None, REL_LAG_UNPARSEABLE, {"lag": "unparseable", "raw_value": str(raw_value)}
    days = float(result.normalized_days) if result.normalized_days is not None else None
    if result.conversion_status == "assumed_days":
        return (
            days,
            REL_UNSUPPORTED_LAG_UNIT,
            {"lag": "unit_unknown_assumed_days", "raw_unit": str(raw_unit)},
        )
    return days, None, {}


def compute_forward_pass(
    activities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    graph_result: GraphBuildResult,
    *,
    anchor: datetime | None,
    anchor_source: str | None,
    calendars: list[dict[str, Any]] | None = None,
) -> ForwardPassResult:
    """Compute a deterministic forward pass over the Phase 1 graph result."""
    calendars = calendars or []
    diagnostic_count = len(graph_result.diagnostics)
    fatal = [d for d in graph_result.diagnostics if d.diagnostic_type in FATAL_GRAPH_DIAGNOSTICS]

    if graph_result.topological_order is None or fatal:
        return ForwardPassResult(
            run_status=RUN_BLOCKED,
            block_reason=BLOCK_GRAPH_DIAGNOSTIC,
            anchor_iso=anchor.isoformat() if anchor else None,
            anchor_source=anchor_source,
            node_count=graph_result.node_count,
            edge_count=graph_result.edge_count,
            diagnostic_count=diagnostic_count,
            computed_activity_count=0,
            blocked_activity_count=0,
            cpm_recalculation_status=RUN_BLOCKED,
        )

    if anchor is None:
        return ForwardPassResult(
            run_status=RUN_BLOCKED,
            block_reason=BLOCK_MISSING_ANCHOR,
            anchor_iso=None,
            anchor_source=anchor_source,
            node_count=graph_result.node_count,
            edge_count=graph_result.edge_count,
            diagnostic_count=diagnostic_count,
            computed_activity_count=0,
            blocked_activity_count=0,
            cpm_recalculation_status=RUN_BLOCKED,
        )

    activity_by_id = {str(a.get("activity_id")): a for a in activities if a.get("activity_id") is not None}

    # Incoming / outgoing relationship maps over present nodes (excluding self-loops, which
    # would have been fatal). Edges referencing missing endpoints were also fatal, so every
    # endpoint here exists.
    incoming: dict[str, list[dict[str, Any]]] = {}
    pred_counts: dict[str, int] = {}
    succ_counts: dict[str, int] = {}
    for rel in relationships:
        pred = str(rel.get("predecessor_activity_id", ""))
        succ = str(rel.get("successor_activity_id", ""))
        if pred == succ or pred not in activity_by_id or succ not in activity_by_id:
            continue
        incoming.setdefault(succ, []).append(rel)
        succ_counts[pred] = succ_counts.get(pred, 0) + 1
        pred_counts[succ] = pred_counts.get(succ, 0) + 1

    es_offsets: dict[str, float] = {}
    ef_offsets: dict[str, float | None] = {}
    duration_by_id: dict[str, float | None] = {}
    activity_results: list[ForwardPassActivity] = []
    relationship_results: list[ForwardPassRelationship] = []
    computed_count = 0
    blocked_count = 0

    for topo_index, activity_id in enumerate(graph_result.topological_order):
        activity = activity_by_id.get(activity_id, {"activity_id": activity_id})
        hpd = calendar_hours_per_day(calendars, activity.get("calendar_id"))
        if hpd <= 0:
            hpd = DEFAULT_HOURS_PER_DAY
        duration_days, duration_source = _resolve_duration_days(activity, hpd)
        duration_by_id[activity_id] = duration_days

        candidates: list[float] = []
        node_notes: dict[str, Any] = {}
        for rel in sorted(
            incoming.get(activity_id, []),
            key=lambda r: (
                str(r.get("predecessor_activity_id", "")),
                str(r.get("relationship_type") or ""),
                str(r.get("relationship_row_id") or ""),
            ),
        ):
            rel_result, candidate = _evaluate_relationship(
                rel,
                successor_id=activity_id,
                successor_duration=duration_days,
                es_offsets=es_offsets,
                ef_offsets=ef_offsets,
                hours_per_day=hpd,
            )
            relationship_results.append(rel_result)
            if candidate is not None:
                candidates.append(candidate)

        if pred_counts.get(activity_id, 0) > 0 and not candidates:
            node_notes["incoming"] = "all_incoming_relationships_noncontributing"

        es = max(candidates) if candidates else 0.0
        es = max(es, 0.0)
        es_offsets[activity_id] = es

        if duration_days is None:
            ef: float | None = None
            status = ACT_MISSING_DURATION
            blocked_count += 1
        else:
            ef = es + duration_days
            status = ACT_COMPUTED
            computed_count += 1
        ef_offsets[activity_id] = ef

        activity_results.append(
            ForwardPassActivity(
                activity_id=activity_id,
                activity_name=activity.get("activity_name"),
                topological_index=topo_index,
                early_start_offset_days=_round(es),
                early_finish_offset_days=_round(ef),
                computed_early_start=_iso_from_offset(anchor, _round(es)),
                computed_early_finish=_iso_from_offset(anchor, _round(ef)),
                duration_value=_round(duration_days),
                duration_unit="day",
                duration_source=duration_source,
                predecessor_count=pred_counts.get(activity_id, 0),
                successor_count=succ_counts.get(activity_id, 0),
                forward_pass_status=status,
                notes=node_notes,
            )
        )

    relationship_results.sort(
        key=lambda r: (r.successor_activity_id, r.predecessor_activity_id, r.relationship_ref)
    )

    return ForwardPassResult(
        run_status=RUN_FORWARD_PASS_ONLY,
        block_reason=None,
        anchor_iso=anchor.isoformat(),
        anchor_source=anchor_source,
        node_count=graph_result.node_count,
        edge_count=graph_result.edge_count,
        diagnostic_count=diagnostic_count,
        computed_activity_count=computed_count,
        blocked_activity_count=blocked_count,
        activities=activity_results,
        relationships=relationship_results,
    )


def _evaluate_relationship(
    relationship: dict[str, Any],
    *,
    successor_id: str,
    successor_duration: float | None,
    es_offsets: dict[str, float],
    ef_offsets: dict[str, float | None],
    hours_per_day: float,
) -> tuple[ForwardPassRelationship, float | None]:
    """Evaluate one relationship and return (result row, candidate successor ES | None)."""
    pred = str(relationship.get("predecessor_activity_id", ""))
    rel_type_raw = relationship.get("relationship_type")
    rel_type = str(rel_type_raw) if rel_type_raw not in (None, "") else None
    pred_es = es_offsets.get(pred)
    pred_ef = ef_offsets.get(pred)

    lag_days, lag_status_override, lag_notes = _normalize_lag(relationship, hours_per_day)

    def build(status: str, candidate: float | None, extra: dict[str, Any] | None = None):
        notes = dict(lag_notes)
        if extra:
            notes.update(extra)
        return (
            ForwardPassRelationship(
                relationship_row_id=relationship.get("relationship_row_id"),
                relationship_ref=_ref(pred, successor_id, rel_type),
                predecessor_activity_id=pred,
                successor_activity_id=successor_id,
                relationship_type=rel_type,
                lag_value=relationship.get("lag_value"),
                lag_unit=relationship.get("lag_unit"),
                normalized_lag_days=_round(lag_days),
                predecessor_early_start_offset=_round(pred_es),
                predecessor_early_finish_offset=_round(pred_ef),
                candidate_successor_early_start_offset=_round(candidate),
                relationship_calc_status=status,
                notes=notes,
            ),
            candidate,
        )

    if rel_type not in SUPPORTED_RELATIONSHIP_TYPES:
        return build(REL_UNSUPPORTED_TYPE, None)
    if lag_status_override == REL_LAG_UNPARSEABLE or lag_days is None:
        return build(REL_LAG_UNPARSEABLE, None)

    # Successful per-type forward-pass constraint. FF/SF derive the successor ES from a
    # finish constraint, so they need the successor's duration.
    if rel_type == "SS":
        candidate = (pred_es or 0.0) + lag_days
    elif rel_type == "FS":
        if pred_ef is None:
            return build(REL_BLOCKED_PRED_NO_FINISH, None)
        candidate = pred_ef + lag_days
    elif rel_type == "FF":
        if pred_ef is None:
            return build(REL_BLOCKED_PRED_NO_FINISH, None)
        if successor_duration is None:
            return build(REL_SUCCESSOR_DURATION_UNKNOWN, None)
        candidate = pred_ef + lag_days - successor_duration
    else:  # SF
        if successor_duration is None:
            return build(REL_SUCCESSOR_DURATION_UNKNOWN, None)
        candidate = (pred_es or 0.0) + lag_days - successor_duration

    status = lag_status_override or REL_COMPUTED
    return build(status, candidate)


__all__ = [
    "ForwardPassActivity",
    "ForwardPassRelationship",
    "ForwardPassResult",
    "compute_forward_pass",
    "SUPPORTED_RELATIONSHIP_TYPES",
    "FATAL_GRAPH_DIAGNOSTICS",
    "RUN_FORWARD_PASS_ONLY",
    "RUN_BLOCKED",
    "BLOCK_GRAPH_DIAGNOSTIC",
    "BLOCK_MISSING_ANCHOR",
]
