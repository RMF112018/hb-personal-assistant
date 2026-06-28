"""CPM backward pass foundation: deterministic late start / late finish computation.

PHASE 3 SCOPE — BACKWARD PASS ONLY. Over the Phase 1 verified acyclic graph and the
persisted Phase 2 forward-pass results, this module computes application-owned late start
(LS) and late finish (LF) for each activity. It is a pure computation layer: it takes the
Phase 1 ``GraphBuildResult`` plus the forward-pass activity/relationship outputs and a
finish anchor, and returns typed result objects. It executes NO SQL.

It deliberately does NOT compute float (total/free/interfering/independent), the longest
path, or the critical path. It NEVER reads or overwrites source-export fields (source
early/late dates, source total float, derived float, source_critical_flag,
source_driving_path_flag, is_critical). Late dates are derived only from the forward-pass
early dates, the durations, the relationship logic, and the finish anchor.

DATE MODEL: identical to Phase 2 — continuous day-offsets from the schedule START anchor
(day 0 = start anchor) are authoritative; a convenience ISO datetime is derived as
``start_anchor + timedelta(days=offset)`` using CALENDAR-day addition (no weekend/holiday/
calendar engine). The finish anchor is expressed as an offset in the same space so the
backward pass stays internally consistent with the forward pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .schedule_cpm_forward_pass import (
    _OFFSET_DECIMALS,
    FATAL_GRAPH_DIAGNOSTICS,
    RUN_BLOCKED,
    SUPPORTED_RELATIONSHIP_TYPES,
)
from .schedule_cpm_graph import GraphBuildResult

# Run-level status.
RUN_BACKWARD_PASS_ONLY = "backward_pass_only"

# Block reasons.
BLOCK_GRAPH_DIAGNOSTIC = "blocked_by_graph_diagnostic"
BLOCK_MISSING_FORWARD_PASS = "blocked_by_missing_forward_pass"
BLOCK_MISSING_FINISH_ANCHOR = "missing_finish_anchor"

# Per-activity backward_pass_status.
ACT_COMPUTED = "computed"
ACT_MISSING_DURATION = "missing_duration"

# Per-relationship backward_relationship_calc_status.
REL_COMPUTED = "computed"
REL_UNSUPPORTED_TYPE = "unsupported_relationship_type"
REL_BLOCKED_SUCC_NO_LATE_START = "blocked_successor_no_late_start"
REL_BLOCKED_SUCC_NO_LATE_FINISH = "blocked_successor_no_late_finish"
REL_PREDECESSOR_DURATION_UNKNOWN = "predecessor_duration_unknown"

# Finish-anchor sources.
ANCHOR_SOURCE_SCHEDULED_FINISH = "source_scheduled_finish"
ANCHOR_SOURCE_PLANNED_FINISH = "source_planned_finish"
ANCHOR_SOURCE_MAX_EARLY_FINISH = "max_forward_early_finish"

# Run-level caveat when an imported finish anchor precedes the forward-pass finish.
CAVEAT_FINISH_BEFORE_FORWARD = "finish_anchor_before_forward_pass_finish"


@dataclass
class BackwardPassActivity:
    activity_id: str
    activity_name: str | None
    topological_index: int | None
    duration_value: float | None
    early_start_offset_days: float | None
    early_finish_offset_days: float | None
    late_start_offset_days: float | None
    late_finish_offset_days: float | None
    computed_late_start: str | None
    computed_late_finish: str | None
    terminal_activity_flag: bool
    controlling_successor_activity_id: str | None
    controlling_successor_relationship_id: str | None
    backward_pass_status: str
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackwardPassRelationship:
    relationship_row_id: Any
    relationship_ref: str
    predecessor_activity_id: str
    successor_activity_id: str
    relationship_type: str | None
    normalized_lag_days: float | None
    candidate_predecessor_late_start: float | None
    candidate_predecessor_late_finish: float | None
    backward_relationship_calc_status: str
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackwardPassResult:
    run_status: str
    block_reason: str | None
    finish_anchor_offset: float | None
    finish_anchor_iso: str | None
    finish_anchor_source: str | None
    finish_anchor_caveat: str | None
    node_count: int
    edge_count: int
    diagnostic_count: int
    late_date_activity_count: int
    late_date_blocked_activity_count: int
    activities: list[BackwardPassActivity] = field(default_factory=list)
    relationships: list[BackwardPassRelationship] = field(default_factory=list)
    calculation_type: str = "backward_pass"
    cpm_recalculation_status: str = RUN_BACKWARD_PASS_ONLY


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, _OFFSET_DECIMALS)


def _iso_from_offset(start_anchor: datetime | None, offset: float | None) -> str | None:
    if offset is None or start_anchor is None:
        return None
    return (start_anchor + timedelta(days=offset)).isoformat()


def resolve_finish_anchor(
    *,
    source_scheduled_finish: datetime | None,
    source_planned_finish: datetime | None,
    max_early_finish_offset: float | None,
    start_anchor: datetime,
) -> tuple[float | None, str | None, str | None]:
    """Deterministic finish-anchor precedence. Returns (offset, source, caveat).

    1. Imported scheduled finish (``finish_date``) — converted to an offset by calendar-day
       delta from the start anchor (consistent with the Phase 2 offset<->ISO mapping).
    2. Imported planned finish (``planned_finish``).
    3. Maximum forward-pass computed early finish offset.
    4. else (None, None, None) -> caller blocks with missing_finish_anchor.

    Uses imported finish dates only — never source early/late finish, float, or critical
    flags. When an imported anchor precedes the forward-pass finish, the offset is still
    returned (do not fail) with caveat ``finish_anchor_before_forward_pass_finish``.
    """
    offset: float | None
    source: str | None
    if source_scheduled_finish is not None:
        offset = round((source_scheduled_finish - start_anchor).days, _OFFSET_DECIMALS)
        source = ANCHOR_SOURCE_SCHEDULED_FINISH
    elif source_planned_finish is not None:
        offset = round((source_planned_finish - start_anchor).days, _OFFSET_DECIMALS)
        source = ANCHOR_SOURCE_PLANNED_FINISH
    elif max_early_finish_offset is not None:
        offset = _round(max_early_finish_offset)
        source = ANCHOR_SOURCE_MAX_EARLY_FINISH
    else:
        return None, None, None

    caveat: str | None = None
    if (
        max_early_finish_offset is not None
        and offset is not None
        and offset < max_early_finish_offset - 1e-9
    ):
        caveat = CAVEAT_FINISH_BEFORE_FORWARD
    return offset, source, caveat


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_backward_pass(
    graph_result: GraphBuildResult,
    forward_activities: list[dict[str, Any]],
    forward_relationships: list[dict[str, Any]],
    *,
    finish_anchor_offset: float | None,
    finish_anchor_source: str | None,
    finish_anchor_caveat: str | None,
    start_anchor: datetime | None,
) -> BackwardPassResult:
    """Compute a deterministic backward pass over the reverse topological order."""
    diagnostic_count = len(graph_result.diagnostics)
    fatal = [d for d in graph_result.diagnostics if d.diagnostic_type in FATAL_GRAPH_DIAGNOSTICS]

    def _blocked(reason: str) -> BackwardPassResult:
        return BackwardPassResult(
            run_status=RUN_BLOCKED,
            block_reason=reason,
            finish_anchor_offset=finish_anchor_offset,
            finish_anchor_iso=_iso_from_offset(start_anchor, finish_anchor_offset),
            finish_anchor_source=finish_anchor_source,
            finish_anchor_caveat=finish_anchor_caveat,
            node_count=graph_result.node_count,
            edge_count=graph_result.edge_count,
            diagnostic_count=diagnostic_count,
            late_date_activity_count=0,
            late_date_blocked_activity_count=0,
            cpm_recalculation_status=RUN_BLOCKED,
        )

    if graph_result.topological_order is None or fatal:
        return _blocked(BLOCK_GRAPH_DIAGNOSTIC)
    if not forward_activities:
        return _blocked(BLOCK_MISSING_FORWARD_PASS)
    if finish_anchor_offset is None:
        return _blocked(BLOCK_MISSING_FINISH_ANCHOR)

    fwd_by_id = {str(a.get("activity_id")): a for a in forward_activities}

    # Outgoing relationship map over present nodes (exclude self-loops / missing endpoints,
    # which would have been fatal). out-degree 0 => terminal activity.
    outgoing: dict[str, list[dict[str, Any]]] = {}
    for rel in forward_relationships:
        pred = str(rel.get("predecessor_activity_id", ""))
        succ = str(rel.get("successor_activity_id", ""))
        if pred == succ or pred not in fwd_by_id or succ not in fwd_by_id:
            continue
        outgoing.setdefault(pred, []).append(rel)

    ls_offsets: dict[str, float | None] = {}
    lf_offsets: dict[str, float | None] = {}
    activity_results: list[BackwardPassActivity] = []
    relationship_results: list[BackwardPassRelationship] = []
    computed_count = 0
    blocked_count = 0

    for activity_id in reversed(graph_result.topological_order):
        fwd = fwd_by_id.get(activity_id, {})
        duration = _as_float(fwd.get("duration_value"))
        successors = sorted(
            outgoing.get(activity_id, []),
            key=lambda r: (
                str(r.get("successor_activity_id", "")),
                str(r.get("relationship_type") or ""),
                str(r.get("relationship_row_id") or ""),
            ),
        )
        notes: dict[str, Any] = {}

        if not successors:
            # Terminal activity: late finish is the schedule finish anchor.
            lf: float | None = finish_anchor_offset
            terminal = True
            controlling_activity = None
            controlling_rel = None
        else:
            terminal = False
            best_lf: float | None = None
            controlling_activity = None
            controlling_rel = None
            for rel in successors:
                rel_result, cand_lf = _evaluate_relationship(
                    rel,
                    predecessor_id=activity_id,
                    predecessor_duration=duration,
                    ls_offsets=ls_offsets,
                    lf_offsets=lf_offsets,
                )
                relationship_results.append(rel_result)
                if cand_lf is not None and (best_lf is None or cand_lf < best_lf):
                    best_lf = cand_lf
                    controlling_activity = str(rel.get("successor_activity_id", ""))
                    controlling_rel = rel_result.relationship_ref
            lf = best_lf
            if lf is None and successors:
                notes["successors"] = "no_successor_relationship_contributed_late_finish"

        if lf is None:
            ls: float | None = None
        elif duration is None:
            ls = None
        else:
            ls = lf - duration

        lf_offsets[activity_id] = _round(lf)
        ls_offsets[activity_id] = _round(ls)

        if duration is None:
            status = ACT_MISSING_DURATION
            blocked_count += 1
        else:
            status = ACT_COMPUTED
            computed_count += 1

        activity_results.append(
            BackwardPassActivity(
                activity_id=activity_id,
                activity_name=fwd.get("activity_name"),
                topological_index=fwd.get("topological_index"),
                duration_value=_round(duration),
                early_start_offset_days=_as_float(fwd.get("early_start_offset_days")),
                early_finish_offset_days=_as_float(fwd.get("early_finish_offset_days")),
                late_start_offset_days=_round(ls),
                late_finish_offset_days=_round(lf),
                computed_late_start=_iso_from_offset(start_anchor, _round(ls)),
                computed_late_finish=_iso_from_offset(start_anchor, _round(lf)),
                terminal_activity_flag=terminal,
                controlling_successor_activity_id=controlling_activity,
                controlling_successor_relationship_id=controlling_rel,
                backward_pass_status=status,
                notes=notes,
            )
        )

    relationship_results.sort(
        key=lambda r: (r.predecessor_activity_id, r.successor_activity_id, r.relationship_ref)
    )

    return BackwardPassResult(
        run_status=RUN_BACKWARD_PASS_ONLY,
        block_reason=None,
        finish_anchor_offset=_round(finish_anchor_offset),
        finish_anchor_iso=_iso_from_offset(start_anchor, finish_anchor_offset),
        finish_anchor_source=finish_anchor_source,
        finish_anchor_caveat=finish_anchor_caveat,
        node_count=graph_result.node_count,
        edge_count=graph_result.edge_count,
        diagnostic_count=diagnostic_count,
        late_date_activity_count=computed_count,
        late_date_blocked_activity_count=blocked_count,
        activities=activity_results,
        relationships=relationship_results,
    )


def _evaluate_relationship(
    relationship: dict[str, Any],
    *,
    predecessor_id: str,
    predecessor_duration: float | None,
    ls_offsets: dict[str, float | None],
    lf_offsets: dict[str, float | None],
) -> tuple[BackwardPassRelationship, float | None]:
    """Evaluate one outgoing relationship; return (result row, candidate predecessor LF).

    Mirrors the Phase 2 forward formulas in reverse. The successor's late dates are already
    computed (reverse topological order). LS = LF - duration, so SS/SF candidates (which
    constrain the predecessor LS) are converted to an LF-equivalent for the controlling
    minimum.
    """
    succ_id = str(relationship.get("successor_activity_id", ""))
    rel_type_raw = relationship.get("relationship_type")
    rel_type = str(rel_type_raw) if rel_type_raw not in (None, "") else None
    lag = _as_float(relationship.get("normalized_lag_days"))
    succ_ls = ls_offsets.get(succ_id)
    succ_lf = lf_offsets.get(succ_id)
    ref = relationship.get("relationship_ref") or f"{predecessor_id}->{succ_id}"

    def build(status: str, cand_ls: float | None, cand_lf: float | None, extra=None):
        notes: dict[str, Any] = {}
        if extra:
            notes.update(extra)
        return (
            BackwardPassRelationship(
                relationship_row_id=relationship.get("relationship_row_id"),
                relationship_ref=str(ref),
                predecessor_activity_id=predecessor_id,
                successor_activity_id=succ_id,
                relationship_type=rel_type,
                normalized_lag_days=_round(lag),
                candidate_predecessor_late_start=_round(cand_ls),
                candidate_predecessor_late_finish=_round(cand_lf),
                backward_relationship_calc_status=status,
                notes=notes,
            ),
            cand_lf,
        )

    if rel_type not in SUPPORTED_RELATIONSHIP_TYPES:
        return build(REL_UNSUPPORTED_TYPE, None, None)
    lag = lag if lag is not None else 0.0

    # FS/SS constrain via the successor LS; FF/SF via the successor LF.
    if rel_type in ("FS", "SS") and succ_ls is None:
        return build(REL_BLOCKED_SUCC_NO_LATE_START, None, None)
    if rel_type in ("FF", "SF") and succ_lf is None:
        return build(REL_BLOCKED_SUCC_NO_LATE_FINISH, None, None)

    if rel_type == "FS":
        cand_lf = succ_ls - lag
        cand_ls = cand_lf - predecessor_duration if predecessor_duration is not None else None
        return build(REL_COMPUTED, cand_ls, cand_lf)
    if rel_type == "FF":
        cand_lf = succ_lf - lag
        cand_ls = cand_lf - predecessor_duration if predecessor_duration is not None else None
        return build(REL_COMPUTED, cand_ls, cand_lf)

    # SS / SF constrain the predecessor LS; convert to LF using the predecessor duration.
    # SS reads the successor LS, SF the successor LF (both guarded non-None above).
    if predecessor_duration is None:
        return build(REL_PREDECESSOR_DURATION_UNKNOWN, None, None)
    cand_ls = succ_ls - lag if rel_type == "SS" else succ_lf - lag
    cand_lf = cand_ls + predecessor_duration
    return build(REL_COMPUTED, cand_ls, cand_lf)


__all__ = [
    "BackwardPassActivity",
    "BackwardPassRelationship",
    "BackwardPassResult",
    "compute_backward_pass",
    "resolve_finish_anchor",
    "RUN_BACKWARD_PASS_ONLY",
    "RUN_BLOCKED",
    "BLOCK_GRAPH_DIAGNOSTIC",
    "BLOCK_MISSING_FORWARD_PASS",
    "BLOCK_MISSING_FINISH_ANCHOR",
    "CAVEAT_FINISH_BEFORE_FORWARD",
    "ANCHOR_SOURCE_SCHEDULED_FINISH",
    "ANCHOR_SOURCE_PLANNED_FINISH",
    "ANCHOR_SOURCE_MAX_EARLY_FINISH",
]
