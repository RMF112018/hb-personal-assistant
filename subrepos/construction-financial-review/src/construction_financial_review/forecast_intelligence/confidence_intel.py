"""Calibrated 0-1 confidence for the next-gen forecast, including schedule-association strength.

Reuses the proven ``forecast_accuracy.confidence`` helpers and adds a fifth component: how strongly
this code's remaining-cost estimate is tied to schedule evidence (``schedule_confidence``). Confidence
describes trust in the forecast; it never changes a number.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import dec
from ..forecast_accuracy.confidence import _clamp01, _months_apart, band

W_DENSITY = Decimal("0.25")
W_AGREEMENT = Decimal("0.25")
W_RECENCY = Decimal("0.15")
W_STABILITY = Decimal("0.15")
W_SCHEDULE = Decimal("0.20")


def score(bundle: dict, recommendation: dict) -> OrderedDict:
    density = _clamp01(Decimal(bundle.get("evidence_depth_intel") or 0) / Decimal("6"))

    n_ind = recommendation.get("n_independent_models") or 0
    divergence = dec(recommendation.get("model_divergence")) or Decimal("0")
    if n_ind >= 2:
        agreement = _clamp01(Decimal("1") - (divergence if divergence < 1 else Decimal("1")))
    else:
        agreement = Decimal("0.5")

    gap = _months_apart(bundle.get("latest_actual_month"), bundle.get("data_date"))
    recency = Decimal("0.3") if gap is None else _clamp01(Decimal("1") - Decimal(gap) * Decimal("0.1"))

    cov = dec(bundle.get("cost_volatility_cov"))
    stability = Decimal("0.5") if cov is None else _clamp01(Decimal("1") - cov)

    sched = dec(bundle.get("schedule_confidence")) or Decimal("0")
    schedule_strength = _clamp01(sched)

    raw = (W_DENSITY * density + W_AGREEMENT * agreement + W_RECENCY * recency
           + W_STABILITY * stability + W_SCHEDULE * schedule_strength)
    s = _clamp01(raw).quantize(Decimal("0.01"))

    components = OrderedDict([
        ("signal_density", str(density.quantize(Decimal("0.01")))),
        ("model_agreement", str(agreement.quantize(Decimal("0.01")))),
        ("data_recency", str(recency.quantize(Decimal("0.01")))),
        ("burn_stability", str(stability.quantize(Decimal("0.01")))),
        ("schedule_association_strength", str(schedule_strength.quantize(Decimal("0.01")))),
    ])
    weighted = [
        ("signal_density", W_DENSITY * density),
        ("model_agreement", W_AGREEMENT * agreement),
        ("data_recency", W_RECENCY * recency),
        ("burn_stability", W_STABILITY * stability),
        ("schedule_association_strength", W_SCHEDULE * schedule_strength),
    ]
    weighted.sort(key=lambda kv: kv[1], reverse=True)
    drivers = [k for k, _ in weighted]

    # Confidence specifically in the overrun verdict: gated by evidence breadth + agreement.
    if recommendation.get("overrun_projected"):
        overrun_conf = _clamp01(min(s, (agreement + density) / Decimal("2"))).quantize(Decimal("0.01"))
    else:
        overrun_conf = Decimal("0.00")

    return OrderedDict([
        ("project_key", bundle.get("project_key")),
        ("budget_code_key", bundle.get("budget_code_key")),
        ("calibrated_confidence", str(s)),
        ("confidence_band", band(s)),
        ("overrun_confidence", str(overrun_conf)),
        ("n_independent_models", n_ind),
        ("evidence_depth_intel", bundle.get("evidence_depth_intel")),
        ("evidence_families_present", bundle.get("evidence_families_present")),
        ("components", components),
        ("confidence_drivers", drivers),
    ])
