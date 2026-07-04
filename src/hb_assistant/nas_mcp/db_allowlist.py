"""Default-deny DB table/column allowlist for NAS MCP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TableAllowSpec:
    table_key: str
    table_name: str
    columns: tuple[str, ...]
    order_by_columns: tuple[str, ...]


# Production proposal — disabled by default until operator approval.
PRODUCTION_TABLE_PROPOSAL: dict[str, TableAllowSpec] = {
    "schema_version": TableAllowSpec(
        table_key="schema_version",
        table_name="schema_version",
        columns=("version", "applied_at"),
        order_by_columns=("version",),
    ),
}

# Scratch/test-only table (enabled via register_test_allowlist).
_TEST_TABLE = TableAllowSpec(
    table_key="nas_mcp_test_items",
    table_name="nas_mcp_test_items",
    columns=("id", "label", "category"),
    order_by_columns=("id", "label", "category"),
)

_registry: dict[str, TableAllowSpec] = dict(PRODUCTION_TABLE_PROPOSAL)


def register_test_allowlist() -> None:
    _registry[_TEST_TABLE.table_key] = _TEST_TABLE


def clear_test_allowlist() -> None:
    _registry.pop(_TEST_TABLE.table_key, None)


def get_table_spec(table_key: str) -> TableAllowSpec:
    spec = _registry.get(table_key)
    if spec is None:
        raise KeyError(f"table_key not allowlisted: {table_key}")
    return spec


def list_allowlisted_table_keys() -> list[str]:
    return sorted(_registry.keys())


def validate_columns(spec: TableAllowSpec, columns: list[str]) -> None:
    if not columns:
        raise ValueError("columns required (SELECT * forbidden)")
    if "*" in columns:
        raise ValueError("SELECT * forbidden")
    allowed = set(spec.columns)
    unknown = [c for c in columns if c not in allowed]
    if unknown:
        raise ValueError(f"columns not allowlisted: {unknown}")


def validate_filter_columns(spec: TableAllowSpec, filters: dict[str, Any]) -> None:
    allowed = set(spec.columns)
    unknown = [k for k in filters if k not in allowed]
    if unknown:
        raise ValueError(f"filter columns not allowlisted: {unknown}")


def validate_order_by(spec: TableAllowSpec, order_by: str | None) -> None:
    if order_by is None:
        return
    if order_by not in spec.order_by_columns:
        raise ValueError(f"order_by not allowlisted: {order_by}")
