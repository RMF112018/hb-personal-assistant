"""Shared path-walking, classification, and identifier helpers for endpoint-specific
Procore structured projection.

This module is the single source of truth for:

- **path normalization** — turning a payload into the set of canonical JSON paths it
  contains, with list indices collapsed to ``[]`` so ``attachments[0].url`` and
  ``attachments[1].url`` map to the one registry path ``$.attachments[].url``. The
  inventory engine, the completeness audit, and the projection engine all import the
  same walker so they can never disagree about what a payload contains.
- **business categorisation** — a deterministic leaf-key classifier that drives which
  fields are promoted to first-class columns (high-value) versus a lossless sidecar.
- **transport-secret exclusion** — reuses ``structured_analytics.AUTH_SECRET_KEY_RE`` so
  the registry exclusions can never diverge from the runtime payload scrubber.
- **SQL identifier sanitisation** — deterministic, collision-free column names derived
  from JSON paths.

Nothing here emits payload *values*; only structural metadata (paths, types, counts,
categories, column names).
"""

from __future__ import annotations

import keyword
import re
from typing import Any, Iterator

# Reuse the exact credential-key matcher used by the live payload scrubber so the
# registry's transport-secret exclusions and the runtime scrub can never diverge.
from .structured_analytics import AUTH_SECRET_KEY_RE

ROOT = "$"

# --- Path walking -----------------------------------------------------------------


def _join(prefix: str, key: str) -> str:
    # Escape a literal dot inside a key so path splitting stays unambiguous.
    safe = str(key).replace(".", "\\.")
    return f"{prefix}.{safe}"


def iter_path_types(value: Any, prefix: str = ROOT) -> Iterator[tuple[str, str]]:
    """Yield ``(normalised_path, observed_type)`` for every node in ``value``.

    ``observed_type`` is one of: ``object``, ``array``, ``string``, ``integer``,
    ``number``, ``boolean``, ``null``. List indices are collapsed to ``[]`` so every
    item of an array shares one canonical path.
    """
    if isinstance(value, dict):
        yield prefix, "object"
        for key, child in value.items():
            yield from iter_path_types(child, _join(prefix, key))
    elif isinstance(value, list):
        yield prefix, "array"
        for child in value:
            yield from iter_path_types(child, f"{prefix}[]")
    else:
        yield prefix, _scalar_type(value)


def _scalar_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def walk_paths(value: Any) -> set[str]:
    """Return the set of canonical (index-collapsed) JSON paths present in ``value``."""
    return {path for path, _ in iter_path_types(value)}


def leaf_key(json_path: str) -> str:
    """Return the final key segment of a canonical path (``[]`` stripped).

    ``$.change_items[].budget_code.flat_code`` -> ``flat_code``.
    ``$.attachments[]`` -> ``attachments``.
    """
    trimmed = json_path
    while trimmed.endswith("[]"):
        trimmed = trimmed[:-2]
    parts = _split_path(trimmed)
    return parts[-1] if parts else ""


def _split_path(json_path: str) -> list[str]:
    body = json_path[len(ROOT) :] if json_path.startswith(ROOT) else json_path
    body = body.lstrip(".")
    if not body:
        return []
    # Split on unescaped dots, then unescape and strip trailing [] tokens per segment.
    raw = re.split(r"(?<!\\)\.", body)
    out: list[str] = []
    for seg in raw:
        seg = seg.replace("\\.", ".")
        while seg.endswith("[]"):
            seg = seg[:-2]
        if seg:
            out.append(seg)
    return out


def path_depth(json_path: str) -> int:
    """Number of key segments below the root. ``$`` -> 0, ``$.a`` -> 1, ``$.a.b`` -> 2."""
    return len(_split_path(json_path))


def is_array_path(json_path: str) -> bool:
    return json_path.endswith("[]")


def under_array(json_path: str) -> bool:
    """True if any ancestor segment of ``json_path`` is an array (contains ``[]``)."""
    return "[]" in json_path[:-2] if json_path.endswith("[]") else "[]" in json_path


# --- Business categorisation ------------------------------------------------------

BusinessCategory = str

# Order matters: first match wins. Patterns match against the lowercased leaf key.
_CATEGORY_RULES: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("identity", re.compile(r"^(id|.*_id|uuid|guid|number|.*_number|full_number|code|.*_code)$")),
    ("date", re.compile(r"(_at$|_date$|^date$|_on$|due|deadline|issued|expires?|timestamp|_utc$)")),
    (
        "money",
        re.compile(
            r"(amount|amounts|total|totals|subtotal|grand_total|sum|price|cost(?!_code)|"
            r"unit_cost|value|balance|retainage|markup|tax|budget|contract_sum|claimed|"
            r"invoiced|billed|payment|paid|currency)"
        ),
    ),
    (
        "quantity",
        re.compile(r"(quantity|qty|count|hours|hour|manpower|workers|uom|unit_of_measure|units?)$"),
    ),
    (
        "cost_code",
        re.compile(
            r"(cost_code|cost_type|wbs|budget_code|flat_code|segment|path_codes?|path_ids?)"
        ),
    ),
    (
        "person",
        re.compile(
            r"(created_by|updated_by|deleted_by|assignee|assignees|assigned_to|"
            r"ball_in_court|responsible|owner|manager|inspector|approver|requester|"
            r"submitter|author|recipient|member|contact|signed_by|received_by|login|email)"
        ),
    ),
    (
        "company",
        re.compile(
            r"(company|companies|vendor|subcontractor|contractor|supplier|organization|firm)"
        ),
    ),
    (
        "attachment",
        re.compile(
            r"(attachment|attachments|file|files|document|documents|url|filename|"
            r"prostore|image|photo|thumbnail|signed)"
        ),
    ),
    ("custom_field", re.compile(r"(custom_field|custom_fields|external_data)")),
    (
        "status",
        re.compile(
            r"(status|state|current_state|stage|phase|disposition|resolution|"
            r"approved|executed|private|closed|deleted|open|review)"
        ),
    ),
    (
        "title",
        re.compile(
            r"(title|subject|name|description|scope|notes?|comment|comments|reason|"
            r"question|answer|body|summary|label|remark)"
        ),
    ),
)

# Categories that MUST be promoted to first-class columns when present (amendment 4):
# money, quantity, unit cost, cost code, WBS/segment, vendor/company, status,
# title/description, date, responsible-party, plus stable identity.
HIGH_VALUE_CATEGORIES = frozenset(
    {"identity", "date", "money", "quantity", "cost_code", "person", "company", "status", "title"}
)


def classify_category(json_path: str) -> BusinessCategory:
    """Classify a path into a coarse business category from its leaf key."""
    key = leaf_key(json_path).lower()
    for category, pattern in _CATEGORY_RULES:
        if pattern.search(key):
            return category
    return "other"


def is_high_value(category: BusinessCategory) -> bool:
    return category in HIGH_VALUE_CATEGORIES


def is_transport_secret(json_path: str) -> bool:
    """True if the leaf key denotes an auth/transport credential (never business data)."""
    return bool(AUTH_SECRET_KEY_RE.search(leaf_key(json_path)))


# --- SQL identifier sanitisation --------------------------------------------------

_SQL_RESERVED_SUFFIX = "_col"


def sanitize_identifier(json_path: str, *, relative_to: str | None = None) -> str:
    """Derive a deterministic, SQL-safe column name from a JSON path.

    ``relative_to`` (a child array path) is stripped first so child columns are named
    by their path *within* the item (``budget_code.flat_code`` -> ``budget_code__flat_code``).
    """
    path = json_path
    if relative_to:
        rel = relative_to
        if path == rel or path.startswith(rel + "."):
            path = path[len(rel) :].lstrip(".") or leaf_key(json_path)
    parts = _split_path(path if path.startswith(ROOT) else f"{ROOT}.{path}")
    if not parts:
        parts = [leaf_key(json_path) or "field"]
    name = "__".join(parts)
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    if not name:
        name = "field"
    if name[0].isdigit():
        name = f"f_{name}"
    if keyword.iskeyword(name) or name in _SQLITE_RESERVED:
        name = f"{name}{_SQL_RESERVED_SUFFIX}"
    return name


# SQLite keywords + the full set of standard projection columns that every generated
# table carries. A payload field whose sanitized name collides with any of these is
# suffixed (``_col``) so it can never shadow a standard column in the generated DDL.
STANDARD_COLUMNS = frozenset(
    {
        "record_key",
        "raw_payload_id",
        "endpoint_key",
        "endpoint_family",
        "project_key",
        "project_id",
        "project_id_hash",
        "company_id",
        "company_id_hash",
        "record_id",
        "record_id_hash",
        "parent_record_id",
        "parent_record_id_hash",
        "primary_record_key",
        "parent_item_id",
        "item_id",
        "child_index",
        "array_path",
        "payload_sidecar_json",
        "payload_hash",
        "source_quality",
        "payload_seen_first_utc",
        "payload_seen_last_utc",
        "is_current",
        "created_utc",
        "updated_utc",
        "external_writeback_performed",
        "raw_payload_emitted_to_read_model",
        "raw_payload_emitted_to_evidence",
    }
)

_SQLITE_RESERVED = STANDARD_COLUMNS | frozenset(
    {
        "index",
        "order",
        "group",
        "select",
        "where",
        "from",
        "table",
        "check",
        "default",
        "references",
        "primary",
        "foreign",
        "unique",
        "values",
        "create",
    }
)


def resolve_arrays(payload: Any, array_path: str) -> Iterator[tuple[list[int], Any]]:
    """Yield ``(index_chain, item)`` for every element matched by ``array_path``.

    ``array_path`` is a canonical path ending in ``[]`` (possibly with intermediate
    ``[]`` segments for arrays nested inside array items). ``index_chain`` records the
    positional index at each ``[]`` level so callers can build deterministic child keys
    and parent-item linkage.
    """
    tokens = _tokenize(array_path)
    yield from _resolve(payload, tokens, [])


def _resolve(
    node: Any, tokens: list[tuple[str, str]], chain: list[int]
) -> Iterator[tuple[list[int], Any]]:
    if not tokens:
        return
    kind, value = tokens[0]
    rest = tokens[1:]
    if kind == "key" and isinstance(node, dict) and value in node:
        yield from _resolve(node[value], rest, chain)
    elif kind == "array" and isinstance(node, list):
        for i, item in enumerate(node):
            new_chain = [*chain, i]
            if not rest:
                yield new_chain, item
            else:
                yield from _resolve(item, rest, new_chain)


def _tokenize(array_path: str) -> list[tuple[str, str]]:
    """Tokenize a canonical path into ('key', name) / ('array', '') tokens in order."""
    body = array_path[len(ROOT) :] if array_path.startswith(ROOT) else array_path
    tokens: list[tuple[str, str]] = []
    for seg in re.split(r"(?<!\\)\.", body):
        if not seg:
            continue
        # A segment may be ``name`` or ``name[]`` or just ``[]`` (after a leading dot trim).
        base = seg
        arrays = 0
        while base.endswith("[]"):
            base = base[:-2]
            arrays += 1
        base = base.replace("\\.", ".")
        if base:
            tokens.append(("key", base))
        for _ in range(arrays):
            tokens.append(("array", ""))
    return tokens


def get_relative(item: Any, rel_path: str) -> Any:
    """Resolve a path relative to a row-owner item. ``rel_path`` like ``budget_code.flat_code``."""
    cur = item
    for part in _split_path(rel_path if rel_path.startswith(ROOT) else f"{ROOT}.{rel_path}"):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur
