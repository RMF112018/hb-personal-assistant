"""Forecast cost-frequency / billing-cadence evidence layer.

Deterministic, additive slice that classifies each canonical budget code's cost-incurrence cadence
(weekly / twice-monthly / monthly / irregular / one-time / inactive / insufficient) from real
CostEntries (transaction dates + per-month entry counts), recognizes the configured weekly internal
staffing codes, computes weekday-normalized staffing daily rates from the latest COMPLETE actual month,
revalidates cadence against the most recent actuals, and emits advisory monthly phasing. CostEntries
remain accounting truth; cadence is timing/shape evidence only — never an actual, never a cap, never a
change to any accepted final cost. The pure phasing functions here are also imported by ``forecast_monthly``
so a single cadence logic drives both the standalone evidence package and the monthly integration.
"""
