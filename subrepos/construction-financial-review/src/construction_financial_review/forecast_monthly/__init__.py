"""Forecast monthly — deterministic time-phased month-by-month cost forecast.

Additive over the accepted forecast_intelligence final-cost package. It time-phases each budget code's
recommended / worst-credible cost-to-complete across the remaining forecast months (system current
month -> month containing the latest scheduled finish date), by budget code, owner scope, division,
and project total, and identifies which months carry the projected overrun exposure.

Timing comes from THREE independently-built signals — CostEntries actual-cost trend, subcontractor
invoice/pay-app trend, and schedule remaining-work phasing — blended with reported source weights.
Subcontractor invoice and owner pay-app values are progress/exposure/timing evidence ONLY, never
accounting actuals. Project-level schedule association is context only and never drives a code's
monthly cost. Actual cost to date is the only hard floor; nothing is capped at ERP / budget /
commitment / owner SOV / pay-app / prior output.

The quantitative core is deterministic (frozen stamp + captured as-of date); the optional local-Ollama
narrative layer is advisory, never numeric, and excluded from the byte-identical determinism gate.
Source data, Excel, and SQLite are never mutated (the DB is opened read-only).
"""
