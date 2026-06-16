"""Forecast accuracy, ability & confidence layer.

Adds independent, deterministic multi-method EAC/ETC estimates grounded in accounting actuals,
commitments, owner progress, and schedule; reconciles them into an *advisory*
``model_recommended_projected_cost`` (always floored to actuals, human-gated); calibrates a 0-1
confidence with a real backtest; flags where the ERP forecast is likely inaccurate; and produces an
optional advisory local-Ollama reasoning layer.

Accounting actuals (CostEntries) remain truth: no estimator or LLM ever overrides actuals or sets the
authoritative rule-based ``recommended_projected_cost``. Every advisory EAC is >= actual-to-date.
See ``docs/workflow/07_forecast_accuracy.md``.
"""
