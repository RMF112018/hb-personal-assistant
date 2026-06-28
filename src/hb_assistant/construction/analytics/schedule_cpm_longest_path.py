"""CPM longest path foundation: deterministic application-computed longest path.

PHASE 5 SCOPE — LONGEST PATH ONLY. Identifies the deterministic chain of activities that
controls the maximum computed early finish in the application-owned forward-pass result set,
traced backward through controlling predecessor relationships. It is a pure computation
layer: it takes the Phase 1 ``GraphBuildResult`` plus the persisted Phase 4 float-run
activity/relationship rows (which carry the combined early/late/float fields and the Phase 2
forward candidate per relationship), and returns typed result objects. It executes NO SQL.

THIS IS A LONGEST-PATH BASIS, NOT A CRITICAL-PATH DECLARATION. It does NOT mark any activity
critical, add a computed critical flag, compute a near-critical path, apply a total-float
threshold, or integrate/relabel the DCMA critical-path metric. It NEVER reads or overwrites
imported/source critical/driving-path/float/early/late fields — every input is an
application-computed value from Phases 2–4.

Conservative degradation: unsupported or unreconstructable relationship types encountered
during the backtrace are recorded as explicit caveats (never silently skipped); if no
supported candidate cleanly controls the current activity's early value, the backtrace stops
conservatively with a degraded status rather than walking past it or faking precision.
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

RUN_LONGEST_PATH_ONLY = "longest_path_only"
PATH_TYPE_LONGEST = "longest_path"
PATH_BASIS = "max_forward_early_finish_backtrace"

# Block reasons (run-level).
BLOCK_GRAPH_DIAGNOSTIC = "blocked_by_graph_diagnostic"
BLOCK_MISSING_FORWARD_PASS = "blocked_by_missing_forward_pass"
BLOCK_MISSING_FLOAT_RUN = "blocked_by_missing_float_run"

# Path statuses.
PATH_COMPUTED = "computed"
PATH_DEGRADED_PARTIAL = "degraded_partial_backtrace"
PATH_UNSUPPORTED_TYPE = "unsupported_relationship_type"
PATH_MISSING_CANDIDATE = "missing_candidate_relationship"

_TOL = 1e-6
_ANCHOR_OFFSET = 0.0  # forward pass floors early start at the schedule anchor (day 0)


@dataclass
class LongestPathActivity:
    path_sequence: int
    activity_id: str
    activity_name: str | None
    relationship_from_previous_id: Any
    relationship_from_previous_ref: str | None
    computed_early_start: str | None
    computed_early_finish: str | None
    computed_late_start: str | None
    computed_late_finish: str | None
    early_start_offset_days: float | None
    early_finish_offset_days: float | None
    computed_total_float: float | None
    computed_free_float: float | None
    duration_value: float | None
    topological_index: int | None
    selection_basis: str
    selection_notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class LongestPathSummary:
    start_activity_id: str | None
    end_activity_id: str | None
    activity_count: int
    relationship_count: int
    path_start_offset_days: float | None
    path_finish_offset_days: float | None
    path_duration: float | None
    path_total_float: float | None
    path_basis: str
    path_status: str
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class LongestPathResult:
    run_status: str
    block_reason: str | None
    node_count: int
    edge_count: int
    diagnostic_count: int
    path_count: int
    summary: LongestPathSummary | None
    activities: list[LongestPathActivity] = field(default_factory=list)
    calculation_type: str = "longest_path"
    cpm_recalculation_status: str = RUN_LONGEST_PATH_ONLY


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


def compute_longest_path(
    graph_result: GraphBuildResult,
    float_activities: list[dict[str, Any]],
    float_relationships: list[dict[str, Any]],
) -> LongestPathResult:
    """Identify the deterministic longest path from the persisted CPM (Phase 2/4) results."""
    diagnostic_count = len(graph_result.diagnostics)
    fatal = [d for d in graph_result.diagnostics if d.diagnostic_type in FATAL_GRAPH_DIAGNOSTICS]

    def _blocked(reason: str) -> LongestPathResult:
        return LongestPathResult(
            run_status=RUN_BLOCKED,
            block_reason=reason,
            node_count=graph_result.node_count,
            edge_count=graph_result.edge_count,
            diagnostic_count=diagnostic_count,
            path_count=0,
            summary=None,
            cpm_recalculation_status=RUN_BLOCKED,
        )

    if graph_result.topological_order is None or fatal:
        return _blocked(BLOCK_GRAPH_DIAGNOSTIC)
    if not float_activities:
        # Caller distinguishes missing forward vs float; default to float here.
        return _blocked(BLOCK_MISSING_FLOAT_RUN)

    by_id = {str(a.get("activity_id")): a for a in float_activities}

    # incoming[successor] = list of relationship rows controlling that successor.
    incoming: dict[str, list[dict[str, Any]]] = {}
    for rel in float_relationships:
        pred = str(rel.get("predecessor_activity_id", ""))
        succ = str(rel.get("successor_activity_id", ""))
        if pred == succ or pred not in by_id or succ not in by_id:
            continue
        incoming.setdefault(succ, []).append(rel)

    end_id, endpoint_notes = _select_end_activity(by_id)
    if end_id is None:
        return _blocked(BLOCK_MISSING_FLOAT_RUN)

    nodes, rel_into, path_status, path_notes = _backtrace(end_id, by_id, incoming)
    path_notes.update(endpoint_notes)

    activities = _build_path_activities(nodes, rel_into, by_id)
    summary = _build_summary(activities, by_id, path_status, path_notes)

    return LongestPathResult(
        run_status=RUN_LONGEST_PATH_ONLY,
        block_reason=None,
        node_count=graph_result.node_count,
        edge_count=graph_result.edge_count,
        diagnostic_count=diagnostic_count,
        path_count=1,
        summary=summary,
        activities=activities,
    )


def _select_end_activity(
    by_id: dict[str, dict[str, Any]],
) -> tuple[str | None, dict[str, Any]]:
    """Max computed early finish, tie -> larger ES -> lower topo index -> smallest id."""

    def sort_key(item: tuple[str, dict[str, Any]]):
        aid, row = item
        ef = _as_float(row.get("early_finish_offset_days"))
        es = _as_float(row.get("early_start_offset_days"))
        topo = row.get("topological_index")
        topo_val = topo if isinstance(topo, int) else 1_000_000_000
        ef_key = ef if ef is not None else float("-inf")
        es_key = es if es is not None else float("-inf")
        return (-ef_key, -es_key, topo_val, aid)

    items = sorted(by_id.items(), key=sort_key)
    if not items:
        return None, {}
    best_id = items[0][0]
    notes: dict[str, Any] = {}
    if len(items) > 1:
        best_ef = _as_float(items[0][1].get("early_finish_offset_days"))
        second_ef = _as_float(items[1][1].get("early_finish_offset_days"))
        if best_ef is not None and second_ef is not None and abs(best_ef - second_ef) <= _TOL:
            notes["endpoint_tie_break"] = "multiple_activities_share_max_early_finish"
    return best_id, notes


def _candidate(
    rel: dict[str, Any], by_id: dict[str, dict[str, Any]]
) -> tuple[float | None, bool, str | None]:
    """Return (candidate_successor_es, supported, note).

    Prefers the persisted Phase 2 candidate; reconstructs from offsets+type+lag when absent.
    ``supported=False`` flags an unsupported type or an unreconstructable candidate.
    """
    rtype_raw = rel.get("relationship_type")
    rtype = str(rtype_raw) if rtype_raw not in (None, "") else None
    if rtype not in SUPPORTED_RELATIONSHIP_TYPES:
        return None, False, "unsupported_relationship_type"

    persisted = _as_float(rel.get("candidate_successor_early_start_offset"))
    if persisted is not None:
        return persisted, True, None

    pred = str(rel.get("predecessor_activity_id", ""))
    succ = str(rel.get("successor_activity_id", ""))
    prow = by_id.get(pred, {})
    srow = by_id.get(succ, {})
    pe_es = _as_float(prow.get("early_start_offset_days"))
    pe_ef = _as_float(prow.get("early_finish_offset_days"))
    lag = _as_float(rel.get("normalized_lag_days")) or 0.0
    succ_dur = _as_float(srow.get("duration_value"))

    if rtype == "FS":
        cand = pe_ef + lag if pe_ef is not None else None
    elif rtype == "SS":
        cand = pe_es + lag if pe_es is not None else None
    elif rtype == "FF":
        cand = pe_ef + lag - succ_dur if (pe_ef is not None and succ_dur is not None) else None
    else:  # SF
        cand = pe_es + lag - succ_dur if (pe_es is not None and succ_dur is not None) else None

    if cand is None:
        return None, False, "unreconstructable_candidate"
    return cand, True, "reconstructed_candidate"


def _backtrace(
    end_id: str,
    by_id: dict[str, dict[str, Any]],
    incoming: dict[str, list[dict[str, Any]]],
) -> tuple[list[str], dict[str, dict[str, Any]], str, dict[str, Any]]:
    """Walk end->start through controlling predecessors. Returns (nodes_end_to_start,
    rel_into[activity]=controlling rel, status, notes)."""
    nodes: list[str] = [end_id]
    rel_into: dict[str, dict[str, Any]] = {}
    status = PATH_COMPUTED
    notes: dict[str, Any] = {}
    caveats: list[dict[str, Any]] = []
    visited: set[str] = set()
    cur = end_id

    while True:
        if cur in visited:
            status = PATH_DEGRADED_PARTIAL
            notes["cycle_guard"] = f"revisited:{cur}"
            break
        visited.add(cur)

        rels = sorted(
            incoming.get(cur, []),
            key=lambda r: (
                str(r.get("predecessor_activity_id", "")),
                str(r.get("relationship_type") or ""),
                str(r.get("relationship_ref") or ""),
                str(r.get("relationship_row_id") or ""),
            ),
        )
        if not rels:
            break  # true start (no incoming logic)

        cur_es = _as_float(by_id.get(cur, {}).get("early_start_offset_days"))
        matches: list[dict[str, Any]] = []
        unsupported_type = False
        unreconstructable = False
        for rel in rels:
            cand, supported, note = _candidate(rel, by_id)
            if not supported:
                if note == "unsupported_relationship_type":
                    unsupported_type = True
                else:
                    unreconstructable = True
                caveats.append(
                    {
                        "activity_id": cur,
                        "relationship_ref": rel.get("relationship_ref"),
                        "relationship_type": rel.get("relationship_type"),
                        "reason": note,
                    }
                )
                continue
            if cand is not None and cur_es is not None and abs(cand - cur_es) <= _TOL:
                matches.append(rel)

        if matches:
            controlling = _tie_break(matches, by_id)
            rel_into[cur] = controlling
            pred = str(controlling.get("predecessor_activity_id", ""))
            nodes.append(pred)
            cur = pred
            continue

        # No supported candidate controls cur's early start.
        if cur_es is not None and abs(cur_es - _ANCHOR_OFFSET) <= _TOL:
            # Anchor-driven open start: a legitimate path start, not a degradation.
            if unsupported_type or unreconstructable:
                notes["non_controlling_caveats"] = caveats
            break
        if unsupported_type:
            status = PATH_UNSUPPORTED_TYPE
        elif unreconstructable:
            status = PATH_DEGRADED_PARTIAL
        else:
            status = PATH_DEGRADED_PARTIAL
        notes["stopped_at"] = cur
        notes["stop_reason"] = status
        break

    if caveats and "non_controlling_caveats" not in notes:
        notes["caveats"] = caveats
    return nodes, rel_into, status, notes


def _tie_break(
    matches: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Larger pred EF -> larger pred ES -> lower pred topo index -> smallest pred id ->
    smallest relationship_ref."""

    def key(rel: dict[str, Any]):
        pred = str(rel.get("predecessor_activity_id", ""))
        prow = by_id.get(pred, {})
        ef = _as_float(prow.get("early_finish_offset_days"))
        es = _as_float(prow.get("early_start_offset_days"))
        topo = prow.get("topological_index")
        topo_val = topo if isinstance(topo, int) else 1_000_000_000
        return (
            -(ef if ef is not None else float("-inf")),
            -(es if es is not None else float("-inf")),
            topo_val,
            pred,
            str(rel.get("relationship_ref") or ""),
        )

    return sorted(matches, key=key)[0]


def _build_path_activities(
    nodes_end_to_start: list[str],
    rel_into: dict[str, dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> list[LongestPathActivity]:
    ordered = list(reversed(nodes_end_to_start))  # start -> end
    out: list[LongestPathActivity] = []
    for seq, activity_id in enumerate(ordered, start=1):
        row = by_id.get(activity_id, {})
        rel = rel_into.get(activity_id)  # controlling rel from the previous (predecessor)
        out.append(
            LongestPathActivity(
                path_sequence=seq,
                activity_id=activity_id,
                activity_name=row.get("activity_name"),
                relationship_from_previous_id=(rel.get("relationship_row_id") if rel else None),
                relationship_from_previous_ref=(rel.get("relationship_ref") if rel else None),
                computed_early_start=row.get("computed_early_start"),
                computed_early_finish=row.get("computed_early_finish"),
                computed_late_start=row.get("computed_late_start"),
                computed_late_finish=row.get("computed_late_finish"),
                early_start_offset_days=_as_float(row.get("early_start_offset_days")),
                early_finish_offset_days=_as_float(row.get("early_finish_offset_days")),
                computed_total_float=_as_float(row.get("computed_total_float")),
                computed_free_float=_as_float(row.get("computed_free_float")),
                duration_value=_as_float(row.get("duration_value")),
                topological_index=(
                    row.get("topological_index")
                    if isinstance(row.get("topological_index"), int)
                    else None
                ),
                selection_basis=("controlling_predecessor" if rel else "path_start"),
                selection_notes={},
            )
        )
    return out


def _build_summary(
    activities: list[LongestPathActivity],
    by_id: dict[str, dict[str, Any]],
    path_status: str,
    notes: dict[str, Any],
) -> LongestPathSummary:
    if not activities:
        return LongestPathSummary(
            start_activity_id=None, end_activity_id=None, activity_count=0,
            relationship_count=0, path_start_offset_days=None,
            path_finish_offset_days=None, path_duration=None, path_total_float=None,
            path_basis=PATH_BASIS, path_status=path_status, notes=notes,
        )
    start = activities[0]
    end = activities[-1]
    rel_count = sum(1 for a in activities if a.relationship_from_previous_ref is not None)
    p_start = start.early_start_offset_days
    p_finish = end.early_finish_offset_days
    duration = (
        _round(p_finish - p_start)
        if (p_start is not None and p_finish is not None)
        else None
    )
    return LongestPathSummary(
        start_activity_id=start.activity_id,
        end_activity_id=end.activity_id,
        activity_count=len(activities),
        relationship_count=rel_count,
        path_start_offset_days=_round(p_start),
        path_finish_offset_days=_round(p_finish),
        path_duration=duration,
        path_total_float=end.computed_total_float,  # nullable; NOT a criticality signal
        path_basis=PATH_BASIS,
        path_status=path_status,
        notes=notes,
    )


__all__ = [
    "LongestPathActivity",
    "LongestPathSummary",
    "LongestPathResult",
    "compute_longest_path",
    "RUN_LONGEST_PATH_ONLY",
    "RUN_BLOCKED",
    "PATH_TYPE_LONGEST",
    "PATH_BASIS",
    "BLOCK_GRAPH_DIAGNOSTIC",
    "BLOCK_MISSING_FORWARD_PASS",
    "BLOCK_MISSING_FLOAT_RUN",
    "PATH_COMPUTED",
    "PATH_DEGRADED_PARTIAL",
    "PATH_UNSUPPORTED_TYPE",
]
