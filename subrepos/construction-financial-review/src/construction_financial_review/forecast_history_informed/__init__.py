"""Historical-forecast-assumption evidence slice.

Additive, deterministic, read-only. Mines prior cash-flow and GC/GR forecast assumptions, weighs each
against CostEntries/Sage actual-cost truth (plus schedule / invoice / owner / current-model evidence),
and emits ADVISORY recommendations, confidence/uncertainty shifts, and monthly-shape signals.

Historical forecasts are prior-assumption evidence — never actuals, never caps. CostEntries/Sage
incurred cost is the primary reality check. Nothing here mutates source data or accepted packages.
"""
