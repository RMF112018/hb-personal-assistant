"""Strict field classifiers for forecasting evidence profiling and semantic catalog.

These classifiers reduce false positives in amount/date profiling by using column
name shape, declared SQLite type, and table context — not broad substring matching
alone. No raw values are exported by callers; profiling uses hashes/shapes only.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Mapping, Optional


class AmountFieldKind(StrEnum):
    MONETARY = "true_monetary_amount"
    QUANTITY = "quantity"
    PERCENT = "percentage"
    COUNT = "count"
    BOOLEAN_FLAG = "boolean_flag"
    ENUM_STATUS = "enum_status_dimension"
    IDENTIFIER = "identifier_key"
    TEXT = "text_description"
    EXCLUDED_FALSE_POSITIVE = "excluded_false_positive"
    UNKNOWN = "unknown"


class DateFieldKind(StrEnum):
    CREATED = "created_timestamp"
    UPDATED = "updated_timestamp"
    SUBMITTED = "submitted_timestamp"
    EXECUTED = "executed_date"
    DUE = "due_date"
    BILLING_PERIOD = "billing_period_start_end"
    INVOICE = "invoice_billing_payment_date"
    FORECAST_PERIOD = "forecast_period_month"
    BUSINESS_EVENT = "business_event_date"
    TO_DATE_METRIC = "non_date_to_date_metric"
    UNKNOWN = "unknown"


# Columns that look amount-like but are not numeric aggregates.
_AMOUNT_FALSE_POSITIVE_PATTERNS = (
    re.compile(r"source_of_", re.I),
    re.compile(r"_method$", re.I),
    re.compile(r"^allow_", re.I),
    re.compile(r"^display_", re.I),
    re.compile(r"_status$", re.I),
    re.compile(r"_type$", re.I),
    re.compile(r"_name$", re.I),
    re.compile(r"_title$", re.I),
    re.compile(r"_description$", re.I),
    re.compile(r"_number$", re.I),
    re.compile(r"_code$", re.I),
    re.compile(r"_id$", re.I),
    re.compile(r"_key$", re.I),
    re.compile(r"_hash$", re.I),
    re.compile(r"_url$", re.I),
    re.compile(r"_json$", re.I),
    re.compile(r"_payload$", re.I),
    re.compile(r"invoicing_method", re.I),
    re.compile(r"payment_applications", re.I),
    re.compile(r"work_retainage$", re.I),
    re.compile(r"impact_source", re.I),
    re.compile(r"stage$", re.I),
)

_MONETARY_PATTERNS = (
    re.compile(r"(^|_)(amount|grand_total|total|balance|price|cost|value|payment|retainage|forecast|actual|committed|invoice|over|under|eac|etc|ftc|remaining|scheduled_value|claimed)(_|$)", re.I),
    re.compile(r"(direct_cost|job_to_date_cost|erp_job_to_date|erp_direct)", re.I),
    re.compile(r"(change_order.*amount|line_item_amount|quote_amount|modification_amount)", re.I),
    re.compile(r"(work_completed|materials_presently_stored|subcontractor_claimed)", re.I),
)

_QUANTITY_PATTERNS = (
    re.compile(r"(quantity|qty|units|count_of)", re.I),
    re.compile(r"scheduled_quantity", re.I),
)

_PERCENT_PATTERNS = (
    re.compile(r"(percent|pct|percentage|_rate$)", re.I),
    re.compile(r"retainage_percent", re.I),
)

_COUNT_PATTERNS = (
    re.compile(r"(^|_)(row_count|line_count|attachment_count|days_in_stage)(_|$)", re.I),
)

_BOOLEAN_IN_AMOUNT_CONTEXT = (
    re.compile(r"^(is_|has_|allow_|enable_|display_)", re.I),
    re.compile(r"(confirmed|executed|paid|private|final|active|current)$", re.I),
)

# Financial/progress "to date" metrics — not calendar dates.
_TO_DATE_METRIC_PATTERNS = (
    re.compile(r"to_date($|_)", re.I),
    re.compile(r"job_to_date", re.I),
    re.compile(r"completed_and_stored_to_date", re.I),
    re.compile(r"from_previous_application", re.I),
    re.compile(r"this_period$", re.I),
)

_DATE_TIMESTAMP_PATTERNS = {
    DateFieldKind.CREATED: (re.compile(r"(^created|created_at|created_utc|created_on)", re.I),),
    DateFieldKind.UPDATED: (re.compile(r"(^updated|updated_at|updated_utc|updated_on)", re.I),),
    DateFieldKind.SUBMITTED: (re.compile(r"(submitted_at|submitted_on|submitted_date)", re.I),),
    DateFieldKind.EXECUTED: (re.compile(r"(executed_at|executed_on|executed_date|signed_change_order_received_date)", re.I),),
    DateFieldKind.DUE: (re.compile(r"(due_date|delivery_date)", re.I),),
    DateFieldKind.BILLING_PERIOD: (re.compile(r"(billing_period|period_start|period_end|start_date|end_date)", re.I),),
    DateFieldKind.INVOICE: (re.compile(r"(billing_date|payment_date|invoice_date|paid_date)", re.I),),
    DateFieldKind.FORECAST_PERIOD: (re.compile(r"(forecast_month|forecast_period|period_month)", re.I),),
    DateFieldKind.BUSINESS_EVENT: (re.compile(r"(_date$|_at$|issued_date|received_date|in_status_since)", re.I),),
}


def _declared_type_is_numeric(declared_type: Optional[str]) -> bool:
    if not declared_type:
        return False
    upper = declared_type.upper()
    return any(tok in upper for tok in ("INT", "REAL", "NUM", "DEC", "FLOAT"))


def classify_amount_field(
    *,
    table: str,
    column: str,
    declared_type: Optional[str] = None,
    sample_value_shape: Optional[str] = None,
) -> dict[str, Any]:
    """Classify a column for amount normalization and aggregation eligibility."""
    col = column.strip()
    table_l = table.lower()

    for pat in _AMOUNT_FALSE_POSITIVE_PATTERNS:
        if pat.search(col):
            return _amount_result(AmountFieldKind.EXCLUDED_FALSE_POSITIVE, aggregate=False, reason=f"false_positive:{pat.pattern}")

    for pat in _BOOLEAN_IN_AMOUNT_CONTEXT:
        if pat.search(col):
            return _amount_result(AmountFieldKind.BOOLEAN_FLAG, aggregate=False, reason="boolean_like_name")

    for pat in _PERCENT_PATTERNS:
        if pat.search(col):
            return _amount_result(AmountFieldKind.PERCENT, aggregate=True, normalize="decimal_ratio_document_basis")

    for pat in _QUANTITY_PATTERNS:
        if pat.search(col):
            return _amount_result(AmountFieldKind.QUANTITY, aggregate=True, normalize="decimal")

    for pat in _COUNT_PATTERNS:
        if pat.search(col):
            return _amount_result(AmountFieldKind.COUNT, aggregate=False, normalize="integer")

    for pat in _MONETARY_PATTERNS:
        if pat.search(col):
            return _amount_result(AmountFieldKind.MONETARY, aggregate=True, normalize="decimal")

    if _declared_type_is_numeric(declared_type) and not re.search(r"(id|key|code|hash)$", col, re.I):
        return _amount_result(AmountFieldKind.UNKNOWN, aggregate=False, reason="numeric_type_needs_review")

    if re.search(r"(status|scope|reason|method|origin|source|type|title|name|description|email|url)", col, re.I):
        return _amount_result(AmountFieldKind.ENUM_STATUS, aggregate=False, normalize="normalized_text")

    if re.search(r"(id|key|hash|uuid|record_key)$", col, re.I):
        return _amount_result(AmountFieldKind.IDENTIFIER, aggregate=False, normalize="text_identity")

    if "budget" in table_l and re.search(r"(projected|actual|committed|direct|erp)", col, re.I):
        return _amount_result(AmountFieldKind.MONETARY, aggregate=True, normalize="decimal", reason="budget_table_context")

    return _amount_result(AmountFieldKind.UNKNOWN, aggregate=False, reason="unclassified")


def classify_date_field(
    *,
    table: str,
    column: str,
    declared_type: Optional[str] = None,
    sample_value_shape: Optional[str] = None,
) -> dict[str, Any]:
    """Classify a column for date normalization and forecast time-axis selection."""
    col = column.strip()

    for pat in _TO_DATE_METRIC_PATTERNS:
        if pat.search(col):
            return _date_result(DateFieldKind.TO_DATE_METRIC, parse_as_date=False, reason=f"to_date_metric:{pat.pattern}")

    for kind, patterns in _DATE_TIMESTAMP_PATTERNS.items():
        for pat in patterns:
            if pat.search(col):
                return _date_result(kind, parse_as_date=True)

    if re.search(r"(_utc$|_at$|_date$|_on$)", col, re.I):
        return _date_result(DateFieldKind.BUSINESS_EVENT, parse_as_date=True, reason="suffix_date_like")

    if declared_type and declared_type.upper() == "TEXT" and sample_value_shape == "iso_timestamp":
        return _date_result(DateFieldKind.UNKNOWN, parse_as_date=True, reason="shape_iso_needs_name_review")

    return _date_result(DateFieldKind.UNKNOWN, parse_as_date=False)


def normalize_boolean_value(raw: Any) -> dict[str, Any]:
    """Normalize observed boolean-like values without assuming unknown = false."""
    if raw is None:
        return {"normalized": None, "confidence": "high", "raw_presence": "null"}
    s = str(raw).strip()
    if s == "":
        return {"normalized": None, "confidence": "high", "raw_presence": "blank"}
    low = s.lower()
    if low in {"1", "true", "yes", "y", "t"}:
        return {"normalized": True, "confidence": "high", "raw_presence": "truthy"}
    if low in {"0", "false", "no", "n", "f"}:
        return {"normalized": False, "confidence": "high", "raw_presence": "falsy"}
    return {"normalized": None, "confidence": "low", "raw_presence": "unknown", "requires_review": True}


_STATUS_INCLUSION: Mapping[str, str] = {
    "approved": "included_actual_approved",
    "complete": "included_actual_approved",
    "closed": "included_actual_approved",
    "executed": "included_actual_approved",
    "paid": "included_actual_approved",
    "open": "pending_probability_weighted",
    "pending": "pending_probability_weighted",
    "draft": "pending_probability_weighted",
    "processing": "pending_probability_weighted",
    "review": "pending_probability_weighted",
    "void": "excluded_void",
    "cancelled": "excluded_void",
    "canceled": "excluded_void",
    "deleted": "excluded_void",
    "rejected": "excluded_void",
}


def normalize_status_group(raw: Any, *, table_family: str = "") -> dict[str, Any]:
    """Map raw status to inclusion group; preserve raw value and uncertainty."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return {
            "raw_status": raw,
            "normalized_group": "unresolved",
            "inclusion_logic": "conservative_exclude_pending_review",
            "confidence": "low",
        }
    raw_s = str(raw).strip()
    key = raw_s.lower().replace(" ", "_")
    inclusion = _STATUS_INCLUSION.get(key, "unresolved")
    confidence = "high" if inclusion != "unresolved" else "low"
    return {
        "raw_status": raw_s,
        "normalized_group": key,
        "inclusion_logic": inclusion,
        "confidence": confidence,
        "table_family": table_family,
    }


def _amount_result(
    kind: AmountFieldKind,
    *,
    aggregate: bool,
    normalize: str = "none",
    reason: str = "",
) -> dict[str, Any]:
    return {
        "kind": kind.value,
        "approved_for_aggregation": aggregate,
        "normalization": normalize,
        "reason": reason or kind.value,
    }


def _date_result(
    kind: DateFieldKind,
    *,
    parse_as_date: bool,
    reason: str = "",
) -> dict[str, Any]:
    return {
        "kind": kind.value,
        "parse_as_date": parse_as_date,
        "reason": reason or kind.value,
    }