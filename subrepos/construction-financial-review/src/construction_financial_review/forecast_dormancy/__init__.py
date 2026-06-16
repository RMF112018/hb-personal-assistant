"""Deterministic dormant / closed-code trend suppression.

Before any monthly phasing, model shape, S-curve, history, frequency, or schedule allocation runs, this
layer classifies each canonical ``budget_code_key`` by inactivity + closure evidence and suppresses
future forecast for codes that are no longer forecastable: ``CLOSED - DO NOT USE`` codes and codes with
no incurred cost for a trailing window (default 18 months) and no affirmative remaining-cost evidence get
``recommended_cost_to_complete = 0``, future months ``0``, and ``final = actual cost to date``.

This is a trend/inactivity conclusion, NOT a budget cap: actual cost to date is never reduced and the
final forecast never drops below actuals. Dormancy is overridden only by affirmative remaining-cost
evidence (open commitment remaining, recent owner/subcontractor pay-app activity, mapped future schedule
work, recent actual cost) or by a **value-asserting** accepted operator forecast-model control (one that
provides a positive remaining/final value — shape/window/timing-only controls never revive a dormant
code).

The authoritative decision is created ONCE in ``forecast_intelligence`` and emitted as
``dormant_code_status_by_budget_code.jsonl``; downstream consumers enforce it defensively and never invent
a conflicting classification. See ``docs/architecture/forecast_dormancy.md``.
"""
