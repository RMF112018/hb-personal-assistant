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
        "ep_key": "record_id",
        "target_key": "contract_id",
        "amount_field": "grand_total",
        "updated_field": "updated_at",
    },
    {
        "ep_table": "procore_ep_purchase_order_contracts",
        "target_table": "procore_financial_contracts",
        "family": "purchase_order",
        "ep_key": "record_id",
        "target_key": "contract_id",
        "amount_field": "grand_total",
        "updated_field": "updated_at",
        "expected_financial_only": ["commitment_backed_po"],
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

        invoice_table = "procore_ep_subcontractor_invoice_contract_detail_items"
        if _table_exists(conn, "procore_ep_budget_detail_rows") and _table_exists(conn, invoice_table):
            budget_cols = _table_columns(conn, "procore_ep_budget_detail_rows")
            invoice_cols = _table_columns(conn, invoice_table)
            if (
                _columns_available(budget_cols, ("budget_code_id", "actual_cost", "budget_code", "project_key"))
                and _columns_available(
                    invoice_cols, ("cost_code_id", "total_completed_and_stored_to_date")
                )
            ):
                rows = conn.execute(
                    f"""
                    SELECT b.project_key, b.budget_code AS budget_code_key,
                           b.actual_cost, SUM(CAST(i.total_completed_and_stored_to_date AS REAL)) AS invoice_progress_sum
                    FROM procore_ep_budget_detail_rows b
                    JOIN {invoice_table} i
                      ON CAST(i.cost_code_id AS TEXT) = CAST(b.budget_code_id AS TEXT)
                    WHERE b.actual_cost IS NOT NULL AND TRIM(b.actual_cost) <> ''
                    GROUP BY b.project_key, b.budget_code, b.actual_cost
                    LIMIT 200
                    """
                ).fetchall()
            else:
                rows = []
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


def _parity_key_sets(
    conn: sqlite3.Connection,
    *,
    ep_table: str,
    target_table: str,
    family: str,
    ep_key: str,
    target_key: str,
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    ep_cols = _table_columns(conn, ep_table)
    fin_cols = _table_columns(conn, target_table)
    if ep_key not in ep_cols or target_key not in fin_cols:
        return set(), set()
    ep_rows = conn.execute(
        f"SELECT project_key, CAST({ep_key} AS TEXT) AS record_key FROM {ep_table} "
        f"WHERE {ep_key} IS NOT NULL AND TRIM(CAST({ep_key} AS TEXT)) <> ''"
    ).fetchall()
    fin_rows = conn.execute(
        f"SELECT project_key, CAST({target_key} AS TEXT) AS record_key FROM {target_table} "
        f"WHERE contract_family = ? AND {target_key} IS NOT NULL "
        f"AND TRIM(CAST({target_key} AS TEXT)) <> ''",
        (family,),
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
) -> int:
    ep_cols = _table_columns(conn, ep_table)
    fin_cols = _table_columns(conn, target_table)
    if "status" not in ep_cols or "status" not in fin_cols:
        return 0
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS mismatch_count
        FROM {ep_table} ep
        JOIN {target_table} fin
          ON fin.project_key = ep.project_key
         AND CAST(fin.{target_key} AS TEXT) = CAST(ep.{ep_key} AS TEXT)
         AND fin.contract_family = ?
        WHERE COALESCE(LOWER(TRIM(ep.status)), '') <> COALESCE(LOWER(TRIM(fin.status)), '')
        """,
        (family,),
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
    amount_field: str,
) -> tuple[int, list[str]]:
    ep_cols = _table_columns(conn, ep_table)
    fin_cols = _table_columns(conn, target_table)
    if amount_field not in ep_cols or amount_field not in fin_cols:
        return 0, []
    count_row = conn.execute(
        f"""
        SELECT COUNT(*) AS mismatch_count
        FROM {ep_table} ep
        JOIN {target_table} fin
          ON fin.project_key = ep.project_key
         AND CAST(fin.{target_key} AS TEXT) = CAST(ep.{ep_key} AS TEXT)
         AND fin.contract_family = ?
        WHERE COALESCE(TRIM(ep.{amount_field}), '') <> COALESCE(TRIM(fin.{amount_field}), '')
        """,
        (family,),
    ).fetchone()
    count = int(count_row["mismatch_count"] or 0)
    rows = conn.execute(
        f"""
        SELECT ep.project_key, CAST(ep.{ep_key} AS TEXT) AS record_key
        FROM {ep_table} ep
        JOIN {target_table} fin
          ON fin.project_key = ep.project_key
         AND CAST(fin.{target_key} AS TEXT) = CAST(ep.{ep_key} AS TEXT)
         AND fin.contract_family = ?
        WHERE COALESCE(TRIM(ep.{amount_field}), '') <> COALESCE(TRIM(fin.{amount_field}), '')
        LIMIT ?
        """,
        (family, _KEY_SAMPLE_LIMIT),
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
) -> int:
    ep_cols = _table_columns(conn, ep_table)
    fin_cols = _table_columns(conn, target_table)
    fin_field = "updated_at_utc" if "updated_at_utc" in fin_cols else fin_updated
    ep_field = ep_updated if ep_updated in ep_cols else ("updated_utc" if "updated_utc" in ep_cols else None)
    if not ep_field or fin_field not in fin_cols:
        return 0
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS mismatch_count
        FROM {ep_table} ep
        JOIN {target_table} fin
          ON fin.project_key = ep.project_key
         AND CAST(fin.{target_key} AS TEXT) = CAST(ep.{ep_key} AS TEXT)
         AND fin.contract_family = ?
        WHERE COALESCE(TRIM(ep.{ep_field}), '') <> COALESCE(TRIM(fin.{fin_field}), '')
        """,
        (family,),
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

    with _connect_ro(path) as conn:
        for cfg in _PARITY_PAIR_CONFIGS:
            ep_table = str(cfg["ep_table"])
            fin_table = str(cfg["target_table"])
            family = str(cfg["family"])
            ep_key = str(cfg["ep_key"])
            target_key = str(cfg["target_key"])
            amount_field = str(cfg.get("amount_field") or "grand_total")
            updated_field = str(cfg.get("updated_field") or "updated_at")

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
            fin_count = conn.execute(
                f"SELECT COUNT(*) FROM {fin_table} WHERE contract_family = ?",
                (family,),
            ).fetchone()[0]

            ep_keys, fin_keys = _parity_key_sets(
                conn,
                ep_table=ep_table,
                target_table=fin_table,
                family=family,
                ep_key=ep_key,
                target_key=target_key,
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
            if ep_count != adjusted_fin_count:
                findings.append(
                    {
                        "family": family,
                        "severity": "warning",
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