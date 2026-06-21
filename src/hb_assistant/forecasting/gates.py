"""Read-only forecasting data-quality gates (double-count, actuals reconciliation, parity).

All gates run against a SQLite DB path in read-only mode. No raw payload bodies are
exported — only keys, counts, and aggregate numeric differences.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

GateMode = Literal["warn", "strict"]

_DEFAULT_ABSOLUTE_THRESHOLD = Decimal("100.00")
_DEFAULT_PERCENT_THRESHOLD = Decimal("0.005")

_APPROVED_CCO_STATUSES = ("approved", "complete", "closed", "executed")

_PARITY_PAIR_CONFIGS: tuple[dict[str, Any], ...] = (
    {
        "ep_table": "procore_ep_commitment_contracts",
        "target_table": "procore_financial_contracts",
        "family": "commitment",
        "parity_kind": "contract_family",
        "contract_family": "commitment",
        "ep_key": "record_id",
        "target_key": "contract_id",
        "amount_field": "grand_total",
        "updated_field": "updated_at",
    },
    {
        "ep_table": "procore_ep_purchase_order_contracts",
        "target_table": "procore_financial_contracts",
        "family": "purchase_order",
        "parity_kind": "contract_family",
        "contract_family": "purchase_order",
        "ep_key": "record_id",
        "target_key": "contract_id",
        "amount_field": "grand_total",
        "updated_field": "updated_at",
        "expected_financial_only": ["commitment_backed_po"],
    },
    {
        "ep_table": "procore_ep_prime_contracts",
        "target_table": "procore_financial_contracts",
        "family": "prime",
        "parity_kind": "contract_family",
        "contract_family": "owner",
        "ep_key": "record_id",
        "target_key": "contract_id",
        "amount_field": "grand_total",
        "updated_field": "updated_at",
        "ep_status_field": "status",
    },
    {
        "ep_table": "procore_ep_change_events",
        "target_table": "procore_financial_change_events",
        "family": "change_event",
        "parity_kind": "direct_id",
        "ep_key": "record_id",
        "target_key": "change_event_id",
        "updated_field": "updated_at",
        "ep_status_field": "status_name",
        "target_status_field": "status",
    },
    {
        "ep_table": "procore_ep_subcontractor_invoices",
        "target_table": "procore_financial_subcontractor_invoices",
        "family": "subcontractor_invoice",
        "parity_kind": "direct_id",
        "ep_key": "record_id",
        "target_key": "invoice_id",
        "amount_field": "total_claimed_amount",
        "updated_field": "updated_at",
        "ep_status_field": "status",
    },
    {
        "ep_table": "procore_ep_rfqs",
        "target_table": "procore_financial_rfqs",
        "family": "rfq",
        "parity_kind": "direct_id",
        "ep_key": "record_id",
        "target_key": "rfq_id",
        "updated_field": "updated_at",
        "parity_availability": "unsupported_ep_scope_subset",
        "unsupported_reason": (
            "Financial RFQ projection scope exceeds current EP rfqs endpoint sync; "
            "parity counts are informational only until EP coverage aligns."
        ),
    },
)

_KEY_SAMPLE_LIMIT = 10


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


def _column_populated(column: str) -> str:
    return f"{column} IS NOT NULL AND TRIM({column}) <> '' AND TRIM({column}) <> '0'"


def _abbreviate_gate_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate": report.get("gate"),
        "ok": report.get("ok"),
        "finding_count": report.get("finding_count", 0),
        "warning_count": report.get("warning_count", 0),
        "error_count": report.get("error_count", 0),
    }


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def _pick_column(columns: set[str], candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        if name in columns:
            return name
    return None


def _columns_available(columns: set[str], required: tuple[str, ...]) -> bool:
    return all(name in columns for name in required)


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

        invoice_table = "procore_ep_subcontractor_invoice_contract_detail_items"
        if _table_exists(conn, "procore_ep_budget_detail_rows") and _table_exists(conn, invoice_table):
            budget_cols = _table_columns(conn, "procore_ep_budget_detail_rows")
            invoice_cols = _table_columns(conn, invoice_table)
            invoice_key = _pick_column(
                invoice_cols, ("detail_line_item_id", "line_item_id", "record_id")
            )
            q_name = "budget_actual_plus_invoice_detail_same_code"
            if (
                invoice_key
                and "cost_code_id" in invoice_cols
                and "total_completed_and_stored_to_date" in invoice_cols
                and "budget_code_id" in budget_cols
                and "actual_cost" in budget_cols
            ):
                rows = conn.execute(
                    f"""
                    SELECT b.project_key, b.budget_code AS budget_code_key,
                           COUNT(DISTINCT b.record_key) AS budget_rows,
                           COUNT(DISTINCT i.{invoice_key}) AS invoice_detail_rows
                    FROM procore_ep_budget_detail_rows b
                    JOIN {invoice_table} i
                      ON CAST(i.cost_code_id AS TEXT) = CAST(b.budget_code_id AS TEXT)
                    WHERE b.actual_cost IS NOT NULL AND TRIM(b.actual_cost) <> ''
                      AND i.total_completed_and_stored_to_date IS NOT NULL
                      AND TRIM(i.total_completed_and_stored_to_date) <> ''
                    GROUP BY b.project_key, b.budget_code
                    LIMIT 200
                    """
                ).fetchall()
            else:
                rows = []
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

        if _table_exists(conn, "procore_ep_budget_detail_rows"):
            from hb_assistant.forecasting.budget_column_roles import overlap_checks

            cols = _table_columns(conn, "procore_ep_budget_detail_rows")
            for check in overlap_checks():
                if not isinstance(check, dict):
                    continue
                check_name = str(check.get("name") or "")
                column_names = tuple(check.get("columns") or ())
                basis = str(check.get("basis") or "budget_column_overlap")
                formula_status = str(check.get("procore_formula_status") or "unresolved")
                base_severity = str(check.get("severity") or "warning")
                if not check_name or not column_names or not all(col in cols for col in column_names):
                    continue
                populated = " AND ".join(_column_populated(col) for col in column_names)
                q_name = f"budget_column_overlap_{check_name}"
                rows = conn.execute(
                    f"""
                    SELECT project_key, budget_code AS budget_code_key, COUNT(*) AS row_count
                    FROM procore_ep_budget_detail_rows
                    WHERE {populated}
                    GROUP BY project_key, budget_code
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
                            "severity": _severity_for_mode(mode, base_severity),
                            "basis": basis,
                            "column_roles": list(column_names),
                            "row_count": int(row["row_count"]),
                            "message": (
                                "Budget columns coexist per Procore standard view; "
                                "do not add component workflow amounts on top of calculated rollups."
                                if formula_status == "proven"
                                else "Budget column coexistence unresolved; apply precedence before summing."
                            ),
                            "procore_formula_status": formula_status,
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


def _actuals_population_summary(conn: sqlite3.Connection) -> dict[str, Any] | None:
    if not _table_exists(conn, "procore_ep_budget_detail_rows"):
        return None
    cols = _table_columns(conn, "procore_ep_budget_detail_rows")
    field_names = (
        "actual_cost",
        "direct_costs",
        "job_to_date_costs",
        "erp_direct_costs",
        "erp_job_to_date_costs",
    )
    select_parts = ["COUNT(*) AS total"]
    for field in field_names:
        if field in cols:
            select_parts.append(
                f"SUM(CASE WHEN {_column_populated(field)} THEN 1 ELSE 0 END) AS {field}_pop"
            )
    row = conn.execute(
        f"SELECT {', '.join(select_parts)} FROM procore_ep_budget_detail_rows"
    ).fetchone()
    total = int(row["total"] or 0)
    actual_pop = int(row["actual_cost_pop"] or 0) if "actual_cost" in cols else 0
    summary: dict[str, Any] = {
        "total_rows": total,
        "actual_cost_populated": actual_pop,
        "actual_cost_null_rate": round(1 - (actual_pop / total), 4) if total and "actual_cost" in cols else None,
        "direct_costs_populated": int(row["direct_costs_pop"] or 0) if "direct_costs" in cols else None,
        "job_to_date_costs_populated": int(row["job_to_date_costs_pop"] or 0) if "job_to_date_costs" in cols else None,
        "erp_direct_costs_populated": int(row["erp_direct_costs_pop"] or 0) if "erp_direct_costs" in cols else None,
        "erp_job_to_date_costs_populated": int(row["erp_job_to_date_costs_pop"] or 0)
        if "erp_job_to_date_costs" in cols
        else None,
    }
    return summary


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
        population = _actuals_population_summary(conn)
        if population:
            findings.append(
                {
                    "basis": "budget_actual_cumulative",
                    "severity": "info",
                    "population": population,
                    "note": (
                        "actual_cost population on budget rows; zero population means use "
                        "job_to_date_costs or monthly actuals with explicit basis tagging."
                    ),
                }
            )
            null_rate = population.get("actual_cost_null_rate")
            if null_rate is not None and null_rate >= 0.99:
                findings.append(
                    {
                        "basis": "budget_actual_cumulative",
                        "severity": "info",
                        "message": "actual_cost column unpopulated on live copy; unresolved Procore mapping.",
                        "procore_formula_status": "unresolved",
                    }
                )

        budget_cols = (
            _table_columns(conn, "procore_ep_budget_detail_rows")
            if _table_exists(conn, "procore_ep_budget_detail_rows")
            else set()
        )
        if (
            _table_exists(conn, "procore_ep_budget_detail_rows")
            and "job_to_date_costs" in budget_cols
            and "erp_job_to_date_costs" in budget_cols
        ):
            agg_rows = conn.execute(
                f"""
                SELECT project_key,
                       COUNT(*) AS compared_rows,
                       SUM(ABS(CAST(job_to_date_costs AS REAL) - CAST(erp_job_to_date_costs AS REAL))) AS abs_diff_sum
                FROM procore_ep_budget_detail_rows
                WHERE {_column_populated('job_to_date_costs')}
                  AND {_column_populated('erp_job_to_date_costs')}
                GROUP BY project_key
                """
            ).fetchall()
            for agg in agg_rows:
                compared = int(agg["compared_rows"] or 0)
                if compared == 0:
                    continue
                diff_sum = _parse_decimal(agg["abs_diff_sum"])
                if diff_sum is None:
                    continue
                avg_diff = diff_sum / Decimal(compared)
                if avg_diff > abs_thr:
                    findings.append(
                        {
                            "project_key": agg["project_key"],
                            "basis": "erp_actual_sidecar",
                            "severity": "warning",
                            "compared_rows": compared,
                            "aggregate_average_difference": str(avg_diff),
                            "note": (
                                "ERP job-to-date differs materially from Procore job-to-date; "
                                "compare only, do not sum or substitute."
                            ),
                        }
                    )

        if (
            _table_exists(conn, "procore_ep_budget_detail_rows")
            and _table_exists(conn, "forecast_monthly_actuals_by_budget_code")
            and "job_to_date_costs" in budget_cols
        ):
            jtd_rows = conn.execute(
                f"""
                SELECT b.project_key, b.budget_code AS budget_code_key,
                       b.job_to_date_costs, m.amount AS monthly_amount
                FROM procore_ep_budget_detail_rows b
                JOIN forecast_monthly_actuals_by_budget_code m
                  ON m.project_key = b.project_key
                 AND m.budget_code_key = b.budget_code
                WHERE {_column_populated('job_to_date_costs')}
                  AND m.amount IS NOT NULL AND TRIM(m.amount) <> ''
                LIMIT 500
                """
            ).fetchall()
            for row in jtd_rows:
                cumulative = _parse_decimal(row["job_to_date_costs"])
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
                            "basis": "monthly_periodized_actual",
                            "difference": str(diff),
                            "percent_difference": str(pct),
                            "severity": _severity_for_mode(mode, "warning"),
                            "note": (
                                "Cumulative job-to-date differs from a single monthly actual row; "
                                "reconcile by period, do not add."
                            ),
                        }
                    )

            actual_rows: list[sqlite3.Row] = []
            if "actual_cost" in budget_cols:
                actual_rows = conn.execute(
                    f"""
                    SELECT b.project_key, b.budget_code AS budget_code_key,
                           b.actual_cost, m.amount AS monthly_amount
                    FROM procore_ep_budget_detail_rows b
                    JOIN forecast_monthly_actuals_by_budget_code m
                      ON m.project_key = b.project_key
                     AND m.budget_code_key = b.budget_code
                    WHERE {_column_populated('actual_cost')}
                      AND m.amount IS NOT NULL AND TRIM(m.amount) <> ''
                    LIMIT 500
                    """
                ).fetchall()
            for row in actual_rows:
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
                            "basis": "budget_actual_cumulative",
                            "difference": str(diff),
                            "percent_difference": str(pct),
                            "severity": _severity_for_mode(mode, "warning"),
                            "note": "Cumulative budget actual differs materially from monthly actual.",
                        }
                    )

        if (
            _table_exists(conn, "procore_ep_budget_detail_rows")
            and "actual_cost" in budget_cols
            and "erp_job_to_date_costs" in budget_cols
        ):
            rows = conn.execute(
                f"""
                SELECT project_key, budget_code AS budget_code_key,
                       actual_cost, erp_job_to_date_costs
                FROM procore_ep_budget_detail_rows
                WHERE {_column_populated('actual_cost')}
                  AND {_column_populated('erp_job_to_date_costs')}
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
                            "basis": "erp_actual_sidecar",
                            "difference": str(diff),
                            "percent_difference": str(pct),
                            "severity": "warning",
                            "note": "ERP and Procore cumulative actuals differ; treat ERP as explicit sidecar.",
                        }
                    )

        invoice_table = "procore_ep_subcontractor_invoice_contract_detail_items"
        if _table_exists(conn, "procore_ep_budget_detail_rows") and _table_exists(conn, invoice_table):
            budget_cols = _table_columns(conn, "procore_ep_budget_detail_rows")
            invoice_cols = _table_columns(conn, invoice_table)
            jtd_field = "job_to_date_costs" if "job_to_date_costs" in budget_cols else "actual_cost"
            invoice_key = _pick_column(invoice_cols, ("detail_line_item_id", "line_item_id", "record_id"))
            if (
                invoice_key
                and _columns_available(budget_cols, ("budget_code_id", jtd_field, "budget_code", "project_key"))
                and _columns_available(invoice_cols, ("cost_code_id", "total_completed_and_stored_to_date"))
            ):
                rows = conn.execute(
                    f"""
                    SELECT b.project_key, b.budget_code AS budget_code_key,
                           COUNT(DISTINCT b.record_key) AS budget_rows,
                           COUNT(DISTINCT i.{invoice_key}) AS invoice_detail_rows
                    FROM procore_ep_budget_detail_rows b
                    JOIN {invoice_table} i
                      ON CAST(i.cost_code_id AS TEXT) = CAST(b.budget_code_id AS TEXT)
                    WHERE {_column_populated(jtd_field)}
                      AND i.total_completed_and_stored_to_date IS NOT NULL
                      AND TRIM(i.total_completed_and_stored_to_date) <> ''
                    GROUP BY b.project_key, b.budget_code
                    LIMIT 200
                    """
                ).fetchall()
            else:
                rows = []
            for row in rows:
                findings.append(
                    {
                        "project_key": row["project_key"],
                        "budget_code_key": row["budget_code_key"],
                        "basis": "invoice_progress_fact",
                        "severity": _severity_for_mode(mode, "warning"),
                        "budget_rows": int(row["budget_rows"]),
                        "invoice_detail_rows": int(row["invoice_detail_rows"]),
                        "note": (
                            "Budget cumulative rollup and invoice detail progress coexist; "
                            "compare only unless double-counting is proven safe."
                        ),
                    }
                )

            if _columns_available(budget_cols, ("budget_code_id", "actual_cost", "budget_code", "project_key")):
                amount_rows = conn.execute(
                    f"""
                    SELECT b.project_key, b.budget_code AS budget_code_key,
                           b.actual_cost, SUM(CAST(i.total_completed_and_stored_to_date AS REAL)) AS invoice_progress_sum
                    FROM procore_ep_budget_detail_rows b
                    JOIN {invoice_table} i
                      ON CAST(i.cost_code_id AS TEXT) = CAST(b.budget_code_id AS TEXT)
                    WHERE {_column_populated('actual_cost')}
                    GROUP BY b.project_key, b.budget_code, b.actual_cost
                    LIMIT 200
                    """
                ).fetchall()
            else:
                amount_rows = []
            for row in amount_rows:
                budget_actual = _parse_decimal(row["actual_cost"])
                invoice_sum = _parse_decimal(row["invoice_progress_sum"])
                if budget_actual is None or invoice_sum is None:
                    continue
                if invoice_sum > budget_actual * (Decimal(1) + pct_thr) and invoice_sum - budget_actual > abs_thr:
                    findings.append(
                        {
                            "project_key": row["project_key"],
                            "budget_code_key": row["budget_code_key"],
                            "basis": "invoice_progress_fact",
                            "difference": str(invoice_sum - budget_actual),
                            "severity": _severity_for_mode(mode, "warning"),
                            "note": "Invoice detail progress exceeds budget cumulative actual; do not add both.",
                        }
                    )

        if _table_exists(conn, "procore_ep_subcontractor_invoices"):
            pay_row = conn.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN payment_date IS NOT NULL AND TRIM(payment_date) <> '' THEN 1 ELSE 0 END) AS payment_pop
                FROM procore_ep_subcontractor_invoices
                """
            ).fetchone()
            total = int(pay_row["total"] or 0)
            payment_pop = int(pay_row["payment_pop"] or 0)
            findings.append(
                {
                    "basis": "payment_cash_flow_fact",
                    "severity": "info",
                    "invoice_count": total,
                    "payment_date_populated": payment_pop,
                    "payment_date_null_rate": round(1 - (payment_pop / total), 4) if total else 1.0,
                    "note": "Payment dates are cash-flow timing facts, not earned actual cost rollups.",
                }
            )

        if (
            _table_exists(conn, "procore_ep_budget_detail_rows")
            and "direct_costs" in budget_cols
            and "job_to_date_costs" in budget_cols
        ):
            direct_rows = conn.execute(
                f"""
                SELECT project_key, COUNT(*) AS rows_with_both
                FROM procore_ep_budget_detail_rows
                WHERE {_column_populated('direct_costs')} AND {_column_populated('job_to_date_costs')}
                GROUP BY project_key
                """
            ).fetchall()
            for row in direct_rows:
                findings.append(
                    {
                        "project_key": row["project_key"],
                        "basis": "direct_cost_rollup",
                        "severity": "info",
                        "rows_with_direct_and_jtd": int(row["rows_with_both"]),
                        "note": (
                            "direct_costs is a workflow-stage component; job_to_date_costs is a calculated "
                            "rollup per Procore doc (Direct Costs + Subcontractor Invoices)."
                        ),
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


def _parity_key_sets(
    conn: sqlite3.Connection,
    *,
    ep_table: str,
    target_table: str,
    ep_key: str,
    target_key: str,
    parity_kind: str = "contract_family",
    contract_family: str | None = None,
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    ep_cols = _table_columns(conn, ep_table)
    fin_cols = _table_columns(conn, target_table)
    if ep_key not in ep_cols or target_key not in fin_cols:
        return set(), set()
    ep_rows = conn.execute(
        f"SELECT project_key, CAST({ep_key} AS TEXT) AS record_key FROM {ep_table} "
        f"WHERE {ep_key} IS NOT NULL AND TRIM(CAST({ep_key} AS TEXT)) <> ''"
    ).fetchall()
    if parity_kind == "contract_family" and contract_family:
        fin_rows = conn.execute(
            f"SELECT project_key, CAST({target_key} AS TEXT) AS record_key FROM {target_table} "
            f"WHERE contract_family = ? AND {target_key} IS NOT NULL "
            f"AND TRIM(CAST({target_key} AS TEXT)) <> ''",
            (contract_family,),
        ).fetchall()
    else:
        fin_rows = conn.execute(
            f"SELECT project_key, CAST({target_key} AS TEXT) AS record_key FROM {target_table} "
            f"WHERE {target_key} IS NOT NULL AND TRIM(CAST({target_key} AS TEXT)) <> ''"
        ).fetchall()
    ep_keys = {(str(r["project_key"]), str(r["record_key"])) for r in ep_rows}
    fin_keys = {(str(r["project_key"]), str(r["record_key"])) for r in fin_rows}
    return ep_keys, fin_keys


def _is_commitment_backed_po(conn: sqlite3.Connection, project_key: str, contract_id: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM procore_financial_contracts
        WHERE project_key = ? AND contract_id = ? AND contract_family = 'commitment'
        LIMIT 1
        """,
        (project_key, contract_id),
    ).fetchone()
    if row:
        return True
    ep_row = conn.execute(
        """
        SELECT 1 FROM procore_ep_commitment_contracts
        WHERE project_key = ? AND CAST(record_id AS TEXT) = ?
        LIMIT 1
        """,
        (project_key, contract_id),
    ).fetchone()
    return ep_row is not None


def _status_mismatch_count(
    conn: sqlite3.Connection,
    *,
    ep_table: str,
    target_table: str,
    family: str,
    ep_key: str,
    target_key: str,
    parity_kind: str = "contract_family",
    contract_family: str | None = None,
    ep_status_field: str | None = None,
    target_status_field: str | None = None,
) -> int:
    ep_cols = _table_columns(conn, ep_table)
    fin_cols = _table_columns(conn, target_table)
    ep_status = _pick_column(ep_cols, (ep_status_field or "status", "status_name", "status_mapped_to_status"))
    fin_status = _pick_column(fin_cols, (target_status_field or "status",))
    if not ep_status or not fin_status:
        return 0
    family_clause = "AND fin.contract_family = ?" if parity_kind == "contract_family" and contract_family else ""
    params: list[Any] = []
    if family_clause:
        params.append(contract_family)
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS mismatch_count
        FROM {ep_table} ep
        JOIN {target_table} fin
          ON fin.project_key = ep.project_key
         AND CAST(fin.{target_key} AS TEXT) = CAST(ep.{ep_key} AS TEXT)
         {family_clause}
        WHERE COALESCE(LOWER(TRIM(ep.{ep_status})), '') <> COALESCE(LOWER(TRIM(fin.{fin_status})), '')
        """,
        params,
    ).fetchone()
    return int(row["mismatch_count"] or 0)


def _amount_mismatch_report(
    conn: sqlite3.Connection,
    *,
    ep_table: str,
    target_table: str,
    family: str,
    ep_key: str,
    target_key: str,
    amount_field: str | None,
    parity_kind: str = "contract_family",
    contract_family: str | None = None,
    target_amount_field: str | None = None,
) -> tuple[int, list[str]]:
    if not amount_field:
        return 0, []
    ep_cols = _table_columns(conn, ep_table)
    fin_cols = _table_columns(conn, target_table)
    fin_amount = target_amount_field or amount_field
    if amount_field not in ep_cols or fin_amount not in fin_cols:
        return 0, []
    family_clause = "AND fin.contract_family = ?" if parity_kind == "contract_family" and contract_family else ""
    params: list[Any] = []
    if family_clause:
        params.append(contract_family)
    count_row = conn.execute(
        f"""
        SELECT COUNT(*) AS mismatch_count
        FROM {ep_table} ep
        JOIN {target_table} fin
          ON fin.project_key = ep.project_key
         AND CAST(fin.{target_key} AS TEXT) = CAST(ep.{ep_key} AS TEXT)
         {family_clause}
        WHERE COALESCE(TRIM(ep.{amount_field}), '') <> COALESCE(TRIM(fin.{fin_amount}), '')
        """,
        params,
    ).fetchone()
    count = int(count_row["mismatch_count"] or 0)
    sample_params = list(params)
    sample_params.append(_KEY_SAMPLE_LIMIT)
    rows = conn.execute(
        f"""
        SELECT ep.project_key, CAST(ep.{ep_key} AS TEXT) AS record_key
        FROM {ep_table} ep
        JOIN {target_table} fin
          ON fin.project_key = ep.project_key
         AND CAST(fin.{target_key} AS TEXT) = CAST(ep.{ep_key} AS TEXT)
         {family_clause}
        WHERE COALESCE(TRIM(ep.{amount_field}), '') <> COALESCE(TRIM(fin.{fin_amount}), '')
        LIMIT ?
        """,
        sample_params,
    ).fetchall()
    return count, [_hash_key(f"{r['project_key']}:{r['record_key']}") for r in rows]


def _updated_field_mismatch_count(
    conn: sqlite3.Connection,
    *,
    ep_table: str,
    target_table: str,
    family: str,
    ep_key: str,
    target_key: str,
    ep_updated: str,
    fin_updated: str,
    parity_kind: str = "contract_family",
    contract_family: str | None = None,
) -> int:
    ep_cols = _table_columns(conn, ep_table)
    fin_cols = _table_columns(conn, target_table)
    fin_field = "updated_at_utc" if "updated_at_utc" in fin_cols else fin_updated
    ep_field = ep_updated if ep_updated in ep_cols else ("updated_utc" if "updated_utc" in ep_cols else None)
    if not ep_field or fin_field not in fin_cols:
        return 0
    family_clause = "AND fin.contract_family = ?" if parity_kind == "contract_family" and contract_family else ""
    params: list[Any] = []
    if family_clause:
        params.append(contract_family)
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS mismatch_count
        FROM {ep_table} ep
        JOIN {target_table} fin
          ON fin.project_key = ep.project_key
         AND CAST(fin.{target_key} AS TEXT) = CAST(ep.{ep_key} AS TEXT)
         {family_clause}
        WHERE COALESCE(TRIM(ep.{ep_field}), '') <> COALESCE(TRIM(fin.{fin_field}), '')
        """,
        params,
    ).fetchone()
    return int(row["mismatch_count"] or 0)


def run_projection_parity_gate(
    *,
    db_path: str | Path,
    mode: GateMode = "warn",
) -> dict[str, Any]:
    """Report count-, key-, and selected-field mismatches between projection layers."""
    path = str(db_path)
    findings: list[dict[str, Any]] = []
    pairs_checked = 0
    pairs_unsupported = 0

    with _connect_ro(path) as conn:
        for cfg in _PARITY_PAIR_CONFIGS:
            ep_table = str(cfg["ep_table"])
            fin_table = str(cfg["target_table"])
            family = str(cfg["family"])
            parity_kind = str(cfg.get("parity_kind") or "contract_family")
            contract_family = str(cfg.get("contract_family") or family)
            ep_key = str(cfg["ep_key"])
            target_key = str(cfg["target_key"])
            amount_field = cfg.get("amount_field")
            if amount_field is not None:
                amount_field = str(amount_field)
            updated_field = str(cfg.get("updated_field") or "updated_at")
            parity_availability = cfg.get("parity_availability")

            if not _table_exists(conn, ep_table) or not _table_exists(conn, fin_table):
                findings.append(
                    {
                        "family": family,
                        "severity": "info",
                        "basis": "table_missing",
                        "source_table": ep_table,
                        "target_table": fin_table,
                        "message": "One or both projection layers missing; parity not evaluated.",
                    }
                )
                continue

            pairs_checked += 1
            ep_count = conn.execute(f"SELECT COUNT(*) FROM {ep_table}").fetchone()[0]
            if parity_kind == "contract_family":
                fin_count = conn.execute(
                    f"SELECT COUNT(*) FROM {fin_table} WHERE contract_family = ?",
                    (contract_family,),
                ).fetchone()[0]
            else:
                fin_count = conn.execute(f"SELECT COUNT(*) FROM {fin_table}").fetchone()[0]

            if parity_availability:
                pairs_unsupported += 1
                findings.append(
                    {
                        "family": family,
                        "severity": "info",
                        "basis": "parity_unsupported",
                        "parity_availability": parity_availability,
                        "source_table": ep_table,
                        "target_table": fin_table,
                        "ep_row_count": ep_count,
                        "financial_row_count": fin_count,
                        "message": str(cfg.get("unsupported_reason") or "Parity pair not fully supported."),
                    }
                )

            ep_keys, fin_keys = _parity_key_sets(
                conn,
                ep_table=ep_table,
                target_table=fin_table,
                ep_key=ep_key,
                target_key=target_key,
                parity_kind=parity_kind,
                contract_family=contract_family,
            )
            source_only = sorted(ep_keys - fin_keys)
            target_only = sorted(fin_keys - ep_keys)
            expected_target_only: list[tuple[str, str]] = []
            unexpected_target_only: list[tuple[str, str]] = []
            for pk, rk in target_only:
                if family == "purchase_order" and _is_commitment_backed_po(conn, pk, rk):
                    expected_target_only.append((pk, rk))
                else:
                    unexpected_target_only.append((pk, rk))

            adjusted_fin_count = fin_count - len(expected_target_only)
            count_mismatch_severity = "info" if parity_availability else "warning"
            if ep_count != adjusted_fin_count and not parity_availability:
                findings.append(
                    {
                        "family": family,
                        "severity": count_mismatch_severity,
                        "basis": "row_count_mismatch",
                        "source_table": ep_table,
                        "ep_row_count": ep_count,
                        "target_table": fin_table,
                        "financial_row_count": fin_count,
                        "financial_row_count_adjusted": adjusted_fin_count,
                        "expected_financial_only_count": len(expected_target_only),
                        "message": "Dual projection layers diverge after expected-drift adjustment.",
                    }
                )

            if source_only:
                findings.append(
                    {
                        "source_table": ep_table,
                        "target_table": fin_table,
                        "family": family,
                        "check": "missing_target_keys",
                        "severity": _severity_for_mode(mode, "warning"),
                        "count": len(source_only),
                        "sample_key_hashes": [
                            _hash_key(f"{pk}:{rk}") for pk, rk in source_only[:_KEY_SAMPLE_LIMIT]
                        ],
                    }
                )
            if expected_target_only:
                findings.append(
                    {
                        "source_table": ep_table,
                        "target_table": fin_table,
                        "family": family,
                        "check": "expected_financial_only_keys",
                        "classification": "commitment_backed_po",
                        "severity": "info",
                        "count": len(expected_target_only),
                        "sample_key_hashes": [
                            _hash_key(f"{pk}:{rk}") for pk, rk in expected_target_only[:_KEY_SAMPLE_LIMIT]
                        ],
                    }
                )
            if unexpected_target_only:
                findings.append(
                    {
                        "source_table": ep_table,
                        "target_table": fin_table,
                        "family": family,
                        "check": "missing_source_keys",
                        "severity": _severity_for_mode(mode, "warning"),
                        "count": len(unexpected_target_only),
                        "sample_key_hashes": [
                            _hash_key(f"{pk}:{rk}") for pk, rk in unexpected_target_only[:_KEY_SAMPLE_LIMIT]
                        ],
                    }
                )

            status_mismatches = _status_mismatch_count(
                conn,
                ep_table=ep_table,
                target_table=fin_table,
                family=family,
                ep_key=ep_key,
                target_key=target_key,
                parity_kind=parity_kind,
                contract_family=contract_family,
                ep_status_field=cfg.get("ep_status_field"),
                target_status_field=cfg.get("target_status_field"),
            )
            if status_mismatches:
                findings.append(
                    {
                        "source_table": ep_table,
                        "target_table": fin_table,
                        "family": family,
                        "check": "status_field_mismatch",
                        "severity": _severity_for_mode(mode, "warning"),
                        "count": status_mismatches,
                    }
                )

            amount_count, amount_samples = _amount_mismatch_report(
                conn,
                ep_table=ep_table,
                target_table=fin_table,
                family=family,
                ep_key=ep_key,
                target_key=target_key,
                amount_field=amount_field,
                parity_kind=parity_kind,
                contract_family=contract_family,
                target_amount_field=cfg.get("target_amount_field"),
            )
            if amount_count:
                findings.append(
                    {
                        "source_table": ep_table,
                        "target_table": fin_table,
                        "family": family,
                        "check": "amount_field_mismatch",
                        "severity": _severity_for_mode(mode, "warning"),
                        "count": amount_count,
                        "sample_key_hashes": amount_samples,
                    }
                )

            updated_mismatches = _updated_field_mismatch_count(
                conn,
                ep_table=ep_table,
                target_table=fin_table,
                family=family,
                ep_key=ep_key,
                target_key=target_key,
                ep_updated=updated_field,
                fin_updated="updated_at_utc",
                parity_kind=parity_kind,
                contract_family=contract_family,
            )
            if updated_mismatches:
                findings.append(
                    {
                        "source_table": ep_table,
                        "target_table": fin_table,
                        "family": family,
                        "check": "updated_field_mismatch",
                        "severity": "info",
                        "count": updated_mismatches,
                    }
                )

    warning_count = sum(1 for f in findings if f.get("severity") == "warning")
    error_count = sum(1 for f in findings if f.get("severity") == "error")

    return {
        "ok": error_count == 0,
        "gate": "forecast_projection_parity",
        "db_path": path,
        "checked_at_utc": _utc_now(),
        "mode": mode,
        "pairs_checked": pairs_checked,
        "pairs_unsupported": pairs_unsupported,
        "finding_count": len(findings),
        "warning_count": warning_count,
        "error_count": error_count,
        "findings": findings,
    }


def run_budget_dynamic_columns_gate(
    *,
    db_path: str | Path,
    mode: GateMode = "warn",
) -> dict[str, Any]:
    """Classify budget-view dynamic columns; block silent model consumption of unknown numerics."""
    from hb_assistant.forecasting.budget_column_roles import (
        load_budget_column_roles,
        procore_label_to_role_key,
    )
    from hb_assistant.forecasting.field_classifiers import classify_amount_field

    path = str(db_path)
    findings: list[dict[str, Any]] = []
    classification_counts: dict[str, int] = {}

    with _connect_ro(path) as conn:
        if not _table_exists(conn, "procore_ep_budget_detail_columns"):
            return {
                "ok": True,
                "gate": "forecast_budget_dynamic_columns",
                "db_path": path,
                "checked_at_utc": _utc_now(),
                "mode": mode,
                "finding_count": 0,
                "warning_count": 0,
                "error_count": 0,
                "findings": [],
                "message": "Budget detail columns table missing; gate skipped.",
            }

        roles = load_budget_column_roles().get("budget_column_roles", {})
        if not isinstance(roles, dict):
            roles = {}

        columns = conn.execute(
            """
            SELECT budget_view_id, column_id, column_key, name, label, data_type
            FROM procore_ep_budget_detail_columns
            WHERE is_current = 1
            GROUP BY budget_view_id, column_id, column_key, name, label, data_type
            """
        ).fetchall()

        cell_counts: dict[tuple[str, str], int] = {}
        if _table_exists(conn, "procore_ep_budget_detail_row_cells"):
            for row in conn.execute(
                """
                SELECT column_key, column_name,
                       SUM(CASE WHEN value_decimal_text IS NOT NULL AND TRIM(value_decimal_text) <> '' THEN 1 ELSE 0 END) AS numeric_cells
                FROM procore_ep_budget_detail_row_cells
                WHERE is_current = 1
                GROUP BY column_key, column_name
                """
            ).fetchall():
                cell_counts[(str(row["column_key"] or ""), str(row["column_name"] or ""))] = int(
                    row["numeric_cells"] or 0
                )

        for col in columns:
            column_key = str(col["column_key"] or "")
            name = str(col["name"] or "")
            label = str(col["label"] or "")
            data_type = str(col["data_type"] or "")
            role_key = procore_label_to_role_key(column_key or name or label)

            if role_key and role_key in roles:
                role_meta = roles[role_key]
                source_type = str(role_meta.get("source_type") or "")
                classification = (
                    "known_calculated_rollup" if source_type == "calculated" else "standard_known_column"
                )
            elif data_type in ("standard",) and (column_key or name).lower() in {
                "budget code",
                "description",
                "detail type",
                "item",
                "vendor",
            }:
                classification = "custom_status_or_dimension"
            elif "note" in (column_key or name or label).lower():
                classification = "custom_text_or_note"
            else:
                amount_kind = classify_amount_field(
                    table="procore_ep_budget_detail_row_cells",
                    column=name or column_key,
                    declared_type="TEXT",
                )
                kind = str(amount_kind.get("kind") or "")
                if kind == "true_monetary_amount":
                    classification = "custom_numeric_candidate"
                elif kind in ("enum_status_dimension", "text_description", "identifier_key"):
                    classification = "custom_status_or_dimension"
                elif data_type in ("source", "budget_forecast"):
                    classification = "review_required"
                else:
                    classification = "review_required"

            classification_counts[classification] = classification_counts.get(classification, 0) + 1
            numeric_cells = cell_counts.get((column_key, name), 0)

            if classification in ("custom_numeric_candidate", "review_required") and numeric_cells > 0:
                findings.append(
                    {
                        "budget_view_id": col["budget_view_id"],
                        "column_key": column_key,
                        "column_name": name,
                        "classification": classification,
                        "numeric_cell_count": numeric_cells,
                        "severity": _severity_for_mode(mode, "warning"),
                        "message": (
                            "Unmapped budget-view column has numeric cells; "
                            "requires catalog entry before model input."
                        ),
                    }
                )
            elif classification == "custom_text_or_note":
                findings.append(
                    {
                        "budget_view_id": col["budget_view_id"],
                        "column_key": column_key,
                        "classification": classification,
                        "severity": "info",
                        "message": "Text/note column excluded from monetary parsing.",
                    }
                )

        unmapped_numeric = sum(
            1 for f in findings if f.get("classification") in ("custom_numeric_candidate", "review_required")
        )
        if unmapped_numeric:
            findings.insert(
                0,
                {
                    "basis": "dynamic_column_summary",
                    "severity": "info",
                    "classification_counts": classification_counts,
                    "unmapped_numeric_columns": unmapped_numeric,
                    "message": "Unknown/custom columns must not become model inputs without catalog validation.",
                },
            )

    warning_count = sum(1 for f in findings if f.get("severity") == "warning")
    error_count = sum(1 for f in findings if f.get("severity") == "error")

    return {
        "ok": error_count == 0,
        "gate": "forecast_budget_dynamic_columns",
        "db_path": path,
        "checked_at_utc": _utc_now(),
        "mode": mode,
        "classification_counts": classification_counts,
        "finding_count": len(findings),
        "warning_count": warning_count,
        "error_count": error_count,
        "findings": findings,
    }


def run_cost_type_guard_gate(*, db_path: str | Path) -> dict[str, Any]:
    """Report cost_type sparsity; never infer category as cost_type."""
    path = str(db_path)
    findings: list[dict[str, Any]] = []

    with _connect_ro(path) as conn:
        if _table_exists(conn, "procore_ep_budget_detail_rows"):
            cols = _table_columns(conn, "procore_ep_budget_detail_rows")
            cost_type_expr = (
                "SUM(CASE WHEN cost_type IS NOT NULL AND TRIM(cost_type) <> '' THEN 1 ELSE 0 END)"
                if "cost_type" in cols
                else "0"
            )
            category_expr = (
                "SUM(CASE WHEN category IS NOT NULL AND TRIM(category) <> '' THEN 1 ELSE 0 END)"
                if "category" in cols
                else "0"
            )
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS total,
                       {cost_type_expr} AS populated,
                       {category_expr} AS category_populated
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

    warning_count = sum(1 for f in findings if f.get("severity") == "warning")
    error_count = sum(1 for f in findings if f.get("severity") == "error")

    return {
        "ok": error_count == 0,
        "gate": "forecast_cost_type_guard",
        "db_path": path,
        "checked_at_utc": _utc_now(),
        "finding_count": len(findings),
        "warning_count": warning_count,
        "error_count": error_count,
        "findings": findings,
    }


def run_all_forecasting_gates(
    *,
    db_path: str | Path,
    mode: GateMode = "warn",
    include_full_reports: bool = False,
) -> dict[str, Any]:
    """Run all forecasting gates and return a combined report."""
    full_reports = [
        run_double_count_gate(db_path=db_path, mode=mode),
        run_actuals_reconciliation_gate(db_path=db_path, mode=mode),
        run_projection_parity_gate(db_path=db_path, mode=mode),
        run_budget_dynamic_columns_gate(db_path=db_path, mode=mode),
        run_cost_type_guard_gate(db_path=db_path),
    ]
    abbreviated = [_abbreviate_gate_report(r) for r in full_reports]
    warning_count = sum(g["warning_count"] for g in abbreviated)
    error_count = sum(g["error_count"] for g in abbreviated)
    passed_count = sum(1 for g in abbreviated if g["ok"])
    result: dict[str, Any] = {
        "ok": all(r.get("ok") for r in full_reports),
        "checked_at_utc": _utc_now(),
        "db_path": str(db_path),
        "mode": mode,
        "gates": abbreviated,
        "summary": {
            "gate_count": len(abbreviated),
            "passed_count": passed_count,
            "warning_count": warning_count,
            "error_count": error_count,
        },
    }
    if include_full_reports:
        result["full_reports"] = full_reports
    return result