"""Read-only loading of every input surface the improvement audit consumes.

All packages are discovered via the shared comprehensive package_discovery; the schedule / history
packages are resolved from their config keys. The SQLite DB is read strictly read-only here so that the
downstream build step is a pure deterministic function of the returned ``inputs`` dict.
"""
from __future__ import annotations

import sqlite3
from collections import OrderedDict
from pathlib import Path

from ..common.io import read_json, read_jsonl
from ..forecast_comprehensive import package_discovery
from ..forecast_intelligence import db_inventory


def _jsonl(path: Path):
    return list(read_jsonl(path)) if path and path.exists() else []


def _json(path: Path):
    return read_json(path) if path and path.exists() else None


def _ctx_canonical(ctx: Path, name: str):
    return _jsonl(ctx / "canonical" / name) if ctx else []


def _by_key(rows, key="budget_code_key"):
    out = {}
    for r in rows:
        k = r.get(key)
        if k and k not in out:
            out[k] = r
    return out


def _change_orders_ro(cfg: dict, project_key: str):
    """Read CO + contract rows read-only (status/amount/flags only; no redacted bodies)."""
    path = db_inventory.resolve_db_path(cfg)
    if not path.exists():
        return {"db_present": False, "change_orders": [], "contracts": []}
    con = db_inventory._connect_ro(path)
    try:
        cur = con.cursor()
        cos = []
        try:
            for r in cur.execute(
                "SELECT record_key, change_order_family, contract_record_key, number, status, "
                "executed, paid, grand_total, schedule_impact_amount, due_date "
                "FROM procore_financial_change_orders WHERE project_key=? ORDER BY record_key",
                (project_key,)).fetchall():
                cos.append(OrderedDict(zip(
                    ("record_key", "change_order_family", "contract_record_key", "number", "status",
                     "executed", "paid", "grand_total", "schedule_impact_amount", "due_date"), r,
                    strict=False)))
        except sqlite3.Error:
            cos = []
        contracts = []
        try:
            for r in cur.execute(
                "SELECT record_key, contract_family, contract_type, status, executed, grand_total, "
                "approved_change_orders_amount, pending_change_orders_amount "
                "FROM procore_financial_contracts WHERE project_key=? ORDER BY record_key",
                (project_key,)).fetchall():
                contracts.append(OrderedDict(zip(
                    ("record_key", "contract_family", "contract_type", "status", "executed",
                     "grand_total", "approved_change_orders_amount", "pending_change_orders_amount"), r,
                    strict=False)))
        except sqlite3.Error:
            contracts = []
        return {"db_present": True, "change_orders": cos, "contracts": contracts}
    finally:
        con.close()


def load_inputs(cfg: dict, data_root: Path, project_key: str) -> OrderedDict:
    discovery = package_discovery.discover(cfg, data_root)
    fhi = cfg.get("forecast_history_informed") or {}

    ctx = Path(discovery["context"]["path"]) if discovery["context"]["present"] else None
    acc = Path(discovery["intelligence"]["path"]) if discovery["intelligence"]["present"] else None
    mon = Path(discovery["monthly"]["path"]) if discovery["monthly"]["present"] else None
    prob = Path(discovery["probability"]["path"]) if discovery["probability"]["present"] else None
    sched_pkg = data_root / (cfg.get("schedule_package") or "project_schedule_json_package")
    gcgr_pkg = data_root / (fhi.get("gcgr_history_package") or "gcgr_forecast_history_json_package")
    cf_pkg = data_root / (fhi.get("cash_flow_history_package") or "cash_flow_forecast_history_json_package")

    budget_codes = _ctx_canonical(ctx, "budget_codes.jsonl")
    monthly_actuals = _ctx_canonical(ctx, "monthly_actuals_by_budget_code.jsonl")
    latest_sub_invoice = _ctx_canonical(ctx, "procore_latest_subcontractor_invoice_by_budget_code.jsonl")
    owner_pay_totals = _ctx_canonical(ctx, "owner_pay_app_totals.jsonl")

    accuracy = _jsonl(acc / "forecast_accuracy_next_by_budget_code.jsonl") if acc else []
    recommendations = _jsonl(acc / "forecast_recommendations_by_budget_code.jsonl") if acc else []
    trend = _jsonl(acc / "trend_evidence_by_budget_code.jsonl") if acc else []
    sched_evidence = _jsonl(acc / "schedule_forecast_evidence_by_budget_code.jsonl") if acc else []
    backtest = _json(acc / "model_backtest_results.json") if acc else None
    calibration_summary = _json(acc / "model_calibration_summary.json") if acc else None

    monthly_conf = _jsonl(mon / "monthly_forecast_confidence_by_budget_code.jsonl") if mon else []
    prob_backtest = _json(prob / "probabilistic_backtest_results.json") if prob else None
    code_overrun = _jsonl(prob / "code_overrun_probabilities.jsonl") if prob else []

    schedule_activities = _jsonl(sched_pkg / "schedule_activities.jsonl")
    gcgr_line_summary = _json(gcgr_pkg / "gcgr_forecast_history_line_summary.json")
    gcgr_monthly = _jsonl(gcgr_pkg / "gcgr_forecast_history_monthly_values_nonzero.jsonl")
    cf_code_rows = _jsonl(cf_pkg / "cash_flow_forecast_history_code_rows.jsonl")

    db = _change_orders_ro(cfg, project_key)
    db_schema_inventory = db_inventory.inventory(cfg, project_key)

    # the set of source files whose integrity we hash (deterministic order; bounded)
    source_files = []
    for base in (ctx, acc, mon, prob, sched_pkg, gcgr_pkg, cf_pkg):
        if base and Path(base).exists():
            source_files.extend(sorted(Path(base).rglob("*.jsonl")))
            source_files.extend(sorted(Path(base).rglob("*.json")))
    source_files = sorted(set(source_files))[:600]

    return OrderedDict([
        ("project_key", project_key),
        ("data_root", str(data_root)),
        ("discovery", discovery),
        ("budget_codes", budget_codes),
        ("budget_by_key", _by_key(budget_codes)),
        ("monthly_actuals", monthly_actuals),
        ("latest_sub_invoice_by_key", _by_key(latest_sub_invoice, "mapped_budget_code_key")),
        ("owner_pay_totals", owner_pay_totals),
        ("accuracy_by_key", _by_key(accuracy)),
        ("recommendations_by_key", _by_key(recommendations)),
        ("trend_by_key", _by_key(trend)),
        ("sched_evidence_by_key", _by_key(sched_evidence)),
        ("backtest", backtest),
        ("calibration_summary", calibration_summary),
        ("monthly_conf_by_key", _by_key(monthly_conf)),
        ("prob_backtest", prob_backtest),
        ("code_overrun", code_overrun),
        ("schedule_activities", schedule_activities),
        ("gcgr_line_summary", gcgr_line_summary or []),
        ("gcgr_monthly", gcgr_monthly),
        ("cf_code_rows", cf_code_rows),
        ("db", db),
        ("db_schema_inventory", db_schema_inventory),
        ("source_files", source_files),
    ])
