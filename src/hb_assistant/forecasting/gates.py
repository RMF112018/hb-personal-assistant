"""Read-only forecasting data-quality gates (double-count, actuals reconciliation, parity).

All gates run against a SQLite DB path in read-only mode. No raw payload bodies are
exported — only keys, counts, and aggregate numeric differences.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

GateMode = Literal["warn", "strict"]

_DEFAULT_ABSOLUTE_THRESHOLD = Decimal("100.00")
_DEFAULT_PERCENT_THRESHOLD = Decimal("0.005")

_APPROVED_CCO_STATUSES = ("approved", "complete", "closed", "executed")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _connect_ro(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    uri = f"file:{path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return Decimal(s.replace(",", "").replace("$", ""))
    except (InvalidOperation, ValueError):
        return None


def _severity_for_mode(mode: GateMode, base: str) -> str:
    if base == "error":
        return "error"
    if mode == "strict" and base == "warning":
        return "error"
    return base


def run_double_count_gate(
    *,
    db_path: str | Path,
    mode: GateMode = "warn",
) -> dict[str, Any]:
    """Detect potential double-count risks across workflow stages."""
    path = str(db_path)
    findings: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []

    with _connect_ro(path) as conn:
        if _table_exists(conn, "procore_ep_change_events_change_items"):
            q_name = "change_event_to_rfq_overlap"
            rows = conn.execute(
                """
                WITH change_event_cost AS (
                  SELECT project_key, budget_code_id,
                         SUM(CASE WHEN latest_cost_values_amount IS NOT NULL
                                   AND TRIM(latest_cost_values_amount) <> '' THEN 1 ELSE 0 END) AS ce_amount_populated
                  FROM procore_ep_change_events_change_items
                  WHERE budget_code_id IS NOT NULL
                  GROUP BY project_key, budget_code_id
                ),
                rfq_cost AS (
                  SELECT ce.project_key, li.cost_code_id AS budget_code_proxy,
                         COUNT(*) AS rfq_line_count
                  FROM procore_ep_rfqs_change_event_change_event_line_items li
                  JOIN procore_ep_rfqs r ON r.record_key = li.primary_record_key
                  JOIN procore_ep_change_events ce ON ce.record_id = r.change_event_id
                  WHERE li.cost_code_id IS NOT NULL
                  GROUP BY ce.project_key, li.cost_code_id
                )
                SELECT ce.project_key, ce.budget_code_id, ce.ce_amount_populated, COALESCE(r.rfq_line_count, 0) AS rfq_line_count
                FROM change_event_cost ce
                LEFT JOIN rfq_cost r ON r.project_key = ce.project_key AND r.budget_code_proxy = ce.budget_code_id
                WHERE ce.ce_amount_populated > 0 AND COALESCE(r.rfq_line_count, 0) > 0
                LIMIT 200
                """
            ).fetchall()
            queries.append({"name": q_name, "ok": True, "row_count": len(rows)})
            for row in rows:
                findings.append(
                    {
                        "query": q_name,
                        "project_key": row["project_key"],
                        "budget_code_key": str(row["budget_code_id"]),
                        "severity": _severity_for_mode(mode, "warning"),
                        "basis": "change_event_and_rfq_same_budget_code",
                        "ce_amount_rows": int(row["ce_amount_populated"]),
                        "rfq_line_count": int(row["rfq_line_count"]),
                        "message": "Change event amounts and RFQ lines share budget code; apply lifecycle precedence.",
                    }
                )

        if _table_exists(conn, "procore_ep_change_events_change_items") and _table_exists(
            conn, "procore_ep_commitment_change_orders"
        ):
            q_name = "change_event_to_approved_cco_overlap"
            status_placeholders = ",".join("?" for _ in _APPROVED_CCO_STATUSES)
            rows = conn.execute(
                f"""
                WITH ce AS (
                  SELECT project_key, budget_code_id,
                         COUNT(*) AS ce_lines
                  FROM procore_ep_change_events_change_items
                  WHERE budget_code_id IS NOT NULL
                    AND latest_cost_values_amount IS NOT NULL
                    AND TRIM(latest_cost_values_amount) <> ''
                  GROUP BY project_key, budget_code_id
                ),
                cco AS (
                  SELECT cc.project_key, COUNT(*) AS approved_cco_count
                  FROM procore_ep_commitment_change_orders cco
                  JOIN procore_ep_commitment_contracts cc ON cc.record_id = cco.contract_id
                  WHERE LOWER(COALESCE(cco.status, '')) IN ({status_placeholders})
                  GROUP BY cc.project_key
                )
                SELECT ce.project_key, ce.budget_code_id, ce.ce_lines, COALESCE(cco.approved_cco_count, 0) AS approved_cco_count
                FROM ce
                JOIN cco ON cco.project_key = ce.project_key
                LIMIT 200
                """,
                _APPROVED_CCO_STATUSES,
            ).fetchall()
            queries.append({"name": q_name, "ok": True, "row_count": len(rows)})
            for row in rows:
                findings.append(
                    {
                        "query": q_name,
                        "project_key": row["project_key"],
                        "budget_code_key": str(row["budget_code_id"]),
                        "severity": _severity_for_mode(mode, "warning"),
                        "basis": "change_event_and_approved_cco_same_project",
                        "ce_lines": int(row["ce_lines"]),
                        "approved_cco_count": int(row["approved_cco_count"]),
                        "message": "Approved CCO exists while change-event amounts remain populated; prefer CCO precedence.",
                    }
                )

        if _table_exists(conn, "procore_ep_budget_detail_rows") and _table_exists(
            conn, "procore_ep_subcontractor_invoice_contract_detail_items"
        ):
            q_name = "budget_actual_plus_invoice_detail_same_code"
            rows = conn.execute(
                """
                SELECT b.project_key, b.budget_code AS budget_code_key,
                       COUNT(DISTINCT b.record_key) AS budget_rows,
                       COUNT(DISTINCT i.line_item_id) AS invoice_detail_rows
                FROM procore_ep_budget_detail_rows b
                JOIN procore_ep_subcontractor_invoice_contract_detail_items i
                  ON CAST(i.cost_code_id AS TEXT) = CAST(b.budget_code_id AS TEXT)
                WHERE b.actual_cost IS NOT NULL AND TRIM(b.actual_cost) <> ''
                  AND i.total_completed_and_stored_to_date IS NOT NULL
                  AND TRIM(i.total_completed_and_stored_to_date) <> ''
                GROUP BY b.project_key, b.budget_code
                LIMIT 200
                """
            ).fetchall()
            queries.append({"name": q_name, "ok": True, "row_count": len(rows)})
            for row in rows:
                findings.append(
                    {
                        "query": q_name,
                        "project_key": row["project_key"],
                        "budget_code_key": row["budget_code_key"],
                        "severity": _severity_for_mode(mode, "warning"),
                        "basis": "budget_cumulative_actual_and_invoice_detail_progress",
                        "budget_rows": int(row["budget_rows"]),
                        "invoice_detail_rows": int(row["invoice_detail_rows"]),
                        "message": "Budget rollup actual and invoice detail progress coexist; do not sum both.",
                    }
                )

        if _table_exists(conn, "procore_ep_budget_modifications") and _table_exists(
            conn, "procore_ep_change_events_change_items"
        ):
            q_name = "budget_modification_and_change_event_overlap"
            rows = conn.execute(
                """
                SELECT bm.project_key, COUNT(*) AS mod_rows,
                       COUNT(DISTINCT ce.budget_code_id) AS ce_codes
                FROM procore_ep_budget_modifications bm
                JOIN procore_ep_change_events_change_items ce
                  ON ce.project_key = bm.project_key
                WHERE ce.budget_code_id IS NOT NULL
                GROUP BY bm.project_key
                HAVING mod_rows > 0 AND ce_codes > 0
                LIMIT 50
                """
            ).fetchall()
            queries.append({"name": q_name, "ok": True, "row_count": len(rows)})
            for row in rows:
                findings.append(
                    {
                        "query": q_name,
                        "project_key": row["project_key"],
                        "severity": "info",
                        "basis": "budget_modification_and_change_event_coexist",
                        "mod_rows": int(row["mod_rows"]),
                        "ce_codes": int(row["ce_codes"]),
                        "message": "Budget modifications and change events coexist; verify budget calculated column precedence.",
                    }
                )

    error_count = sum(1 for f in findings if f["severity"] == "error")
    warning_count = sum(1 for f in findings if f["severity"] == "warning")
    ok = error_count == 0

    return {
        "ok": ok,
        "gate": "forecast_double_count_prevention",
        "db_path": path,
        "checked_at_utc": _utc_now(),
        "mode": mode,
        "finding_count": len(findings),
        "error_count": error_count,
        "warning_count": warning_count,
        "findings": findings,
        "queries": queries,
    }


def run_actuals_reconciliation_gate(
    *,
    db_path: str | Path,
    absolute_threshold: Decimal | str = _DEFAULT_ABSOLUTE_THRESHOLD,
    percent_threshold: Decimal | str = _DEFAULT_PERCENT_THRESHOLD,
    mode: GateMode = "warn",
) -> dict[str, Any]:
    """Reconcile cumulative, monthly, invoice, and ERP actual sources without double-counting."""
    path = str(db_path)
    abs_thr = Decimal(str(absolute_threshold))
    pct_thr = Decimal(str(percent_threshold))
    findings: list[dict[str, Any]] = []

    with _connect_ro(path) as conn:
        if _table_exists(conn, "procore_ep_budget_detail_rows") and _table_exists(
            conn, "forecast_monthly_actuals_by_budget_code"
        ):
            rows = conn.execute(
                """
                SELECT b.project_key, b.budget_code AS budget_code_key,
                       b.actual_cost, m.amount AS monthly_amount
                FROM procore_ep_budget_detail_rows b
                JOIN forecast_monthly_actuals_by_budget_code m
                  ON m.project_key = b.project_key
                 AND m.budget_code_key = b.budget_code
                WHERE b.actual_cost IS NOT NULL AND TRIM(b.actual_cost) <> ''
                  AND m.amount IS NOT NULL AND TRIM(m.amount) <> ''
                LIMIT 500
                """
            ).fetchall()
            for row in rows:
                cumulative = _parse_decimal(row["actual_cost"])
                monthly = _parse_decimal(row["monthly_amount"])
                if cumulative is None or monthly is None:
                    continue
                diff = abs(cumulative - monthly)
                pct = (diff / cumulative) if cumulative != 0 else Decimal(0)
                if diff > abs_thr and pct > pct_thr:
                    findings.append(
                        {
                            "project_key": row["project_key"],
                            "budget_code_key": row["budget_code_key"],
                            "basis": "budget_actual_vs_monthly_actuals",
                            "difference": str(diff),
                            "percent_difference": str(pct),
                            "severity": _severity_for_mode(mode, "warning"),
                            "note": "Cumulative budget actual differs materially from monthly actual; not equivalent without period reconciliation.",
                        }
                    )

        if _table_exists(conn, "procore_ep_budget_detail_rows"):
            rows = conn.execute(
                """
                SELECT project_key, budget_code AS budget_code_key,
                       actual_cost, erp_job_to_date_costs
                FROM procore_ep_budget_detail_rows
                WHERE actual_cost IS NOT NULL AND TRIM(actual_cost) <> ''
                  AND erp_job_to_date_costs IS NOT NULL AND TRIM(erp_job_to_date_costs) <> ''
                LIMIT 500
                """
            ).fetchall()
            for row in rows:
                base = _parse_decimal(row["actual_cost"])
                erp = _parse_decimal(row["erp_job_to_date_costs"])
                if base is None or erp is None:
                    continue
                diff = abs(base - erp)
                pct = (diff / base) if base != 0 else Decimal(0)
                if diff > abs_thr and pct > pct_thr:
                    findings.append(
                        {
                            "project_key": row["project_key"],
                            "budget_code_key": row["budget_code_key"],
                            "basis": "procore_actual_vs_erp_job_to_date",
                            "difference": str(diff),
                            "percent_difference": str(pct),
                            "severity": "info",
                            "note": "ERP and Procore cumulative actuals differ; treat ERP as explicit sidecar.",
                        }
                    )

        if _table_exists(conn, "procore_ep_budget_detail_rows") and _table_exists(
            conn, "procore_ep_subcontractor_invoice_contract_detail_items"
        ):
            rows = conn.execute(
                """
                SELECT b.project_key, b.budget_code AS budget_code_key,
                       b.actual_cost, SUM(CAST(i.total_completed_and_stored_to_date AS REAL)) AS invoice_progress_sum
                FROM procore_ep_budget_detail_rows b
                JOIN procore_ep_subcontractor_invoice_contract_detail_items i
                  ON CAST(i.cost_code_id AS TEXT) = CAST(b.budget_code_id AS TEXT)
                WHERE b.actual_cost IS NOT NULL AND TRIM(b.actual_cost) <> ''
                GROUP BY b.project_key, b.budget_code, b.actual_cost
                LIMIT 200
                """
            ).fetchall()
            for row in rows:
                budget_actual = _parse_decimal(row["actual_cost"])
                invoice_sum = _parse_decimal(row["invoice_progress_sum"])
                if budget_actual is None or invoice_sum is None:
                    continue
                if invoice_sum > budget_actual * (Decimal(1) + pct_thr) and invoice_sum - budget_actual > abs_thr:
                    findings.append(
                        {
                            "project_key": row["project_key"],
                            "budget_code_key": row["budget_code_key"],
                            "basis": "invoice_detail_exceeds_budget_cumulative",
                            "difference": str(invoice_sum - budget_actual),
                            "severity": _severity_for_mode(mode, "warning"),
                            "note": "Invoice detail progress exceeds budget cumulative actual; verify precedence, do not add both.",
                        }
                    )

    error_count = sum(1 for f in findings if f["severity"] == "error")
    warning_count = sum(1 for f in findings if f["severity"] == "warning")
    ok = error_count == 0

    return {
        "ok": ok,
        "gate": "forecast_actuals_reconciliation",
        "db_path": path,
        "checked_at_utc": _utc_now(),
        "mode": mode,
        "absolute_threshold": str(abs_thr),
        "percent_threshold": str(pct_thr),
        "finding_count": len(findings),
        "error_count": error_count,
        "warning_count": warning_count,
        "findings": findings,
    }


def run_projection_parity_gate(*, db_path: str | Path) -> dict[str, Any]:
    """Report row-count mismatches between procore_ep_* and procore_financial_* layers."""
    path = str(db_path)
    pairs = [
        ("procore_ep_commitment_contracts", "procore_financial_contracts", "commitment"),
        ("procore_ep_purchase_order_contracts", "procore_financial_contracts", "purchase_order"),
    ]
    findings: list[dict[str, Any]] = []

    with _connect_ro(path) as conn:
        for ep_table, fin_table, family in pairs:
            if not _table_exists(conn, ep_table) or not _table_exists(conn, fin_table):
                findings.append(
                    {
                        "family": family,
                        "severity": "info",
                        "basis": "table_missing",
                        "ep_table": ep_table,
                        "financial_table": fin_table,
                        "message": "One or both projection layers missing; parity not evaluated.",
                    }
                )
                continue
            ep_count = conn.execute(f"SELECT COUNT(*) FROM {ep_table}").fetchone()[0]
            fin_count = conn.execute(
                f"SELECT COUNT(*) FROM {fin_table} WHERE contract_family = ?",
                (family if family != "commitment" else "commitment",),
            ).fetchone()[0]
            if ep_count != fin_count:
                findings.append(
                    {
                        "family": family,
                        "severity": "warning",
                        "basis": "row_count_mismatch",
                        "ep_table": ep_table,
                        "ep_row_count": ep_count,
                        "financial_table": fin_table,
                        "financial_row_count": fin_count,
                        "message": "Dual projection layers diverge; investigate before modeling.",
                    }
                )

    return {
        "ok": all(f["severity"] != "error" for f in findings),
        "gate": "forecast_projection_parity",
        "db_path": path,
        "checked_at_utc": _utc_now(),
        "finding_count": len(findings),
        "findings": findings,
    }


def run_cost_type_guard_gate(*, db_path: str | Path) -> dict[str, Any]:
    """Report cost_type sparsity; never infer category as cost_type."""
    path = str(db_path)
    findings: list[dict[str, Any]] = []

    with _connect_ro(path) as conn:
        if _table_exists(conn, "procore_ep_budget_detail_rows"):
            row = conn.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN cost_type IS NOT NULL AND TRIM(cost_type) <> '' THEN 1 ELSE 0 END) AS populated,
                       SUM(CASE WHEN category IS NOT NULL AND TRIM(category) <> '' THEN 1 ELSE 0 END) AS category_populated
                FROM procore_ep_budget_detail_rows
                """
            ).fetchone()
            total = int(row["total"] or 0)
            populated = int(row["populated"] or 0)
            cat_pop = int(row["category_populated"] or 0)
            null_rate = 1.0 - (populated / total) if total else 0.0
            findings.append(
                {
                    "table": "procore_ep_budget_detail_rows",
                    "severity": "warning" if null_rate > 0.5 else "info",
                    "cost_type_populated": populated,
                    "cost_type_null_rate": round(null_rate, 4),
                    "category_populated": cat_pop,
                    "message": "category/category_id must not be mapped to cost_type without row-level evidence.",
                    "category_to_cost_type_mapping": "forbidden_unresolved",
                }
            )

    return {
        "ok": True,
        "gate": "forecast_cost_type_guard",
        "db_path": path,
        "checked_at_utc": _utc_now(),
        "finding_count": len(findings),
        "findings": findings,
    }


def run_all_forecasting_gates(
    *,
    db_path: str | Path,
    mode: GateMode = "warn",
) -> dict[str, Any]:
    """Run all forecasting gates and return a combined report."""
    reports = [
        run_double_count_gate(db_path=db_path, mode=mode),
        run_actuals_reconciliation_gate(db_path=db_path, mode=mode),
        run_projection_parity_gate(db_path=db_path),
        run_cost_type_guard_gate(db_path=db_path),
    ]
    return {
        "ok": all(r.get("ok") for r in reports),
        "checked_at_utc": _utc_now(),
        "db_path": str(db_path),
        "mode": mode,
        "gates": reports,
    }