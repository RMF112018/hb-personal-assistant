"""CPM graph foundation: typed graph models, structural diagnostics, topological order.

PHASE 1 SCOPE — GRAPH DIAGNOSTICS ONLY. This module builds a directed activity graph
from committed schedule activities and relationships and reports structural diagnostics
(missing endpoints, self/duplicate/unsupported edges, open ends, cycles) plus a
deterministic topological order for acyclic graphs.

It intentionally does NOT compute CPM dates, float, early/late dates, the critical path,
or the longest path. No forward or backward pass is performed. Source-export critical
flags (``source_critical_flag``, ``source_driving_path_flag``, ``source_longest_path_flag``),
derived float, and ``is_critical`` remain evidence only and are NOT read by this layer —
the graph is built purely from ``activity_id`` and relationship predecessor/successor/type.

``GraphBuildResult.cpm_recalculation_status`` is always ``"not_implemented"`` so callers
and persisted runs clearly report that CPM recalculation does not exist beyond these
graph diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schedule_graph import build_adjacency

# Finish-Start, Start-Start, Finish-Finish, Start-Finish — the four standard P6/MSP
# relationship types. Anything else (including missing/empty) is unsupported and surfaced
# as a diagnostic, but the dependency edge is still honored for topological purposes.
SUPPORTED_RELATIONSHIP_TYPES: frozenset[str] = frozenset({"FS", "SS", "FF", "SF"})

ANALYSIS_SCOPE = "graph_diagnostics_only"
CPM_RECALCULATION_STATUS = "not_implemented"

# Diagnostic type identifiers (stable strings persisted as evidence).
DIAG_MISSING_PREDECESSOR = "missing_predecessor_activity"
DIAG_MISSING_SUCCESSOR = "missing_successor_activity"
DIAG_SELF_RELATIONSHIP = "self_relationship"
DIAG_DUPLICATE_RELATIONSHIP = "duplicate_relationship"
DIAG_UNSUPPORTED_TYPE = "unsupported_relationship_type"
DIAG_OPEN_START = "open_start"
DIAG_OPEN_FINISH = "open_finish"
DIAG_CYCLE = "cycle"

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"


@dataclass
class ActivityNode:
    """A graph node. Carries only identity plus a little evidence metadata.

    No float/critical/date fields are consumed for graph logic — this is deliberate so the
    foundation cannot accidentally relabel a source-export flag as computed CPM.
    """

    activity_id: str
    activity_name: str | None = None
    is_milestone: bool = False


@dataclass
class RelationshipEdge:
    """A directed dependency edge (predecessor -> successor)."""

    predecessor_activity_id: str
    successor_activity_id: str
    relationship_type: str | None = None
    lag_value: str | None = None
    lag_unit: str | None = None
    relationship_row_id: Any = None

    @property
    def ref(self) -> str:
        """Stable human-readable reference for diagnostics/evidence."""
        base = f"{self.predecessor_activity_id}->{self.successor_activity_id}"
        if self.relationship_type:
            return f"{base} ({self.relationship_type})"
        return base


@dataclass
class GraphDiagnostic:
    """One structural finding about the graph."""

    diagnostic_type: str
    severity: str
    summary: str
    activity_id: str | None = None
    relationship_ref: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphBuildResult:
    """Outcome of building the CPM graph for one schedule version.

    ``topological_order`` is ``None`` when the graph is cyclic. ``cpm_recalculation_status``
    is always ``"not_implemented"`` in this phase.
    """

    node_count: int
    edge_count: int
    is_acyclic: bool
    topological_order: list[str] | None
    diagnostics: list[GraphDiagnostic] = field(default_factory=list)
    analysis_scope: str = ANALYSIS_SCOPE
    cpm_recalculation_status: str = CPM_RECALCULATION_STATUS

    def diagnostics_as_dicts(self) -> list[dict[str, Any]]:
        return [
            {
                "diagnostic_type": d.diagnostic_type,
                "severity": d.severity,
                "summary": d.summary,
                "activity_id": d.activity_id,
                "relationship_ref": d.relationship_ref,
                "evidence": dict(d.evidence),
            }
            for d in self.diagnostics
        ]


def _node_from_activity(activity: dict[str, Any]) -> ActivityNode | None:
    raw_id = activity.get("activity_id")
    if raw_id is None or str(raw_id) == "":
        return None
    return ActivityNode(
        activity_id=str(raw_id),
        activity_name=activity.get("activity_name"),
        is_milestone=bool(activity.get("is_milestone")),
    )


def _edge_from_relationship(relationship: dict[str, Any]) -> RelationshipEdge:
    rel_type = relationship.get("relationship_type")
    return RelationshipEdge(
        predecessor_activity_id=str(relationship.get("predecessor_activity_id", "")),
        successor_activity_id=str(relationship.get("successor_activity_id", "")),
        relationship_type=str(rel_type) if rel_type not in (None, "") else None,
        lag_value=(
            str(relationship.get("lag_value"))
            if relationship.get("lag_value") is not None
            else None
        ),
        lag_unit=relationship.get("lag_unit"),
        relationship_row_id=relationship.get("relationship_row_id"),
    )


def _edge_sort_key(edge: RelationshipEdge) -> tuple[str, str, str, str]:
    # Deterministic ordering independent of input order or row-id presence.
    row_id = "" if edge.relationship_row_id is None else str(edge.relationship_row_id)
    return (
        edge.predecessor_activity_id,
        edge.successor_activity_id,
        edge.relationship_type or "",
        row_id,
    )


def build_graph(
    activities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> GraphBuildResult:
    """Build the activity graph and return structural diagnostics + topological order.

    Deterministic: nodes and edges are processed in a stable sorted order so the same input
    always yields the same diagnostics and topological order.
    """
    nodes: dict[str, ActivityNode] = {}
    for activity in activities:
        node = _node_from_activity(activity)
        if node is not None and node.activity_id not in nodes:
            nodes[node.activity_id] = node
    node_ids = set(nodes)

    edges = sorted((_edge_from_relationship(r) for r in relationships), key=_edge_sort_key)

    diagnostics: list[GraphDiagnostic] = []

    # Valid edges feed the topological graph. An edge is excluded from topo when it is a
    # self-loop or references a missing endpoint, so a data defect cannot masquerade as a
    # false cycle. Duplicates collapse to a single adjacency entry.
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    indegree: dict[str, int] = dict.fromkeys(node_ids, 0)
    valid_edge_count = 0
    seen_edge_keys: set[tuple[str, str, str]] = set()

    for edge in edges:
        pred = edge.predecessor_activity_id
        succ = edge.successor_activity_id
        rel_type = edge.relationship_type

        if rel_type is None or rel_type not in SUPPORTED_RELATIONSHIP_TYPES:
            diagnostics.append(
                GraphDiagnostic(
                    diagnostic_type=DIAG_UNSUPPORTED_TYPE,
                    severity=SEVERITY_WARNING,
                    summary=(
                        f"Relationship {edge.ref} has unsupported type "
                        f"{rel_type!r} (expected one of {sorted(SUPPORTED_RELATIONSHIP_TYPES)})."
                    ),
                    relationship_ref=edge.ref,
                    evidence={
                        "predecessor_activity_id": pred,
                        "successor_activity_id": succ,
                        "relationship_type": rel_type,
                    },
                )
            )

        if pred == succ:
            diagnostics.append(
                GraphDiagnostic(
                    diagnostic_type=DIAG_SELF_RELATIONSHIP,
                    severity=SEVERITY_ERROR,
                    summary=f"Activity {pred} has a relationship to itself.",
                    activity_id=pred,
                    relationship_ref=edge.ref,
                    evidence={"activity_id": pred, "relationship_type": rel_type},
                )
            )
            continue

        missing_pred = pred not in node_ids
        missing_succ = succ not in node_ids
        if missing_pred:
            diagnostics.append(
                GraphDiagnostic(
                    diagnostic_type=DIAG_MISSING_PREDECESSOR,
                    severity=SEVERITY_ERROR,
                    summary=f"Relationship {edge.ref} references missing predecessor {pred}.",
                    activity_id=pred,
                    relationship_ref=edge.ref,
                    evidence={"missing_activity_id": pred, "endpoint": "predecessor"},
                )
            )
        if missing_succ:
            diagnostics.append(
                GraphDiagnostic(
                    diagnostic_type=DIAG_MISSING_SUCCESSOR,
                    severity=SEVERITY_ERROR,
                    summary=f"Relationship {edge.ref} references missing successor {succ}.",
                    activity_id=succ,
                    relationship_ref=edge.ref,
                    evidence={"missing_activity_id": succ, "endpoint": "successor"},
                )
            )
        if missing_pred or missing_succ:
            continue

        edge_key = (pred, succ, rel_type or "")
        if edge_key in seen_edge_keys:
            diagnostics.append(
                GraphDiagnostic(
                    diagnostic_type=DIAG_DUPLICATE_RELATIONSHIP,
                    severity=SEVERITY_WARNING,
                    summary=f"Duplicate relationship {edge.ref}.",
                    relationship_ref=edge.ref,
                    evidence={
                        "predecessor_activity_id": pred,
                        "successor_activity_id": succ,
                        "relationship_type": rel_type,
                    },
                )
            )
            continue
        seen_edge_keys.add(edge_key)

        adjacency[pred].append(succ)
        indegree[succ] += 1
        valid_edge_count += 1

    # Open ends — purely topological in/out degree over valid edges. These are graph
    # diagnostics, NOT the DCMA open-ends quality metric (which is unchanged elsewhere).
    outdegree: dict[str, int] = {nid: len(adjacency[nid]) for nid in node_ids}
    for nid in sorted(node_ids):
        if indegree[nid] == 0:
            diagnostics.append(
                GraphDiagnostic(
                    diagnostic_type=DIAG_OPEN_START,
                    severity=SEVERITY_INFO,
                    summary=f"Activity {nid} has no predecessors (open start).",
                    activity_id=nid,
                    evidence={"indegree": 0},
                )
            )
        if outdegree[nid] == 0:
            diagnostics.append(
                GraphDiagnostic(
                    diagnostic_type=DIAG_OPEN_FINISH,
                    severity=SEVERITY_INFO,
                    summary=f"Activity {nid} has no successors (open finish).",
                    activity_id=nid,
                    evidence={"outdegree": 0},
                )
            )

    topo_order, is_acyclic, cyclic_nodes = _topological_order(adjacency, indegree, node_ids)
    if not is_acyclic:
        diagnostics.append(
            GraphDiagnostic(
                diagnostic_type=DIAG_CYCLE,
                severity=SEVERITY_ERROR,
                summary=(
                    "Schedule logic contains a cycle; "
                    f"{len(cyclic_nodes)} activities could not be ordered."
                ),
                evidence={"cyclic_activity_ids": cyclic_nodes},
            )
        )

    return GraphBuildResult(
        node_count=len(node_ids),
        edge_count=valid_edge_count,
        is_acyclic=is_acyclic,
        topological_order=topo_order if is_acyclic else None,
        diagnostics=diagnostics,
    )


def _topological_order(
    adjacency: dict[str, list[str]],
    indegree: dict[str, int],
    node_ids: set[str],
) -> tuple[list[str], bool, list[str]]:
    """Kahn's algorithm with deterministic (sorted) tie-breaking.

    Returns ``(order, is_acyclic, cyclic_nodes)``. When a cycle exists, ``order`` holds the
    nodes that could be sequenced and ``cyclic_nodes`` the sorted remainder.
    """
    remaining = dict(indegree)
    # Sorted ready set for deterministic output; re-sorted each step is fine at this scale.
    ready = sorted(nid for nid in node_ids if remaining[nid] == 0)
    order: list[str] = []
    while ready:
        nid = ready.pop(0)
        order.append(nid)
        newly_ready: list[str] = []
        for succ in adjacency[nid]:
            remaining[succ] -= 1
            if remaining[succ] == 0:
                newly_ready.append(succ)
        if newly_ready:
            ready = sorted(ready + newly_ready)

    if len(order) == len(node_ids):
        return order, True, []
    cyclic_nodes = sorted(nid for nid in node_ids if nid not in set(order))
    return order, False, cyclic_nodes


__all__ = [
    "ActivityNode",
    "RelationshipEdge",
    "GraphDiagnostic",
    "GraphBuildResult",
    "build_graph",
    "build_adjacency",
    "SUPPORTED_RELATIONSHIP_TYPES",
    "ANALYSIS_SCOPE",
    "CPM_RECALCULATION_STATUS",
]
