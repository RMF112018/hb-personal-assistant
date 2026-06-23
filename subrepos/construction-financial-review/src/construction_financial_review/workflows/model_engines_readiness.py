"""Phase I PR 1 — model-engines data + semantic readiness evidence (read-only, no dependency).

Answers TWO questions with deterministic, auditable evidence, for the tropical project, before any
statsforecast investment:

  1. Time-series sufficiency — does the per-code monthly actual history support a future
     ``statsforecast`` estimator (enough completed months, clean enough series)?
  2. Semantic safety — are the monthly actuals + budget-code denominators safe to use as
     model-engine inputs under the forecasting semantic catalog + gates already built in the main
     hb_assistant repo (actuals precedence, ERP sidecar, double-count, projection parity, budget
     column roles, dynamic columns)?

Evidence only. This module adds NO dependency, edits NO forecast core
(``forecast_intelligence/estimators_uncapped.py`` stays a 6-estimator ensemble; ``reconcile_final``
untouched), changes NO schema/migrator, and edits NOTHING under ``hb_assistant.forecasting`` (it is
consumed, never modified). It consumes an EXISTING context package (never generates one) and opens
the operator-supplied DB strictly read-only via the semantic gates.

CFR/stdlib for the time-series half. The semantic half calls
``hb_assistant.forecasting.readiness.evaluate_forecast_semantic_gates`` via a lazy, fail-closed
import (mirrors ``db_cutover_readiness._refuse_if_live_db`` discipline): if the layer is unavailable
or the gate call fails, the semantic section is recorded as ``not_available`` and a READY decision
is blocked — never silently passed.

Decision: ``model_engines_data_ready`` only when the data is both time-series-sufficient AND
semantically safe (no gate errors, gates available). Gate WARNINGS are carried into the evidence
but do not block; gate ERRORS or gates-not-available block READY.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from ..common.hashing import sha256_file
from ..common.io import read_jsonl
from ..common.money import D, dec, money_str
from ..common.project_eligibility import eligible_projects, is_project_eligible
from ..forecast_cost_frequency.weekday_calendar import months_between

SUPPORTED_PROJECT_KEY = "tropical"
REPORT_SCHEMA_VERSION = 1

READINESS_SUBDIR = "model_engines_readiness"
READINESS_REPORT_NAME = "model_engines_readiness_report.json"

MONTHLY_ACTUALS_REL = "canonical/monthly_actuals_by_budget_code.jsonl"
BUDGET_CODES_REL = "canonical/budget_codes.jsonl"

ACTUAL_SOURCE = "CostEntries"
COMPLETED_BUCKET = "through_may_2026"
TO_DATE_BUCKET = "june_2026_to_date"
FUTURE_BUCKET = "after_june_2026"

# Candidate tiers — deliberately aligned with the existing ensemble gates so readiness speaks the
# same language as the code that would consume the estimator: trend_projection_eac applies at >= 3
# completed months and reaches medium reliability at >= 6; 12 = a full annual cycle for ETS/Theta.
MIN_MONTHS_CANDIDATE = 3
MIN_MONTHS_RELIABLE = 6
MIN_MONTHS_SEASONAL = 12

# Go/no-go thresholds (tunable; recorded in the report). READY needs broad code coverage AND a
# majority of cost-to-complete dollars eligible; below the floor on both is NOT_READY.
READY_CODE_COVERAGE = Decimal("0.30")
READY_DOLLAR_COVERAGE = Decimal("0.50")
INSUFFICIENT_FLOOR = Decimal("0.05")

DECISION_READY = "model_engines_data_ready"
DECISION_INSUFFICIENT = "model_engines_data_insufficient"
DECISION_NOT_READY = "not_ready"

GATE_PROJECTION_PARITY = "forecast_projection_parity"
GATE_DOUBLE_COUNT = "forecast_double_count_prevention"

# Known projection-parity limitations from the forecasting DB audit — carried as warnings, never
# hidden. (RFQ scope mismatch; prime change-order line-item parity fan-out.)
PROJECTION_PARITY_KNOWN_LIMITS = (
    "RFQ scope mismatch: only a subset of RFQs trace to commitment change-order packages.",
    "Prime change-order line items fan out under multi-level budget-code segmentation; "
    "line-item parity is approximate.",
)

ZERO = Decimal("0")
_QUANT4 = Decimal("0.0001")

# Controlled-safety guard only (mirrors the generators' live Synology root). Monkeypatched in tests.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class ModelEnginesReadinessError(RuntimeError):
    """Raised when a readiness run is rejected by a preflight safety check (fail closed)."""


# --------------------------------------------------------------------------- shared utilities


def _is_under(path: Path, root: Path) -> bool:
    """True when ``path`` equals or is nested under ``root`` (resolved, non-strict)."""
    rp = path.expanduser().resolve(strict=False)
    rr = root.expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _write_json_deterministic(path: Path, obj: dict) -> Path:
    """Write sorted-key, indented JSON with a trailing newline (no wall-clock); return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _frac(numerator: Decimal, denominator: Decimal) -> str:
    """Deterministic 4dp fraction string; 0.0000 when the denominator is zero."""
    if denominator <= 0:
        return "0.0000"
    return str((numerator / denominator).quantize(_QUANT4))


# --------------------------------------------------------------------------- time-series read


def _read_monthly_actuals(path: Path) -> tuple[OrderedDict, int]:
    """Read canonical monthly actuals (CostEntries truth) into a per-code month map.

    Returns ``(by_key, row_count)`` where ``by_key[code] = {"months": {month: {"amount": Decimal,
    "bucket": str}}, "source_contaminated": bool}``. Amounts are summed per (code, month); rows whose
    ``source != "CostEntries"`` mark the code contaminated and are skipped (mirrors
    ``actuals_export.load_costentries_monthly`` precedence). The bucket is the row's own
    ``actual_period_bucket`` (deterministic, never a wall clock).
    """
    by_key: "OrderedDict[str, dict]" = OrderedDict()
    row_count = 0
    for r in read_jsonl(path):
        row_count += 1
        key = r.get("budget_code_key") or r.get("mapped_budget_code_key")
        if not key:
            continue
        rec = by_key.setdefault(key, {"months": OrderedDict(), "source_contaminated": False})
        if r.get("source") != ACTUAL_SOURCE:
            rec["source_contaminated"] = True
            continue
        month = r.get("month")
        if not month:
            continue
        amt = D(
            r.get("amount_decimal_string")
            if r.get("amount_decimal_string") is not None
            else r.get("amount")
        )
        bucket = r.get("actual_period_bucket") or "undated"
        cell = rec["months"].setdefault(month, {"amount": ZERO, "bucket": bucket})
        cell["amount"] += amt
    return by_key, row_count


def _read_projected_costs(path: Path) -> dict[str, Decimal]:
    """Map budget_code_key -> projected_costs (a terminal/calculated column used ONLY as a
    coverage-denominator reference scale, never as an additive model feature)."""
    out: dict[str, Decimal] = {}
    for r in read_jsonl(path):
        key = r.get("budget_code_key")
        if not key:
            continue
        amounts = r.get("amounts") or {}
        pc = dec(amounts.get("projected_costs"))
        if pc is not None:
            out[key] = pc
    return out


def _code_metrics(code: str, rec: dict, projected: Decimal | None) -> dict[str, Any]:
    """Per-code time-series metrics + data-quality flags + statsforecast eligibility."""
    months = rec["months"]
    completed = OrderedDict((m, c) for m, c in months.items() if c["bucket"] == COMPLETED_BUCKET)
    completed_keys = sorted(completed)
    completed_count = len(completed_keys)
    nonzero_count = sum(1 for m in completed_keys if completed[m]["amount"] != ZERO)
    first_m = completed_keys[0] if completed_keys else None
    last_m = completed_keys[-1] if completed_keys else None
    span = len(months_between(first_m, last_m)) if first_m and last_m else 0
    gap_count = max(0, span - completed_count)

    june_present = any(c["bucket"] == TO_DATE_BUCKET for c in months.values())
    after_june_count = sum(1 for c in months.values() if c["bucket"] == FUTURE_BUCKET)

    # Cumulative actual to date = CostEntries through-May + June-to-date (precedence #1 axis).
    cum_actual = sum(
        (c["amount"] for c in months.values() if c["bucket"] in (COMPLETED_BUCKET, TO_DATE_BUCKET)),
        ZERO,
    )
    ctc = max(ZERO, projected - cum_actual) if projected is not None else None

    flags: list[str] = []
    if rec["source_contaminated"]:
        flags.append("source_contamination")
    if completed_count == 0:
        flags.append("short_history")
    else:
        if completed_count < MIN_MONTHS_CANDIDATE:
            flags.append("short_history")
        if nonzero_count == 0:
            flags.append("all_zero")
        if any(completed[m]["amount"] < ZERO for m in completed_keys):
            flags.append("negative_or_credit_months")
        if nonzero_count == 1 and completed_count >= MIN_MONTHS_CANDIDATE:
            flags.append("single_spike")
        if gap_count > 0:
            flags.append("has_gaps")
    flags = sorted(set(flags))

    if completed_count >= MIN_MONTHS_SEASONAL:
        tier = "ge12"
    elif completed_count >= MIN_MONTHS_RELIABLE:
        tier = "ge6"
    elif completed_count >= MIN_MONTHS_CANDIDATE:
        tier = "ge3"
    else:
        tier = "below_min"

    # Negative months and interior gaps are reported but do NOT disqualify (statsforecast tolerates
    # them); all-zero, single-spike, too-short, and contaminated do.
    eligible = (
        completed_count >= MIN_MONTHS_CANDIDATE
        and "all_zero" not in flags
        and "single_spike" not in flags
        and "source_contamination" not in flags
    )

    return {
        "budget_code_key": code,
        "completed_month_count": completed_count,
        "nonzero_completed_month_count": nonzero_count,
        "first_completed_month": first_m,
        "last_completed_month": last_m,
        "span_months": span,
        "gap_count": gap_count,
        "june_to_date_present": june_present,
        "after_june_dated_month_count": after_june_count,
        "cumulative_actual_to_date": money_str(cum_actual),
        "projected_costs": money_str(projected) if projected is not None else None,
        "cost_to_complete_proxy": money_str(ctc) if ctc is not None else None,
        "candidate_tier": tier,
        "data_quality_flags": flags,
        "statsforecast_eligible": eligible,
        "_has_any_actual": completed_count > 0 or june_present,
        "_ctc": ctc,
        "_eligible": eligible,
        "_has_projected": projected is not None,
    }


# --------------------------------------------------------------------------- semantic gates


def _not_available(reason: str) -> dict[str, Any]:
    return {
        "status": "not_available",
        "reason": reason,
        "ok": None,
        "gate_count": 0,
        "passed_count": 0,
        "warning_count": 0,
        "error_count": 0,
        "per_gate": [],
    }


def _build_semantic(report: dict[str, Any], gate_mode: str) -> dict[str, Any]:
    summary = report.get("summary") or {}
    per_gate = [
        {
            "gate": g.get("gate"),
            "ok": g.get("ok"),
            "finding_count": int(g.get("finding_count", 0) or 0),
            "warning_count": int(g.get("warning_count", 0) or 0),
            "error_count": int(g.get("error_count", 0) or 0),
        }
        for g in report.get("gates", [])
    ]
    return {
        "status": report.get("gate_status", "warning"),
        "reason": None,
        "ok": report.get("ok"),
        "mode": gate_mode,
        "gate_count": int(summary.get("gate_count", len(per_gate)) or 0),
        "passed_count": int(summary.get("passed_count", 0) or 0),
        "warning_count": int(summary.get("warning_count", 0) or 0),
        "error_count": int(summary.get("error_count", 0) or 0),
        "per_gate": per_gate,
        "readiness_note": report.get("readiness_note"),
    }


def _gate_by_name(semantic: dict[str, Any], name: str) -> dict[str, Any] | None:
    for g in semantic.get("per_gate", []):
        if g.get("gate") == name:
            return g
    return None


def _semantic_catalog_versions() -> dict[str, Any]:
    """Best-effort read of catalog file ``version:`` lines (no YAML dependency; null on any error)."""
    out: dict[str, Any] = {"semantic_catalog": None, "actuals_precedence_model": None}
    try:
        import hb_assistant.forecasting as _fpkg

        base = (
            Path(_fpkg.__file__).resolve().parents[3] / "docs" / "forecasting" / "semantic-catalog"
        )
        for key, fname in (
            ("semantic_catalog", "semantic_catalog.yml"),
            ("actuals_precedence_model", "actuals_precedence_model.yml"),
        ):
            fp = base / fname
            if not fp.exists():
                continue
            for line in fp.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("version:"):
                    raw = stripped.split(":", 1)[1].strip()
                    out[key] = int(raw) if raw.isdigit() else raw
                    break
    except Exception:  # noqa: BLE001 - informational only; fail closed to null
        return {"semantic_catalog": None, "actuals_precedence_model": None}
    return out


def _resolve_semantic_gate(
    db_path: Path, gate_mode: str, semantic_gate_fn: Callable | None
) -> dict[str, Any]:
    gate_fn = semantic_gate_fn
    if gate_fn is None:
        try:
            from hb_assistant.forecasting.readiness import evaluate_forecast_semantic_gates
        except ImportError as exc:
            return _not_available(f"hb_assistant forecasting layer unavailable: {exc}")
        gate_fn = evaluate_forecast_semantic_gates
    try:
        report = gate_fn(db_path=str(db_path), mode=gate_mode)
    except Exception as exc:  # noqa: BLE001 - fail-closed boundary; any gate failure => not_available
        return _not_available(f"semantic gate evaluation failed: {exc}")
    return _build_semantic(report, gate_mode)


# --------------------------------------------------------------------------- main entry point


def run_model_engines_readiness(
    *,
    context_package: Path,
    db_path: Path,
    work_root: Path,
    project_key: str = SUPPORTED_PROJECT_KEY,
    gate_mode: str = "warn",
    semantic_gate_fn: Callable | None = None,
) -> dict[str, Any]:
    """Produce deterministic model-engines data + semantic readiness evidence for tropical.

    Preflight fails closed (``ModelEnginesReadinessError``) BEFORE any output on: non-tropical
    project; missing/non-dir context package; missing canonical monthly-actuals or budget-codes
    file; missing db_path; missing work root or a work root at/under the live forecast root; or a
    ``<work_root>/model_engines_readiness`` that already holds output.

    Reads the per-code monthly series (time-series sufficiency) and budget-code projected costs
    (coverage denominator) read-only, then runs the hb_assistant forecasting semantic gates against
    ``db_path`` read-only. Returns the readiness report dict (plus ``report_path``). ``semantic_gate_fn``
    is an injection seam for tests; production passes None (real lazy import).
    """
    # --- Preflight (fail closed before any output). ----------------------------------------------
    if not is_project_eligible(project_key):
        raise ModelEnginesReadinessError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    if not context_package:
        raise ModelEnginesReadinessError("context_package is required (explicit existing package)")
    context_package = Path(context_package)
    if not context_package.exists() or not context_package.is_dir():
        raise ModelEnginesReadinessError(
            f"context_package not found or not a directory: {context_package}"
        )
    monthly_path = context_package / MONTHLY_ACTUALS_REL
    if not monthly_path.exists():
        raise ModelEnginesReadinessError(
            f"required input missing: {MONTHLY_ACTUALS_REL} (this PR consumes an existing package, "
            f"never generates one): {monthly_path}"
        )
    budget_codes_path = context_package / BUDGET_CODES_REL
    if not budget_codes_path.exists():
        raise ModelEnginesReadinessError(
            f"required input missing: {BUDGET_CODES_REL} (dollar-coverage denominator): "
            f"{budget_codes_path}"
        )
    if not db_path:
        raise ModelEnginesReadinessError("db_path is required (read-only DB for semantic gates)")
    db_path = Path(db_path)
    if not db_path.exists():
        raise ModelEnginesReadinessError(f"db_path not found: {db_path}")
    if not work_root:
        raise ModelEnginesReadinessError(
            "work_root is required (explicit; no implicit output root)"
        )
    work_root = Path(work_root)
    if _is_under(work_root, _LIVE_ROOT):
        raise ModelEnginesReadinessError(
            f"work_root is at/under the live forecast root (refused): {work_root}"
        )
    out_root = work_root / READINESS_SUBDIR
    if out_root.exists() and any(out_root.iterdir()):
        raise ModelEnginesReadinessError(
            f"readiness work root already contains output (refusing to reuse): {out_root}"
        )

    # --- Time-series sufficiency. ----------------------------------------------------------------
    by_key, monthly_row_count = _read_monthly_actuals(monthly_path)
    projected = _read_projected_costs(budget_codes_path)

    per_code: list[dict[str, Any]] = []
    for code in sorted(by_key):
        per_code.append(_code_metrics(code, by_key[code], projected.get(code)))

    codes_total = len(per_code)
    codes_with_any = sum(1 for m in per_code if m["_has_any_actual"])
    codes_ge3 = sum(1 for m in per_code if m["completed_month_count"] >= MIN_MONTHS_CANDIDATE)
    codes_ge6 = sum(1 for m in per_code if m["completed_month_count"] >= MIN_MONTHS_RELIABLE)
    codes_ge12 = sum(1 for m in per_code if m["completed_month_count"] >= MIN_MONTHS_SEASONAL)
    codes_eligible = sum(1 for m in per_code if m["_eligible"])

    histogram = {"0": 0, "1-2": 0, "3-5": 0, "6-11": 0, "12+": 0}
    for m in per_code:
        c = m["completed_month_count"]
        if c == 0:
            histogram["0"] += 1
        elif c <= 2:
            histogram["1-2"] += 1
        elif c <= 5:
            histogram["3-5"] += 1
        elif c <= 11:
            histogram["6-11"] += 1
        else:
            histogram["12+"] += 1

    dollar_total = sum((m["_ctc"] for m in per_code if m["_has_projected"]), ZERO)
    dollar_eligible = sum(
        (m["_ctc"] for m in per_code if m["_has_projected"] and m["_eligible"]), ZERO
    )
    code_cov = (Decimal(codes_eligible) / Decimal(codes_total)) if codes_total else ZERO
    dollar_cov = (dollar_eligible / dollar_total) if dollar_total > 0 else ZERO

    dq = {
        "codes_with_gaps": sum(1 for m in per_code if "has_gaps" in m["data_quality_flags"]),
        "codes_all_zero": sum(1 for m in per_code if "all_zero" in m["data_quality_flags"]),
        "codes_single_spike": sum(1 for m in per_code if "single_spike" in m["data_quality_flags"]),
        "codes_negative_months": sum(
            1 for m in per_code if "negative_or_credit_months" in m["data_quality_flags"]
        ),
        "codes_source_contaminated": sum(
            1 for m in per_code if "source_contamination" in m["data_quality_flags"]
        ),
        "codes_short_history": sum(
            1 for m in per_code if "short_history" in m["data_quality_flags"]
        ),
    }

    # --- Semantic safety. ------------------------------------------------------------------------
    semantic = _resolve_semantic_gate(db_path, gate_mode, semantic_gate_fn)
    catalog_versions = _semantic_catalog_versions()
    parity_gate = _gate_by_name(semantic, GATE_PROJECTION_PARITY)
    double_count_gate = _gate_by_name(semantic, GATE_DOUBLE_COUNT)
    projection_parity_summary = {
        "gate": parity_gate,
        "known_limitations": list(PROJECTION_PARITY_KNOWN_LIMITS),
    }
    double_count_risk_summary = {
        "gate": double_count_gate,
        "rule": "Evidence in the same independence group counts once; the same CostEntries trend "
        "surfacing across slices is never weighted multiple times.",
    }

    semantic_not_available = semantic.get("status") == "not_available"
    semantic_errors = int(semantic.get("error_count", 0) or 0)
    semantic_hard_fail = semantic_not_available or semantic_errors > 0

    # --- Decision. -------------------------------------------------------------------------------
    blockers: list[str] = []
    warnings: list[str] = []
    if codes_total == 0 or codes_with_any == 0:
        blockers.append("no_completed_monthly_actuals: nothing to model")
    if semantic_not_available:
        blockers.append(f"semantic_gates_not_available: {semantic.get('reason')}")
    elif semantic_errors > 0:
        blockers.append(f"semantic_gate_errors: {semantic_errors} blocking finding(s) across gates")
    for g in semantic.get("per_gate", []):
        if int(g.get("warning_count", 0) or 0) > 0:
            warnings.append(f"gate {g.get('gate')}: {g.get('warning_count')} warning(s)")
    if not semantic_not_available and parity_gate is not None:
        warnings.extend(PROJECTION_PARITY_KNOWN_LIMITS)
    if dq["codes_single_spike"]:
        warnings.append(
            f"{dq['codes_single_spike']} single-spike code(s) excluded from eligibility"
        )
    if dq["codes_short_history"]:
        warnings.append(
            f"{dq['codes_short_history']} code(s) below {MIN_MONTHS_CANDIDATE}-month floor"
        )

    if codes_total == 0 or codes_with_any == 0 or semantic_hard_fail:
        decision = DECISION_NOT_READY
    elif code_cov >= READY_CODE_COVERAGE and dollar_cov >= READY_DOLLAR_COVERAGE:
        decision = DECISION_READY
    elif code_cov >= INSUFFICIENT_FLOOR or dollar_cov >= INSUFFICIENT_FLOOR:
        decision = DECISION_INSUFFICIENT
    else:
        decision = DECISION_NOT_READY
    status = {
        DECISION_READY: "ready",
        DECISION_INSUFFICIENT: "insufficient",
        DECISION_NOT_READY: "not_ready",
    }[decision]

    public_per_code = [{k: v for k, v in m.items() if not k.startswith("_")} for m in per_code]

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "status": status,
        "decision": decision,
        "context_package": str(context_package),
        "db_path": str(db_path),
        "work_root": str(work_root),
        "semantic_catalog_version": catalog_versions,
        "actuals_basis_used": {
            "time_series_training_axis": "forecast_monthly_actuals_by_budget_code "
            "(CostEntries accounting truth)",
            "cumulative_actual_basis": "costentries_monthly_to_date "
            "(precedence #1: forecast_monthly_actuals_by_budget_code)",
            "db_semantic_cumulative_basis": "job_to_date_costs "
            "(precedence #2; primary when actual_cost is null)",
        },
        "actuals_basis_caveats": [
            "actual_cost is 100% null on the live copy; never used as a basis.",
            "CostEntries monthly actuals are the periodization axis, kept distinct from "
            "invoice/progress, payment/cash-flow, and cumulative-budget facts (never summed).",
        ],
        "erp_basis_handling": "explicit_sidecar: erp_direct_costs / erp_job_to_date_costs are "
        "compare-only, never substituted for or summed with CostEntries / job_to_date_costs.",
        "budget_column_role_policy": "Terminal/calculated columns (projected_costs, EAC, projected "
        "over/under, revised/projected budget) are reference-only; projected_costs is used solely as "
        "a coverage-denominator scale, never as an additive model feature.",
        "dynamic_budget_column_policy": "Unmapped numeric budget-view columns are review_required, "
        "never auto-eligible as model features (enforced by the budget-dynamic-columns gate).",
        "forecast_gate_summary": semantic,
        "projection_parity_summary": projection_parity_summary,
        "double_count_risk_summary": double_count_risk_summary,
        "readiness_blockers": blockers,
        "readiness_warnings": sorted(set(warnings)),
        "statsforecast_candidate_code_count": codes_eligible,
        "statsforecast_candidate_dollar_coverage": _frac(dollar_eligible, dollar_total),
        "fallback_to_existing_ensemble_count": codes_total - codes_eligible,
        "inputs": {
            "monthly_actuals_path": str(monthly_path),
            "monthly_actuals_sha256": sha256_file(monthly_path),
            "monthly_actuals_row_count": monthly_row_count,
            "budget_codes_path": str(budget_codes_path),
            "budget_codes_sha256": sha256_file(budget_codes_path),
            "completed_bucket": COMPLETED_BUCKET,
            "to_date_bucket": TO_DATE_BUCKET,
            "future_bucket": FUTURE_BUCKET,
            "actual_source_required": ACTUAL_SOURCE,
        },
        "thresholds": {
            "min_months_candidate": MIN_MONTHS_CANDIDATE,
            "min_months_reliable": MIN_MONTHS_RELIABLE,
            "min_months_seasonal": MIN_MONTHS_SEASONAL,
            "ready_code_coverage": str(READY_CODE_COVERAGE),
            "ready_dollar_coverage": str(READY_DOLLAR_COVERAGE),
            "insufficient_floor": str(INSUFFICIENT_FLOOR),
        },
        "aggregate": {
            "codes_total": codes_total,
            "codes_with_any_actuals": codes_with_any,
            "codes_ge3": codes_ge3,
            "codes_ge6": codes_ge6,
            "codes_ge12": codes_ge12,
            "codes_eligible": codes_eligible,
            "codes_falling_back_to_ensemble": codes_total - codes_eligible,
            "completed_month_histogram": histogram,
        },
        "coverage": {
            "code_coverage_fraction": _frac(Decimal(codes_eligible), Decimal(codes_total or 1))
            if codes_total
            else "0.0000",
            "dollar_coverage_fraction": _frac(dollar_eligible, dollar_total),
            "dollar_eligible": money_str(dollar_eligible),
            "dollar_total": money_str(dollar_total),
        },
        "data_quality": dq,
        "per_code": public_per_code,
        "deferral": {
            "statsforecast_dependency_added": False,
            "forecast_core_edited": False,
            "schema_or_migrator_changed": False,
            "hb_forecasting_layer_edited": False,
            "live_root_written": False,
            "note": "Evidence-only. Wiring statsforecast as a 7th estimator into "
            "estimators_uncapped.INDEPENDENT_METHODS + reconcile_final is DEFERRED to a later PR, "
            "gated on this report showing READY.",
        },
    }
    report_path = _write_json_deterministic(out_root / READINESS_REPORT_NAME, report)
    return {**report, "report_path": str(report_path)}
