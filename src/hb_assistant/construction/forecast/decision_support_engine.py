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

import contextlib
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import open_connection, transaction

from . import assumptions_repository as assumptions_repo
from . import decision_support_repository as repo
from . import model_registry_repository as model_registry
from .source_domain_engine import is_live_db_path  # reuse the fail-closed live-DB guard

GUARDRAILS = {
    "scope": "v65_decision_support_derive_and_project_only",
    "tables": "maturity_snapshots/data_availability_profiles/confidence_scorecards/confidence_factors",
    "external_systems": "none",
    "forecast_reads": "file_backed_unchanged",
    # P5: the only derived number is a deterministic, count-derived per-domain availability score
    # (availability-gated completeness ratio). No model/ML scoring is invented.
    "new_scoring_math": "deterministic_count_derived_availability_score_only",
    "dry_run_writes": False,
    "apply_requires_explicit_db_path": True,
    "apply_refuses_live_db": True,
}

_PLAN_KEYS = (
    "maturity",
    "availability",
    "scorecards",
    "factors",
    "method_eligibility",
    "model_selection",
)

# Reused from CFR workflows/model_engines_readiness.py (do not re-tune here).
MIN_MONTHS_CANDIDATE = 3
MIN_MONTHS_RELIABLE = 6
MIN_MONTHS_SEASONAL = 12

# Domains backed by a v59 source-domain table (presence/coverage from the source rows).
_DB_DOMAINS = ("budget", "cost_actuals", "monthly_actuals")

# P5: domains backed by a v63 forecast-output table (presence/coverage from the run's output rows).
# (domain, output table, is_per_code) — per-code domains carry budget_code_key and get
# completeness/mapping_quality derived from budget-code coverage.
_OUTPUT_DOMAINS = (
    ("commitment", "forecast_output_commitment_exposure", True),
    ("schedule", "forecast_output_schedule_phasing", True),
    ("changes", "forecast_output_changes", True),
    ("risk", "forecast_output_risks", True),
    ("probability", "forecast_output_probability", True),
    ("staffing", "forecast_output_staffing", False),
)

# P5: domains with NO forecast backing table yet — recorded "unavailable" (confidence penalty,
# not a block). procore data lives in the schedule source domain, not a forecast output table.
_NO_TABLE_DOMAINS = ("owner", "procore")

# P5: project closeout (M5) is declared when the run's output header shows cost-to-complete has
# fallen to a small fraction of the estimated-final-cost. A ratio (not absolute dollars) so a tiny
# retainage/warranty residual does not block it. NOTE (accepted risk, see ADR 308): a project
# stalled with budget exhausted before completion produces the same near-zero CTC and would be
# labeled closeout — the engine has no source signal to distinguish stall from genuine closeout.
M5_CLOSEOUT_CTC_FRACTION = Decimal("0.005")

# Coded lifecycle signal per maturity tier (path-free enum; safe for the read-model/API surface).
_LIFECYCLE_SIGNAL = {
    "M0": "pre_start",
    "M1": "mobilizing",
    "M2": "in_progress",
    "M3": "in_progress",
    "M4": "mature",
    "M5": "closeout",
}

CONFIDENCE_ROLLUP_FILE = "confidence_rollup.json"

# Phase 2c — forecast_accuracy package sources for per-method rollups.
EAC_ESTIMATES_FILE = "eac_estimates_by_budget_code.jsonl"
RECONCILIATION_FILE = "forecast_reconciliation_by_budget_code.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def _maturity_tier(completed_months: int, budget_present: bool, closeout: bool = False) -> str:
    if closeout:  # output evidence shows work essentially complete (CTC -> ~0 of EAC)
        return "M5"
    if completed_months >= MIN_MONTHS_RELIABLE:  # >=6 (incl. >=12) -> mature
        return "M4"
    if completed_months >= MIN_MONTHS_CANDIDATE:  # 3-5
        return "M3"
    if completed_months >= 1:  # 1-2
        return "M2"
    return "M1" if budget_present else "M0"  # 0 completed: mobilization vs pre-start


def _dec(value: Any) -> Decimal:
    """Parse a Decimal-string cell to Decimal; missing/garbage -> 0 (deterministic)."""
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _ratio(numerator: int, denominator: int) -> str | None:
    """Deterministic 4dp ratio string (capped at 1.0000); None when denominator is 0."""
    if denominator <= 0:
        return None
    r = Decimal(numerator) / Decimal(denominator)
    if r > 1:
        r = Decimal("1")
    return str(r.quantize(Decimal("0.0001")))


def _is_closeout(conn: sqlite3.Connection, run_id: str | None, project_key: str) -> bool:
    """M5 closeout: the run's output header CTC is <= M5_CLOSEOUT_CTC_FRACTION of EAC."""
    if run_id is None or not _table_exists(conn, "forecast_outputs"):
        return False
    rows = conn.execute(
        "SELECT estimated_final_cost, cost_to_complete FROM forecast_outputs "
        "WHERE run_id=? AND project_key=?",
        (run_id, project_key),
    ).fetchall()
    if not rows:
        return False
    eac = sum((_dec(r[0]) for r in rows), Decimal("0"))
    ctc = sum((_dec(r[1]) for r in rows), Decimal("0"))
    if eac <= 0:
        return False
    return (ctc / eac) <= M5_CLOSEOUT_CTC_FRACTION


def _count_output_rows(conn: sqlite3.Connection, table: str, run_id: str | None,
                       project_key: str) -> int:
    """Two-hop count of a v63 output child table for this run (child.output_id -> forecast_outputs).

    Child tables carry output_id, NOT run_id; the run/project scope lives on the header. Both
    run_id AND project_key are in the predicate so a shared run_id never cross-counts projects.
    """
    if run_id is None or not _table_exists(conn, table) or not _table_exists(conn, "forecast_outputs"):
        return 0
    return conn.execute(
        f"SELECT COUNT(*) FROM {table} t "
        "JOIN forecast_outputs fo ON fo.output_id = t.output_id "
        "WHERE fo.run_id=? AND fo.project_key=?",
        (run_id, project_key),
    ).fetchone()[0]


def _output_code_coverage(conn: sqlite3.Connection, table: str, run_id: str | None,
                          project_key: str) -> tuple[int, int]:
    """(mapped_codes, domain_codes) for a per-code output table: distinct budget_code_key in the
    domain, and how many resolve to a forecast_budget_details code for this project. Two-hop join,
    run_id + project_key scoped."""
    if run_id is None or not _table_exists(conn, table) or not _table_exists(conn, "forecast_outputs"):
        return 0, 0
    domain_codes = conn.execute(
        f"SELECT COUNT(DISTINCT t.budget_code_key) FROM {table} t "
        "JOIN forecast_outputs fo ON fo.output_id = t.output_id "
        "WHERE fo.run_id=? AND fo.project_key=?",
        (run_id, project_key),
    ).fetchone()[0]
    mapped = 0
    if _table_exists(conn, "forecast_budget_details"):
        mapped = conn.execute(
            f"SELECT COUNT(DISTINCT t.budget_code_key) FROM {table} t "
            "JOIN forecast_outputs fo ON fo.output_id = t.output_id "
            "JOIN forecast_budget_details bd "
            "  ON bd.budget_code_key = t.budget_code_key AND bd.project_key = fo.project_key "
            "WHERE fo.run_id=? AND fo.project_key=?",
            (run_id, project_key),
        ).fetchone()[0]
    return mapped, domain_codes


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
    accuracy_package: Path | None = None,
    operator_assumptions: list[dict[str, Any]] | None = None,
    required_assumptions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Derive maturity/availability from DB inputs + project confidence from the package.

    Reads inputs read-only; builds planned rows in memory; performs no writes. When
    ``accuracy_package`` is supplied (explicit only), per-method eligibility and
    model-selection rollups are projected from the forecast_accuracy package files.

    P2: ``operator_assumptions`` / ``required_assumptions`` are PRE-HYDRATED lists (read
    elsewhere, read-only, from the live managed DB — see ``project_decision_support``). When
    present they add confidence-modifier + required-gate factors to the existing scorecards.
    Both default to ``None`` (and empty lists are a no-op), so the no-assumptions output is
    byte-identical to before — the planner never opens the assumptions DB itself.
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
        closeout = _is_closeout(conn, run_id, project_key) if has_outputs else False
        tier = _maturity_tier(completed, budget_codes > 0, closeout)
        lifecycle_signal = _LIFECYCLE_SIGNAL[tier]
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
                "lifecycle_signal": lifecycle_signal,
                "basis": "completed_month_count_vs_model_engines_readiness_thresholds+closeout_ctc",
                "raw_json": json.dumps(
                    {
                        "maturity_tier": tier,
                        "lifecycle_signal": lifecycle_signal,
                        "closeout": closeout,
                        "completed_month_count": completed,
                        "nonzero_month_count": nonzero,
                        "budget_codes": budget_codes,
                        "thresholds": {
                            "candidate": MIN_MONTHS_CANDIDATE,
                            "reliable": MIN_MONTHS_RELIABLE,
                            "seasonal": MIN_MONTHS_SEASONAL,
                            "closeout_ctc_fraction": str(M5_CLOSEOUT_CTC_FRACTION),
                        },
                    },
                    sort_keys=True,
                ),
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )

        # ---- data availability profiles (P5: v59 source + v63 output + v66 + no-table) ----
        # The project maturity tier is layered onto every domain row; score is the
        # availability-gated completeness ratio (per-code domains) or the availability flag.
        def _avail(domain, *, present, coverage, freshness, reason,
                   completeness=None, mapping_quality=None):
            score = (completeness if (present and completeness is not None)
                     else ("1.0000" if present else "0.0000"))
            planned["availability"].append(
                _availability_row(
                    run_id, project_key, source_package, domain,
                    availability="available" if present else "unavailable",
                    coverage=coverage, freshness=freshness, reason=reason,
                    completeness=completeness, mapping_quality=mapping_quality,
                    maturity=tier, score=score, now_utc=now_utc,
                )
            )

        _present_reason = "rows present in v59 source-domain table"
        _absent_reason = "no rows in v59 source-domain table"
        _avail("budget", present=budget_codes > 0,
               coverage=str(budget_codes) if budget_codes else "0", freshness=None,
               reason=_present_reason if budget_codes else _absent_reason)
        _avail("cost_actuals", present=cost_rows > 0,
               coverage=str(cost_rows) if cost_rows else "0", freshness=None,
               reason=_present_reason if cost_rows else _absent_reason)
        _avail("monthly_actuals", present=completed > 0,
               coverage=str(completed) if completed else "0", freshness=freshness,
               reason=_present_reason if completed else _absent_reason)

        # v63 forecast-output backed (P5: output-aware — no longer always "unavailable")
        for domain, table, per_code in _OUTPUT_DOMAINS:
            total = _count_output_rows(conn, table, run_id, project_key)
            completeness = mapping_quality = None
            if per_code and total:
                mapped, domain_codes = _output_code_coverage(conn, table, run_id, project_key)
                completeness = _ratio(mapped, budget_codes)
                mapping_quality = _ratio(mapped, domain_codes)
            _avail(domain, present=total > 0, coverage=str(total) if total else "0",
                   freshness=None, completeness=completeness, mapping_quality=mapping_quality,
                   reason=("rows present in v63 forecast-output table" if total
                           else "no rows in v63 forecast-output table for this run"))

        # v66 assumptions (run-scoped; ship empty until the operator UI populates them)
        assume_total = 0
        for atable in ("forecast_operator_assumptions", "forecast_required_assumptions"):
            if _table_exists(conn, atable):
                assume_total += conn.execute(
                    f"SELECT COUNT(*) FROM {atable} WHERE run_id=? AND project_key=?",
                    (run_id, project_key),
                ).fetchone()[0]
        _avail("assumptions", present=assume_total > 0,
               coverage=str(assume_total) if assume_total else "0", freshness=None,
               reason=("operator/required assumptions recorded for this run" if assume_total
                       else "no operator/required assumptions recorded for this run"))

        # no forecast backing table yet (procore lives in the schedule source domain)
        for domain in _NO_TABLE_DOMAINS:
            _avail(domain, present=False, coverage=None, freshness=None,
                   reason="no forecast backing table for this domain yet (confidence penalty, not a block)")

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

    # ---- per-method rollups from the forecast_accuracy package (file reads only) -------
    if accuracy_package is not None:
        _emit_method_rollups(planned, run_id, project_key, Path(accuracy_package), now_utc, warnings)

    # ---- P2: operator-assumption consumption (pre-hydrated; empty/None = no-op) ---------
    if operator_assumptions or required_assumptions:
        _apply_assumption_factors(
            planned, run_id, project_key,
            operator_assumptions or [], required_assumptions or [], warnings, now_utc,
        )

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
                      freshness, reason, now_utc, completeness=None, mapping_quality=None,
                      maturity=None, score=None) -> dict[str, Any]:
    return {
        "id": f"fdap-{_hash(f'{run_id}|{domain}')[:32]}",
        "run_id": run_id,
        "project_key": project_key,
        "source_package": source_package,
        "domain": domain,
        "availability": availability,
        "coverage": coverage,
        "freshness": freshness,
        "completeness": completeness,
        "mapping_quality": mapping_quality,
        "maturity": maturity,
        "score": score,
        "reason": reason,
        "raw_json": json.dumps(
            {"domain": domain, "availability": availability, "coverage": coverage,
             "freshness": freshness, "completeness": completeness,
             "mapping_quality": mapping_quality, "maturity": maturity, "score": score,
             "reason": reason},
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


# P2: operator confidence_impact -> persisted factor direction.
_CONFIDENCE_IMPACT_DIRECTION = {"raises": "booster", "lowers": "penalty", "neutral": "neutral"}


def _apply_assumption_factors(planned, run_id, project_key, operator_assumptions,
                              required_assumptions, warnings, now_utc) -> None:
    """Emit confidence-modifier + required-gate factors from operator assumptions.

    Factors attach to EXISTING scorecards only (the factors table FKs ``scorecard_id``): a
    matching per-code scorecard is preferred, else the project scorecard. Each emitted factor
    is an ordinary confidence factor row, persisted via the existing ``apply_plan`` writer —
    no new tables, no schema change. Consumption is degraded-not-fatal: anything that cannot
    attach is recorded as a warning, never a failure.
    """
    existing = {s["scorecard_id"] for s in planned["scorecards"]}
    project_sid = f"fcs-{_hash(f'{run_id}|project|project')[:32]}"

    for a in operator_assumptions:
        impact = (a.get("confidence_impact") or "").strip().lower()
        direction = _CONFIDENCE_IMPACT_DIRECTION.get(impact)
        if direction is None:
            continue  # no/unknown confidence_impact -> not a confidence modifier
        atype = a.get("assumption_type") or "unspecified"
        code = a.get("budget_code_key")
        sid = f"fcs-{_hash(f'{run_id}|budget_code|{code}')[:32]}" if code else project_sid
        if sid not in existing:
            sid = project_sid  # fall back to the project scorecard if the code has none
        if sid not in existing:
            warnings.append(f"operator assumption '{atype}' skipped: no scorecard to attach to")
            continue
        reason = a.get("source") or a.get("value") or f"operator assumption: {atype}"
        planned["factors"].append(
            _factor_row(sid, run_id, project_key, f"operator_assumption:{atype}",
                        direction, None, reason, now_utc)
        )

    for r in required_assumptions:
        if r.get("satisfied"):
            continue
        atype = r.get("assumption_type") or "unspecified"
        warnings.append(f"required assumption '{atype}' is unsatisfied")
        if project_sid in existing:
            planned["factors"].append(
                _factor_row(project_sid, run_id, project_key,
                            f"required_assumption_unsatisfied:{atype}", "penalty", None,
                            r.get("reason") or f"required assumption unsatisfied: {atype}",
                            now_utc)
            )


def _hydrate_assumptions(
    *, project_key: str, assumptions_db_path: Path | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read operator/required assumptions read-only when consumption is enabled.

    Returns ``([], [])`` when the flag is off, no DB is available, or the read fails —
    consumption is degraded-not-fatal and never blocks a run. The assumptions live in the
    LIVE managed DB (where the operator write surface puts them); this opens it ``mode=ro``
    only. ``assumptions_db_path`` lets tests point at a seeded temp DB (no live access).
    """
    # Lazy import: keep the flag-off path free of the analytics-config dependency.
    from hb_assistant.construction.analytics.forecast_runtime_config import (
        resolve_assumption_consumption_enabled,
    )

    if not resolve_assumption_consumption_enabled():
        return [], []
    src = assumptions_db_path
    if src is None:
        from hb_assistant.config.path_policy import PathPolicy

        src = PathPolicy().get_db_path()
    try:
        conn = _connect_ro(Path(src))
    except sqlite3.Error:
        return [], []
    try:
        return (
            assumptions_repo.read_operator_assumptions_from_db(conn, project_key=project_key),
            assumptions_repo.read_required_assumptions_from_db(conn, project_key=project_key),
        )
    except sqlite3.Error:
        return [], []
    finally:
        conn.close()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _emit_method_rollups(planned, run_id, project_key, accuracy_package, now_utc, warnings) -> None:
    """Aggregate per-code forecast_accuracy estimates/contributions into per-method run rows.

    Project-level rollups (the v66 tables are keyed UNIQUE(run_id, method)); the per-code detail
    is summarized into raw_json. No new scoring math — only counts and a mean of emitted weights.
    """
    est_rows = _read_jsonl(accuracy_package / EAC_ESTIMATES_FILE)
    if not est_rows:
        warnings.append(f"{EAC_ESTIMATES_FILE} not found or empty; no method-eligibility rows")
    elig: dict[str, dict[str, Any]] = {}
    total_codes = len(est_rows)
    for row in est_rows:
        for est in row.get("estimates") or []:
            method = est.get("method")
            if not method:
                continue
            agg = elig.setdefault(method, {"applicable": 0, "reliability": {}})
            if est.get("applicable"):
                agg["applicable"] += 1
                rel = est.get("reliability")
                if rel:
                    agg["reliability"][rel] = agg["reliability"].get(rel, 0) + 1
    for method in sorted(elig):
        agg = elig[method]
        applicable = agg["applicable"]
        rel = agg["reliability"]
        if applicable == 0:
            status = "rejected_missing_data"
        elif rel.get("high") or rel.get("medium"):
            status = "eligible_weighted"
        else:
            status = "eligible_advisory"
        planned["method_eligibility"].append(
            {
                "id": f"fmel-{_hash(f'{run_id}|{method}')[:32]}",
                "run_id": run_id,
                "project_key": project_key,
                "method": method,
                "status": status,
                "weight": None,
                "reason": f"applicable for {applicable}/{total_codes} budget codes",
                "raw_json": json.dumps(
                    {"applicable_count": applicable, "total_codes": total_codes,
                     "reliability_histogram": rel},
                    sort_keys=True,
                ),
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )

    rec_rows = _read_jsonl(accuracy_package / RECONCILIATION_FILE)
    if not rec_rows:
        warnings.append(f"{RECONCILIATION_FILE} not found or empty; no model-selection rows")
    sel: dict[str, dict[str, Any]] = {}
    for row in rec_rows:
        for contrib in row.get("contributions") or []:
            method = contrib.get("method")
            if not method:
                continue
            agg = sel.setdefault(method, {"count": 0, "weights": []})
            agg["count"] += 1
            with contextlib.suppress(InvalidOperation, TypeError):
                agg["weights"].append(Decimal(str(contrib.get("effective_weight"))))
    for method in sorted(sel):
        agg = sel[method]
        weights = agg["weights"]
        mean_w = (sum(weights) / Decimal(len(weights))) if weights else None
        planned["model_selection"].append(
            {
                "id": f"fmsd-{_hash(f'{run_id}|{method}')[:32]}",
                "run_id": run_id,
                "project_key": project_key,
                "method": method,
                "contributed": 1 if agg["count"] > 0 else 0,
                "weight": f"{mean_w:.4f}" if mean_w is not None else None,
                "reason": f"contributed to {agg['count']} budget codes",
                "raw_json": json.dumps(
                    {"contributed_code_count": agg["count"],
                     "mean_effective_weight": f"{mean_w:.4f}" if mean_w is not None else None},
                    sort_keys=True,
                ),
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )


def project_decision_support(
    *,
    db_path: Path,
    analysis_package: Path,
    project_key: str,
    apply: bool = False,
    parity: bool = False,
    run_id: str | None = None,
    now_utc: str | None = None,
    accuracy_package: Path | None = None,
    assumptions_db_path: Path | None = None,
) -> dict[str, Any]:
    """Derive+project decision-support; dry-run plans only, apply writes to a temp DB.

    P2: when ``HB_FORECAST_ASSUMPTION_CONSUMPTION_ENABLED`` is set, operator/required
    assumptions are read read-only (from ``assumptions_db_path`` or, by default, the live
    managed DB) and threaded into the plan. The flag is off by default — output is then
    byte-identical to before. The ``is_live_db_path`` guard below still applies only to the
    run/write ``db_path``; the assumptions read is a separate ``mode=ro`` connection.
    """
    # Fail closed before any read/write: never touch the live/default DB.
    if is_live_db_path(db_path):
        return {
            "ok": False,
            "mode": "apply" if apply else "dry_run",
            "reason": "refuses_live_db",
            "warnings": ["db_path resolves to the live/default DB (or is unresolvable); refusing"],
        }

    operator_assumptions, required_assumptions = _hydrate_assumptions(
        project_key=project_key, assumptions_db_path=assumptions_db_path
    )

    plan = plan_decision_support(
        db_path=db_path,
        analysis_package=analysis_package,
        project_key=project_key,
        run_id=run_id,
        now_utc=now_utc,
        accuracy_package=accuracy_package,
        operator_assumptions=operator_assumptions,
        required_assumptions=required_assumptions,
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

    # P6: when model governance is on, persist model-registry provenance alongside the apply.
    # Fail closed before any write if the accuracy package / methodology descriptor / run_id is
    # missing, so we never record a half-provenance. Flag-off => no governance, byte-identical.
    from ..analytics.forecast_runtime_config import resolve_model_governance_enabled

    governance_on = resolve_model_governance_enabled()
    if governance_on and (
        run_id is None
        or accuracy_package is None
        or not model_registry.has_methodology(Path(accuracy_package))
    ):
        plan["ok"] = False
        plan["mode"] = "apply"
        plan["reason"] = "model_governance_requires_accuracy_methodology"
        plan["warnings"].append(
            "HB_FORECAST_MODEL_GOVERNANCE_ENABLED is set but no run_id / accuracy_package "
            "model_methodology.json was supplied; refusing to write a partial provenance"
        )
        return plan

    written: dict[str, int] = dict.fromkeys(_PLAN_KEYS, 0)
    provenance: dict[str, Any] | None = None
    if plan["ok"]:
        with open_connection(Path(db_path)) as conn, transaction(conn):
            written = repo.apply_plan(conn, plan["planned"])
            if governance_on and accuracy_package is not None and run_id is not None:
                provenance = model_registry.persist_run_model_provenance(
                    conn,
                    run_id=run_id,
                    project_key=project_key,
                    accuracy_package=Path(accuracy_package),
                    now_utc=now_utc or _now(),
                )
    plan["mode"] = "apply"
    plan["written"] = written
    if provenance is not None:
        plan["model_provenance"] = provenance

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
            "method_eligibility": repo.read_method_eligibility_from_db(conn, run_id=run_id),
            "model_selection": repo.read_model_selection_from_db(conn, run_id=run_id),
        }
    finally:
        conn.close()
    for kind, db_rows in checks.items():
        expected = len(planned.get(kind, []))
        match = len(db_rows) == expected
        per_table[kind] = {"db_rows": len(db_rows), "planned_rows": expected, "match": match}
        proven = proven and match
    return {"requested": True, "proven": proven, "by_table": per_table}
