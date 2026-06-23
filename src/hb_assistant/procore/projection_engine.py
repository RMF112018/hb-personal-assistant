"""Deterministic endpoint-specific projection from full raw Procore payloads into the
V47 ``procore_ep_*`` primary + child tables.

Guarantees:

- **Registry-driven** — the committed projection registry decides every column, child
  table, and lossless sidecar; this module contains no per-endpoint logic.
- **Fail closed on unknown paths** — a payload path absent from the registry allow-list
  is never silently dropped. In ``enforce`` mode (audit / reprocess ``--apply``) it raises
  ``UnknownProjectionPath``; in ``live`` mode it degrades the receipt
  (``state=degraded_unknown_projection_fields``, ``ok=False``) without writing a partial
  projection — the full raw payload has already been persisted upstream, so nothing is
  lost (amendment 2).
- **Idempotent** — the primary row upserts on ``record_key``; child rows are deleted by
  parent and re-inserted, so replaying the same payload yields identical rows.
- **Source-quality precedence** — reuses the shared rank helpers so a lower-quality
  payload never downgrades an existing higher-quality projection.
- **No raw value emission** — receipts carry counts and field *names* only.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import open_connection, transaction

from . import endpoints as endpoint_registry
from . import projection_paths as pp
from . import projection_registry as registry
from .projects_projection import (
    PROJECTS_PRIMARY_TABLE,
    payload_matches_projects_context,
    primary_upsert_conflict_key,
    projects_record_key_for_project_key,
)
from .structured_analytics import (
    RAW_LANDING_TABLE,
    _existing_source_quality_rank,
    _rank,
    structured_record_key,
)

MODE_LIVE = "live"
MODE_ENFORCE = "enforce"


class UnknownProjectionPath(RuntimeError):
    """Raised in enforce mode when a payload contains a path absent from the registry."""

    def __init__(self, endpoint_id: str, unknown: list[str]) -> None:
        self.endpoint_id = endpoint_id
        self.unknown = unknown
        super().__init__(f"{endpoint_id}: {len(unknown)} unmapped business field path(s)")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def _child_record_key(primary_key: str, array_path: str, chain: list[int], item_id: Any) -> str:
    key = "|".join([primary_key, array_path, ",".join(map(str, chain)), str(item_id)])
    return f"pesc-{_hash(key)[:32]}"


def _scalar(value: Any) -> str | None:
    """Stringify a scalar for a TEXT column; objects/lists collapse via the shared scalarizer."""
    cleaned = _collapse_scalar(value)
    return None if cleaned is None else str(cleaned)


def _collapse_scalar(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ("flat_code", "code", "name", "display_name", "login", "title", "label", "id"):
            candidate = value.get(key)
            if candidate not in (None, ""):
                return candidate
        return None
    if isinstance(value, list):
        return None
    if value == "":
        return None
    return value


def _array_levels(array_path: str) -> int:
    return array_path.count("[]")


def _top_segment(array_path: str) -> str | None:
    """Return the key of a top-level array NODE path ``$.<key>`` (no ancestor arrays)."""
    if _array_levels(array_path) != 0:
        return None
    body = array_path[len(pp.ROOT) + 1 :]
    return body if body and "." not in body else None


def _iter_items(payload: Any, array_node_path: str) -> Any:
    """Iterate ``(index_chain, item)`` for an array NODE path (its elements)."""
    return pp.resolve_arrays(payload, array_node_path + "[]")


def _resolve_item_at(payload: Any, array_node_path: str, chain: list[int]) -> Any:
    """Re-resolve the array item identified by ``chain`` (used for parent-item linkage)."""
    for idx_chain, item in _iter_items(payload, array_node_path):
        if idx_chain == chain:
            return item
    return None


def project_endpoint_specific(
    conn: sqlite3.Connection,
    *,
    endpoint_id: str,
    project_key: str | None,
    procore_project_id: str | None,
    record_id: str,
    parent_record_id: str | None,
    payload: dict[str, Any],
    raw_payload_id: str,
    payload_hash: str,
    source_quality: str,
    fetched_at: str | None,
    now_utc: str,
    mode: str = MODE_LIVE,
) -> dict[str, Any]:
    """Project one full payload into its endpoint-specific primary + child tables."""
    receipt: dict[str, Any] = {
        "endpoint_key": endpoint_id,
        "endpoint_specific_projection_status": "ok",
        "ok": True,
        "primary_rows": 0,
        "child_rows": 0,
        "child_rows_by_table": {},
        "unknown_field_path_count": 0,
    }
    plan = registry.plan_for(endpoint_id)
    if plan is None:
        receipt["endpoint_specific_projection_status"] = "no_registry_endpoint"
        return receipt

    observed = pp.walk_paths(payload)
    unknown = sorted(
        p
        for p in observed
        if p != pp.ROOT and p not in plan.known_paths and not pp.is_transport_secret(p)
    )
    if unknown:
        if mode == MODE_ENFORCE:
            raise UnknownProjectionPath(endpoint_id, unknown)
        receipt.update(
            {
                "endpoint_specific_projection_status": "degraded_unknown_projection_fields",
                "ok": False,
                "state": "degraded_unknown_projection_fields",
                "unknown_field_path_count": len(unknown),
                "unknown_field_paths_sample": unknown[:20],  # field NAMES only, never values
            }
        )
        return receipt

    if not payload_matches_projects_context(
        endpoint_id=endpoint_id,
        procore_project_id=procore_project_id,
        record_id=record_id,
        payload=payload,
    ):
        receipt["endpoint_specific_projection_status"] = "skipped_non_matching_project"
        return receipt

    if plan.primary_table == PROJECTS_PRIMARY_TABLE and project_key:
        record_key = projects_record_key_for_project_key(str(project_key))
    else:
        record_key = structured_record_key(
            endpoint_id, project_key, record_id, parent_record_id or None
        )
    incoming_rank = _rank(source_quality)
    if _existing_source_quality_rank(conn, plan.primary_table, record_key) > incoming_rank:
        receipt["endpoint_specific_projection_status"] = "skipped_higher_quality"
        return receipt

    adapter = endpoint_registry.get(endpoint_id)
    family = adapter.family if adapter else endpoint_id
    company_id = payload.get("company_id")
    project_id = payload.get("project_id") or procore_project_id

    _upsert_primary(
        conn,
        plan=plan,
        record_key=record_key,
        endpoint_id=endpoint_id,
        family=family,
        project_key=project_key,
        project_id=project_id,
        company_id=company_id,
        record_id=record_id,
        parent_record_id=parent_record_id,
        payload=payload,
        raw_payload_id=raw_payload_id,
        payload_hash=payload_hash,
        source_quality=source_quality,
        fetched_at=fetched_at,
        now_utc=now_utc,
    )
    receipt["primary_rows"] = 1

    for child in plan.child_tables:
        _delete_child_rows(conn, child.table, record_key)
        written = _insert_child_rows(
            conn,
            plan=plan,
            child=child,
            primary_record_key=record_key,
            endpoint_id=endpoint_id,
            family=family,
            project_key=project_key,
            project_id=project_id,
            company_id=company_id,
            payload=payload,
            raw_payload_id=raw_payload_id,
            payload_hash=payload_hash,
            source_quality=source_quality,
            now_utc=now_utc,
        )
        if written:
            receipt["child_rows_by_table"][child.table] = written
            receipt["child_rows"] += written
    return receipt


def _upsert_primary(
    conn: sqlite3.Connection,
    *,
    plan: registry.EndpointPlan,
    record_key: str,
    endpoint_id: str,
    family: str,
    project_key: str | None,
    project_id: str | None,
    company_id: Any,
    record_id: str,
    parent_record_id: str | None,
    payload: dict[str, Any],
    raw_payload_id: str,
    payload_hash: str,
    source_quality: str,
    fetched_at: str | None,
    now_utc: str,
) -> None:
    values: dict[str, Any] = {
        "record_key": record_key,
        "raw_payload_id": raw_payload_id,
        "endpoint_key": endpoint_id,
        "endpoint_family": family,
        "project_key": project_key,
        "project_id": str(project_id) if project_id is not None else None,
        "project_id_hash": _hash(str(project_id)) if project_id is not None else None,
        "company_id": str(company_id) if company_id not in (None, "") else None,
        "company_id_hash": _hash(str(company_id)) if company_id not in (None, "") else None,
        "record_id": record_id,
        "record_id_hash": _hash(record_id),
        "parent_record_id": parent_record_id,
        "parent_record_id_hash": _hash(parent_record_id) if parent_record_id else None,
    }
    for rel, column in plan.primary_columns:
        values[column] = _scalar(pp.get_relative(payload, rel))
    values["payload_sidecar_json"] = _primary_sidecar(plan, payload)
    values.update(
        {
            "payload_hash": payload_hash,
            "source_quality": source_quality,
            "payload_seen_first_utc": fetched_at,
            "payload_seen_last_utc": fetched_at,
            "is_current": 1,
            "created_utc": now_utc,
            "updated_utc": now_utc,
        }
    )
    conflict_key = primary_upsert_conflict_key(plan.primary_table)
    if conflict_key == "project_key":
        if not project_key or not str(project_key).strip():
            return
        values["record_key"] = projects_record_key_for_project_key(str(project_key))
    _upsert(conn, plan.primary_table, values, conflict_key=conflict_key)


def _insert_child_rows(
    conn: sqlite3.Connection,
    *,
    plan: registry.EndpointPlan,
    child: registry.ChildTable,
    primary_record_key: str,
    endpoint_id: str,
    family: str,
    project_key: str | None,
    project_id: str | None,
    company_id: Any,
    payload: dict[str, Any],
    raw_payload_id: str,
    payload_hash: str,
    source_quality: str,
    now_utc: str,
) -> int:
    # An array NODE path is iterated by appending one ``[]`` level, so its chain length is
    # one more than the ancestor-array count; the parent item lives at the prefix.
    parent_levels = (_array_levels(child.parent_array_path) + 1) if child.parent_array_path else 0
    written = 0
    for chain, item in _iter_items(payload, child.array_path):
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        parent_item_id = None
        if child.parent_array_path:
            parent_item = _resolve_item_at(payload, child.parent_array_path, chain[:parent_levels])
            if isinstance(parent_item, dict):
                parent_item_id = parent_item.get("id")
        values: dict[str, Any] = {
            "record_key": _child_record_key(primary_record_key, child.array_path, chain, item_id),
            "primary_record_key": primary_record_key,
            "parent_item_id": str(parent_item_id) if parent_item_id is not None else None,
            "raw_payload_id": raw_payload_id,
            "endpoint_key": endpoint_id,
            "endpoint_family": family,
            "project_key": project_key,
            "project_id": str(project_id) if project_id is not None else None,
            "company_id": str(company_id) if company_id not in (None, "") else None,
            "item_id": str(item_id) if item_id is not None else None,
            "child_index": chain[-1] if chain else None,
            "array_path": child.array_path,
        }
        for rel, column in child.columns:
            values[column] = _scalar(pp.get_relative(item, rel))
        values["payload_sidecar_json"] = _child_sidecar(plan, child, item)
        values.update(
            {
                "payload_hash": payload_hash,
                "source_quality": source_quality,
                "is_current": 1,
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )
        _upsert(conn, child.table, values, conflict_key="record_key")
        written += 1
    return written


def _primary_sidecar(plan: registry.EndpointPlan, payload: dict[str, Any]) -> str | None:
    """Lossless remainder: payload minus top-level child arrays and top-level promoted
    columns. Nested objects (whose deeper leaves may be columns) are kept whole."""
    drop = {"id", "company_id", "project_id"}
    drop |= {rel for rel, _ in plan.primary_columns if "." not in rel and "[]" not in rel}
    for child in plan.child_tables:
        seg = _top_segment(child.array_path)
        if seg:
            drop.add(seg)
    remainder = {k: v for k, v in payload.items() if k not in drop}
    return json.dumps(remainder, sort_keys=True, separators=(",", ":")) if remainder else None


def _child_sidecar(
    plan: registry.EndpointPlan, child: registry.ChildTable, item: dict[str, Any]
) -> str | None:
    drop = {"id"}
    drop |= {rel for rel, _ in child.columns if "." not in rel and "[]" not in rel}
    # Drop only grandchild arrays that are DIRECT top-level keys of this item (so they are
    # not duplicated with their grandchild table). Grandchild arrays nested inside an object
    # (rel contains a dot) leave that object intact in the sidecar to stay lossless.
    for gc in plan.child_tables:
        if gc.parent_array_path == child.array_path:
            rel = gc.array_path[len(child.array_path) + 2 :].lstrip(".")
            if rel and "." not in rel:
                drop.add(rel)
    remainder = {k: v for k, v in item.items() if k not in drop}
    return json.dumps(remainder, sort_keys=True, separators=(",", ":")) if remainder else None


def _delete_child_rows(conn: sqlite3.Connection, table: str, primary_record_key: str) -> None:
    conn.execute(f"DELETE FROM {table} WHERE primary_record_key = ?", (primary_record_key,))


def _upsert(
    conn: sqlite3.Connection, table: str, values: dict[str, Any], *, conflict_key: str
) -> None:
    cols = list(values.keys())
    placeholders = ", ".join("?" for _ in cols)
    assignments = ", ".join(
        f"{col}=excluded.{col}" for col in cols if col not in {conflict_key, "created_utc"}
    )
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT({conflict_key}) DO UPDATE SET {assignments}"
    )
    conn.execute(sql, tuple(values[col] for col in cols))


# --- Backfill / replay ------------------------------------------------------------


def backfill_endpoint_specific_from_raw_payloads(
    *,
    db_path: str | Path | None = None,
    apply: bool = False,
    project_key: str | None = None,
    endpoint: str | None = None,
    limit: int = 1000,
    mode: str = MODE_ENFORCE,
) -> dict[str, Any]:
    """Replay full raw payloads (``raw_procore_payload_persisted=1``) into the V47
    endpoint-specific tables. No live Procore calls. Idempotent. Honors source-quality
    precedence. ``apply=False`` is a dry run that writes nothing."""
    with open_connection(Path(db_path) if db_path is not None else None) as conn:
        return _backfill_endpoint_specific_with_conn(
            conn, apply=apply, project_key=project_key, endpoint=endpoint, limit=limit, mode=mode
        )


def _backfill_endpoint_specific_with_conn(
    conn: sqlite3.Connection,
    *,
    apply: bool,
    project_key: str | None,
    endpoint: str | None,
    limit: int,
    mode: str,
) -> dict[str, Any]:
    # Hard pre-write parity guard: verify every planned primary AND child insert column
    # exists physically before any INSERT. A drifted schema returns a structured
    # ``schema_parity_broken`` receipt instead of crashing with sqlite3.OperationalError.
    if apply:
        from .projection_audit import TABLE_MISSING, plan_schema_mismatches

        mismatches = plan_schema_mismatches(conn)
        if mismatches:
            missing_tables = sum(1 for m in mismatches if m[2] == TABLE_MISSING)
            return {
                "command": "hb-assistant procore analytics projection-reprocess",
                "mode": "apply",
                "ok": False,
                "status": "schema_parity_broken",
                "runtime_plan_schema_mismatches": len(mismatches),
                "missing_table_count": missing_tables,
                "missing_column_count": len(mismatches) - missing_tables,
                "mismatches_sample": [
                    {"endpoint_id": e, "table": t, "column": c, "context": ctx}
                    for e, t, c, ctx in mismatches[:50]
                ],
                "primary_rows_written": 0,
                "child_rows_written": 0,
                "external_writeback_performed": 0,
                "hint": "run SQLiteMigrator.apply() to reconcile columns (V48), then retry",
                "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
            }

    in_scope = registry.in_scope_endpoints()
    clauses = ["raw_procore_payload_persisted = 1", "is_current = 1"]
    params: list[Any] = []
    if project_key:
        clauses.append("project_key = ?")
        params.append(project_key)
    if endpoint:
        clauses.append("endpoint_key = ?")
        params.append(endpoint)
    sql = (
        f"SELECT endpoint_key, project_key, project_id, record_id, parent_record_id, "
        f"raw_payload_id, payload_hash, payload_json, source_quality, payload_seen_last_utc "
        f"FROM {RAW_LANDING_TABLE} WHERE {' AND '.join(clauses)} "
        f"ORDER BY endpoint_key, project_key, parent_record_id, record_id LIMIT ?"
    )
    params.append(limit)
    try:
        rows = list(conn.execute(sql, tuple(params)))
    except sqlite3.Error:
        rows = []

    inspected = 0
    primary_written = 0
    child_written = 0
    skipped_out_of_scope = 0
    skipped_higher = 0
    degraded = 0
    by_endpoint: dict[str, dict[str, int]] = {}
    source_quality_breakdown: dict[str, int] = {}
    now_utc = _now()

    def _run(active: sqlite3.Connection) -> None:
        nonlocal inspected, primary_written, child_written
        nonlocal skipped_out_of_scope, skipped_higher, degraded
        for row in rows:
            inspected += 1
            endpoint_id = row[0]
            source_quality_breakdown[row[8]] = source_quality_breakdown.get(row[8], 0) + 1
            if endpoint_id not in in_scope:
                skipped_out_of_scope += 1
                continue
            try:
                payload = json.loads(row[7])
            except (json.JSONDecodeError, TypeError):
                degraded += 1
                continue
            if not isinstance(payload, dict):
                degraded += 1
                continue
            receipt = project_endpoint_specific(
                active,
                endpoint_id=endpoint_id,
                project_key=row[1],
                procore_project_id=row[2],
                record_id=str(row[3]),
                parent_record_id=row[4] or None,
                payload=payload,
                raw_payload_id=row[5],
                payload_hash=row[6],
                source_quality=row[8],
                fetched_at=row[9] or now_utc,
                now_utc=now_utc,
                mode=mode,
            )
            status = receipt["endpoint_specific_projection_status"]
            stats = by_endpoint.setdefault(
                endpoint_id, {"primary": 0, "child": 0, "skipped_higher": 0, "degraded": 0}
            )
            if status == "skipped_higher_quality":
                skipped_higher += 1
                stats["skipped_higher"] += 1
            elif status == "degraded_unknown_projection_fields":
                degraded += 1
                stats["degraded"] += 1
            else:
                primary_written += receipt["primary_rows"]
                child_written += receipt["child_rows"]
                stats["primary"] += receipt["primary_rows"]
                stats["child"] += receipt["child_rows"]

    if apply:
        with transaction(conn):
            _run(conn)

    ok = degraded == 0
    return {
        "command": "hb-assistant procore analytics projection-reprocess",
        "mode": "apply" if apply else "dry_run",
        "enforcement": mode,
        "ok": ok,
        "raw_full_rows_inspected": inspected if apply else len(rows),
        "primary_rows_written": primary_written,
        "child_rows_written": child_written,
        "skipped_out_of_scope_endpoint": skipped_out_of_scope,
        "skipped_due_to_higher_quality": skipped_higher,
        "degraded_unknown_projection_fields": degraded,
        "by_endpoint": by_endpoint,
        "source_quality_breakdown": source_quality_breakdown,
        "live_procore_calls": 0,
        "external_writeback_performed": 0,
        "filters": {"project_key": project_key, "endpoint": endpoint, "limit": limit},
        "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
    }


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "MODE_ENFORCE",
    "MODE_LIVE",
    "UnknownProjectionPath",
    "backfill_endpoint_specific_from_raw_payloads",
    "project_endpoint_specific",
]
