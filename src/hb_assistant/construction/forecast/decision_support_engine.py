"""Derive + project per-run forecast decision-support into the v65 tables.

This engine PERSISTS decision-support that is already defined/computed elsewhere — it does not
invent new scoring math:

- maturity tier + per-domain data availability are DERIVED from the v59 source-domain tables in
  the (temp) DB, reusing the month-count thresholds documented in CFR
  ``workflows/model_engines_readiness.py`` (>=3 / >=6 / >=12);
- the project confidence scorecard is PROJECTED from the analysis package's
  ``confidence_rollup.json``; per-code scorecards reuse the per-code ``confidence`` already
  projected into v63 ``forecast_output_budget_codes`` (Phase 2a).

Every confidence scorecard emits at least one factor row (the persisted explanation).

Safety (mirrors the v59/v63 projectors): the engine refuses to operate on the live/default DB
(``is_live_db_path``); inputs are read read-only; ``apply`` writes outputs in a single
transaction; a dry-run writes nothing. Money/scores stay TEXT (Decimal strings), never floats.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import open_connection, transaction

from . import decision_support_repository as repo
from .source_domain_engine import is_live_db_path  # reuse the fail-closed live-DB guard

GUARDRAILS = {
    "scope": "v65_decision_support_derive_and_project_only",
    "tables": "maturity_snapshots/data_availability_profiles/confidence_scorecards/confidence_factors",
    "external_systems": "none",
    "forecast_reads": "file_backed_unchanged",
    "new_scoring_math": False,
    "dry_run_writes": False,
    "apply_requires_explicit_db_path": True,
    "apply_refuses_live_db": True,
}

_PLAN_KEYS = ("maturity", "availability", "scorecards", "factors")

# Reused from CFR workflows/model_engines_readiness.py (do not re-tune here).
MIN_MONTHS_CANDIDATE = 3
MIN_MONTHS_RELIABLE = 6
MIN_MONTHS_SEASONAL = 12

# Domains that have a v59 source-domain table today; the rest are recorded "unavailable".
_DB_DOMAINS = ("budget", "cost_actuals", "monthly_actuals")
_ABSENT_DOMAINS = ("owner", "commitment", "schedule", "staffing")

CONFIDENCE_ROLLUP_FILE = "confidence_rollup.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def _maturity_tier(completed_months: int, budget_present: bool) -> str:
    if completed_months >= MIN_MONTHS_RELIABLE:  # >=6 (incl. >=12) -> mature; M5 closeout deferred
        return "M4"
    if completed_months >= MIN_MONTHS_CANDIDATE:  # 3-5
        return "M3"
    if completed_months >= 1:  # 1-2
        return "M2"
    return "M1" if budget_present else "M0"  # 0 completed: mobilization vs pre-start


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def plan_decision_support(
    *,
    db_path: Path,
    analysis_package: Path,
    project_key: str,
    run_id: str | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Derive maturity/availability from DB inputs + project confidence from the package.

    Reads inputs read-only; builds planned rows in memory; performs no writes.
    """
    now_utc = now_utc or _now()
    analysis_package = Path(analysis_package)
    source_package = analysis_package.name
    warnings: list[str] = []
    planned: dict[str, list[dict[str, Any]]] = {k: [] for k in _PLAN_KEYS}

    conn = _connect_ro(db_path)
    try:
        has_monthly = _table_exists(conn, "forecast_monthly_actuals_by_budget_code")
        has_budget = _table_exists(conn, "forecast_budget_details")
        has_cost = _table_exists(conn, "forecast_cost_entries")
        has_outputs = _table_exists(conn, "forecast_output_budget_codes")

        completed = nonzero = 0
        freshness = None
        if has_monthly:
            completed = conn.execute(
                "SELECT COUNT(DISTINCT month) FROM forecast_monthly_actuals_by_budget_code WHERE project_key=?",
                (project_key,),
            ).fetchone()[0]
            nonzero = conn.execute(
                "SELECT COUNT(DISTINCT month) FROM forecast_monthly_actuals_by_budget_code "
                "WHERE project_key=? AND amount IS NOT NULL AND amount != 0",
                (project_key,),
            ).fetchone()[0]
            freshness = conn.execute(
                "SELECT MAX(month) FROM forecast_monthly_actuals_by_budget_code WHERE project_key=?",
                (project_key,),
            ).fetchone()[0]
        budget_codes = (
            conn.execute(
                "SELECT COUNT(DISTINCT budget_code_key) FROM forecast_budget_details WHERE project_key=?",
                (project_key,),
            ).fetchone()[0]
            if has_budget
            else 0
        )
        cost_rows = (
            conn.execute(
                "SELECT COUNT(*) FROM forecast_cost_entries WHERE project_key=?", (project_key,)
            ).fetchone()[0]
            if has_cost
            else 0
        )

        # ---- maturity snapshot -------------------------------------------------------
        tier = _maturity_tier(completed, budget_codes > 0)
        snapshot_id = f"fms-{_hash(f'{run_id}|{project_key}|{source_package}')[:32]}"
        planned["maturity"].append(
            {
                "snapshot_id": snapshot_id,
                "run_id": run_id,
                "project_key": project_key,
                "source_package": source_package,
                "maturity_tier": tier,
                "completed_month_count": completed,
                "nonzero_month_count": nonzero,
                "lifecycle_signal": None,
                "basis": "completed_month_count_vs_model_engines_readiness_thresholds",
                "raw_json": json.dumps(
                    {
                        "maturity_tier": tier,
                        "completed_month_count": completed,
                        "nonzero_month_count": nonzero,
                        "budget_codes": budget_codes,
                        "thresholds": {
                            "candidate": MIN_MONTHS_CANDIDATE,
                            "reliable": MIN_MONTHS_RELIABLE,
                            "seasonal": MIN_MONTHS_SEASONAL,
                        },
                    },
                    sort_keys=True,
                ),
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )

        # ---- data availability profiles ---------------------------------------------
        domain_facts = {
            "budget": (budget_codes > 0, str(budget_codes), None),
            "cost_actuals": (cost_rows > 0, str(cost_rows), None),
            "monthly_actuals": (completed > 0, str(completed), freshness),
        }
        for domain in _DB_DOMAINS:
            present, count_str, fresh = domain_facts[domain]
            planned["availability"].append(
                _availability_row(
                    run_id, project_key, source_package, domain,
                    availability="available" if present else "unavailable",
                    coverage=count_str if present else "0",
                    freshness=fresh,
                    reason=("rows present in v59 source-domain table" if present
                            else "no rows in v59 source-domain table"),
                    now_utc=now_utc,
                )
            )
        for domain in _ABSENT_DOMAINS:
            planned["availability"].append(
                _availability_row(
                    run_id, project_key, source_package, domain,
                    availability="unavailable", coverage=None, freshness=None,
                    reason="no v59 source-domain table for this domain yet (confidence penalty, not a block)",
                    now_utc=now_utc,
                )
            )

        # ---- project confidence scorecard (from confidence_rollup.json) -------------
        rollup_path = analysis_package / CONFIDENCE_ROLLUP_FILE
        if rollup_path.is_file():
            rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
            _emit_project_scorecard(planned, run_id, project_key, rollup, now_utc, warnings)
        else:
            warnings.append(f"{CONFIDENCE_ROLLUP_FILE} not found; no project confidence scorecard")

        # ---- per-code confidence scorecards (reuse v63 forecast_output_budget_codes) -
        if has_outputs:
            rows = conn.execute(
                "SELECT budget_code_key, confidence, forecast_action, raw_json "
                "FROM forecast_output_budget_codes WHERE project_key=? ORDER BY source_row_number",
                (project_key,),
            ).fetchall()
            for key, confidence, action, raw in rows:
                _emit_code_scorecard(
                    planned, run_id, project_key, key, confidence, action, raw, now_utc
                )
        else:
            warnings.append("forecast_output_budget_codes absent; no per-code scorecards")
    finally:
        conn.close()

    counts = {k: len(v) for k, v in planned.items()}
    return {
        "ok": True,
        "project_key": project_key,
        "source_package": source_package,
        "run_id": run_id,
        "planned": planned,
        "counts": counts,
        "warnings": warnings,
    }


def _availability_row(run_id, project_key, source_package, domain, *, availability, coverage,
                      freshness, reason, now_utc) -> dict[str, Any]:
    return {
        "id": f"fdap-{_hash(f'{run_id}|{domain}')[:32]}",
        "run_id": run_id,
        "project_key": project_key,
        "source_package": source_package,
        "domain": domain,
        "availability": availability,
        "coverage": coverage,
        "freshness": freshness,
        "completeness": None,
        "mapping_quality": None,
        "maturity": None,
        "score": None,
        "reason": reason,
        "raw_json": json.dumps(
            {"domain": domain, "availability": availability, "coverage": coverage,
             "freshness": freshness, "reason": reason},
            sort_keys=True,
        ),
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }


def _emit_project_scorecard(planned, run_id, project_key, rollup, now_utc, warnings) -> None:
    by_conf = rollup.get("count_by_confidence") or {}
    # modal band (deterministic summary label; not a new numeric score)
    label = max(by_conf, key=lambda k: (by_conf[k], k)) if by_conf else None
    scorecard_id = f"fcs-{_hash(f'{run_id}|project|project')[:32]}"
    planned["scorecards"].append(
        {
            "scorecard_id": scorecard_id,
            "run_id": run_id,
            "output_id": None,
            "project_key": project_key,
            "scope": "project",
            "scope_key": "project",
            "score": None,  # numeric project score deferred (needs the forecast_accuracy artifact)
            "label": label,
            "rollup_json": json.dumps(rollup, sort_keys=True),
            "raw_json": json.dumps(rollup, sort_keys=True),
            "created_utc": now_utc,
            "updated_utc": now_utc,
        }
    )
    # one factor per confidence band (booster/penalty) — the persisted explanation
    for band, count in sorted(by_conf.items()):
        direction = "booster" if band == "high" else ("penalty" if band in ("low", "none") else "neutral")
        planned["factors"].append(
            _factor_row(scorecard_id, run_id, project_key, f"confidence_{band}", direction,
                        str(count), f"{count} budget codes at {band} confidence", now_utc)
        )
    neither = rollup.get("count_with_neither_owner_nor_procore")
    if neither:
        planned["factors"].append(
            _factor_row(scorecard_id, run_id, project_key, "no_owner_or_procore_evidence",
                        "penalty", str(neither),
                        f"{neither} budget codes lack owner/Procore pay-app evidence", now_utc)
        )
    if not planned["factors"]:
        # guarantee at least one factor for the scorecard
        planned["factors"].append(
            _factor_row(scorecard_id, run_id, project_key, "rollup_present", "neutral", None,
                        "confidence rollup present with no per-band counts", now_utc)
        )


def _emit_code_scorecard(planned, run_id, project_key, key, confidence, action, raw, now_utc) -> None:
    scorecard_id = f"fcs-{_hash(f'{run_id}|budget_code|{key}')[:32]}"
    try:
        rec = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        rec = {}
    planned["scorecards"].append(
        {
            "scorecard_id": scorecard_id,
            "run_id": run_id,
            "output_id": None,
            "project_key": project_key,
            "scope": "budget_code",
            "scope_key": key,
            "score": None,
            "label": confidence,
            "rollup_json": None,
            "raw_json": json.dumps(
                {"budget_code_key": key, "confidence": confidence, "forecast_action": action,
                 "evidence_depth": rec.get("evidence_depth"),
                 "confidence_reason": rec.get("confidence_reason")},
                sort_keys=True,
            ),
            "created_utc": now_utc,
            "updated_utc": now_utc,
        }
    )
    direction = "booster" if confidence == "high" else ("penalty" if confidence in ("low", "none") else "neutral")
    planned["factors"].append(
        _factor_row(scorecard_id, run_id, project_key, "per_code_confidence", direction,
                    None, rec.get("confidence_reason") or f"confidence={confidence}", now_utc)
    )


def _factor_row(scorecard_id, run_id, project_key, factor_key, direction, magnitude, reason,
                now_utc) -> dict[str, Any]:
    return {
        "id": f"fcf-{_hash(f'{scorecard_id}|{factor_key}')[:32]}",
        "scorecard_id": scorecard_id,
        "run_id": run_id,
        "project_key": project_key,
        "factor_key": factor_key,
        "direction": direction,
        "magnitude": magnitude,
        "reason": reason,
        "raw_json": json.dumps(
            {"factor_key": factor_key, "direction": direction, "magnitude": magnitude,
             "reason": reason},
            sort_keys=True,
        ),
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }


def project_decision_support(
    *,
    db_path: Path,
    analysis_package: Path,
    project_key: str,
    apply: bool = False,
    parity: bool = False,
    run_id: str | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Derive+project decision-support; dry-run plans only, apply writes to a temp DB."""
    # Fail closed before any read/write: never touch the live/default DB.
    if is_live_db_path(db_path):
        return {
            "ok": False,
            "mode": "apply" if apply else "dry_run",
            "reason": "refuses_live_db",
            "warnings": ["db_path resolves to the live/default DB (or is unresolvable); refusing"],
        }

    plan = plan_decision_support(
        db_path=db_path,
        analysis_package=analysis_package,
        project_key=project_key,
        run_id=run_id,
        now_utc=now_utc,
    )
    plan["guardrails"] = GUARDRAILS

    if not apply:
        plan["mode"] = "dry_run"
        if parity:
            plan["ok"] = False
            plan["parity"] = {
                "requested": True,
                "proven": False,
                "reason": "parity_requires_applied_db",
            }
            plan["warnings"].append("--parity needs --apply against an explicit temp DB")
        return plan

    written: dict[str, int] = dict.fromkeys(_PLAN_KEYS, 0)
    if plan["ok"]:
        with open_connection(Path(db_path)) as conn, transaction(conn):
            written = repo.apply_plan(conn, plan["planned"])
    plan["mode"] = "apply"
    plan["written"] = written

    if parity and run_id is not None:
        plan["parity"] = _prove_parity(db_path=Path(db_path), run_id=run_id, planned=plan["planned"])
        if not plan["parity"]["proven"]:
            plan["ok"] = False
    return plan


def _prove_parity(*, db_path: Path, run_id: str, planned: dict[str, list[dict]]) -> dict[str, Any]:
    """Read maturity/availability/scorecards back and compare counts to the plan."""
    per_table: dict[str, Any] = {}
    proven = True
    conn = _connect_ro(db_path)
    try:
        checks = {
            "maturity": repo.read_maturity_from_db(conn, run_id=run_id),
            "availability": repo.read_availability_from_db(conn, run_id=run_id),
            "scorecards": repo.read_scorecards_from_db(conn, run_id=run_id),
        }
    finally:
        conn.close()
    for kind, db_rows in checks.items():
        expected = len(planned.get(kind, []))
        match = len(db_rows) == expected
        per_table[kind] = {"db_rows": len(db_rows), "planned_rows": expected, "match": match}
        proven = proven and match
    return {"requested": True, "proven": proven, "by_table": per_table}
