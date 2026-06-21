#!/usr/bin/env python3
"""Safe actual/ERP semantics audit (read-only SQLite). No raw financial row values."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)
    ).fetchone()
    return row is not None


def _populated(column: str) -> str:
    return f"{column} IS NOT NULL AND TRIM({column}) <> '' AND TRIM({column}) <> '0'"


def _parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    s = str(value).strip().replace(",", "").replace("$", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def audit_actual_erp_semantics(db_path: Path) -> dict:
    result: dict = {
        "db_path": str(db_path),
        "budget_detail_population": {},
        "per_project_population": [],
        "erp_vs_jtd_aggregate_variance": [],
        "invoice_coverage": {},
        "monthly_actual_coverage": {},
        "forecast_cost_entries_coverage": {},
        "reconciliation_posture": {},
    }

    with _connect_ro(db_path) as conn:
        if _table_exists(conn, "procore_ep_budget_detail_rows"):
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN {_populated('actual_cost')} THEN 1 ELSE 0 END) AS actual_cost_pop,
                       SUM(CASE WHEN {_populated('direct_costs')} THEN 1 ELSE 0 END) AS direct_costs_pop,
                       SUM(CASE WHEN {_populated('job_to_date_costs')} THEN 1 ELSE 0 END) AS jtd_pop,
                       SUM(CASE WHEN {_populated('erp_direct_costs')} THEN 1 ELSE 0 END) AS erp_direct_pop,
                       SUM(CASE WHEN {_populated('erp_job_to_date_costs')} THEN 1 ELSE 0 END) AS erp_jtd_pop,
                       COUNT(DISTINCT project_key) AS projects,
                       COUNT(DISTINCT budget_code) AS budget_codes
                FROM procore_ep_budget_detail_rows
                """
            ).fetchone()
            total = int(row["total"] or 0)
            result["budget_detail_population"] = {
                "total_rows": total,
                "actual_cost_populated": int(row["actual_cost_pop"] or 0),
                "actual_cost_null_rate": round(1 - (int(row["actual_cost_pop"] or 0) / total), 4) if total else 1.0,
                "direct_costs_populated": int(row["direct_costs_pop"] or 0),
                "job_to_date_costs_populated": int(row["jtd_pop"] or 0),
                "erp_direct_costs_populated": int(row["erp_direct_pop"] or 0),
                "erp_job_to_date_costs_populated": int(row["erp_jtd_pop"] or 0),
                "distinct_projects": int(row["projects"] or 0),
                "distinct_budget_codes": int(row["budget_codes"] or 0),
            }

            per_project = conn.execute(
                f"""
                SELECT project_key,
                       SUM(CASE WHEN {_populated('actual_cost')} THEN 1 ELSE 0 END) AS actual_cost_rows,
                       SUM(CASE WHEN {_populated('job_to_date_costs')} THEN 1 ELSE 0 END) AS jtd_rows,
                       SUM(CASE WHEN {_populated('erp_job_to_date_costs')} THEN 1 ELSE 0 END) AS erp_jtd_rows,
                       SUM(CASE WHEN {_populated('direct_costs')} THEN 1 ELSE 0 END) AS direct_rows
                FROM procore_ep_budget_detail_rows
                GROUP BY project_key
                """
            ).fetchall()
            result["per_project_population"] = [dict(r) for r in per_project]

            agg_rows = conn.execute(
                f"""
                SELECT project_key,
                       SUM(CAST(job_to_date_costs AS REAL)) AS jtd_sum,
                       SUM(CAST(erp_job_to_date_costs AS REAL)) AS erp_jtd_sum,
                       COUNT(*) AS compared_rows
                FROM procore_ep_budget_detail_rows
                WHERE {_populated('job_to_date_costs')} AND {_populated('erp_job_to_date_costs')}
                GROUP BY project_key
                """
            ).fetchall()
            for agg in agg_rows:
                jtd = _parse_decimal(agg["jtd_sum"])
                erp = _parse_decimal(agg["erp_jtd_sum"])
                if jtd is None or erp is None or jtd == 0:
                    continue
                diff = abs(jtd - erp)
                pct = float(diff / jtd)
                result["erp_vs_jtd_aggregate_variance"].append(
                    {
                        "project_key": agg["project_key"],
                        "compared_rows": int(agg["compared_rows"]),
                        "aggregate_difference": str(diff),
                        "aggregate_percent_difference": round(pct, 4),
                    }
                )

        if _table_exists(conn, "procore_ep_subcontractor_invoices"):
            inv = conn.execute(
                """
                SELECT COUNT(*) AS invoice_count,
                       COUNT(DISTINCT project_key) AS projects,
                       SUM(CASE WHEN payment_date IS NOT NULL AND TRIM(payment_date) <> '' THEN 1 ELSE 0 END) AS payment_date_pop,
                       SUM(CASE WHEN total_claimed_amount IS NOT NULL AND TRIM(total_claimed_amount) <> '' THEN 1 ELSE 0 END) AS claimed_pop
                FROM procore_ep_subcontractor_invoices
                """
            ).fetchone()
            result["invoice_coverage"] = dict(inv)

        detail_table = "procore_ep_subcontractor_invoice_contract_detail_items"
        if _table_exists(conn, detail_table):
            detail = conn.execute(
                f"""
                SELECT COUNT(*) AS detail_items,
                       COUNT(DISTINCT project_key) AS projects,
                       COUNT(DISTINCT cost_code_id) AS distinct_cost_codes
                FROM {detail_table}
                """
            ).fetchone()
            result["invoice_coverage"]["detail_items"] = int(detail["detail_items"] or 0)
            result["invoice_coverage"]["detail_projects"] = int(detail["projects"] or 0)
            result["invoice_coverage"]["detail_distinct_cost_codes"] = int(detail["distinct_cost_codes"] or 0)

        if _table_exists(conn, "forecast_monthly_actuals_by_budget_code"):
            monthly = conn.execute(
                """
                SELECT COUNT(*) AS monthly_rows,
                       COUNT(DISTINCT project_key) AS projects,
                       COUNT(DISTINCT budget_code_key) AS budget_codes
                FROM forecast_monthly_actuals_by_budget_code
                """
            ).fetchone()
            result["monthly_actual_coverage"] = dict(monthly)

        if _table_exists(conn, "forecast_cost_entries"):
            entries = conn.execute(
                """
                SELECT COUNT(*) AS entry_rows,
                       COUNT(DISTINCT project_key) AS projects,
                       COUNT(DISTINCT budget_code_key) AS budget_codes
                FROM forecast_cost_entries
                """
            ).fetchone()
            result["forecast_cost_entries_coverage"] = dict(entries)

    result["reconciliation_posture"] = {
        "actual_cost": "unresolved_local_column_zero_population; do not use as primary cumulative actual on live copy",
        "job_to_date_costs": "procore_calculated_rollup_direct_plus_invoices_per_procore_doc",
        "erp_job_to_date_costs": "erp_sidecar_not_interchangeable_with_procore_jtd",
        "invoice_progress": "detail_facts_compare_only_not_additive_with_budget_rollups",
        "monthly_actuals": "periodized_training_source_separate_from_cumulative",
        "payment_timing": "cash_flow_fact_not_earned_actual_cost",
        "never_add_together": [
            "budget_cumulative_actual + invoice_detail_progress",
            "procore_job_to_date + erp_job_to_date",
            "monthly_periodized + cumulative_without_period_reconciliation",
        ],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit actual/ERP semantics (read-only)")
    parser.add_argument("--db-path", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = audit_actual_erp_semantics(args.db_path)
    payload = json.dumps(report, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())