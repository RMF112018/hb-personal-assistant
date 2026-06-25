"""True DB-native forecast generation contract + fail-closed seam (Phase B).

This module defines the *contract* for true DB-native generation — sourcing inputs directly from the
app DB and persisting forecast outputs to the DB with no required source/context/analysis package —
and provides the route seam that Phase C/D/E/F will implement. In Phase B it is **fail-closed**: it
returns a curated, path-free ``db_native_generation_not_implemented`` result and persists nothing.

Boundary invariants (asserted by tests):
- This seam MUST NOT call package-backed generation: ``_run_generation``, ``generate_and_persist``,
  ``ForecastDbConfigRunService.start_db_config_run``, the CFR context/analysis or live-write
  workflows, or any package_resolution helper. It imports none of them.
- The request/response contract is path-free (no local paths, run roots, raw payloads).

See ADR 314 (this contract seam) and ADR 313 (the fail-closed boundary + future CFR work).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hb_assistant.construction.analytics.forecast_generation_modes import GenerationMode
from hb_assistant.construction.analytics.forecast_run_output_persistence_service import (
    FAILURE_DB_NATIVE_NOT_IMPLEMENTED,
    failure_message_for,
)


@dataclass(frozen=True)
class DbNativeGenerationRequest:
    """Path-free request contract for true DB-native generation.

    ``source_snapshot_id`` is the deterministic provenance of the source-data snapshot the run is
    computed against; Phase C/F resolves and (if a schema path exists) persists it. In Phase B it is
    an optional pass-through contract field (default ``None``).
    """

    project_key: str
    generator_kind: str
    forecast_start_date: str | None = None
    forecast_cutoff_date: str | None = None
    forecast_cutoff_date_basis: str | None = None
    source_snapshot_id: str | None = None


@dataclass(frozen=True)
class DbNativeGenerationResult:
    """Path-free result contract for a DB-native generation attempt.

    While the seam is fail-closed: ``request_status="failed"``, ``db_persisted=False``,
    ``persisted_output_ids=()``, and a curated coded failure. Phase C/D/E populates the persisted
    fields once true DB-native generation lands.
    """

    mode: str
    request_status: str
    db_persisted: bool
    failure_code: str | None = None
    failure_message: str | None = None
    persisted_output_ids: tuple[str, ...] = field(default_factory=tuple)
    source_snapshot_id: str | None = None


def generate_db_native(request: DbNativeGenerationRequest) -> DbNativeGenerationResult:
    """Fail-closed DB-native generation seam (Phase B).

    Returns a curated, path-free ``db_native_generation_not_implemented`` result and persists
    nothing. Never falls back to package-backed generation — that non-dependency is the whole point
    of the explicit ``db_native`` boundary. Phase C/D/E/F replace this body with real DB-sourced,
    package-free context, calculation, and direct DB persistence.
    """
    return DbNativeGenerationResult(
        mode=GenerationMode.DB_NATIVE.value,
        request_status="failed",
        db_persisted=False,
        failure_code=FAILURE_DB_NATIVE_NOT_IMPLEMENTED,
        failure_message=failure_message_for(FAILURE_DB_NATIVE_NOT_IMPLEMENTED),
        persisted_output_ids=(),
        source_snapshot_id=request.source_snapshot_id,
    )
