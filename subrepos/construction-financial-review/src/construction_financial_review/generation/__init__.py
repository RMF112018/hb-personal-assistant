"""Package-free DB-native forecast generation (Phase E).

Turns the Phase D ``DbNativeForecastContext`` (financial spine) into a typed, in-memory forecast
result object — no source/context/analysis package files, no run-lineage resolution, no
``hb_assistant`` import. The result object is the seam Phase F persists directly to the DB.

Scope (Phase E): the ``comprehensive`` generator kind produces a financial-spine-only forecast that
reuses the canonical ``forecast_cost_basis`` rules (actuals floor, asymmetric raise, dormancy
suppression). The ``monthly`` / ``probability`` / ``model_controls`` kinds return an honest
*unsupported* result because their required input families (phasing/trend signals, Monte-Carlo
simulation inputs, operator config) are not yet DB-native. DB-native-unsupported is a valid honest
terminal state — NOT an implementation gap to "fix" by inventing values. See ADR 317.
"""
