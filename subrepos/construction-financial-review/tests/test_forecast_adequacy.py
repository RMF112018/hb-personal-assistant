"""Forecast adequacy classification (ERP vs independent model, materiality-gated)."""
from construction_financial_review.forecast_accuracy import forecast_adequacy as fa


def _recon(erp, model, n=2):
    return {"budget_code_key": "k", "erp_projected_costs": erp,
            "model_recommended_projected_cost": model, "n_independent_models": n}


def test_adequate_when_within_materiality():
    out = fa.assess_adequacy(_recon("100000.00", "105000.00"), "tropical")
    assert out["forecast_adequacy"] == "adequate"      # 5% < 10% gate


def test_likely_low_when_model_materially_above_erp():
    out = fa.assess_adequacy(_recon("100000.00", "200000.00"), "tropical")
    assert out["forecast_adequacy"] == "likely_low"
    assert out["adequacy_severity"] in ("medium", "high", "critical")
    assert out["requires_human_review"] is True


def test_likely_high_when_model_materially_below_erp():
    out = fa.assess_adequacy(_recon("600000.00", "300000.00"), "tropical")
    assert out["forecast_adequacy"] == "likely_high"
    assert out["adequacy_severity"] == "critical"      # 300k abs & 50% pct


def test_indeterminate_without_independent_models():
    out = fa.assess_adequacy(_recon("100000.00", "100000.00", n=0), "tropical")
    assert out["forecast_adequacy"] == "indeterminate"
    assert out["requires_human_review"] is False
