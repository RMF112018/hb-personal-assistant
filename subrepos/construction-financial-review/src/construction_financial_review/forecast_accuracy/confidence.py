"""Calibrated 0-1 forecast confidence from signal density, model agreement, recency, and volatility.

Richer than the existing 4-level label. Deterministic, Decimal. Confidence describes how trustworthy
the *model-reconciled* forecast is; it never changes a number.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.dates import normalize_date
from ..common.money import dec

# component weights (sum to 1)
W_DENSITY = Decimal("0.30")
W_AGREEMENT = Decimal("0.30")
W_RECENCY = Decimal("0.20")
W_STABILITY = Decimal("0.20")


def _clamp01(x: Decimal) -> Decimal:
    if x < 0:
        return Decimal("0")
    if x > 1:
        return Decimal("1")
    return x


def _months_apart(a: Optional[str], b: Optional[str]) -> Optional[int]:
    a, b = normalize_date(a), normalize_date(b)
    if not a or not b:
        return None
    ay, am = int(a[:4]), int(a[5:7])
    by, bm = int(b[:4]), int(b[5:7])
    return abs((by - ay) * 12 + (bm - am))


def band(score: Decimal) -> str:
    if score >= Decimal("0.85"):
        return "very_high"
    if score >= Decimal("0.70"):
        return "high"
    if score >= Decimal("0.50"):
        return "medium"
    if score >= Decimal("0.30"):
        return "low"
    return "very_low"


def score_confidence(bundle: dict, reconciliation: dict) -> OrderedDict:
    """Return a confidence row with score, band, components, and ranked drivers."""
    # density: independent evidence families present (0..5) -> 0..1
    density = _clamp01(Decimal(bundle.get("evidence_depth") or 0) / Decimal("5"))

    # agreement: 1 - normalized divergence; neutral 0.5 when fewer than 2 independent models
    n_ind = reconciliation.get("n_independent_models") or 0
    divergence = dec(reconciliation.get("model_divergence")) or Decimal("0")
    if n_ind >= 2:
        agreement = _clamp01(Decimal("1") - (divergence if divergence < 1 else Decimal("1")))
    else:
        agreement = Decimal("0.5")

    # recency: latest actual month vs data date (0 months -> 1.0, decays ~0.1/month)
    gap = _months_apart(bundle.get("latest_actual_month"), bundle.get("data_date"))
    if gap is None:
        recency = Decimal("0.3")
    else:
        recency = _clamp01(Decimal("1") - Decimal(gap) * Decimal("0.1"))

    # stability: inverse of burn volatility (cov 0 -> 1, cov >= 1 -> 0)
    cov = dec(bundle.get("burn_volatility_cov"))
    if cov is None:
        stability = Decimal("0.5")
    else:
        stability = _clamp01(Decimal("1") - cov)

    score = (W_DENSITY * density + W_AGREEMENT * agreement
             + W_RECENCY * recency + W_STABILITY * stability)
    score = _clamp01(score).quantize(Decimal("0.01"))

    components = OrderedDict([
        ("signal_density", str(density.quantize(Decimal("0.01")))),
        ("model_agreement", str(agreement.quantize(Decimal("0.01")))),
        ("data_recency", str(recency.quantize(Decimal("0.01")))),
        ("burn_stability", str(stability.quantize(Decimal("0.01")))),
    ])
    # drivers: rank components by contribution (weight x value), label up/down
    weighted = [
        ("signal_density", W_DENSITY * density),
        ("model_agreement", W_AGREEMENT * agreement),
        ("data_recency", W_RECENCY * recency),
        ("burn_stability", W_STABILITY * stability),
    ]
    weighted.sort(key=lambda kv: kv[1], reverse=True)
    drivers = [k for k, _ in weighted]

    return OrderedDict([
        ("project_key", bundle.get("project_key")),
        ("budget_code_key", bundle.get("budget_code_key")),
        ("calibrated_confidence", str(score)),
        ("confidence_band", band(score)),
        ("n_independent_models", n_ind),
        ("evidence_depth", bundle.get("evidence_depth")),
        ("components", components),
        ("confidence_drivers", drivers),
        ("notes", None),
    ])
