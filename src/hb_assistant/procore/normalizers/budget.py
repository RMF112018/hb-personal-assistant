"""Phase 05 budget normalizers.

Pure functions over raw Procore payloads for the budget surface: budget views +
their detail columns/rows, and budget change history / change line items /
modifications. Never persists, never reads network, never echoes bodies.

Budget column names + view labels are business metadata and are kept; amounts /
quantities are preserved verbatim (decimal-safe); free text (descriptions, notes,
unbudgeted reasons) is reduced to a hash + length + PII-masked excerpt
(``summarize_text``). The projection stays column-name-agnostic — the variable
per-tenant columns live in the separate column catalog, not assumed here.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .financial import (
    extract_currency_config,
    extract_wbs_cost_code,
    person_hash_summary,
    summarize_text,
)
from .financial import parse_amount as _parse_amount

NORMALIZATION_SCHEMA_VERSION = 1

# Named amount fields recognised on a budget detail row (decimal-safe). Optional
# fields are kept only when present — no assumption that every tenant exposes them.
_ROW_AMOUNTS = (
    "original_budget_amount",
    "revised_budget",
    "approved_change_orders",
    "pending_budget_changes",
    "projected_budget",
    "committed_costs",
    "direct_costs",
    "projected_costs",
    "actual_cost",
    "forecast_to_complete",
    "estimated_cost_at_completion",
    "projected_over_under",
    "variance",
    "over_under",
)


def _base(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    category: str,
    correlation_id: str,
    fetched_at: str,
    canonical_fields: Dict[str, Any],
    review_required: bool,
    routing_reason: str,
    entity_stable_key: str,
) -> Dict[str, Any]:
    return {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": entity_stable_key,
        "category": category,
        "review_required": review_required,
        "routing_reason": routing_reason,
        "canonical_fields": canonical_fields,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }


def _require_id(raw: Any, fn: str) -> None:
    if not isinstance(raw, dict):
        raise TypeError(f"{fn} requires a dict payload")
    if raw.get("id") in (None, ""):
        raise ValueError(f"{fn} requires raw['id']")


def _keep_scalars(raw: Dict[str, Any], keys: Any, out: Dict[str, Any]) -> None:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            out[key] = value


def _keep_amounts(raw: Dict[str, Any], keys: Any, out: Dict[str, Any]) -> None:
    for key in keys:
        amount = _parse_amount(raw.get(key))
        if amount is not None:
            out[key] = amount


def _summarize_into(out: Dict[str, Any], raw: Dict[str, Any], keys: Any) -> None:
    for key in keys:
        summary = summarize_text(raw.get(key))
        if summary is not None:
            out[f"{key}_summary"] = summary


def normalize_budget_view(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_budget_view")
    cf: Dict[str, Any] = {}
    _keep_scalars(raw, ("name", "role", "updated_at"), cf)  # name/role are labels (kept)
    _summarize_into(cf, raw, ("description",))
    person = person_hash_summary(raw.get("created_by"))
    if person is not None:
        cf["created_by_ref"] = person
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="budget_views",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=False,
        routing_reason="budget_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def normalize_budget_detail_column(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_budget_detail_column")
    cf: Dict[str, Any] = {}
    # Column definitions are business metadata (no PII) — kept verbatim.
    _keep_scalars(raw, ("name", "type", "position", "aggregatable", "filterable", "groupable"), cf)
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="budget_detail_columns",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=False,
        routing_reason="budget_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def normalize_budget_detail_row(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_budget_detail_row")
    cf: Dict[str, Any] = {}
    _keep_scalars(raw, ("category", "company", "cost_code", "updated_at"), cf)
    # Code identifiers kept as strings (consistent with the projection / repository).
    for id_key in ("wbs_code_id", "cost_code_id", "root_cost_code_id"):
        if raw.get(id_key) is not None:
            cf[id_key] = str(raw[id_key])
    _keep_amounts(raw, _ROW_AMOUNTS, cf)
    forecast = raw.get("budget_forecast")
    if isinstance(forecast, dict):
        fc: Dict[str, Any] = {}
        _keep_amounts(forecast, ("amount", "automatic_amount", "manual_amount"), fc)
        _summarize_into(fc, forecast, ("notes",))
        if fc:
            cf["budget_forecast"] = fc
    cf.update(extract_currency_config(raw))
    cf.update(extract_wbs_cost_code(raw))
    _summarize_into(cf, raw, ("unbudgeted_reason",))
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="budget_detail_rows",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=False,
        routing_reason="budget_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def normalize_budget_change_history(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise TypeError("normalize_budget_change_history requires a dict payload")
    cf: Dict[str, Any] = {}
    # budget_code / column / type are business metadata (kept); values are amounts.
    _keep_scalars(raw, ("budget_code", "column", "type", "created_at"), cf)
    _keep_amounts(raw, ("old_value", "new_value"), cf)
    _summarize_into(cf, raw, ("description",))
    person = person_hash_summary(raw.get("created_by"))
    if person is not None:
        cf["created_by_ref"] = person
    return _base(
        raw if raw.get("id") not in (None, "") else {**raw, "id": "change_history"},
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="budget_change_history",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=False,
        routing_reason="budget_high_sensitivity",
        entity_stable_key=str(raw.get("id") or "change_history"),
    )


def normalize_budget_change_line_item(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_budget_change_line_item")
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        (
            "adjustment_number",
            "budget_change_id",
            "budget_change_number",
            "budget_change_name",
            "budget_change_status",
            "type",
            "uom",
            "wbs_code_id",
        ),
        cf,
    )
    _keep_amounts(raw, ("amount", "quantity"), cf)
    _summarize_into(cf, raw, ("description",))
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="budget_change_line_items",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=False,
        routing_reason="budget_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def normalize_budget_modification(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_budget_modification")
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        (
            "from_budget_line_item_id",
            "to_budget_line_item_id",
            "origin_id",
            "created_at",
            "updated_at",
        ),
        cf,
    )
    _keep_amounts(raw, ("transfer_amount",), cf)
    _summarize_into(cf, raw, ("notes",))
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="budget_modifications",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=False,
        routing_reason="budget_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


__all__: List[str] = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_budget_view",
    "normalize_budget_detail_column",
    "normalize_budget_detail_row",
    "normalize_budget_change_history",
    "normalize_budget_change_line_item",
    "normalize_budget_modification",
]
