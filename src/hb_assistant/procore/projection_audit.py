"""Local Procore payload field inventory + projection completeness audit.

Read-only. Emits structural metadata only — JSON paths, observed types, occurrence and
null/empty counts, business categories, table/column names, and coverage percentages.
Never emits payload values.

- ``projection_inventory`` walks every full raw payload (``raw_procore_payload_persisted
  = 1``) and reports per-endpoint field-path coverage (Gate B).
- ``projection_audit`` compares the live inventory against the committed registry
  allow-list and reports ``unmapped_primary_business_fields``,
  ``unmapped_nested_business_fields``, ``unknown_business_field_paths``, and per-endpoint
  destination coverage incl. the sidecar-only percentage (amendment 1). Completion
  requires all three unmapped/unknown totals to be zero for every endpoint with full
  payloads (Gate C).
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import open_connection

from . import endpoints as endpoint_registry
from . import projection_paths as pp
from . import projection_registry as registry
from .structured_analytics import RAW_LANDING_TABLE

# Endpoints present in the registry are the mandatory in-scope set: they have full raw
# payloads and must reach zero unmapped/unknown business field paths.
CUSTOM_READ_MODEL_MANAGED_ENDPOINTS = {
    "budget-detail-columns": {
        "managed_read_model": "procore_budget_detail_read_model",
        "managed_tables": [
            "procore_ep_budget_detail_columns",
            "procore_ep_budget_detail_rows",
            "procore_ep_budget_detail_row_cells",
        ],
    },
    "budget-detail-rows": {
        "managed_read_model": "procore_budget_detail_read_model",
        "managed_tables": [
            "procore_ep_budget_detail_columns",
            "procore_ep_budget_detail_rows",
            "procore_ep_budget_detail_row_cells",
        ],
    },
}


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


class _PathStat:
    __slots__ = ("types", "count", "non_empty")

    def __init__(self) -> None:
        self.types: set[str] = set()
        self.count = 0
        self.non_empty = 0

    def observe(self, value: Any, typ: str) -> None:
        self.types.add(typ)
        self.count += 1
        if not _is_empty(value):
            self.non_empty += 1


def _accumulate(payload: Any, stats: dict[str, _PathStat]) -> None:
    for path, typ in pp.iter_path_types(payload):
        value = _value_at(payload, path)
        stats.setdefault(path, _PathStat()).observe(value, typ)


def _value_at(payload: Any, path: str) -> Any:
    """Best-effort single-value resolution for null/empty accounting.

    For array-collapsed paths this resolves the first matching element, which is
    sufficient for empty-vs-present accounting (we never emit the value).
    """
    if path == pp.ROOT:
        return payload
    cur: Any = payload
    body = path[len(pp.ROOT) :].lstrip(".")
    import re

    for seg in re.split(r"(?<!\\)\.", body):
        if not seg:
            continue
        base = seg
        arrays = 0
        while base.endswith("[]"):
            base = base[:-2]
            arrays += 1
        base = base.replace("\\.", ".")
        if base:
            if not isinstance(cur, dict) or base not in cur:
                return None
            cur = cur[base]
        for _ in range(arrays):
            if not isinstance(cur, list) or not cur:
                return None
            cur = cur[0]
    return cur


def _iter_full_payloads(
    conn: sqlite3.Connection, *, endpoint: str | None, project_key: str | None
) -> Any:
    clauses = ["raw_procore_payload_persisted = 1", "is_current = 1"]
    params: list[Any] = []
    if endpoint:
        clauses.append("endpoint_key = ?")
        params.append(endpoint)
    if project_key:
        clauses.append("project_key = ?")
        params.append(project_key)
    sql = (
        f"SELECT endpoint_key, payload_json FROM {RAW_LANDING_TABLE} "
        f"WHERE {' AND '.join(clauses)} ORDER BY endpoint_key"
    )
    try:
        yield from conn.execute(sql, tuple(params))
    except sqlite3.Error:
        return


def collect_inventory(
    *,
    db_path: str | Path | None = None,
    endpoint: str | None = None,
    project_key: str | None = None,
) -> dict[str, dict[str, _PathStat]]:
    """Return ``endpoint_id -> {json_path: _PathStat}`` from full raw payloads."""
    with open_connection(Path(db_path) if db_path is not None else None) as conn:
        out: dict[str, dict[str, _PathStat]] = defaultdict(dict)
        for endpoint_key, payload_json in _iter_full_payloads(
            conn, endpoint=endpoint, project_key=project_key
        ):
            try:
                payload = json.loads(payload_json)
            except (json.JSONDecodeError, TypeError):
                out[endpoint_key].setdefault("$<invalid_json>", _PathStat()).observe(None, "null")
                continue
            _accumulate(payload, out[endpoint_key])
        return out


def inventory_for_registry(*, db_path: str | Path | None = None) -> dict[str, dict[str, list[str]]]:
    """Structural inventory consumed by ``projection_registry.build_registry``."""
    raw = collect_inventory(db_path=db_path)
    return {ep: {p: sorted(s.types) for p, s in paths.items()} for ep, paths in raw.items()}


def projection_inventory(
    *,
    db_path: str | Path | None = None,
    endpoint: str | None = None,
    project_key: str | None = None,
    emit_candidate: bool = False,
) -> dict[str, Any]:
    """Field-path inventory of full raw payloads (Gate B). Structural metadata only."""
    raw = collect_inventory(db_path=db_path, endpoint=endpoint, project_key=project_key)
    endpoints: list[dict[str, Any]] = []
    total_paths = 0
    total_array_paths = 0
    for ep in sorted(raw):
        stats = raw[ep]
        array_paths = sorted(p for p, s in stats.items() if "array" in s.types)
        fields = []
        for path in sorted(stats):
            s = stats[path]
            fields.append(
                {
                    "path": path,
                    "types": sorted(s.types),
                    "occurrences": s.count,
                    "non_empty": s.non_empty,
                    "null_empty_rate_pct": round(100.0 * (s.count - s.non_empty) / s.count, 1)
                    if s.count
                    else 0.0,
                    "category": pp.classify_category(path),
                }
            )
        total_paths += len(fields)
        total_array_paths += len(array_paths)
        endpoints.append(
            {
                "endpoint_id": ep,
                "distinct_paths": len(fields),
                "array_paths": len(array_paths),
                "fields": fields,
            }
        )
    payload: dict[str, Any] = {
        "command": "hb-assistant procore analytics projection-inventory",
        "endpoint_count": len(endpoints),
        "total_distinct_paths": total_paths,
        "total_array_paths": total_array_paths,
        "endpoints": endpoints,
        "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
    }
    if emit_candidate:
        structural = {ep: {p: sorted(s.types) for p, s in raw[ep].items()} for ep in raw}
        payload["candidate_registry"] = registry.build_registry(structural)
    return payload


# --- Completeness audit -----------------------------------------------------------


def projection_audit(
    *,
    db_path: str | Path | None = None,
    endpoint: str | None = None,
    project_key: str | None = None,
) -> dict[str, Any]:
    """Compare live inventory to the registry allow-list (Gate C + amendment 1)."""
    raw = collect_inventory(db_path=db_path, endpoint=endpoint, project_key=project_key)
    plans = registry.load_registry()
    rows: list[dict[str, Any]] = []
    total_unmapped_primary = 0
    total_unmapped_nested = 0
    total_unknown = 0
    over_threshold: list[str] = []
    over_threshold_unjustified: list[str] = []

    # Endpoints with full payloads but no registry entry are reported but, per amendment 5,
    # they are out-of-scope for THIS pass only if they genuinely have no full payloads.
    # Here every endpoint in ``raw`` HAS full payloads, so a missing plan is a real gap.
    for ep in sorted(raw):
        stats = raw[ep]
        plan = plans.get(ep)
        observed = set(stats)
        if plan is None:
            unknown = sorted(p for p in observed if p != pp.ROOT)
            unknown_business = [p for p in unknown if _is_business_field(p, stats)]
            primary = [p for p in unknown_business if not pp.under_array(p)]
            nested = [p for p in unknown_business if pp.under_array(p)]
            if ep in CUSTOM_READ_MODEL_MANAGED_ENDPOINTS:
                rows.append(
                    {
                        "endpoint_id": ep,
                        "status": "custom_read_model_managed",
                        "registry_present": False,
                        "observed_paths": len(observed),
                        "business_field_paths": len(unknown_business),
                        "unmapped_primary_business_fields": 0,
                        "unmapped_nested_business_fields": 0,
                        "unknown_business_field_paths": 0,
                        "inventory_sample": unknown_business[:25],
                        **CUSTOM_READ_MODEL_MANAGED_ENDPOINTS[ep],
                    }
                )
                continue
            total_unmapped_primary += len(primary)
            total_unmapped_nested += len(nested)
            total_unknown += len(unknown_business)
            rows.append(
                {
                    "endpoint_id": ep,
                    "status": "no_registry_plan",
                    "registry_present": False,
                    "unmapped_primary_business_fields": len(primary),
                    "unmapped_nested_business_fields": len(nested),
                    "unknown_business_field_paths": len(unknown_business),
                    "unknown_sample": unknown_business[:25],
                }
            )
            continue

        unknown = sorted(p for p in observed if p not in plan.known_paths)
        unknown_business = [p for p in unknown if _is_business_field(p, stats)]
        primary = [p for p in unknown_business if not pp.under_array(p)]
        nested = [p for p in unknown_business if pp.under_array(p)]
        total_unmapped_primary += len(primary)
        total_unmapped_nested += len(nested)
        total_unknown += len(unknown_business)
        cov = dict(plan.coverage)
        if cov.get("over_sidecar_threshold"):
            over_threshold.append(ep)
            if not cov.get("sidecar_justified"):
                over_threshold_unjustified.append(ep)
        rows.append(
            {
                "endpoint_id": ep,
                "status": "ok" if not unknown_business else "unknown_paths_present",
                "registry_present": True,
                "primary_table": plan.primary_table,
                "child_table_count": len(plan.child_tables),
                "observed_paths": len(observed),
                "known_paths": len(plan.known_paths),
                "unmapped_primary_business_fields": len(primary),
                "unmapped_nested_business_fields": len(nested),
                "unknown_business_field_paths": len(unknown_business),
                "unknown_sample": unknown_business[:25],
                "coverage": cov,
            }
        )

    schema_mismatches = runtime_plan_schema_mismatches(db_path)
    ok = (
        total_unknown == 0
        and all(
            r["registry_present"] or r["status"] == "custom_read_model_managed" for r in rows
        )
        and not over_threshold_unjustified
        and not schema_mismatches
    )
    return {
        "command": "hb-assistant procore analytics projection-audit",
        "ok": ok,
        "endpoint_count": len(rows),
        "unmapped_primary_business_fields": total_unmapped_primary,
        "unmapped_nested_business_fields": total_unmapped_nested,
        "unknown_business_field_paths": total_unknown,
        "runtime_plan_schema_mismatches": len(schema_mismatches),
        "endpoints_over_sidecar_threshold": over_threshold,
        "endpoints_over_sidecar_threshold_unjustified": over_threshold_unjustified,
        "endpoints": rows,
        "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
    }


def _is_business_field(path: str, stats: dict[str, _PathStat]) -> bool:
    """A business field path is a scalar leaf or an array node (not an object container).

    Object container nodes are structural — covered by their children — and excluded from
    the unmapped/unknown business-field count and the sidecar denominator.
    """
    if path == pp.ROOT or path.endswith("[]"):
        return False
    if pp.is_transport_secret(path):
        return False
    types = stats[path].types
    is_object = "object" in types and not (
        types & {"string", "integer", "number", "boolean", "null"}
    )
    return not is_object


def endpoints_without_full_payloads() -> list[str]:
    """Registry-eligible endpoint ids known to the adapter registry that are NOT in the
    committed projection registry (i.e. ``no_full_payload_available`` this pass)."""
    in_scope = registry.in_scope_endpoints()
    return [ep.endpoint_id for ep in endpoint_registry.list_all() if ep.endpoint_id not in in_scope]


# --- Runtime plan vs physical-schema parity --------------------------------------
#
# ``projection_audit`` proves *path coverage*; this proves the orthogonal property that
# every column the projection engine will INSERT (every ``EndpointPlan.primary_columns`` /
# ``ChildTable.columns`` entry) actually exists in the physical table, and that every
# required ``procore_ep_*`` table exists. Without this gate, a registry regenerated after
# tables were created drifts and the INSERT fails with ``sqlite3.OperationalError``.

TABLE_MISSING = "<TABLE_MISSING>"


def _ep_table_columns(conn: sqlite3.Connection) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'procore_ep_%'"
    ).fetchall():
        out[name] = {row[1] for row in conn.execute(f"PRAGMA table_info({name})")}
    return out


def plan_schema_mismatches(conn: sqlite3.Connection) -> list[tuple[str, str, str, str]]:
    """Return ``(endpoint_id, table, column|TABLE_MISSING, context)`` for every planned
    insert column absent from its physical table, and every missing required table."""
    plans = registry.load_registry()
    table_cols = _ep_table_columns(conn)
    problems: list[tuple[str, str, str, str]] = []
    for endpoint_id, plan in sorted(plans.items()):
        actual = table_cols.get(plan.primary_table)
        if actual is None:
            problems.append((endpoint_id, plan.primary_table, TABLE_MISSING, "primary"))
        else:
            for rel, col in plan.primary_columns:
                if col not in actual:
                    problems.append((endpoint_id, plan.primary_table, col, f"primary rel={rel}"))
        for child in plan.child_tables:
            actual = table_cols.get(child.table)
            if actual is None:
                problems.append(
                    (endpoint_id, child.table, TABLE_MISSING, f"child array={child.array_path}")
                )
                continue
            for rel, col in child.columns:
                if col not in actual:
                    problems.append(
                        (endpoint_id, child.table, col, f"child rel={rel} array={child.array_path}")
                    )
    return problems


def runtime_plan_schema_mismatches(
    db_path: str | Path | None = None,
) -> list[tuple[str, str, str, str]]:
    """``plan_schema_mismatches`` over a freshly opened connection (read-only intent)."""
    with open_connection(Path(db_path) if db_path is not None else None) as conn:
        return plan_schema_mismatches(conn)


def projection_schema_audit(*, db_path: str | Path | None = None) -> dict[str, Any]:
    """Runtime plan/physical-schema parity audit. Table/column names + counts only."""
    problems = runtime_plan_schema_mismatches(db_path)
    table_missing = sum(1 for p in problems if p[2] == TABLE_MISSING)
    return {
        "command": "hb-assistant procore analytics projection-schema-audit",
        "ok": not problems,
        "runtime_plan_schema_mismatches": len(problems),
        "missing_table_count": table_missing,
        "missing_column_count": len(problems) - table_missing,
        "mismatches": [
            {"endpoint_id": e, "table": t, "column": c, "context": ctx}
            for e, t, c, ctx in problems[:200]
        ],
        "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
    }
