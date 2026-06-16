"""Forecast intelligence — next-gen anticipated-final-cost projection per budget code.

An additive slice over the proven ``forecast_accuracy`` machinery. It projects the real
anticipated final cost for each canonical budget code and surfaces budget-code-level overruns.

Core principle (Bobby's rule): the only hard lower bound on a forecast is actual-cost-to-date.
Final cost is NEVER capped at ERP projected cost, revised budget, committed cost, owner SOV value,
Procore pay-app value, or prior model output. References are reported for comparison, never used to
clamp. Overrun is defined against current projected cost; separate flags also test revised budget,
committed cost, and owner SOV value.

The quantitative core is deterministic; the optional local-Ollama narrative layer is advisory,
never numeric, and excluded from the byte-identical determinism gate. Source data, Excel, and SQLite
are never mutated (the DB is opened read-only for a schema+counts inventory).
"""
