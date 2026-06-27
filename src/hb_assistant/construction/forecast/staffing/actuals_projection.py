"""Normalized staffing-actuals projection (Phase 2b).

Projects ``forecast_cost_entries`` (FLAT ``raw_json``) into the normalized
``forecast_cost_entry_staffing_actuals`` table, keyed idempotently by ``cost_entry_id``. Reads
ONLY ``cost_code`` / ``category`` / ``description`` / ``amount`` / ``accounting_date`` /
``accounting_month`` / ``budget_code_key`` — never ``tran_type`` or ``application_of_origin`` (those
must not influence association). ``description`` is a context label, not a person identity.

Classification by ``category``:
- LAB / LBN -> staffing-attributable (``attribution_status='unmatched'`` until a rule matches).
- MAT       -> ``not_applicable_materials`` (summarized by cost_code elsewhere; never row-attributed).
- other     -> ``not_applicable_non_staffing``.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from hb_assistant.store.connection import open_connection, transaction

from ._common import assert_schema, stable_id, upsert, utc_now

_ATTRIBUTABLE = frozenset({"LAB", "LBN"})


def _amount_str(value: Any) -> str | None:
    """Money to a 2dp Decimal string. Accepts the float/int/str forms seen in cost-entry rows."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError):
        return None


def _key_part(budget_code_key: Any, index: int) -> str | None:
    """sub_job.cost_code.category -> the requested part (1=cost_code, 2=category)."""
    if not isinstance(budget_code_key, str):
        return None
    parts = budget_code_key.split(".")
    if len(parts) != 3 or not all(parts):
        return None
    return parts[index]


def _classify(category: str | None) -> tuple[int, str]:
    if category in _ATTRIBUTABLE:
        return 1, "unmatched"
    if category == "MAT":
        return 0, "not_applicable_materials"
    return 0, "not_applicable_non_staffing"


def project_staffing_actuals(db_path: str, project_key: str) -> dict[str, int]:
    """(Re)project all cost entries for a project into the normalized actuals table. Idempotent."""
    now = utc_now()
    projected = 0
    with open_connection(db_path) as conn:
        assert_schema(conn)
        entries = conn.execute(
            "SELECT cost_entry_id, raw_json FROM forecast_cost_entries WHERE project_key = ? "
            "ORDER BY source_row_number",
            (project_key,),
        ).fetchall()
        with transaction(conn):
            for cost_entry_id, raw_json in entries:
                row = json.loads(raw_json)
                budget_code_key = row.get("budget_code_key")
                cost_code = row.get("cost_code") or _key_part(budget_code_key, 1)
                category = row.get("category") or _key_part(budget_code_key, 2)
                attributable, status = _classify(category)
                values = {
                    "staffing_actual_id": stable_id("staffing-actual", cost_entry_id),
                    "cost_entry_id": cost_entry_id,
                    "project_key": project_key,
                    "budget_code_key": budget_code_key,
                    "cost_code": cost_code,
                    "category": category,
                    "accounting_date": row.get("accounting_date"),
                    "accounting_month": row.get("accounting_month"),
                    "amount": _amount_str(row.get("amount")),
                    "description": row.get("description"),
                    "employee_name_source": None,
                    "employee_name_normalized": None,
                    "is_employee_attributable": attributable,
                    "attribution_status": status,
                    "staffing_config_id": None,
                    "attribution_rule_id": None,
                    "created_utc": now,
                    "updated_utc": now,
                    "raw_json": "{}",
                }
                upsert(
                    conn,
                    "forecast_cost_entry_staffing_actuals",
                    values,
                    ("staffing_actual_id",),
                )
                projected += 1
    return {"projected": projected}
