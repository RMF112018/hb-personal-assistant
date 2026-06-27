"""LAB/LBN cost_code+category attribution (Phase 2b).

No person/fuzzy matching (real cost-entry ``description`` carries no person identity). Attribution
groups attributable (LAB/LBN) actuals by ``(cost_code, category)``; a manual rule maps the group to
a staffing row, otherwise the group aggregates into the review bucket. MAT actuals are summarized by
cost_code only (never row-attributed, never in the review bucket). Idempotent end to end.
"""

from __future__ import annotations

from typing import Any

from hb_assistant.store.connection import open_connection, transaction

from ._common import assert_schema, stable_id, sum_decimals, utc_now
from .actuals_projection import project_staffing_actuals
from .repositories import AttributionReviewRepository, AttributionRuleRepository


def _review_id(project_key: str, cost_code: str, category: str) -> str:
    return stable_id("staffing-review", project_key, cost_code, category)


def refresh_attribution(db_path: str, project_key: str) -> dict[str, int]:
    """Apply rules to attributable actuals + (re)build the unmatched review bucket. Idempotent."""
    now = utc_now()
    matched_groups = 0
    review_items = 0
    with open_connection(db_path) as conn:
        assert_schema(conn)
        groups = conn.execute(
            "SELECT DISTINCT cost_code, category FROM forecast_cost_entry_staffing_actuals "
            "WHERE project_key = ? AND is_employee_attributable = 1",
            (project_key,),
        ).fetchall()
        with transaction(conn):
            for cost_code, category in groups:
                rule = conn.execute(
                    "SELECT attribution_rule_id, staffing_config_id "
                    "FROM forecast_project_staffing_attribution_rules "
                    "WHERE project_key = ? AND cost_code = ? AND category = ? "
                    "AND active_status = 'active' ORDER BY created_utc DESC LIMIT 1",
                    (project_key, cost_code, category),
                ).fetchone()
                if rule is not None:
                    conn.execute(
                        "UPDATE forecast_cost_entry_staffing_actuals "
                        "SET staffing_config_id = ?, attribution_rule_id = ?, "
                        "attribution_status = 'matched_rule', updated_utc = ? "
                        "WHERE project_key = ? AND cost_code = ? AND category = ? "
                        "AND is_employee_attributable = 1",
                        (rule[1], rule[0], now, project_key, cost_code, category),
                    )
                    conn.execute(
                        "DELETE FROM forecast_project_staffing_attribution_review_items "
                        "WHERE review_item_id = ? AND review_status != 'resolved'",
                        (_review_id(project_key, cost_code, category),),
                    )
                    matched_groups += 1
                    continue

                # unmatched: reset attribution + aggregate into the review bucket
                conn.execute(
                    "UPDATE forecast_cost_entry_staffing_actuals "
                    "SET staffing_config_id = NULL, attribution_rule_id = NULL, "
                    "attribution_status = 'unmatched', updated_utc = ? "
                    "WHERE project_key = ? AND cost_code = ? AND category = ? "
                    "AND is_employee_attributable = 1",
                    (now, project_key, cost_code, category),
                )
                rows = conn.execute(
                    "SELECT amount, accounting_month, description "
                    "FROM forecast_cost_entry_staffing_actuals "
                    "WHERE project_key = ? AND cost_code = ? AND category = ? "
                    "AND is_employee_attributable = 1",
                    (project_key, cost_code, category),
                ).fetchall()
                amount = sum_decimals(r[0] for r in rows)
                months = sorted(m for m in (r[1] for r in rows) if m)
                label = next((r[2] for r in rows if r[2]), None)
                conn.execute(
                    "INSERT INTO forecast_project_staffing_attribution_review_items "
                    "(review_item_id, project_key, cost_code, category, description_label, "
                    "actuals_start_month, actuals_through_month, actual_amount, "
                    "suggested_staffing_config_id, review_status, resolved_staffing_config_id, "
                    "resolved_by_role, created_utc, updated_utc, raw_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'unmatched', NULL, NULL, ?, ?, '{}') "
                    "ON CONFLICT(review_item_id) DO UPDATE SET "
                    "description_label = excluded.description_label, "
                    "actuals_start_month = excluded.actuals_start_month, "
                    "actuals_through_month = excluded.actuals_through_month, "
                    "actual_amount = excluded.actual_amount, updated_utc = excluded.updated_utc "
                    "WHERE forecast_project_staffing_attribution_review_items.review_status "
                    "!= 'resolved'",
                    (
                        _review_id(project_key, cost_code, category),
                        project_key,
                        cost_code,
                        category,
                        label,
                        months[0] if months else None,
                        months[-1] if months else None,
                        amount,
                        now,
                        now,
                    ),
                )
                review_items += 1
    return {"matched_groups": matched_groups, "review_items": review_items}


def rebuild(db_path: str, project_key: str) -> dict[str, int]:
    """Project cost entries then (re)apply attribution. The full idempotent pipeline."""
    projected = project_staffing_actuals(db_path, project_key)
    applied = refresh_attribution(db_path, project_key)
    return {**projected, **applied}


def resolve_review_item(
    db_path: str,
    review_item_id: str,
    *,
    staffing_config_id: str,
    resolved_by_role: str | None = None,
) -> dict[str, Any]:
    """Resolve a review item: persist a manual rule + re-apply so future runs auto-match."""
    reviews = AttributionReviewRepository(db_path=db_path)
    item = reviews.get(review_item_id)
    if item is None:
        raise ValueError(f"unknown review item {review_item_id}")
    AttributionRuleRepository(db_path=db_path).upsert_rule(
        project_key=item["project_key"],
        cost_code=item["cost_code"],
        category=item["category"],
        staffing_config_id=staffing_config_id,
        match_source="manual_review",
        created_by_role=resolved_by_role,
    )
    reviews.resolve(
        review_item_id, staffing_config_id=staffing_config_id, resolved_by_role=resolved_by_role
    )
    refresh_attribution(db_path, item["project_key"])
    return {"resolved": review_item_id, "project_key": item["project_key"]}


def list_unmatched_actuals(db_path: str, project_key: str) -> list[dict[str, Any]]:
    """The unmatched LAB/LBN review bucket (aggregated by cost_code + category)."""
    return AttributionReviewRepository(db_path=db_path).list(project_key, status="unmatched")
