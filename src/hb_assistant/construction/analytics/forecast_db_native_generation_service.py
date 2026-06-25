"""True DB-native forecast generation seam — compute, certify, and persist (Phase F).

This module owns the route seam for true DB-native generation: sourcing inputs directly from the app
DB and persisting forecast outputs to the DB with **no** source / context / analysis package. It runs
the read-only DB-native adapter chain, then — only when the run-output DB-write gate is enabled and a
package-free certification preflight passes — persists the result to the v63 forecast output tables in
a single transaction. It never falls back to package-backed generation; that non-dependency is the
whole point of the explicit ``db_native`` boundary.

Posture (ADR 319, building on ADR 313/314/317):
- Write gate **off** (default) → curated ``run_output_db_write_disabled`` refusal; nothing computed
  is dropped silently.
- Write gate **on** → compute via the adapter, branch on result status:
  - ``generated`` / ``generated_degraded`` → certify + atomically persist (v63 only); success carries
    the persisted ``output_id`` and the run lineage ``run_id``.
  - ``unsupported`` (non-comprehensive kind) → coded ``db_native_generator_kind_unsupported``, no write.
  - ``insufficient_basis`` → coded ``db_native_insufficient_basis``, no write.
  - certification rejection → ``db_native_output_certification_failed``; DB error → ``db_persistence_failed``.

Boundary invariants (asserted by tests):
- This seam MUST NOT call package-backed generation: ``_run_generation``, ``generate_and_persist``,
  ``ForecastDbConfigRunService.start_db_config_run``, the CFR context/analysis or live-write
  workflows, or any package_resolution helper.
- The request/response contract is path-free (no local paths, run roots, raw payloads).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hb_assistant.construction.analytics.forecast_db_native_output_persistence import (
    FAILURE_CERTIFICATION,
    FAILURE_DB_PERSISTENCE,
    persist_db_native_result,
)
from hb_assistant.construction.analytics.forecast_generation_modes import GenerationMode
from hb_assistant.construction.analytics.forecast_run_output_persistence_service import (
    FAILURE_DISABLED,
)

# Coded, path-free DB-native failure reasons (stored on the request row; returned to the UI).
FAILURE_KIND_UNSUPPORTED = "db_native_generator_kind_unsupported"
FAILURE_INSUFFICIENT_BASIS = "db_native_insufficient_basis"

# Curated, path-free messages keyed by failure code (never echo exception text / data_root paths).
_FAILURE_MESSAGES = {
    FAILURE_DISABLED: (
        "DB-native forecast output persistence is turned off for this runtime; enable the "
        "run-output DB-write setting to persist a forecast."
    ),
    FAILURE_KIND_UNSUPPORTED: (
        "This generator kind isn't available for DB-native generation yet; only the comprehensive "
        "forecast is supported."
    ),
    FAILURE_INSUFFICIENT_BASIS: (
        "DB-native forecast could not be generated: the required financial basis is unavailable."
    ),
    FAILURE_CERTIFICATION: (
        "The DB-native forecast output did not pass persistence certification and was not written."
    ),
    FAILURE_DB_PERSISTENCE: "The DB-native forecast output could not be persisted.",
}

_GENERATED_STATUSES = frozenset({"generated", "generated_degraded"})


@dataclass(frozen=True)
class DbNativeGenerationRequest:
    """Path-free request contract for true DB-native generation.

    ``db_path`` and ``write_enabled`` are injected by the route from the resolved app-DB path and the
    run-output DB-write gate; they let the service persist (to a temp DB in tests) while keeping the
    public request contract path-free. ``source_snapshot_id`` is the deterministic provenance of the
    source-data snapshot the run is computed against. ``request_id`` is the durable request-ledger id.
    """

    project_key: str
    generator_kind: str
    forecast_start_date: str | None = None
    forecast_cutoff_date: str | None = None
    forecast_end_date: str | None = None
    forecast_cutoff_date_basis: str | None = None
    source_snapshot_id: str | None = None
    request_id: str | None = None
    db_path: str | None = None
    write_enabled: bool = False


@dataclass(frozen=True)
class DbNativeGenerationResult:
    """Path-free result contract for a DB-native generation attempt."""

    mode: str
    request_status: str
    db_persisted: bool
    failure_code: str | None = None
    failure_message: str | None = None
    persisted_output_ids: tuple[str, ...] = field(default_factory=tuple)
    source_snapshot_id: str | None = None
    run_id: str | None = None


def _failed(request: DbNativeGenerationRequest, code: str) -> DbNativeGenerationResult:
    return DbNativeGenerationResult(
        mode=GenerationMode.DB_NATIVE.value,
        request_status="failed",
        db_persisted=False,
        failure_code=code,
        failure_message=_FAILURE_MESSAGES.get(code),
        persisted_output_ids=(),
        source_snapshot_id=request.source_snapshot_id,
    )


def generate_db_native(request: DbNativeGenerationRequest) -> DbNativeGenerationResult:
    """Compute, certify, and persist a DB-native forecast — or return a coded, path-free failure.

    Never falls back to package-backed generation. Persists only when the run-output DB-write gate is
    enabled and the package-free certification preflight passes.
    """
    if not request.write_enabled:
        return _failed(request, FAILURE_DISABLED)

    # Lazy import: the adapter resolves CFR lazily, so importing this module pulls in no CFR code.
    from hb_assistant.construction.analytics.forecast_db_native_engine_adapter import (
        compute_db_native_forecast,
    )

    window: dict[str, str] = {}
    if request.forecast_start_date:
        window["forecast_start_date"] = request.forecast_start_date
    if request.forecast_cutoff_date:
        window["forecast_cutoff_date"] = request.forecast_cutoff_date
    if request.forecast_end_date:
        window["forecast_end_date"] = request.forecast_end_date

    result = compute_db_native_forecast(
        request.project_key,
        request.generator_kind,
        forecast_window=window or None,
        db_path=request.db_path,
    )
    status = result.get("status")

    if status == "unsupported":
        return _failed(request, FAILURE_KIND_UNSUPPORTED)
    if status not in _GENERATED_STATUSES:
        return _failed(request, FAILURE_INSUFFICIENT_BASIS)

    outcome = persist_db_native_result(
        result=result,
        project_key=request.project_key,
        generator_kind=request.generator_kind,
        request_id=request.request_id or "",
        db_path=request.db_path or "",
        source_snapshot_id=request.source_snapshot_id,
    )
    if not outcome.db_persisted:
        return _failed(request, outcome.failure_code or FAILURE_DB_PERSISTENCE)

    return DbNativeGenerationResult(
        mode=GenerationMode.DB_NATIVE.value,
        request_status="completed",
        db_persisted=True,
        persisted_output_ids=(outcome.output_id,) if outcome.output_id else (),
        source_snapshot_id=request.source_snapshot_id,
        run_id=outcome.run_id,
    )
