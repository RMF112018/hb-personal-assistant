"""Forecast JSON/JSONL → SQLite projection (Phases 2–3).

Phase 2 (lineage-only): read-only projection of a completed CFR forecast *run* and
its packages into the five v58 foundation/lineage tables (``forecast_projects``,
``forecast_runs``, ``forecast_source_ingestions``, ``forecast_package_manifests``,
``forecast_validation_events``) — project/run identity, per-package manifests,
per-source ingestion records, per-gate validation events.

Phase 3 (source-domain read parity): projection of selected TWN cost-forecast JSONL
source rows into the three v59 source-domain tables (``forecast_budget_details``,
``forecast_cost_entries``, ``forecast_monthly_actuals_by_budget_code``) plus DB-backed
read repositories that return the original JSONL row shape, to prove DB↔JSONL parity.
Phase 3 does NOT change forecast behavior or read paths — forecast model reads remain
file-backed, and these tables are written only to explicit temp DBs (never the live DB).

The engine reads ``.cfr_run_state``, package manifests, and source ``*.jsonl`` files as
plain JSON; it does NOT import the construction-financial-review Python package.
"""

from .projection_engine import plan_run, project_run
from .source_domain_engine import plan_source_domain_projection, project_source_domain

__all__ = [
    "plan_run",
    "project_run",
    "plan_source_domain_projection",
    "project_source_domain",
]
