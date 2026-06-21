"""Read-only baseline loaders for external-forecast evaluation (Implementation Phase 4).

Sources every comparison baseline without ever writing anything:

* **Actuals / current budget / ERP-JTD** — the v59 source-domain tables
  (``forecast_monthly_actuals_by_budget_code``, ``forecast_budget_details``) opened ``mode=ro``;
  money lives in each row's authoritative ``raw_json`` (``amounts.revised_budget``,
  ``amounts.erp_job_to_date_costs``).
* **Backend model EAC / P50 / P80** — an operator-selected backend forecast package directory on
  disk (``integrated_final_cost_recommendations.jsonl`` + ``integrated_probability_by_budget_code.jsonl``).
* **Prior external** — prior eval-run external rows persisted under the eval-root.

Canonical budget-code keys (for mapping normalization) also come from the v59 budget-details
table. Every loader is tolerant: missing sources yield an empty map (the caller records which
baselines were actually available), never an exception that aborts the evaluation.
"""

from __future__ import annotations

import json
import os
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics.forecast_external_ingest import (
    ENV_DB_PATH,
    ForecastExternalError,
)
from hb_assistant.construction.analytics.forecast_external_metrics import to_decimal

# Baseline identifiers (also used as the `baseline` column value in the v61 result tables).
BASELINE_ACTUALS = "actuals"
BASELINE_CURRENT_BUDGET = "current_budget"
BASELINE_ERP_JTD = "erp_jtd"
BASELINE_MODEL_EAC = "model_eac"
BASELINE_MODEL_P50 = "model_p50"
BASELINE_MODEL_P80 = "model_p80"
BASELINE_PRIOR_EXTERNAL = "prior_external"

_FINAL_COST_FILE = "integrated_final_cost_recommendations.jsonl"
_PROBABILITY_FILE = "integrated_probability_by_budget_code.jsonl"


def resolve_db_path(override: str | None = None) -> Path | None:
    """Resolve the read-only baseline DB path; ``None`` if unavailable (baselines degrade gracefully)."""
    raw = override or os.environ.get(ENV_DB_PATH)
    path = Path(raw) if raw else PathPolicy().get_db_path()
    return path if Path(path).exists() else None


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        raise ForecastExternalError("baseline DB could not be opened read-only") from exc
    return conn


def _amounts(raw_json: str) -> dict[str, Any]:
    try:
        obj = json.loads(raw_json)
    except (ValueError, TypeError):
        return {}
    amounts = obj.get("amounts") if isinstance(obj, dict) else None
    return amounts if isinstance(amounts, dict) else {}


def load_canonical_budget_codes(db_path: Path | None, project_key: str) -> set[str]:
    if db_path is None:
        return set()
    conn = _connect_ro(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT budget_code_key FROM forecast_budget_details WHERE project_key = ?",
            (project_key,),
        ).fetchall()
    except sqlite3.Error:
        return set()
    finally:
        conn.close()
    return {str(r["budget_code_key"]) for r in rows if r["budget_code_key"]}


def load_budget_and_erp(
    db_path: Path | None, project_key: str
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    """Return (current_budget_by_code, erp_jtd_by_code) from v59 budget-details raw_json."""
    budget: dict[str, Decimal] = {}
    erp: dict[str, Decimal] = {}
    if db_path is None:
        return budget, erp
    conn = _connect_ro(db_path)
    try:
        rows = conn.execute(
            "SELECT budget_code_key, raw_json FROM forecast_budget_details WHERE project_key = ?",
            (project_key,),
        ).fetchall()
    except sqlite3.Error:
        return budget, erp
    finally:
        conn.close()
    for r in rows:
        code = str(r["budget_code_key"])
        amt = _amounts(r["raw_json"])
        rb = to_decimal(amt.get("revised_budget"))
        ej = to_decimal(amt.get("erp_job_to_date_costs"))
        if rb is not None:
            budget[code] = rb
        if ej is not None:
            erp[code] = ej
    return budget, erp


def load_actuals(db_path: Path | None, project_key: str) -> dict[str, Decimal]:
    """Actual-to-date per budget code = sum of monthly actual amounts (v59 monthly actuals)."""
    out: dict[str, Decimal] = {}
    if db_path is None:
        return out
    conn = _connect_ro(db_path)
    try:
        rows = conn.execute(
            "SELECT budget_code_key, raw_json FROM forecast_monthly_actuals_by_budget_code "
            "WHERE project_key = ?",
            (project_key,),
        ).fetchall()
    except sqlite3.Error:
        return out
    finally:
        conn.close()
    for r in rows:
        code = str(r["budget_code_key"])
        try:
            amount = to_decimal(json.loads(r["raw_json"]).get("amount"))
        except (ValueError, TypeError):
            amount = None
        if amount is not None:
            out[code] = out.get(code, Decimal(0)) + amount
    return out


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        out.append(obj)
    except (OSError, ValueError):
        return []
    return out


def load_model_baselines(
    package_dir: Path | None,
) -> dict[str, dict[str, Decimal]]:
    """Return {code: {model_eac, model_p50, model_p80}} from a backend forecast package directory."""
    out: dict[str, dict[str, Decimal]] = {}
    if package_dir is None or not Path(package_dir).is_dir():
        return out
    pkg = Path(package_dir)
    for row in _read_jsonl(pkg / _FINAL_COST_FILE):
        code = row.get("budget_code_key")
        eac = to_decimal(row.get("integrated_recommended_final_cost"))
        if code and eac is not None:
            out.setdefault(str(code), {})[BASELINE_MODEL_EAC] = eac
    for row in _read_jsonl(pkg / _PROBABILITY_FILE):
        code = row.get("budget_code_key")
        if not code:
            continue
        p50 = to_decimal(row.get("integrated_p50"))
        p80 = to_decimal(row.get("integrated_p80"))
        slot = out.setdefault(str(code), {})
        if p50 is not None:
            slot[BASELINE_MODEL_P50] = p50
        if p80 is not None:
            slot[BASELINE_MODEL_P80] = p80
    return out
