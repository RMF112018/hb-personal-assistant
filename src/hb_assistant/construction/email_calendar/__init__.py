"""Email + calendar full raw content -> structured projection layer.

Hardens the V42 raw-content tables with source-quality provenance and projects every
available raw email/calendar business field into final structured parent + child tables,
with a mechanical completeness matrix. Outbound surfaces stay redacted; raw bodies live
only in the designated local-private raw tables.
"""

from __future__ import annotations

from . import projection_engine, projection_matrix, projection_registry, schema, source_quality

__all__ = [
    "projection_engine",
    "projection_matrix",
    "projection_registry",
    "schema",
    "source_quality",
]
