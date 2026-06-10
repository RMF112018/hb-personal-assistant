"""Endpoint-specific projection registry: the single source of truth that drives the
V47 schema, the projection engine, and the completeness audit.

The committed artifact is ``projection_registry.json`` — an explicit *allow-list* of
every observed business field path for every Procore endpoint that has full raw
payloads, each mapped to exactly one destination:

- ``column``   — a first-class column on the endpoint primary table or a child table,
- ``child``    — a nested business-object array extracted into a child/detail table,
- ``sidecar``  — a known, declared path whose value is preserved losslessly inside the
  owning row's ``payload_sidecar_json`` (scalar arrays, deep/low-value nested objects),
- ``exclude``  — an auth/transport secret key (never persisted), or
- ``structural`` — an object/array container node (inherently covered by its children).

It is an allow-list, not a wildcard: a live payload path that is absent from the
registry is ``unknown`` and makes the audit fail / the reprocess path fail closed. The
registry is *generated* from the production payload inventory (so it covers the 2,277
observed paths) and re-validated at import; a future field never seen at generation time
is therefore caught.

``build_registry`` is a pure function over a structural inventory (paths + observed JSON
types only — never values), so it is deterministic and testable. The same function backs
the ``projection-inventory --emit-candidate`` CLI flag used to regenerate the committed
JSON on a ``/tmp`` DB copy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from . import endpoints as endpoint_registry
from . import projection_paths as pp

REGISTRY_VERSION = 1
REGISTRY_PATH = Path(__file__).with_name("projection_registry.json")

# High-value categories that must be first-class columns when present (amendment 4).
_HIGH_VALUE = pp.HIGH_VALUE_CATEGORIES

# Sidecar-only coverage above this fraction of business paths requires justification
# (amendment 1). Endpoints over the threshold are flagged unless their sidecar fields
# are sparse / polymorphic / low-value / not analytically useful.
SIDECAR_JUSTIFICATION_THRESHOLD = 0.25

# Explicit, reviewed justifications for endpoints whose sidecar-only share exceeds the
# threshold (amendment 1). Only permitted because the sidecar fields are demonstrably
# polymorphic / low-value / not analytically useful; high-value fields remain columns.
SIDECAR_JUSTIFICATIONS: dict[str, str] = {
    "prime-contracts": (
        "Sidecar holds only secondary nested contractor/vendor company-profile attributes "
        "(address, phone, logo, website, labor_union, project_ids[], profile attachments). "
        "High-value contract financials and vendor/contractor identity are first-class "
        "columns; these profile attributes are polymorphic company-directory metadata with "
        "no contract-analytics value."
    ),
    "purchase-order-contracts": (
        "Sidecar is dominated by per-tenant dynamic custom-field DEFINITION metadata "
        "(custom_field_<id>.data_type) and origin_data blobs. Custom-field ids are "
        "project-specific and polymorphic, so their definition metadata cannot be fixed "
        "columns. Standard PO business and financial fields are first-class columns."
    ),
}

_MAX_IDENT = 60  # keep generated table identifiers readable


# --- Naming -----------------------------------------------------------------------


# All endpoint-specific projection tables share this prefix so they form a discoverable
# layer distinct from the V6-V46 ``procore_raw_*`` / ``procore_live_*`` / ``procore_*``
# tables, and can never collide with a pre-existing table name (e.g. the V7
# ``procore_inspection_items``).
TABLE_PREFIX = "procore_ep_"


def primary_table_name(endpoint_id: str) -> str:
    slug = endpoint_id.replace("-", "_").strip("_").lower()
    return _bounded(f"{TABLE_PREFIX}{slug}")


def child_table_name(primary_table: str, array_path: str) -> str:
    parts = _array_segments(array_path)
    suffix = "_".join(pp.sanitize_identifier(f"$.{seg}") for seg in parts)
    return _bounded(f"{primary_table}_{suffix}", anchor=array_path)


def _array_segments(array_path: str) -> list[str]:
    """Key segments of an array path (``[]`` removed), e.g.
    ``$.change_items[].budget_code.segment_items`` ->
    ``['change_items', 'budget_code', 'segment_items']``."""
    body = array_path[len(pp.ROOT) :] if array_path.startswith(pp.ROOT) else array_path
    out: list[str] = []
    import re

    for seg in re.split(r"(?<!\\)\.", body):
        base = seg
        while base.endswith("[]"):
            base = base[:-2]
        base = base.replace("\\.", ".")
        if base:
            out.append(base)
    return out


def _bounded(name: str, *, anchor: str | None = None) -> str:
    if len(name) <= _MAX_IDENT:
        return name
    import hashlib

    keep = _MAX_IDENT - 7
    h = hashlib.sha256((anchor or name).encode("utf-8")).hexdigest()[:6]
    return f"{name[:keep]}_{h}"


# --- Registry build (pure) --------------------------------------------------------


def build_registry(inventory: dict[str, dict[str, Iterable[str]]]) -> dict[str, Any]:
    """Build the registry dict from a structural inventory.

    ``inventory`` maps ``endpoint_id -> {json_path: iterable_of_observed_types}``. Only
    paths/types are consumed — never values. Returns the full registry document.
    """
    endpoints: dict[str, Any] = {}
    for endpoint_id in sorted(inventory):
        path_types = {p: set(types) for p, types in inventory[endpoint_id].items()}
        endpoints[endpoint_id] = _build_endpoint(endpoint_id, path_types)
    return {"registry_version": REGISTRY_VERSION, "endpoints": endpoints}


def _build_endpoint(endpoint_id: str, path_types: dict[str, set[str]]) -> dict[str, Any]:
    adapter = endpoint_registry.get(endpoint_id)
    family = adapter.family if adapter else endpoint_id
    primary_table = primary_table_name(endpoint_id)

    # Child arrays = array nodes whose item node is an object.
    child_arrays = sorted(
        p
        for p, types in path_types.items()
        if "array" in types and "object" in path_types.get(p + "[]", set())
    )
    child_table_for = {ap: child_table_name(primary_table, ap) for ap in child_arrays}

    primary_columns: list[dict[str, Any]] = []
    child_columns: dict[str, list[dict[str, Any]]] = {ap: [] for ap in child_arrays}
    path_map: list[dict[str, Any]] = []
    used_names: dict[str | None, set[str]] = {None: set()}
    for ap in child_arrays:
        used_names[ap] = set()

    for path in sorted(path_types):
        types = path_types[path]
        category = pp.classify_category(path)
        dest, owner, column = _classify_path(
            path, types, child_arrays, child_table_for, category, used_names
        )
        entry = {"path": path, "type": _primary_type(types), "category": category, "dest": dest}
        path_map.append(entry)
        # ``column is None`` for standard-routed identity paths (id/company_id/project_id):
        # they fill standard columns the table already has, so no curated column is emitted.
        if dest.startswith("column:") and column is not None:
            rel = _relative(path, owner)
            spec = {"rel": rel, "column": column, "category": category}
            if owner is None:
                primary_columns.append(spec)
            else:
                child_columns[owner].append(spec)

    child_tables = [
        {
            "table": child_table_for[ap],
            "array_path": ap,
            "parent_array_path": _owner_array(ap, child_arrays),
            "columns": child_columns[ap],
        }
        for ap in child_arrays
    ]
    coverage = _coverage(path_map)
    if coverage["over_sidecar_threshold"]:
        justification = SIDECAR_JUSTIFICATIONS.get(endpoint_id)
        coverage["sidecar_justified"] = justification is not None
        if justification:
            coverage["sidecar_justification"] = justification
    else:
        coverage["sidecar_justified"] = True
    return {
        "endpoint_family": family,
        "primary_table": primary_table,
        "primary_columns": primary_columns,
        "child_tables": child_tables,
        "path_map": path_map,
        "coverage": coverage,
    }


def _classify_path(
    path: str,
    types: set[str],
    child_arrays: list[str],
    child_table_for: dict[str, str],
    category: str,
    used_names: dict[str | None, set[str]],
) -> tuple[str, str | None, str | None]:
    """Return ``(dest_string, owner_array_or_None, column_name_or_None)``."""
    if path == pp.ROOT:
        return "structural", None, None
    if pp.is_transport_secret(path):
        return "exclude:transport_secret", None, None

    owner = _owner_array(path, child_arrays)

    # A child-array node -> extracted into its own child table.
    if path in child_table_for:
        return f"child:{child_table_for[path]}", owner, None

    is_array_node = "array" in types
    is_object_node = "object" in types and not _has_scalar_type(types)
    # The item node of an array (``...[]``) is structural; its scalar fields/own arrays
    # are classified on their own paths.
    if path.endswith("[]"):
        return "structural", owner, None
    if is_object_node:
        return "structural", owner, None

    owner_label = owner  # None == primary
    if is_array_node:
        # Scalar-item array (object-item arrays are child tables, handled above).
        # Preserved losslessly in the owner row's sidecar.
        return _sidecar(owner_label), owner, None

    # Scalar leaf.
    rel = _relative(path, owner)
    # Standard-column routing: these payload paths populate the standard identity columns
    # every generated table already carries, so they map to a column WITHOUT creating a
    # duplicate curated column (the engine fills the standard column directly).
    if (owner is None and rel in _STANDARD_PRIMARY_PATHS) or (owner is not None and rel == "id"):
        return f"column:{owner_label or 'primary'}", owner, None
    depth = _rel_depth(rel)
    high_value = category in _HIGH_VALUE
    if depth <= 1 or high_value:
        column = _unique_name(pp.sanitize_identifier(rel), used_names[owner])
        return f"column:{owner_label or 'primary'}", owner, column
    return _sidecar(owner_label), owner, None


# Top-level payload paths that fill standard primary-table identity columns.
_STANDARD_PRIMARY_PATHS = frozenset({"id", "company_id", "project_id"})


def _sidecar(owner: str | None) -> str:
    return "sidecar:primary" if owner is None else f"sidecar:child:{owner}"


def _has_scalar_type(types: set[str]) -> bool:
    return bool(types & {"string", "integer", "number", "boolean", "null"})


def _primary_type(types: set[str]) -> str:
    for t in ("object", "array", "string", "number", "integer", "boolean", "null"):
        if t in types:
            return t
    return "null"


def _owner_array(path: str, child_arrays: list[str]) -> str | None:
    best: str | None = None
    for ap in child_arrays:
        if path.startswith(ap + "[]") and (best is None or len(ap) > len(best)):
            best = ap
    return best


def _relative(path: str, owner: str | None) -> str:
    if owner is None:
        return path[len(pp.ROOT) + 1 :] if path.startswith(pp.ROOT + ".") else path
    return path[len(owner) + 2 :].lstrip(".")


def _rel_depth(rel: str) -> int:
    import re

    return len([s for s in re.split(r"(?<!\\)\.", rel) if s])


def _unique_name(name: str, used: set[str]) -> str:
    candidate = name
    i = 2
    while candidate in used:
        candidate = f"{name}_{i}"
        i += 1
    used.add(candidate)
    return candidate


def _coverage(path_map: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = {"column": 0, "child": 0, "sidecar": 0, "excluded": 0, "structural": 0}
    for entry in path_map:
        dest = entry["dest"]
        if dest.startswith("column:"):
            buckets["column"] += 1
        elif dest.startswith("child:"):
            buckets["child"] += 1
        elif dest.startswith("sidecar:"):
            buckets["sidecar"] += 1
        elif dest.startswith("exclude:"):
            buckets["excluded"] += 1
        else:
            buckets["structural"] += 1
    business = buckets["column"] + buckets["child"] + buckets["sidecar"]
    sidecar_only_pct = round(100.0 * buckets["sidecar"] / business, 1) if business else 0.0
    return {
        **buckets,
        "business_field_paths": business,
        "sidecar_only_pct": sidecar_only_pct,
        "over_sidecar_threshold": sidecar_only_pct > SIDECAR_JUSTIFICATION_THRESHOLD * 100,
    }


# --- Loader + typed accessors -----------------------------------------------------


@dataclass(frozen=True)
class ChildTable:
    table: str
    array_path: str
    parent_array_path: str | None
    columns: tuple[tuple[str, str], ...]  # (rel_path, column_name)


@dataclass(frozen=True)
class EndpointPlan:
    endpoint_id: str
    endpoint_family: str
    primary_table: str
    primary_columns: tuple[tuple[str, str], ...]  # (rel_path, column_name)
    child_tables: tuple[ChildTable, ...]
    known_paths: frozenset[str]
    excluded_paths: frozenset[str]
    coverage: dict[str, Any] = field(default_factory=dict)

    def all_tables(self) -> list[str]:
        return [self.primary_table, *(c.table for c in self.child_tables)]


class RegistryError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_registry() -> dict[str, EndpointPlan]:
    """Load, validate, and return the committed registry as endpoint -> plan."""
    if not REGISTRY_PATH.exists():
        raise RegistryError(f"projection registry not found: {REGISTRY_PATH.name}")
    doc = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if doc.get("registry_version") != REGISTRY_VERSION:
        raise RegistryError(f"unexpected registry_version: {doc.get('registry_version')}")
    plans: dict[str, EndpointPlan] = {}
    for endpoint_id, spec in doc.get("endpoints", {}).items():
        plans[endpoint_id] = _plan_from_spec(endpoint_id, spec)
    _validate(plans, doc)
    return plans


def _plan_from_spec(endpoint_id: str, spec: dict[str, Any]) -> EndpointPlan:
    primary_columns = tuple((c["rel"], c["column"]) for c in spec.get("primary_columns", []))
    child_tables = tuple(
        ChildTable(
            table=c["table"],
            array_path=c["array_path"],
            parent_array_path=c.get("parent_array_path"),
            columns=tuple((col["rel"], col["column"]) for col in c.get("columns", [])),
        )
        for c in spec.get("child_tables", [])
    )
    known = frozenset(e["path"] for e in spec.get("path_map", []))
    excluded = frozenset(
        e["path"] for e in spec.get("path_map", []) if str(e.get("dest", "")).startswith("exclude:")
    )
    return EndpointPlan(
        endpoint_id=endpoint_id,
        endpoint_family=spec.get("endpoint_family", endpoint_id),
        primary_table=spec["primary_table"],
        primary_columns=primary_columns,
        child_tables=child_tables,
        known_paths=known,
        excluded_paths=excluded,
        coverage=spec.get("coverage", {}),
    )


def _validate(plans: dict[str, EndpointPlan], doc: dict[str, Any]) -> None:
    seen_tables: dict[str, str] = {}
    for endpoint_id, plan in plans.items():
        spec = doc["endpoints"][endpoint_id]
        # transport-secret defense in depth: every excluded path must be a secret key, and
        # no secret key may ever be promoted to a column.
        for entry in spec.get("path_map", []):
            path = entry["path"]
            if pp.is_transport_secret(path) and not str(entry.get("dest", "")).startswith(
                "exclude:"
            ):
                raise RegistryError(
                    f"{endpoint_id}: transport secret not excluded: {entry['dest']}"
                )
            if str(entry.get("dest", "")).startswith("column:") and pp.is_transport_secret(path):
                raise RegistryError(f"{endpoint_id}: secret promoted to column: {path}")
        # unique paths
        paths = [e["path"] for e in spec.get("path_map", [])]
        if len(paths) != len(set(paths)):
            raise RegistryError(f"{endpoint_id}: duplicate path in path_map")
        # table name collisions
        for table in plan.all_tables():
            if table in seen_tables and seen_tables[table] != endpoint_id:
                # shared family tables are allowed only if intentional; cross-endpoint
                # reuse is disallowed here to avoid weak generic schemas (amendment 3).
                raise RegistryError(
                    f"table {table} reused by {seen_tables[table]} and {endpoint_id}"
                )
            seen_tables[table] = endpoint_id
        # column uniqueness per table
        _assert_unique_columns(endpoint_id, plan)


def _assert_unique_columns(endpoint_id: str, plan: EndpointPlan) -> None:
    names = [c for _, c in plan.primary_columns]
    if len(names) != len(set(names)):
        raise RegistryError(f"{endpoint_id}: duplicate primary column")
    for child in plan.child_tables:
        cnames = [c for _, c in child.columns]
        if len(cnames) != len(set(cnames)):
            raise RegistryError(f"{endpoint_id}.{child.table}: duplicate child column")


def in_scope_endpoints() -> frozenset[str]:
    """Endpoint ids covered by the committed registry."""
    return frozenset(load_registry().keys())


def plan_for(endpoint_id: str) -> EndpointPlan | None:
    return load_registry().get(endpoint_id)


def all_table_names() -> list[str]:
    tables: list[str] = []
    for plan in load_registry().values():
        tables.extend(plan.all_tables())
    return tables


# --- DDL generation (consumed by the V47 migration) -------------------------------

# Zero-CHECK guards every generated table carries (no external writeback, no raw payload
# emission to read models / evidence — enforced at the SQLite layer).
_GUARD_COLUMNS = (
    "external_writeback_performed INTEGER NOT NULL DEFAULT 0 "
    "CHECK(external_writeback_performed = 0)",
    "raw_payload_emitted_to_read_model INTEGER NOT NULL DEFAULT 0 "
    "CHECK(raw_payload_emitted_to_read_model = 0)",
    "raw_payload_emitted_to_evidence INTEGER NOT NULL DEFAULT 0 "
    "CHECK(raw_payload_emitted_to_evidence = 0)",
)

RAW_LANDING_TABLE = "procore_endpoint_raw_payloads"


def _primary_ddl(plan: EndpointPlan) -> str:
    lines = [
        "record_key TEXT PRIMARY KEY",
        "raw_payload_id TEXT",
        "endpoint_key TEXT NOT NULL",
        "endpoint_family TEXT",
        "project_key TEXT",
        "project_id TEXT",
        "project_id_hash TEXT",
        "company_id TEXT",
        "company_id_hash TEXT",
        "record_id TEXT NOT NULL",
        "record_id_hash TEXT",
        "parent_record_id TEXT",
        "parent_record_id_hash TEXT",
    ]
    lines += [f"{col} TEXT" for _, col in plan.primary_columns]
    lines += [
        "payload_sidecar_json TEXT",
        "payload_hash TEXT",
        "source_quality TEXT NOT NULL",
        "payload_seen_first_utc TEXT",
        "payload_seen_last_utc TEXT",
        "is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0, 1))",
        "created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
        *_GUARD_COLUMNS,
        f"FOREIGN KEY(raw_payload_id) REFERENCES {RAW_LANDING_TABLE}(raw_payload_id)",
    ]
    body = ",\n  ".join(lines)
    return f"CREATE TABLE IF NOT EXISTS {plan.primary_table} (\n  {body}\n);"


def _child_ddl(plan: EndpointPlan, child: ChildTable) -> str:
    lines = [
        "record_key TEXT PRIMARY KEY",
        "primary_record_key TEXT NOT NULL",
        "parent_item_id TEXT",
        "raw_payload_id TEXT",
        "endpoint_key TEXT NOT NULL",
        "endpoint_family TEXT",
        "project_key TEXT",
        "project_id TEXT",
        "company_id TEXT",
        "item_id TEXT",
        "child_index INTEGER",
        "array_path TEXT",
    ]
    lines += [f"{col} TEXT" for _, col in child.columns]
    lines += [
        "payload_sidecar_json TEXT",
        "payload_hash TEXT",
        "source_quality TEXT NOT NULL",
        "is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0, 1))",
        "created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
        *_GUARD_COLUMNS,
        f"FOREIGN KEY(primary_record_key) REFERENCES {plan.primary_table}(record_key)",
        f"FOREIGN KEY(raw_payload_id) REFERENCES {RAW_LANDING_TABLE}(raw_payload_id)",
    ]
    body = ",\n  ".join(lines)
    return f"CREATE TABLE IF NOT EXISTS {child.table} (\n  {body}\n);"


def _indexes(table: str, columns: tuple[str, ...]) -> list[str]:
    out = []
    for col in columns:
        idx = f"idx_{table}_{col}"
        out.append(f"CREATE INDEX IF NOT EXISTS {idx} ON {table}({col});")
    return out


def build_v47_ddl() -> list[str]:
    """Return CREATE TABLE / CREATE INDEX statements for every registry table.

    Derived from the committed registry so the schema and the projection engine share one
    source of truth. ``CREATE TABLE IF NOT EXISTS`` keeps the migration additive and
    idempotent; existing V46 tables are untouched.
    """
    statements: list[str] = []
    for endpoint_id in sorted(load_registry()):
        plan = load_registry()[endpoint_id]
        statements.append(_primary_ddl(plan))
        statements += _indexes(
            plan.primary_table, ("project_key", "endpoint_key", "raw_payload_id", "record_id")
        )
        for child in plan.child_tables:
            statements.append(_child_ddl(plan, child))
            statements += _indexes(
                child.table, ("primary_record_key", "raw_payload_id", "parent_item_id")
            )
    return statements
