"""Mechanical field inventory + projection completeness matrix for email/calendar raw
content (Prompt 04A).

Walks the raw tables (scalar columns + nested JSON paths) and classifies every observed
business field path against the committed :mod:`projection_registry` allow-list, producing
the four package completeness metrics per source family:

- ``unmapped_primary_business_fields``
- ``unmapped_nested_business_fields``
- ``observed_nested_arrays_without_child_table_or_mapped_sidecar``
- parent-row parity (``raw_parent_rows`` vs ``projected_parent_rows``)

It emits field names / JSON paths / counts only — never raw values — so it is safe for
``/tmp`` DB-copy validation evidence.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Iterable

from . import projection_registry as reg

# Completeness statuses (Prompt 04D vocabulary).
STATUS_COMPLETE = "complete"
STATUS_COMPLETE_WITH_EXCLUSIONS = "complete_with_policy_exclusions"
STATUS_NO_RAW_ROWS = "no_raw_rows_available_in_current_copy"
STATUS_FAILED_UNMAPPED = "failed_unmapped_fields"


@dataclass
class MatrixRow:
    source_family: str
    source_table: str
    raw_column_or_json_path: str
    observed_type: str
    cardinality: str
    occurrence_count: int
    non_null_count: int
    empty_count: int
    business_category: str
    destination_kind: str
    destination_table: str
    destination_column: str
    extraction_strategy: str
    exclusion_reason: str
    status: str


@dataclass
class FamilyCoverage:
    family: str
    raw_table: str
    structured_table: str
    raw_parent_rows: int
    projected_parent_rows: int
    unmapped_primary_business_fields: int
    unmapped_nested_business_fields: int
    observed_nested_arrays_without_child_table_or_mapped_sidecar: int
    unmapped_primary_samples: list[str] = field(default_factory=list)
    unmapped_nested_samples: list[str] = field(default_factory=list)
    has_exclusions: bool = False
    status: str = STATUS_COMPLETE

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_family": self.family,
            "raw_table": self.raw_table,
            "structured_table": self.structured_table,
            "raw_parent_rows": self.raw_parent_rows,
            "projected_parent_rows": self.projected_parent_rows,
            "unmapped_primary_business_fields": self.unmapped_primary_business_fields,
            "unmapped_nested_business_fields": self.unmapped_nested_business_fields,
            "observed_nested_arrays_without_child_table_or_mapped_sidecar": (
                self.observed_nested_arrays_without_child_table_or_mapped_sidecar
            ),
            "unmapped_primary_samples": self.unmapped_primary_samples[:20],
            "unmapped_nested_samples": self.unmapped_nested_samples[:20],
            "status": self.status,
        }


# --- low-level helpers ------------------------------------------------------------


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    if not _table_exists(conn, table):
        return []
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def _row_count(conn: sqlite3.Connection, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _parse(value: Any) -> Any:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return "__invalid_json__"


def _flatten_paths(obj: Any, prefix: str = "") -> Iterable[str]:
    """Yield every container + leaf path of a JSON object as dotted paths. Lists are yielded
    as a single ``[]`` path (their object items are walked by the caller)."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path
            if isinstance(value, (dict, list)):
                yield from _flatten_paths(value, path)
    elif isinstance(obj, list):
        # path of the list itself already yielded by the parent; mark element shape
        for item in obj:
            if isinstance(item, dict):
                yield from _flatten_paths(item, prefix)


def _resolve_path(obj: Any, path: str | None) -> Any:
    if path is None:
        return obj
    cur = obj
    for seg in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(seg)
        else:
            return None
    return cur


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


# --- coverage computation ---------------------------------------------------------


def compute_family_coverage(
    conn: sqlite3.Connection, plan: reg.SourceFamilyPlan
) -> tuple[FamilyCoverage, list[MatrixRow]]:
    raw_cols = _columns(conn, plan.raw_table)
    raw_rows = _row_count(conn, plan.raw_table)
    projected_rows = _row_count(conn, plan.structured_table)
    rows: list[MatrixRow] = []

    mapped_scalars = plan.mapped_scalar_columns()
    excluded = {e.raw_column: e for e in plan.excluded_columns}
    child_by_column: dict[str, list[reg.ChildArray]] = {}
    for c in plan.child_arrays:
        child_by_column.setdefault(c.source_json_column, []).append(c)
    sidecar_columns = {s.source_json_column for s in plan.sidecar_columns}

    unmapped_primary: list[str] = []
    unmapped_nested: list[str] = []
    arrays_without_dest = 0
    has_exclusions = False

    # --- scalar / business columns ------------------------------------------------
    for col in raw_cols:
        if col == plan.raw_pk:
            continue
        is_json = col.endswith("_json")
        if col in excluded:
            has_exclusions = True
            e = excluded[col]
            rows.append(_matrix_row(plan, col, "column", e.dest_kind, "", "", "excluded", e.reason))
            continue
        if is_json:
            continue  # handled in nested pass
        # business scalar column
        if col in mapped_scalars:
            dest_col = _scalar_dest(plan, col)
            rows.append(
                _matrix_row(
                    plan,
                    col,
                    "column",
                    reg.PRIMARY_COLUMN,
                    plan.structured_table,
                    dest_col,
                    "copy",
                    "",
                )
            )
        else:
            unmapped_primary.append(col)
            rows.append(_matrix_row(plan, col, "column", "UNMAPPED", "", "", "none", ""))

    # --- nested JSON columns ------------------------------------------------------
    for col in raw_cols:
        if not col.endswith("_json"):
            continue
        if col in excluded:
            continue
        is_child_source = col in child_by_column
        is_sidecar = col in sidecar_columns
        if not is_child_source and not is_sidecar:
            # an undeclared JSON column: if any row holds an array-of-objects it is an
            # observed nested array without a destination.
            if _column_has_object_array(conn, plan.raw_table, col):
                arrays_without_dest += 1
                rows.append(
                    _matrix_row(plan, f"{col}[]", "json_path", "UNMAPPED", "", "", "none", "")
                )
            continue
        if is_sidecar and not is_child_source:
            sc = next(s for s in plan.sidecar_columns if s.source_json_column == col)
            rows.append(
                _matrix_row(
                    plan,
                    col,
                    "json_column",
                    reg.LOSSLESS_SIDECAR,
                    plan.structured_table,
                    sc.dest_sidecar_column,
                    "lossless_sidecar",
                    sc.reason,
                )
            )
            continue
        # child-source column: walk declared item keys
        for child in child_by_column[col]:
            observed, type_by_path = _walk_child_keys(conn, plan.raw_table, child)
            allowed = child.declared_item_keys | child.excluded_item_keys
            for path in sorted(observed):
                if path in child.excluded_item_keys:
                    has_exclusions = True
                    dest_kind = reg.EXCLUDED_NON_BUSINESS
                    dest_table = dest_col = ""
                elif path in child.declared_item_keys:
                    dest_kind = reg.CHILD_TABLE_COLUMN
                    dest_table = child.child_table
                    dest_col = _child_dest(child, path)
                else:
                    unmapped_nested.append(f"{child.array_path}.{path}")
                    dest_kind = "UNMAPPED"
                    dest_table = dest_col = ""
                rows.append(
                    MatrixRow(
                        source_family=plan.family,
                        source_table=plan.raw_table,
                        raw_column_or_json_path=f"{child.array_path}.{path}",
                        observed_type=type_by_path.get(path, "string"),
                        cardinality="array_child",
                        occurrence_count=0,
                        non_null_count=0,
                        empty_count=0,
                        business_category="nested",
                        destination_kind=dest_kind,
                        destination_table=dest_table,
                        destination_column=dest_col,
                        extraction_strategy="extract_child_array"
                        if child.source_path is None
                        else "extract_nested_array",
                        exclusion_reason="",
                        status="mapped" if dest_kind != "UNMAPPED" else "unmapped",
                    )
                )
            _ = allowed  # documented intent: declared ∪ excluded is the allow-list

    unmapped_total = len(unmapped_primary) + len(unmapped_nested) + arrays_without_dest
    if raw_rows == 0:
        status = STATUS_NO_RAW_ROWS
    elif unmapped_total > 0:
        status = STATUS_FAILED_UNMAPPED
    elif has_exclusions:
        status = STATUS_COMPLETE_WITH_EXCLUSIONS
    else:
        status = STATUS_COMPLETE

    coverage = FamilyCoverage(
        family=plan.family,
        raw_table=plan.raw_table,
        structured_table=plan.structured_table,
        raw_parent_rows=raw_rows,
        projected_parent_rows=projected_rows,
        unmapped_primary_business_fields=len(unmapped_primary),
        unmapped_nested_business_fields=len(unmapped_nested),
        observed_nested_arrays_without_child_table_or_mapped_sidecar=arrays_without_dest,
        unmapped_primary_samples=unmapped_primary,
        unmapped_nested_samples=unmapped_nested,
        has_exclusions=has_exclusions,
        status=status,
    )
    return coverage, rows


def _column_has_object_array(conn: sqlite3.Connection, table: str, col: str) -> bool:
    try:
        cur = conn.execute(f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL LIMIT 200")
    except sqlite3.Error:
        return False
    for (value,) in cur:
        parsed = _parse(value)
        if isinstance(parsed, list) and any(isinstance(x, dict) for x in parsed):
            return True
    return False


def _walk_child_keys(
    conn: sqlite3.Connection, table: str, child: reg.ChildArray
) -> tuple[set[str], dict[str, str]]:
    observed: set[str] = set()
    type_by_path: dict[str, str] = {}
    try:
        cur = conn.execute(
            f"SELECT {child.source_json_column} FROM {table} "
            f"WHERE {child.source_json_column} IS NOT NULL LIMIT 500"
        )
    except sqlite3.Error:
        return observed, type_by_path
    for (value,) in cur:
        parsed = _parse(value)
        if parsed == "__invalid_json__" or parsed is None:
            continue
        target = _resolve_path(parsed, child.source_path)
        if target is None:
            continue
        items: list[Any]
        if isinstance(target, list):
            items = [x for x in target if isinstance(x, dict)]
        elif isinstance(target, dict):
            items = [target]  # single-object case (e.g. recurrence)
        else:
            continue
        for item in items:
            for path in _flatten_paths(item):
                observed.add(path)
                type_by_path.setdefault(path, _value_type(_resolve_path(item, path)))
    return observed, type_by_path


def _scalar_dest(plan: reg.SourceFamilyPlan, raw_col: str) -> str:
    for f in plan.identity_fields:
        if f.raw_column == raw_col:
            return f.dest_column
    for f in plan.scalar_fields:
        if f.raw_column == raw_col:
            return f.dest_column
    for b in plan.body_fields:
        if b.raw_column == raw_col:
            return b.available_column
    return raw_col


def _child_dest(child: reg.ChildArray, json_key: str) -> str:
    for key, dest in child.item_fields:
        if key == json_key:
            return dest
    for b in child.body_item_fields:
        if b.raw_column == json_key:
            return b.available_column
    return "payload_sidecar_json"


def _matrix_row(
    plan: reg.SourceFamilyPlan,
    path: str,
    cardinality: str,
    dest_kind: str,
    dest_table: str,
    dest_col: str,
    strategy: str,
    reason: str,
) -> MatrixRow:
    status = "mapped"
    if dest_kind == "UNMAPPED":
        status = "unmapped"
    elif dest_kind.startswith("excluded"):
        status = "excluded"
    return MatrixRow(
        source_family=plan.family,
        source_table=plan.raw_table,
        raw_column_or_json_path=path,
        observed_type="",
        cardinality=cardinality,
        occurrence_count=0,
        non_null_count=0,
        empty_count=0,
        business_category="primary" if cardinality == "column" else "nested",
        destination_kind=dest_kind,
        destination_table=dest_table,
        destination_column=dest_col,
        extraction_strategy=strategy,
        exclusion_reason=reason,
        status=status,
    )


def compute_coverage(conn: sqlite3.Connection) -> dict[str, Any]:
    """Full email/calendar projection coverage for the DB on ``conn``."""
    families: list[dict[str, Any]] = []
    matrix_rows: list[MatrixRow] = []
    total_unmapped = 0
    families_with_raw = 0
    for plan in reg.PLANS.values():
        cov, rows = compute_family_coverage(conn, plan)
        families.append(cov.as_dict())
        matrix_rows.extend(rows)
        if cov.raw_parent_rows > 0:
            families_with_raw += 1
            total_unmapped += (
                cov.unmapped_primary_business_fields
                + cov.unmapped_nested_business_fields
                + cov.observed_nested_arrays_without_child_table_or_mapped_sidecar
            )
    ok = total_unmapped == 0
    return {
        "command": "hb-assistant email-calendar raw projection-coverage",
        "ok": ok,
        "registry_version": reg.REGISTRY_VERSION,
        "projection_schema_version": reg.PROJECTION_SCHEMA_VERSION,
        "families_with_raw_rows": families_with_raw,
        "total_unmapped_business_fields": total_unmapped,
        "families": families,
        "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
    }


def matrix_rows_for_db(conn: sqlite3.Connection) -> list[MatrixRow]:
    rows: list[MatrixRow] = []
    for plan in reg.PLANS.values():
        _, family_rows = compute_family_coverage(conn, plan)
        rows.extend(family_rows)
    return rows


MATRIX_CSV_HEADER = [
    "source_family",
    "source_table",
    "raw_column_or_json_path",
    "observed_type",
    "cardinality",
    "occurrence_count",
    "non_null_count",
    "empty_count",
    "business_category",
    "destination_kind",
    "destination_table",
    "destination_column",
    "extraction_strategy",
    "exclusion_reason",
    "status",
]


def matrix_row_as_csv(row: MatrixRow) -> list[str]:
    return [
        row.source_family,
        row.source_table,
        row.raw_column_or_json_path,
        row.observed_type,
        row.cardinality,
        str(row.occurrence_count),
        str(row.non_null_count),
        str(row.empty_count),
        row.business_category,
        row.destination_kind,
        row.destination_table,
        row.destination_column,
        row.extraction_strategy,
        row.exclusion_reason,
        row.status,
    ]


__all__ = [
    "MATRIX_CSV_HEADER",
    "STATUS_COMPLETE",
    "STATUS_COMPLETE_WITH_EXCLUSIONS",
    "STATUS_FAILED_UNMAPPED",
    "STATUS_NO_RAW_ROWS",
    "FamilyCoverage",
    "MatrixRow",
    "compute_coverage",
    "compute_family_coverage",
    "matrix_row_as_csv",
    "matrix_rows_for_db",
]
