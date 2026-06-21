"""Tests for the production-forecast accuracy/trust gate verdict + preflight."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from construction_financial_review.workflows import forecast_accuracy_gate as gate


def _pkg(
    tmp_path: Path, rb: dict | None, name="forecast_accuracy_next_package_tropical_20260101_000000"
):
    p = tmp_path / name
    p.mkdir(parents=True)
    if rb is not None:
        (p / gate.RECONCILED_BACKTEST_NAME).write_text(json.dumps(rb), encoding="utf-8")
    return p


def _rb(cohort, mape, bias, coverage):
    return {
        "cohort_size": cohort,
        "observation_count": cohort * 3,
        "reconciled_final_mape": mape,
        "reconciled_final_mean_bias": bias,
        "worst_credible_coverage_rate": coverage,
        "best_single_method": "commitment_exposure_eac",
        "best_single_method_mape": "0.0700",
        "blend_minus_best_method_delta": "0.0500",
        "naive_erp_mape": "0.0500",
        "reconciled_minus_naive_delta": "0.0700",
        "per_target_mape": {"0.40": "0.10"},
        "recalibrated": {
            "stage_gate_lo": "0.5",
            "stage_gate_hi": "0.8",
            "recalibrated_final_mape": "0.2000",
            "recalibrated_final_mean_bias": "0.1500",
            "recalibrated_worst_credible_coverage_rate": coverage,
            "mape_improvement": "0.2125",
            "bias_abs_improvement": "0.1796",
            "recalibrated_per_target_mape": {"0.40": "0.30"},
        },
        "methodology": "x",
        "reconstruction_fidelity_caveats": ["c"],
    }


def _run(tmp_path, pkg, **kw):
    return gate.run_forecast_accuracy_gate(package=pkg, work_root=tmp_path / "wr", **kw)


def test_recalibration_effect_block(tmp_path):
    # not_ready on baseline, but the recalibration block reports the improvement + recommends it.
    pkg = _pkg(tmp_path, _rb(12, "0.4125", "0.3296", "0.8966"))
    r = _run(tmp_path, pkg)
    assert (
        r["verdict"] == gate.VERDICT_NOT_READY
    )  # verdict stays on baseline (production, flag-off)
    eff = r["recalibration_effect"]
    assert eff["production_flag_default"] == "off"
    assert (
        eff["recalibration_recommended"] is True
    )  # MAPE improves 0.2125, bias improves, coverage held
    assert eff["baseline_mape"] == "0.4125" and eff["recalibrated_mape"] == "0.2000"


def test_verdict_pass(tmp_path):
    pkg = _pkg(tmp_path, _rb(12, "0.1000", "0.0500", "0.9500"))
    r = _run(tmp_path, pkg)
    assert r["verdict"] == gate.VERDICT_PASS
    assert Path(r["report_path"]).is_file()


def test_verdict_insufficient_small_cohort(tmp_path):
    pkg = _pkg(tmp_path, _rb(3, "0.1000", "0.0500", "0.9500"))
    r = _run(tmp_path, pkg)
    assert r["verdict"] == gate.VERDICT_INSUFFICIENT


def test_verdict_not_ready_high_mape(tmp_path):
    pkg = _pkg(tmp_path, _rb(12, "0.4125", "0.3296", "0.8966"))
    r = _run(tmp_path, pkg)
    assert r["verdict"] == gate.VERDICT_NOT_READY


def test_verdict_review_high_bias(tmp_path):
    # mape between pass and fail, bias over tolerance -> review.
    pkg = _pkg(tmp_path, _rb(12, "0.2000", "0.1800", "0.9500"))
    r = _run(tmp_path, pkg)
    assert r["verdict"] == gate.VERDICT_REVIEW
    assert any("bias" in n for n in r["verdict_notes"])


def test_refuse_non_tropical(tmp_path):
    pkg = _pkg(tmp_path, _rb(12, "0.10", "0.05", "0.95"))
    with pytest.raises(gate.ForecastAccuracyGateError, match="project_key"):
        _run(tmp_path, pkg, project_key="other")


def test_refuse_missing_artifact(tmp_path):
    pkg = _pkg(tmp_path, None)  # package exists but no reconciled_forecast_backtest.json
    with pytest.raises(gate.ForecastAccuracyGateError, match="required artifact missing"):
        _run(tmp_path, pkg)


def test_refuse_work_root_under_live_root(tmp_path, monkeypatch):
    live = tmp_path / "live"
    live.mkdir()
    monkeypatch.setattr(gate, "_LIVE_ROOT", live)
    pkg = _pkg(tmp_path, _rb(12, "0.10", "0.05", "0.95"))
    with pytest.raises(gate.ForecastAccuracyGateError, match="live forecast root"):
        gate.run_forecast_accuracy_gate(package=pkg, work_root=live / "wr")


def test_discover_latest_from_data_root(tmp_path):
    _pkg(
        tmp_path,
        _rb(12, "0.10", "0.05", "0.95"),
        name="forecast_accuracy_next_package_tropical_20251201_000000",
    )
    _pkg(
        tmp_path,
        _rb(12, "0.10", "0.05", "0.95"),
        name="forecast_accuracy_next_package_tropical_20260101_000000",
    )
    r = gate.run_forecast_accuracy_gate(package=None, data_root=tmp_path, work_root=tmp_path / "wr")
    assert r["package_scored"].endswith("20260101_000000")  # latest by sort
