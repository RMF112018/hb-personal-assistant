"""Forecast improvement-audit slice (additive, advisory, read-only).

Validates the seven forecasting-priority improvements against repo truth + data truth and implements
each ONLY where the currently available JSON packages / SQLite tables support it. Emits one additive
``forecast_improvement_audit_package_tropical_<stamp>/`` package: a support-decision table, data +
SQLite inventories, a Basis-of-Estimate doc + coverage audit, calibration enhancements, actual-cost
lag diagnostics, a schedule cost-loading readiness audit, GC/GR behavior + fee-cap diagnostics,
change-order exposure evidence, and a data-gap register.

Governance (corrected 2026-06-15):
  * CostEntries/Sage actual cost is accounting truth and the only hard FLOOR, everywhere.
  * Reference values (budget, current projected cost, revised budget, ERP, owner SOV, pay app,
    invoice, schedule, change order, historical forecast) never cap NON-fee forecasts.
  * FEE codes (currently ``20-18-110 CONTRACTORS FEE``) ARE capped by the projected budget value,
    subject to the actuals floor; a missing cap value yields a data-gap, never an invented cap.
  * Everything is advisory (``requires_human_acceptance``); proposed changes carry ``do_not_auto_apply``.
  * Never mutates accepted packages, source packages, Excel, historical JSON, or the SQLite DB; the DB
    is opened strictly read-only.
"""
