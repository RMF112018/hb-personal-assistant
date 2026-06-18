"""Forecast JSON/JSONL → SQLite projection (Phase 2, lineage-only).

Read-only projection of a completed CFR forecast *run* and its packages into the
five v58 foundation/lineage tables (``forecast_projects``, ``forecast_runs``,
``forecast_source_ingestions``, ``forecast_package_manifests``,
``forecast_validation_events``).

Phase 2 scope is strictly lineage: project/run identity, per-package manifests,
per-source ingestion records, and per-gate validation events. It does NOT project
domain rows (monthly values, recommendations, cost entries, BudgetDetails, owner
pay-app, operator controls) — those await v59+ domain tables. It does not change
forecast behavior or read paths (forecast model reads remain file-backed).

The engine reads ``.cfr_run_state`` and package ``manifest.json`` /
``input_inventory.json`` / ``validation_report.json`` as plain JSON; it does NOT
import the construction-financial-review Python package.
"""

from .projection_engine import plan_run, project_run

__all__ = ["plan_run", "project_run"]
