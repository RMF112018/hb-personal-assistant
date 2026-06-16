"""Reconciliation ensemble: weighting, floor, divergence, ERP-only fallback."""
from construction_financial_review.forecast_accuracy import reconcile as rc


def _est(method, source, eac, reliability="medium", applicable=True):
    return {"method": method, "source": source, "applicable": applicable, "eac": eac,
            "reliability": reliability}


def test_reconcile_weighted_and_floored():
    ests = [
        _est("baseline_projected", "erp", "120.00"),
        _est("owner_percent_complete", "independent", "200.00", "medium"),
        _est("commitment_floor", "independent", "300.00", "medium"),
    ]
    out = rc.reconcile("k", "tropical", ests, "100.00")
    assert out["n_independent_models"] == 2
    assert out["model_eac_low"] == "200.00" and out["model_eac_high"] == "300.00"
    # equal weights -> mean 250
    assert out["model_recommended_projected_cost"] == "250.00"
    assert out["model_recommended_floored_to_actuals"] is False
    assert out["requires_human_acceptance"] is True


def test_reconcile_floors_to_actuals():
    ests = [_est("commitment_floor", "independent", "80.00")]
    out = rc.reconcile("k", "tropical", ests, "150.00")
    assert out["model_recommended_projected_cost"] == "150.00"   # floored up to actuals
    assert out["model_recommended_floored_to_actuals"] is True


def test_reconcile_erp_only_fallback():
    ests = [_est("baseline_projected", "erp", "120.00")]
    out = rc.reconcile("k", "tropical", ests, "100.00")
    assert out["n_independent_models"] == 0
    assert out["reconciliation_basis"] == "erp_baseline_only"
    assert out["model_recommended_projected_cost"] == "120.00"


def test_reconcile_calibration_weights_shift_point():
    ests = [
        _est("owner_percent_complete", "independent", "200.00", "medium"),
        _est("commitment_floor", "independent", "300.00", "medium"),
    ]
    # heavily upweight commitment_floor -> point moves toward 300
    out = rc.reconcile("k", "tropical", ests, "100.00",
                       calibration={"commitment_floor": "3.0", "owner_percent_complete": "0.5"})
    assert float(out["model_recommended_projected_cost"]) > 260


def test_divergence_zero_when_models_agree():
    ests = [
        _est("owner_percent_complete", "independent", "200.00"),
        _est("commitment_floor", "independent", "200.00"),
    ]
    out = rc.reconcile("k", "tropical", ests, "100.00")
    assert out["model_divergence"] == "0.0000"
