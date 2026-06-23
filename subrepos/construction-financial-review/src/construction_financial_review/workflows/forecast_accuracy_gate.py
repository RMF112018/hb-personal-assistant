"""Production-forecast accuracy/trust gate (verdict over an existing intelligence package).

Reads the reconciled as-of backtest (`reconciled_forecast_backtest.json`, emitted by every
forecast-intelligence run) plus the per-method backtest, applies deterministic thresholds, and emits
a go/no-go verdict on whether the production reconciled forecast is accurate + unbiased enough to
trust. Evidence only — reads an existing package, writes only its own report under an explicit work
root. Fail-closed preflight before any output; mirrors the prior CFR gate workflows.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from ..common.io import read_json
from ..common.money import dec
from ..common.project_eligibility import eligible_projects, is_project_eligible

SUPPORTED_PROJECT_KEY = "tropical"
REPORT_SCHEMA_VERSION = 1
GATE_SUBDIR = "forecast_accuracy_gate"
GATE_REPORT_NAME = "forecast_accuracy_gate_report.json"
RECONCILED_BACKTEST_NAME = "reconciled_forecast_backtest.json"

# Tunable verdict thresholds (recorded in the report).
MIN_COHORT = 8
MAPE_PASS = Decimal("0.15")
MAPE_FAIL = Decimal("0.30")
BIAS_ABS_PASS = Decimal("0.10")
COVERAGE_PASS = Decimal("0.90")
# Recalibration is "recommended" only if it cuts MAPE by at least this much without losing coverage.
RECAL_MIN_MAPE_IMPROVEMENT = Decimal("0.05")
RECAL_COVERAGE_TOL = Decimal("0.05")

VERDICT_PASS = "pass"
VERDICT_REVIEW = "review_recommended"
VERDICT_NOT_READY = "not_ready"
VERDICT_INSUFFICIENT = "insufficient_evidence"

# Controlled-safety guard (mirrors the generators' live Synology root). Monkeypatched in tests.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class ForecastAccuracyGateError(RuntimeError):
    """Raised when the gate is rejected by a preflight safety check (fail closed)."""


def _is_under(path: Path, root: Path) -> bool:
    rp = path.expanduser().resolve(strict=False)
    rr = root.expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _write_json_deterministic(path: Path, obj: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _resolve_package(package: Optional[Path], data_root: Optional[Path], project_key: str) -> Path:
    if package:
        package = Path(package)
        if not package.exists() or not package.is_dir():
            raise ForecastAccuracyGateError(f"package not found or not a directory: {package}")
        return package
    if not data_root:
        raise ForecastAccuracyGateError("either package or data_root is required")
    data_root = Path(data_root)
    if not data_root.exists() or not data_root.is_dir():
        raise ForecastAccuracyGateError(f"data_root not found or not a directory: {data_root}")
    matches = sorted(data_root.glob(f"forecast_accuracy_next_package_{project_key}_*"))
    if not matches:
        raise ForecastAccuracyGateError(
            f"no forecast_accuracy_next_package_{project_key}_* found under data_root: {data_root}"
        )
    return matches[-1]


def _decide(
    cohort_size: int, mape: Optional[Decimal], bias: Optional[Decimal], coverage: Optional[Decimal]
) -> tuple[str, list[str]]:
    notes: list[str] = []
    if cohort_size < MIN_COHORT or mape is None:
        notes.append(
            f"near-complete cohort {cohort_size} < {MIN_COHORT}; accuracy cannot be certified "
            "from this project's own history yet"
        )
        return VERDICT_INSUFFICIENT, notes
    abs_bias = abs(bias) if bias is not None else None
    if (
        mape <= MAPE_PASS
        and abs_bias is not None
        and abs_bias <= BIAS_ABS_PASS
        and coverage is not None
        and coverage >= COVERAGE_PASS
    ):
        return VERDICT_PASS, notes
    if mape > MAPE_FAIL:
        notes.append(f"reconciled MAPE {mape} exceeds fail threshold {MAPE_FAIL}")
        return VERDICT_NOT_READY, notes
    if abs_bias is not None and abs_bias > BIAS_ABS_PASS:
        notes.append(
            f"reconciled bias {bias} exceeds +/-{BIAS_ABS_PASS} (systematic over/under-forecast)"
        )
    if coverage is not None and coverage < COVERAGE_PASS:
        notes.append(f"worst-case ceiling coverage {coverage} below {COVERAGE_PASS}")
    return VERDICT_REVIEW, notes


def run_forecast_accuracy_gate(
    *,
    package: Optional[Path] = None,
    data_root: Optional[Path] = None,
    work_root: Path,
    project_key: str = SUPPORTED_PROJECT_KEY,
) -> dict[str, Any]:
    """Produce a deterministic accuracy/trust verdict over an existing intelligence package.

    Preflight fails closed BEFORE any output on: non-tropical project; missing package/data_root;
    missing reconciled-backtest artifact; missing work root or one under the live root; or a
    non-empty gate output dir. rc mapping is in the CLI: pass -> 0, otherwise -> 1, refusal -> 3.
    """
    if not is_project_eligible(project_key):
        raise ForecastAccuracyGateError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    if not work_root:
        raise ForecastAccuracyGateError("work_root is required (explicit; no implicit output root)")
    work_root = Path(work_root)
    if _is_under(work_root, _LIVE_ROOT):
        raise ForecastAccuracyGateError(
            f"work_root is at/under the live forecast root (refused): {work_root}"
        )
    out_root = work_root / GATE_SUBDIR
    if out_root.exists() and any(out_root.iterdir()):
        raise ForecastAccuracyGateError(
            f"gate work root already contains output (refusing to reuse): {out_root}"
        )

    pkg = _resolve_package(package, data_root, project_key)
    rb_path = pkg / RECONCILED_BACKTEST_NAME
    if not rb_path.exists():
        raise ForecastAccuracyGateError(
            f"required artifact missing (run forecast-intelligence first): {rb_path}"
        )
    rb = read_json(rb_path)

    cohort_size = int(rb.get("cohort_size") or 0)
    mape = dec(rb.get("reconciled_final_mape"))
    bias = dec(rb.get("reconciled_final_mean_bias"))
    coverage = dec(rb.get("worst_credible_coverage_rate"))
    verdict, notes = _decide(cohort_size, mape, bias, coverage)

    # Completion-stage recalibration effect (what flipping the production p75 stage-gate ON would buy).
    # The verdict above stays on the baseline (production, flag-off) metrics.
    recal = rb.get("recalibrated") or {}
    mape_impr = dec(recal.get("mape_improvement"))
    bias_impr = dec(recal.get("bias_abs_improvement"))
    recal_cov = dec(recal.get("recalibrated_worst_credible_coverage_rate"))
    recalibration_recommended = bool(
        mape_impr is not None
        and mape_impr >= RECAL_MIN_MAPE_IMPROVEMENT
        and bias_impr is not None
        and bias_impr >= Decimal("0")
        and (recal_cov is None or coverage is None or recal_cov >= coverage - RECAL_COVERAGE_TOL)
    )

    # Reliability-damping effect: incremental value of the new lever OVER the p75-only recalibration
    # (current production). Advisory; the verdict stays on the baseline (production) metrics.
    damped = rb.get("damped") or {}
    damp_incr_mape = dec(damped.get("incremental_mape_improvement_over_recalibrated"))
    damp_incr_bias = dec(damped.get("incremental_bias_abs_improvement_over_recalibrated"))
    damp_cov = dec(damped.get("damped_worst_credible_coverage_rate"))
    reliability_damping_recommended = bool(
        damp_incr_mape is not None
        and damp_incr_mape >= RECAL_MIN_MAPE_IMPROVEMENT
        and damp_incr_bias is not None
        and damp_incr_bias >= Decimal("0")
        and (damp_cov is None or recal_cov is None or damp_cov >= recal_cov - RECAL_COVERAGE_TOL)
    )

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "verdict": verdict,
        "package_scored": str(pkg),
        "method_coverage": rb.get("method_coverage"),
        "thresholds": {
            "min_cohort": MIN_COHORT,
            "mape_pass": str(MAPE_PASS),
            "mape_fail": str(MAPE_FAIL),
            "bias_abs_pass": str(BIAS_ABS_PASS),
            "coverage_pass": str(COVERAGE_PASS),
        },
        "metrics": {
            "cohort_size": cohort_size,
            "observation_count": rb.get("observation_count"),
            "reconciled_final_mape": rb.get("reconciled_final_mape"),
            "reconciled_final_mean_bias": rb.get("reconciled_final_mean_bias"),
            "worst_credible_coverage_rate": rb.get("worst_credible_coverage_rate"),
            "best_single_method": rb.get("best_single_method"),
            "best_single_method_mape": rb.get("best_single_method_mape"),
            "blend_minus_best_method_delta": rb.get("blend_minus_best_method_delta"),
            "naive_erp_mape": rb.get("naive_erp_mape"),
            "reconciled_minus_naive_delta": rb.get("reconciled_minus_naive_delta"),
            "per_target_mape": rb.get("per_target_mape"),
        },
        "recalibration_effect": {
            "production_flag_default": "off",
            "recalibration_recommended": recalibration_recommended,
            "baseline_mape": rb.get("reconciled_final_mape"),
            "recalibrated_mape": recal.get("recalibrated_final_mape"),
            "mape_improvement": recal.get("mape_improvement"),
            "baseline_mean_bias": rb.get("reconciled_final_mean_bias"),
            "recalibrated_mean_bias": recal.get("recalibrated_final_mean_bias"),
            "bias_abs_improvement": recal.get("bias_abs_improvement"),
            "baseline_coverage": rb.get("worst_credible_coverage_rate"),
            "recalibrated_coverage": recal.get("recalibrated_worst_credible_coverage_rate"),
            "recalibrated_per_target_mape": recal.get("recalibrated_per_target_mape"),
            "note": "Effect of flipping the completion-stage p75 stage-gate ON; the verdict above is on "
            "the baseline (production) metrics. recalibration_recommended is advisory.",
        },
        "reliability_damping_effect": {
            "production_flag_default": "off",
            "reliability_damping_recommended": reliability_damping_recommended,
            "recalibrated_mape": recal.get("recalibrated_final_mape"),
            "damped_mape": damped.get("damped_final_mape"),
            "incremental_mape_improvement_over_recalibrated": damped.get(
                "incremental_mape_improvement_over_recalibrated"
            ),
            "recalibrated_mean_bias": recal.get("recalibrated_final_mean_bias"),
            "damped_mean_bias": damped.get("damped_final_mean_bias"),
            "incremental_bias_abs_improvement_over_recalibrated": damped.get(
                "incremental_bias_abs_improvement_over_recalibrated"
            ),
            "total_mape_improvement_over_baseline": damped.get(
                "total_mape_improvement_over_baseline"
            ),
            "damped_coverage": damped.get("damped_worst_credible_coverage_rate"),
            "damped_selection": damped.get("damped_selection"),
            "damped_per_target_mape": damped.get("damped_per_target_mape"),
            "note": "Incremental effect of reliability damping (owner/trend) OVER the p75-only "
            "recalibration that is in production. Advisory; verdict stays on baseline.",
        },
        "verdict_notes": notes,
        "reconstruction_fidelity_caveats": rb.get("reconstruction_fidelity_caveats"),
        "methodology": rb.get("methodology"),
    }
    report_path = _write_json_deterministic(out_root / GATE_REPORT_NAME, report)
    return {**report, "report_path": str(report_path)}
