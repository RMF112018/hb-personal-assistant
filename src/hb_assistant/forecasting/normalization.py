"""Runtime field normalization using forecasting field classifiers.

Preserves raw source values alongside normalized outputs. Unknown fields are not
silently coerced into amounts or dates.
"""

from __future__ import annotations

from typing import Any

from hb_assistant.forecasting.field_classifiers import classify_amount_field, classify_date_field
from hb_assistant.procore.normalizers.financial import (
    classify_amount,
    parse_amount,
    to_canonical_decimal_text,
)


def field_amount_parse_allowed(*, table: str, column: str, declared_type: str | None = None) -> dict[str, Any]:
    """Return classifier decision for whether a column may be parsed as numeric."""
    return classify_amount_field(table=table, column=column, declared_type=declared_type)


def field_date_parse_allowed(*, table: str, column: str, declared_type: str | None = None) -> dict[str, Any]:
    """Return classifier decision for whether a column may be parsed as a date."""
    return classify_date_field(table=table, column=column, declared_type=declared_type)


def normalize_amount_field(
    value: Any,
    *,
    table: str,
    column: str,
    field_path: str | None = None,
    declared_type: str | None = None,
    currency_code: str | None = None,
    policy: dict | None = None,
) -> dict[str, Any]:
    """Normalize a monetary/quantity/percent field with classifier guard."""
    classification = classify_amount_field(table=table, column=column, declared_type=declared_type)
    path = field_path or f"{table}.{column}"
    raw_presence = "null" if value is None else ("blank" if str(value).strip() == "" else "present")

    if not classification["approved_for_aggregation"] and classification["kind"] in {
        "excluded_false_positive",
        "boolean_flag",
        "enum_status_dimension",
        "identifier_key",
        "text_description",
    }:
        return {
            "parse_status": "rejected",
            "canonical_decimal_text": None,
            "rejection_reason": f"field_classifier_excluded:{classification['kind']}",
            "source_field_path": path,
            "field_classification": classification,
            "raw_value_presence": raw_presence,
            "advisory_only": 1,
        }

    if classification["kind"] == "unknown":
        return {
            "parse_status": "review_required",
            "canonical_decimal_text": None,
            "rejection_reason": "field_classifier_unknown_manual_review",
            "source_field_path": path,
            "field_classification": classification,
            "raw_value_presence": raw_presence,
            "advisory_only": 1,
        }

    result = classify_amount(
        value,
        field_path=path,
        currency_code=currency_code,
        policy=policy,
    )
    result["field_classification"] = classification
    result["raw_value_presence"] = raw_presence
    return result


def normalize_date_field(
    value: Any,
    *,
    table: str,
    column: str,
    declared_type: str | None = None,
) -> dict[str, Any]:
    """Classify and optionally accept a date field; reject to-date financial metrics."""
    classification = classify_date_field(table=table, column=column, declared_type=declared_type)
    raw_presence = "null" if value is None else ("blank" if str(value).strip() == "" else "present")

    if not classification["parse_as_date"]:
        return {
            "parse_as_date": False,
            "normalized_date": None,
            "reason": classification.get("reason") or classification["kind"],
            "field_classification": classification,
            "raw_value_presence": raw_presence,
        }

    s = str(value).strip() if value is not None else ""
    return {
        "parse_as_date": True,
        "normalized_date": s or None,
        "reason": classification.get("reason") or classification["kind"],
        "field_classification": classification,
        "raw_value_presence": raw_presence,
    }


def coerce_numeric_by_classification(
    value: Any,
    *,
    table: str,
    column: str,
    declared_type: str | None = None,
) -> dict[str, Any]:
    """Lightweight numeric coercion path for non-classify_amount callers."""
    classification = classify_amount_field(table=table, column=column, declared_type=declared_type)
    if not classification["approved_for_aggregation"]:
        return {"coerced": None, "field_classification": classification, "skipped": True}
    parsed = parse_amount(value)
    canonical = to_canonical_decimal_text(parsed) if parsed is not None else None
    return {
        "coerced": canonical,
        "field_classification": classification,
        "skipped": False,
    }