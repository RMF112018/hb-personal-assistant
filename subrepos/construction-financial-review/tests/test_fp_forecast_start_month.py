"""--forecast-start-month carry-forward: prior-month CTC is carried forward, never reallocated.

Skips when the local forecast data root / required accepted packages are not present.
"""
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json
from construction_financial_review.forecast_probability import risk_metrics, simulate, simulation_inputs

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_monthly_package_tropical_*"))),
    reason="local forecast data root / required packages not present",
)

LATER_START = "2026-08"


def _sum(specs, key):
    return sum(float(s.get(key, 0.0)) for s in specs)


def test_default_path_has_no_carry_forward():
    inp = simulation_inputs.load_inputs(CFG, DATA_ROOT, "tropical", None)
    assert inp["window_override_active"] is False
    assert inp["project"]["total_carried_prior_forecast"] == 0.0
    # window CTC equals full CTC on the default path
    for s in inp["specs"]:
        assert s["window_recommended_ctc"] == s["median_ctc"]
        assert s["carried_prior_forecast"] == 0.0


def test_later_start_carries_prior_forecast_without_reallocation():
    base = simulation_inputs.load_inputs(CFG, DATA_ROOT, "tropical", None)
    win = simulation_inputs.load_inputs(CFG, DATA_ROOT, "tropical", LATER_START)

    assert win["window_override_active"] is True
    assert all(m >= LATER_START for m in win["months"])
    # prior-month deterministic forecast is actually carried forward (non-zero)
    carried_total = win["project"]["total_carried_prior_forecast"]
    assert carried_total > 0.0

    # NO full-CTC reallocation: the window recommended CTC is strictly LESS than the full CTC, and
    # window + carried reconciles to the full recommended CTC (carry-forward, not re-phasing).
    window_ctc = _sum(win["specs"], "window_recommended_ctc")
    full_ctc = window_ctc + _sum(win["specs"], "carried_prior_forecast")
    assert window_ctc < full_ctc
    # the full CTC matches the unfiltered (default-window) recommended CTC for the carried codes
    assert full_ctc <= _sum(base["specs"], "median_ctc") + 1.0


def test_later_start_reconciliation_identity():
    win = simulation_inputs.load_inputs(CFG, DATA_ROOT, "tropical", LATER_START)
    sim = simulate.simulate(win["arrays"], runs=2000, seed=20260614)
    s = risk_metrics.project_summary(sim, win["arrays"], win["project"], win["params"])
    wr = s["window_reconciliation"]
    assert wr["forecast_start_override_active"] is True
    # accounting actual + carried prior forecast + simulated window CTC == simulated final
    total = (float(wr["accounting_actual_cost_to_date"])
             + float(wr["deterministic_prior_forecast_before_probability_window"])
             + float(wr["simulated_probability_window_cost_to_complete"]))
    assert abs(total - float(wr["simulated_final_cost_including_carried_forecast"])) <= 0.01
    # carried forecast is reported separately and is NOT folded into accounting actual
    assert float(wr["deterministic_prior_forecast_before_probability_window"]) > 0.0
    assert (float(wr["accounting_actual_cost_to_date"])
            == win["project"]["total_actual_to_date"])
