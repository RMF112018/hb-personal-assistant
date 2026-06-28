"""CPM float foundation: deterministic total float / free float from CPM offsets.

PHASE 4 SCOPE — FLOAT ONLY. Computes application-owned total float and (where cleanly
supported) free float for each activity, derived ONLY from the application-owned early/late
day-offsets already produced by Phase 2 (forward pass) and Phase 3 (backward pass). It is a
pure computation layer: it takes the Phase 1 ``GraphBuildResult`` plus the persisted
backward-run activity/relationship result rows, and returns typed result objects. It
executes NO SQL.

It deliberately does NOT compute or expose the critical path or the longest path, and it
NEVER marks an activity critical (a zero total float is NOT criticality in this phase). It
NEVER reads or overwrites imported/source float or source early/late/critical/driving-path
fields — every input is an application-computed offset from Phases 2–3.

DATE MODEL: same as Phases 2–3 — continuous working-day-equivalent day-offsets. Negative and
fractional float are preserved; values are never clamped to zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schedule_cpm_forward_pass import (
    _OFFSET_DECIMALS,
    FATAL_GRAPH_DIAGNOSTICS,
    RUN_BLOCKED,
    SUPPORTED_RELATIONSHIP_TYPES,
)
from .schedule_cpm_graph import GraphBuildResult

# Run-level.
RUN_FLOAT_ONLY = "float_only"
CPM_STATUS = "forward_backward_float_only"

# Block reasons.
BLOCK_GRAPH_DIAGNOSTIC = "blocked_by_graph_diagnostic"
BLOCK_MISSING_FORWARD_PASS = "blocked_by_missing_forward_pass"
BLOCK_MISSING_BACKWARD_PASS = "blocked_by_missing_backward_pass"

# Total-float status.
TF_COMPUTED = "computed"
TF_MISSING_EARLY_LATE = "missing_early_late_values"
TF_INCONSISTENT = "inconsistent_start_finish_float"

# Free-float status.
FF_COMPUTED = "computed"
FF_NOT_APPLICABLE_TERMINAL = "not_applicable_terminal_activity"
FF_UNSUPPORTED_TYPE = "unsupported_relationship_type"
FF_MISSING_SUCCESSOR_EARLY = "missing_successor_early_values"

# Basis labels.
TF_BASIS_START = "late_start_minus_early_start"
TF_BASIS_FINISH = "late_finish_minus_early_finish"

_FLOAT_TOL = 1e-6


@dataclass
class FloatActivity:
    activity_id: str
    topological_index: int | None
    computed_total_float: float | None
    computed_total_float_basis: str | None
    computed_total_float_status: str
    total_float_notes: dict[str, Any]
    computed_free_float: float | None
    computed_free_float_basis: str | None
    computed_free_float_status: str
    free_float_notes: dict[str, Any]
    controlling_free_float_successor_activity_id: str | None
    controlling_free_float_relationship_id: str | None


@dataclass
class FloatRelationship:
    relationship_row_id: Any
    relationship_ref: str
    predecessor_activity_id: str
    successor_activity_id: str
    relationship_type: str | None
    free_float_candidate: float | None
    free_float_candidate_status: str
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class FloatResult:
    run_status: str
    block_reason: str | None
    node_count: int
    edge_count: int
    diagnostic_count: int
    total_float_computed_count: int
    free_float_computed_count: int
    blocked_activity_count: int
    activities: list[FloatActivity] = field(default_factory=list)
    relationships: list[FloatRelationship] = field(default_factory=list)
    calculation_type: str = "float"
    cpm_recalculation_status: str = CPM_STATUS


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, _OFFSET_DECIMALS)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_float(
    graph_result: GraphBuildResult,
    cpm_activities: list[dict[str, Any]],
    cpm_relationships: list[dict[str, Any]],
) -> FloatResult:
    """Compute deterministic total/free float from persisted CPM (Phase 2/3) offsets."""
    diagnostic_count = len(graph_result.diagnostics)
    fatal = [d for d in graph_result.diagnostics if d.diagnostic_type in FATAL_GRAPH_DIAGNOSTICS]

    def _blocked(reason: str) -> FloatResult:
        return FloatResult(
            run_status=RUN_BLOCKED,
            block_reason=reason,
            node_count=graph_result.node_count,
            edge_count=graph_result.edge_count,
            diagnostic_count=diagnostic_count,
            total_float_computed_count=0,
            free_float_computed_count=0,
            blocked_activity_count=0,
            cpm_recalculation_status=RUN_BLOCKED,
        )

    if graph_result.topological_order is None or fatal:
        return _blocked(BLOCK_GRAPH_DIAGNOSTIC)
    if not cpm_activities:
        # Caller distinguishes missing forward vs backward; default to backward here.
        return _blocked(BLOCK_MISSING_BACKWARD_PASS)

    by_id = {str(a.get("activity_id")): a for a in cpm_activities}

    outgoing: dict[str, list[dict[str, Any]]] = {}
    for rel in cpm_relationships:
        pred = str(rel.get("predecessor_activity_id", ""))
        succ = str(rel.get("successor_activity_id", ""))
        if pred == succ or pred not in by_id or succ not in by_id:
            continue
        outgoing.setdefault(pred, []).append(rel)

    activity_results: list[FloatActivity] = []
    relationship_results: list[FloatRelationship] = []
    total_computed = 0
    free_computed = 0
    blocked = 0

    for activity_id in graph_result.topological_order:
        row = by_id.get(activity_id, {})
        tf_value, tf_basis, tf_status, tf_notes = _total_float(row)
        if tf_status == TF_COMPUTED:
            total_computed += 1
        else:
            blocked += 1

        successors = sorted(
            outgoing.get(activity_id, []),
            key=lambda r: (str(r.get("successor_activity_id", "")), str(r.get("relationship_ref") or "")),
        )
        ff = _free_float(activity_id, row, successors, by_id)
        relationship_results.extend(ff.relationship_rows)
        if ff.status == FF_COMPUTED and ff.value is not None:
            free_computed += 1

        activity_results.append(
            FloatActivity(
                activity_id=activity_id,
                topological_index=row.get("topological_index"),
                computed_total_float=tf_value,
                computed_total_float_basis=tf_basis,
                computed_total_float_status=tf_status,
                total_float_notes=tf_notes,
                computed_free_float=ff.value,
                computed_free_float_basis=ff.basis,
                computed_free_float_status=ff.status,
                free_float_notes=ff.notes,
                controlling_free_float_successor_activity_id=ff.controlling_successor,
                controlling_free_float_relationship_id=ff.controlling_relationship,
            )
        )

    relationship_results.sort(
        key=lambda r: (r.predecessor_activity_id, r.successor_activity_id, r.relationship_ref)
    )

    return FloatResult(
        run_status=RUN_FLOAT_ONLY,
        block_reason=None,
        node_count=graph_result.node_count,
        edge_count=graph_result.edge_count,
        diagnostic_count=diagnostic_count,
        total_float_computed_count=total_computed,
        free_float_computed_count=free_computed,
        blocked_activity_count=blocked,
        activities=activity_results,
        relationships=relationship_results,
    )


def _total_float(
    row: dict[str, Any],
) -> tuple[float | None, str | None, str, dict[str, Any]]:
    es = _as_float(row.get("early_start_offset_days"))
    ef = _as_float(row.get("early_finish_offset_days"))
    ls = _as_float(row.get("late_start_offset_days"))
    lf = _as_float(row.get("late_finish_offset_days"))
    start_tf = ls - es if (ls is not None and es is not None) else None
    finish_tf = lf - ef if (lf is not None and ef is not None) else None

    if start_tf is not None and finish_tf is not None:
        if abs(start_tf - finish_tf) <= _FLOAT_TOL:
            return _round(start_tf), TF_BASIS_START, TF_COMPUTED, {}
        # Conservative: keep the start-based value but flag the mismatch.
        return (
            _round(start_tf),
            TF_BASIS_START,
            TF_INCONSISTENT,
            {
                "start_based_total_float": _round(start_tf),
                "finish_based_total_float": _round(finish_tf),
            },
        )
    if start_tf is not None:
        return _round(start_tf), TF_BASIS_START, TF_COMPUTED, {"basis": "start_only"}
    if finish_tf is not None:
        return _round(finish_tf), TF_BASIS_FINISH, TF_COMPUTED, {"basis": "finish_only"}
    return None, None, TF_MISSING_EARLY_LATE, {}


@dataclass
class _FreeFloatOutcome:
    value: float | None
    basis: str | None
    status: str
    notes: dict[str, Any]
    controlling_successor: str | None
    controlling_relationship: str | None
    relationship_rows: list[FloatRelationship]


def _free_float(
    activity_id: str,
    row: dict[str, Any],
    successors: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> _FreeFloatOutcome:
    if not successors:
        # Terminal: free float is not applicable; NULL (not 0) avoids implying criticality.
        return _FreeFloatOutcome(None, None, FF_NOT_APPLICABLE_TERMINAL, {}, None, None, [])

    pred_es = _as_float(row.get("early_start_offset_days"))
    pred_ef = _as_float(row.get("early_finish_offset_days"))

    rel_rows: list[FloatRelationship] = []
    candidates: list[tuple[float, str, str]] = []
    all_supported = True
    missing_succ = False

    for rel in successors:
        succ = str(rel.get("successor_activity_id", ""))
        rel_type_raw = rel.get("relationship_type")
        rel_type = str(rel_type_raw) if rel_type_raw not in (None, "") else None
        ref = str(rel.get("relationship_ref") or f"{activity_id}->{succ}")
        lag = _as_float(rel.get("normalized_lag_days")) or 0.0
        succ_row = by_id.get(succ, {})
        succ_es = _as_float(succ_row.get("early_start_offset_days"))
        succ_ef = _as_float(succ_row.get("early_finish_offset_days"))

        cand: float | None
        status: str
        if rel_type not in SUPPORTED_RELATIONSHIP_TYPES:
            cand, status, all_supported = None, FF_UNSUPPORTED_TYPE, False
        elif rel_type == "FS":
            cand = (
                succ_es - pred_ef - lag
                if (succ_es is not None and pred_ef is not None)
                else None
            )
            status = FF_COMPUTED if cand is not None else FF_MISSING_SUCCESSOR_EARLY
        elif rel_type == "SS":
            cand = (
                succ_es - pred_es - lag
                if (succ_es is not None and pred_es is not None)
                else None
            )
            status = FF_COMPUTED if cand is not None else FF_MISSING_SUCCESSOR_EARLY
        elif rel_type == "FF":
            cand = (
                succ_ef - pred_ef - lag
                if (succ_ef is not None and pred_ef is not None)
                else None
            )
            status = FF_COMPUTED if cand is not None else FF_MISSING_SUCCESSOR_EARLY
        else:  # SF
            cand = (
                succ_ef - pred_es - lag
                if (succ_ef is not None and pred_es is not None)
                else None
            )
            status = FF_COMPUTED if cand is not None else FF_MISSING_SUCCESSOR_EARLY

        if status == FF_MISSING_SUCCESSOR_EARLY:
            missing_succ = True
        rel_rows.append(
            FloatRelationship(
                relationship_row_id=rel.get("relationship_row_id"),
                relationship_ref=ref,
                predecessor_activity_id=activity_id,
                successor_activity_id=succ,
                relationship_type=rel_type,
                free_float_candidate=_round(cand),
                free_float_candidate_status=status,
                notes={} if cand is not None else {"reason": status},
            )
        )
        if cand is not None:
            candidates.append((cand, succ, ref))

    # Free float is only trustworthy when every successor relationship is supported and has
    # the needed successor early values; otherwise mark (do not emit a misleading minimum).
    if not all_supported:
        return _FreeFloatOutcome(None, None, FF_UNSUPPORTED_TYPE, {}, None, None, rel_rows)
    if missing_succ or not candidates:
        return _FreeFloatOutcome(
            None, None, FF_MISSING_SUCCESSOR_EARLY, {}, None, None, rel_rows
        )

    best = min(candidates, key=lambda c: (c[0], c[1], c[2]))
    return _FreeFloatOutcome(
        value=_round(best[0]),
        basis="min_successor_early_constraint",
        status=FF_COMPUTED,
        notes={},
        controlling_successor=best[1],
        controlling_relationship=best[2],
        relationship_rows=rel_rows,
    )


__all__ = [
    "FloatActivity",
    "FloatRelationship",
    "FloatResult",
    "compute_float",
    "RUN_FLOAT_ONLY",
    "RUN_BLOCKED",
    "CPM_STATUS",
    "BLOCK_GRAPH_DIAGNOSTIC",
    "BLOCK_MISSING_FORWARD_PASS",
    "BLOCK_MISSING_BACKWARD_PASS",
    "TF_INCONSISTENT",
    "FF_NOT_APPLICABLE_TERMINAL",
    "FF_UNSUPPORTED_TYPE",
    "FF_MISSING_SUCCESSOR_EARLY",
]
