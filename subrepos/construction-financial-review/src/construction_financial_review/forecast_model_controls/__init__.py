"""Operator forecast-model controls: accepted, auditable per-code forecast configuration.

A forecast-model control is one operator decision that configures the forecast model for one canonical
budget code: its forecast **window** (start/end), **model shape** (linear / S-curve / bell / manual),
optional **value constraint** (equal-to / cap / floor / explicit final / explicit remaining against a
selected reference), and optional **manual** total or monthly inputs. Final-value pinning is one
subsection of this contract, not the whole thing.

Hard invariants mirror ``forecast_controls``: CostEntries actuals are the only floor, a control applies
ONLY when human-accepted, nothing is ever a hidden cap (a binding ``not_to_exceed`` is disclosed as an
operator constraint), and the resolved window / reference / shape / floor / monthly reconciliation can be
audited independently. Probability is degraded-not-fatal (anchor when a prior accepted row exists, else a
deterministic provisional plausibility assessment). See ``docs/architecture/forecast_model_controls.md``.
"""
