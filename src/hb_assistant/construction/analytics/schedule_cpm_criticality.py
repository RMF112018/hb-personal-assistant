"""CPM criticality foundation: application-computed critical / near-critical classification.

PHASE 6 SCOPE — CRITICALITY CLASSIFICATION ONLY. Classifies each activity as computed
critical / near-critical / noncritical using the application-computed TOTAL FLOAT from
Phase 4, with Phase 5 longest-path membership recorded as CONTEXT only. It is a pure
computation layer: it takes the Phase 1 ``GraphBuildResult`` plus the persisted Phase 4
float-run activity rows and Phase 5 longest-path membership rows, and returns typed result
objects. It executes NO SQL.

THIS IS APPLICATION-COMPUTED CRITICALITY, NOT DCMA CRITICAL-PATH COMPLIANCE. It does NOT
integrate or relabel the DCMA critical-path metric, does NOT mutate ``is_critical``, and
NEVER reads or reinterprets imported/source critical/driving-path/float/early/late fields as
computation inputs. Longest-path membership is contextual evidence only and NEVER overrides
the total-float classification. Negative float is preserved (classifies critical), never
clamped.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .schedule_cpm_forward_pass import (
    FATAL_GRAPH_DIAGNOSTICS,
    RUN_BLOCKED,
)
from .schedule_cpm_graph import GraphBuildResult

RUN_CRITICALITY_ONLY = "criticality_classification_only"
CRITICALITY_BASIS = "computed_total_float_threshold"
MEMBERSHIP_BASIS = "longest_path_run_membership"

DEFAULT_CRITICAL_THRESHOLD = 0.0
DEFAULT_NEAR_CRITICAL_THRESHOLD = 10.0
_TOL = 1e-6

# Block reasons (run-level).
BLOCK_INVALID_THRESHOLDS = "invalid_criticality_thresholds"
BLOCK_GRAPH_DIAGNOSTIC = "blocked_by_graph_diagnostic"
BLOCK_MISSING_FLOAT_RUN = "blocked_by_missing_float_run"
BLOCK_MISSING_LONGEST_PATH_RUN = "blocked_by_missing_longest_path_run"

# Classes.
CLASS_CRITICAL = "computed_critical"
CLASS_NEAR_CRITICAL = "computed_near_critical"
CLASS_NONCRITICAL = "computed_noncritical"
CLASS_UNCLASSIFIED = "unclassified"

# Per-activity status.
STATUS_COMPUTED = "computed"
STATUS_MISSING_TOTAL_FLOAT = "missing_computed_total_float"

# Caveats (notes only — never override the class).
CAVEAT_ZERO_FLOAT_NOT_ON_LP = "zero_float_not_on_longest_path"
CAVEAT_LP_MEMBER_NOT_CRITICAL = "longest_path_member_not_zero_float"
CAVEAT_NEGATIVE_FLOAT = "negative_total_float"
CAVEAT_THRESHOLD_BOUNDARY = "threshold_boundary_value"


@dataclass
class CriticalityActivity:
    activity_id: str
    activity_name: str | None
    topological_index: int | None
    computed_total_float: float | None
    computed_free_float: float | None
    computed_critical_flag: bool
    computed_near_critical_flag: bool
    computed_criticality_class: str
    computed_criticality_status: str
    computed_criticality_basis: str | None
    critical_float_threshold_days: float
    near_critical_float_threshold_days: float
    longest_path_member_flag: bool
    longest_path_sequence: int | None
    longest_path_membership_basis: str | None
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class CriticalityResult:
    run_status: str
    block_reason: str | None
    node_count: int
    edge_count: int
    diagnostic_count: int
    critical_float_threshold_days: float
    near_critical_float_threshold_days: float
    computed_critical_activity_count: int
    computed_near_critical_activity_count: int
    computed_noncritical_activity_count: int
    unclassified_activity_count: int
    longest_path_member_count: int
    caveat_count: int
    activities: list[CriticalityActivity] = field(default_factory=list)
    calculation_type: str = "criticality"
    cpm_recalculation_status: str = RUN_CRITICALITY_ONLY


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def compute_criticality(
    graph_result: GraphBuildResult,
    float_activities: list[dict[str, Any]],
    longest_path_activities: list[dict[str, Any]],
    *,
    critical_threshold_days: float = DEFAULT_CRITICAL_THRESHOLD,
    near_critical_threshold_days: float = DEFAULT_NEAR_CRITICAL_THRESHOLD,
    tolerance: float = _TOL,
) -> CriticalityResult:
    """Classify activities by application-computed total float (longest-path = context)."""
    diagnostic_count = len(graph_result.diagnostics)

    def _blocked(reason: str) -> CriticalityResult:
        return CriticalityResult(
            run_status=RUN_BLOCKED,
            block_reason=reason,
            node_count=graph_result.node_count,
            edge_count=graph_result.edge_count,
            diagnostic_count=diagnostic_count,
            critical_float_threshold_days=_as_float(critical_threshold_days) or 0.0,
            near_critical_float_threshold_days=_as_float(near_critical_threshold_days) or 0.0,
            computed_critical_activity_count=0,
            computed_near_critical_activity_count=0,
            computed_noncritical_activity_count=0,
            unclassified_activity_count=0,
            longest_path_member_count=0,
            caveat_count=0,
            cpm_recalculation_status=RUN_BLOCKED,
        )

    # Validate operator-supplied thresholds BEFORE any classification.
    if (
        not _is_finite_number(critical_threshold_days)
        or not _is_finite_number(near_critical_threshold_days)
        or not _is_finite_number(tolerance)
        or tolerance < 0
        or critical_threshold_days > near_critical_threshold_days
    ):
        return _blocked(BLOCK_INVALID_THRESHOLDS)

    fatal = [d for d in graph_result.diagnostics if d.diagnostic_type in FATAL_GRAPH_DIAGNOSTICS]
    if graph_result.topological_order is None or fatal:
        return _blocked(BLOCK_GRAPH_DIAGNOSTIC)
    if not float_activities:
        # Caller distinguishes missing float vs longest-path; default to float here.
        return _blocked(BLOCK_MISSING_FLOAT_RUN)

    membership: dict[str, dict[str, Any]] = {}
    for row in longest_path_activities:
        aid = str(row.get("activity_id"))
        if aid not in membership:
            membership[aid] = row

    by_id = {str(a.get("activity_id")): a for a in float_activities}

    activities: list[CriticalityActivity] = []
    critical = near = noncritical = unclassified = members = caveats = 0

    for activity_id in graph_result.topological_order:
        row = by_id.get(activity_id)
        if row is None:
            continue
        tf = _as_float(row.get("computed_total_float"))
        member = membership.get(activity_id)
        lp_seq = member.get("path_sequence") if member else None
        is_member = member is not None
        if is_member:
            members += 1

        notes: dict[str, Any] = {}
        if tf is None:
            cls, status, crit_flag, near_flag = (
                CLASS_UNCLASSIFIED, STATUS_MISSING_TOTAL_FLOAT, False, False,
            )
            unclassified += 1
        else:
            status = STATUS_COMPUTED
            if tf <= critical_threshold_days + tolerance:
                cls, crit_flag, near_flag = CLASS_CRITICAL, True, False
                critical += 1
            elif tf <= near_critical_threshold_days + tolerance:
                cls, crit_flag, near_flag = CLASS_NEAR_CRITICAL, False, True
                near += 1
            else:
                cls, crit_flag, near_flag = CLASS_NONCRITICAL, False, False
                noncritical += 1
            # Caveats (do NOT change the class).
            if tf < 0:
                notes[CAVEAT_NEGATIVE_FLOAT] = tf
            if (
                abs(tf - critical_threshold_days) <= tolerance
                or abs(tf - near_critical_threshold_days) <= tolerance
            ):
                notes.setdefault("boundary", CAVEAT_THRESHOLD_BOUNDARY)
            if crit_flag and not is_member:
                notes[CAVEAT_ZERO_FLOAT_NOT_ON_LP] = True
            if is_member and not crit_flag:
                notes[CAVEAT_LP_MEMBER_NOT_CRITICAL] = True

        if notes:
            caveats += 1

        activities.append(
            CriticalityActivity(
                activity_id=activity_id,
                activity_name=row.get("activity_name"),
                topological_index=(
                    row.get("topological_index")
                    if isinstance(row.get("topological_index"), int)
                    else None
                ),
                computed_total_float=tf,
                computed_free_float=_as_float(row.get("computed_free_float")),
                computed_critical_flag=crit_flag,
                computed_near_critical_flag=near_flag,
                computed_criticality_class=cls,
                computed_criticality_status=status,
                computed_criticality_basis=(CRITICALITY_BASIS if tf is not None else None),
                critical_float_threshold_days=float(critical_threshold_days),
                near_critical_float_threshold_days=float(near_critical_threshold_days),
                longest_path_member_flag=is_member,
                longest_path_sequence=lp_seq if isinstance(lp_seq, int) else None,
                longest_path_membership_basis=(MEMBERSHIP_BASIS if is_member else None),
                notes=notes,
            )
        )

    return CriticalityResult(
        run_status=RUN_CRITICALITY_ONLY,
        block_reason=None,
        node_count=graph_result.node_count,
        edge_count=graph_result.edge_count,
        diagnostic_count=diagnostic_count,
        critical_float_threshold_days=float(critical_threshold_days),
        near_critical_float_threshold_days=float(near_critical_threshold_days),
        computed_critical_activity_count=critical,
        computed_near_critical_activity_count=near,
        computed_noncritical_activity_count=noncritical,
        unclassified_activity_count=unclassified,
        longest_path_member_count=members,
        caveat_count=caveats,
        activities=activities,
    )


# Whitelist of app-owned CPM fields the criticality run copies from the float-run row.
# Never blind-copy the whole row; source-export fields must never be carried across.
FLOAT_ROW_WHITELIST: tuple[str, ...] = (
    "activity_id",
    "activity_name",
    "topological_index",
    "computed_early_start",
    "computed_early_finish",
    "computed_late_start",
    "computed_late_finish",
    "early_start_offset_days",
    "early_finish_offset_days",
    "late_start_offset_days",
    "late_finish_offset_days",
    "computed_total_float",
    "computed_free_float",
    "duration_value",
    "duration_unit",
    "duration_source",
    "predecessor_count",
    "successor_count",
)


__all__ = [
    "CriticalityActivity",
    "CriticalityResult",
    "compute_criticality",
    "FLOAT_ROW_WHITELIST",
    "RUN_CRITICALITY_ONLY",
    "RUN_BLOCKED",
    "DEFAULT_CRITICAL_THRESHOLD",
    "DEFAULT_NEAR_CRITICAL_THRESHOLD",
    "BLOCK_INVALID_THRESHOLDS",
    "BLOCK_GRAPH_DIAGNOSTIC",
    "BLOCK_MISSING_FLOAT_RUN",
    "BLOCK_MISSING_LONGEST_PATH_RUN",
    "CLASS_CRITICAL",
    "CLASS_NEAR_CRITICAL",
    "CLASS_NONCRITICAL",
    "CLASS_UNCLASSIFIED",
    "CAVEAT_NEGATIVE_FLOAT",
    "CAVEAT_ZERO_FLOAT_NOT_ON_LP",
    "CAVEAT_LP_MEMBER_NOT_CRITICAL",
]
