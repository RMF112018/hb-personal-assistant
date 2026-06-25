"""HB-side adapter for the DB-native forecast generation engine (Phase E).

Runs the read-only DB-native chain end-to-end and returns a path-free, redaction-safe result dict:

    build_db_native_source_snapshot()                 (HB, Phase C — read-only v59 DB)
        -> context_input_from_snapshot_public()        (CFR, Phase D)
        -> build_db_native_context()                   (CFR, Phase D)
        -> generate_db_native_forecast()               (CFR, Phase E engine)
        -> result.public()

This is the ONLY HB->CFR bridge for DB-native generation (per the cross-repo decoupling rule: the
CFR engine imports no ``hb_assistant``; the bridge lives on the HB side). The CFR imports are lazy
(resolved via ``_ensure_cfr_importable``), so importing this module pulls in no CFR code.

Phase E scope: this adapter is NOT wired into ``POST /api/forecast/runs/db-native`` — that route
stays fail-closed (``db_native_generation_not_implemented``) until Phase F wires
route -> adapter -> persistence -> certified output. It reads the DB read-only and mutates nothing.
See ADR 317.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hb_assistant.construction.analytics.forecast_db_native_source_snapshot import (
    build_db_native_source_snapshot,
)

# Result statuses/codes echoed for the pre-engine (context-build) failure path.
_STATUS_INSUFFICIENT_BASIS = "insufficient_basis"
_GENERATION_SCOPE = "financial_spine_db_native"
_INSUFFICIENT_MESSAGE = (
    "DB-native forecast could not be generated: the required financial basis is unavailable."
)


def compute_db_native_forecast(
    project_key: str,
    generator_kind: str,
    *,
    forecast_window: dict[str, Any] | None = None,
    db_path: str | Path | None = None,
    source_package: str | None = None,
) -> dict[str, Any]:
    """Build the DB-native forecast result for ``project_key`` (read-only). Returns ``result.public()``.

    Fail-closed: if the financial-spine context cannot be built (no usable basis / blocking
    readiness), returns a curated, path-free ``insufficient_basis`` result rather than raising.
    """
    from hb_assistant.construction.analytics.forecast_run_service import _ensure_cfr_importable

    window = dict(forecast_window or {})

    snapshot = build_db_native_source_snapshot(
        project_key, db_path=db_path, source_package=source_package
    )
    snapshot_public = snapshot.public()

    _ensure_cfr_importable()
    from construction_financial_review.context.db_native_context_builder import (
        DbNativeContextError,
        build_db_native_context,
        context_input_from_snapshot_public,
    )
    from construction_financial_review.generation.db_native_generation_engine import (
        DbNativeGenerationEngineInput,
        generate_db_native_forecast,
    )

    try:
        context = build_db_native_context(context_input_from_snapshot_public(snapshot_public))
    except DbNativeContextError as exc:
        return _insufficient_basis_result(
            project_key, generator_kind, window, snapshot_public, reason=str(exc)
        )

    result = generate_db_native_forecast(
        DbNativeGenerationEngineInput(
            project_key=project_key,
            generator_kind=generator_kind,
            forecast_window=window,
            context=context,
        )
    )
    return result.public()


def _insufficient_basis_result(
    project_key: str,
    generator_kind: str,
    window: dict[str, Any],
    snapshot_public: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    """Path-free result for the pre-engine context-build failure (mirrors the engine's contract)."""
    readiness = dict(snapshot_public.get("readiness") or {})
    return {
        "schema_version": 1,
        "project_key": project_key,
        "generator_kind": generator_kind,
        "status": _STATUS_INSUFFICIENT_BASIS,
        "result_code": reason,
        "message": _INSUFFICIENT_MESSAGE,
        "generation_scope": _GENERATION_SCOPE,
        "forecast_window": dict(window),
        "maturity": {
            "tier": readiness.get("forecast_maturity"),
            "readiness_status": readiness.get("readiness_status"),
            "initial_forecast": readiness.get("initial_forecast"),
            "prior_forecast_available": readiness.get("prior_forecast_available"),
            "sparse": bool(readiness.get("sparse")),
        },
        "confidence": {
            "level": readiness.get("confidence_level"),
            "basis_scope": _GENERATION_SCOPE,
            "forecast_basis": readiness.get("forecast_basis"),
            "basis_limitations": list(readiness.get("basis_limitations") or []),
            "note": "owner_procore_evidence_unavailable_confidence_not_elevated",
        },
        "forecast_lines": [],
        "summary": {},
        "assumptions": [],
        "risks": [],
        "unsupported_outputs": {},
        "warnings": [],
        "blockers": [reason],
        "provenance": {
            "row_counts_by_family": dict(
                (snapshot_public.get("provenance") or {}).get("row_counts_by_family") or {}
            ),
            "engine_version": "db_native_generation_engine/1",
        },
    }
