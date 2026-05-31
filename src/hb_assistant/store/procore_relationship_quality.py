"""Phase 06B responsible-party & relationship-quality diagnostics over local SQLite Procore tables.

Deterministic and **read-only**: exposes responsibility / relationship gaps so an operator can see
which records are missing owners / assignees / ball-in-court / responsible-contractor / vendor /
location edges, which child records are orphaned, how well parent/child linkage resolves, and where
commitment/PO duplicate conditions exist. Names / counts / refs only — no live Procore access, no
writeback, no raw payload values, and **no determinations** (these are data-quality / review aids,
not legal/claims/safety/entitlement findings).

Non-guessing posture (stop condition): for a given (endpoint, relationship), if **no** record
carries that edge the relationship is reported ``not_observed`` rather than "100% missing" — the
model never asserts that an endpoint *requires* a relationship it has never been seen to carry. A
relationship is only counted as a real gap (``partial_gap``) when *some* records of the endpoint
carry the edge and others do not. Linkage that cannot be inferred is reported ``unknown``.

Owner mapping: there is no dedicated Procore "owner" edge; the concrete owner-proxy edge is
``created_by`` (emitted across the projection layer). The ``owner`` label is surfaced explicitly so
it never overclaims.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .connection import get_connection
from .procore_action_queue import _record_key

# operator-facing relationship label -> concrete record-edge type (auditable literal map).
_RELATIONSHIP_EDGE_TYPES: Dict[str, str] = {
    "owner": "created_by",
    "assignee": "assignee",
    "ball_in_court": "ball_in_court",
    "responsible_contractor": "responsible_contractor",
    "vendor": "vendor",
    "location": "at_location",
}

_STATUS_COVERED = "covered"
_STATUS_PARTIAL_GAP = "partial_gap"
_STATUS_NOT_OBSERVED = "not_observed"


def _records_by_endpoint(conn: Any, project_key: str) -> Dict[str, List[str]]:
    """endpoint_id -> [record_key] for every live record in the project."""
    out: Dict[str, List[str]] = {}
    for r in conn.execute(
        """
        SELECT endpoint_id, parent_procore_id, procore_record_id
          FROM procore_live_records
         WHERE project_key = ?
        """,
        (project_key,),
    ).fetchall():
        rk = _record_key(project_key, r["endpoint_id"], r["parent_procore_id"], r["procore_record_id"])
        out.setdefault(r["endpoint_id"], []).append(rk)
    return out


def _edges_by_record(conn: Any, project_key: str) -> Dict[str, set[str]]:
    """record_key -> {edge_type} for the relationship edge types we track."""
    edge_types = tuple(sorted(set(_RELATIONSHIP_EDGE_TYPES.values())))
    placeholders = ", ".join("?" for _ in edge_types)
    out: Dict[str, set[str]] = {}
    for r in conn.execute(
        f"""
        SELECT from_record_key, edge_type
          FROM procore_record_edges
         WHERE project_key = ? AND edge_type IN ({placeholders})
        """,
        (project_key, *edge_types),
    ).fetchall():
        out.setdefault(r["from_record_key"], set()).add(r["edge_type"])
    return out


def build_responsible_party_gaps(
    project_key: str,
    *,
    now_utc: str,
    endpoint_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Per-endpoint, per-relationship coverage of the six responsibility edge types.

    Read-only; names / counts only. ``not_observed`` is reported (never a fabricated gap) when an
    endpoint has never been seen to carry a relationship.
    """
    conn = get_connection(db_path)
    records_by_endpoint = _records_by_endpoint(conn, project_key)
    edges_by_record = _edges_by_record(conn, project_key)

    coverage: List[Dict[str, Any]] = []
    by_relationship: Dict[str, Dict[str, int]] = {
        label: {"partial_gap_endpoints": 0, "missing": 0} for label in _RELATIONSHIP_EDGE_TYPES
    }
    partial_gap_total = 0
    missing_total = 0

    endpoints = sorted(
        e for e in records_by_endpoint if endpoint_id is None or e == endpoint_id
    )
    for ep in endpoints:
        rks = records_by_endpoint[ep]
        record_count = len(rks)
        for label, edge_type in _RELATIONSHIP_EDGE_TYPES.items():
            with_edge = sum(1 for rk in rks if edge_type in edges_by_record.get(rk, ()))
            missing = record_count - with_edge
            if with_edge == 0:
                status = _STATUS_NOT_OBSERVED
            elif missing > 0:
                status = _STATUS_PARTIAL_GAP
            else:
                status = _STATUS_COVERED
            if status == _STATUS_PARTIAL_GAP:
                partial_gap_total += 1
                missing_total += missing
                by_relationship[label]["partial_gap_endpoints"] += 1
                by_relationship[label]["missing"] += missing
            coverage.append({
                "endpoint_id": ep,
                "relationship": label,
                "edge_type": edge_type,
                "records": record_count,
                "records_with_edge": with_edge,
                "missing": missing,
                "coverage_pct": round(with_edge / record_count * 100, 1) if record_count else 0.0,
                "status": status,
            })

    coverage.sort(key=lambda c: (c["endpoint_id"], c["relationship"]))
    return {
        "command": "hb-assistant procore live responsible-party-gaps",
        "ok": True,
        "phase": "Phase 06B Prompt 11",
        "project_key": project_key,
        "generated_at": now_utc,
        "filters": {"endpoint_id": endpoint_id},
        "relationship_edge_map": dict(_RELATIONSHIP_EDGE_TYPES),
        "summary": {
            "endpoints": len(endpoints),
            "partial_gap_relationships": partial_gap_total,
            "missing_total": missing_total,
            "by_relationship": by_relationship,
        },
        "coverage": coverage,
        "no_live_call_performed": True,
        "no_raw_values_persisted": True,
        "determinations_made": False,
    }


def build_relationship_quality(
    project_key: str,
    *,
    now_utc: str,
    max_items: int = 50,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Orphaned child records, parent/child linkage coverage, and commitment/PO dedupe warnings.

    Read-only; refs / counts only. Linkage that cannot be inferred is reported ``unknown`` rather
    than guessed. Dedupe warnings cover only the commitment/PO surfaces the repo already supports.
    """
    from .procore_commitment_projection import _commitment_exists

    conn = get_connection(db_path)

    rows = conn.execute(
        """
        SELECT endpoint_id, parent_procore_id, procore_record_id
          FROM procore_live_records
         WHERE project_key = ?
        """,
        (project_key,),
    ).fetchall()

    record_id_universe = {r["procore_record_id"] for r in rows}
    children = [r for r in rows if (r["parent_procore_id"] or "") != ""]
    orphans = [r for r in children if r["parent_procore_id"] not in record_id_universe]

    orphan_by_endpoint: Dict[str, int] = {}
    orphan_sample: List[Dict[str, Any]] = []
    for r in orphans:
        orphan_by_endpoint[r["endpoint_id"]] = orphan_by_endpoint.get(r["endpoint_id"], 0) + 1
    for r in sorted(orphans, key=lambda x: (x["endpoint_id"], str(x["procore_record_id"])))[:max_items]:
        orphan_sample.append({
            "endpoint_id": r["endpoint_id"],
            "procore_record_id": r["procore_record_id"],
            "parent_procore_id": r["parent_procore_id"],
        })

    child_count = len(children)
    resolved = child_count - len(orphans)
    if child_count == 0:
        linkage = {"child_records": 0, "children_with_resolved_parent": 0,
                   "linkage_pct": None, "linkage_status": "unknown"}
    else:
        linkage = {
            "child_records": child_count,
            "children_with_resolved_parent": resolved,
            "linkage_pct": round(resolved / child_count * 100, 1),
            "linkage_status": "complete" if resolved == child_count else "partial",
        }

    # --- dedupe warnings: PO contracts whose contract_id already exists as a commitment ---
    duplicate_warnings: List[Dict[str, Any]] = []
    for r in conn.execute(
        """
        SELECT endpoint_id, record_key, contract_id
          FROM procore_financial_contracts
         WHERE project_key = ? AND contract_family = 'purchase_order'
         ORDER BY record_key
        """,
        (project_key,),
    ).fetchall():
        if _commitment_exists(project_key, r["contract_id"], db_path):
            duplicate_warnings.append({
                "endpoint_id": r["endpoint_id"],
                "record_key": r["record_key"],
                "contract_id": r["contract_id"],
                "duplicate_of": "commitment",
            })

    return {
        "command": "hb-assistant procore live relationship-quality",
        "ok": True,
        "phase": "Phase 06B Prompt 11",
        "project_key": project_key,
        "generated_at": now_utc,
        "summary": {
            "total_records": len(rows),
            "child_records": child_count,
            "orphan_records": len(orphans),
            "linkage_pct": linkage["linkage_pct"],
            "duplicate_warnings": len(duplicate_warnings),
        },
        "orphans": {
            "orphan_count": len(orphans),
            "by_endpoint": dict(sorted(orphan_by_endpoint.items())),
            "sample": orphan_sample,
            "sample_truncated": len(orphans) > len(orphan_sample),
        },
        "linkage": linkage,
        "duplicate_warnings": duplicate_warnings,
        "no_live_call_performed": True,
        "no_raw_values_persisted": True,
        "determinations_made": False,
    }


__all__ = ["build_responsible_party_gaps", "build_relationship_quality"]
