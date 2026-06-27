"""Project Staffing backend services (Phase 2a: foundation).

Repositories, holiday business-day proration, template-inheritance resolution, and validation
over the V76 staffing tables. No FastAPI routes, no forecast-generation, no cost-entry actuals
projection / attribution (those are Phase 2b / 3 / 6). Public repository/readmodel outputs are
redaction-safe: they never expose ``raw_json``, source paths, ``run_id``, or implementation
internals, even though the underlying tables persist ``raw_json`` columns.
"""

from __future__ import annotations
