"""Probabilistic VALIDATION layer for the accepted deterministic forecast.

Monte Carlo / scenario simulation that stress-tests the accepted forecast_intelligence final-cost
package and the accepted forecast_monthly time-phasing. It does NOT replace the deterministic
forecast; it quantifies the probability, range and timing of outcomes (P10..P95 final cost, per-code
overrun probabilities, downside drivers, monthly risk, sensitivity, calibration).

Guardrails (enforced in code):
- Actual cost to date is the ONLY hard lower bound for any simulated final cost.
- Simulated final costs are NEVER capped at ERP projected / revised budget / committed / owner SOV /
  Procore pay-app / prior model output. Upside is uncapped.
- The local LLM may only produce advisory text; it never produces a numeric simulation result.
- Deterministic: same seed + same frozen stamp => byte-identical quantitative core.
- Read-only: no source package / Excel / SQLite / external-system mutation.

Engine: numpy vectorized Monte Carlo with scipy.stats calibration. Money is serialized as Decimal
strings at the JSON boundary; simulation internals are float64.
"""
