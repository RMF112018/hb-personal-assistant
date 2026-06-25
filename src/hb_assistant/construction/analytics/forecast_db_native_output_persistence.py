"""Package-free persistence of a DB-native forecast result into the v63 output tables (Phase F).

Maps the in-memory ``DbNativeForecastResult.public()`` dict (produced by the read-only DB-native
adapter chain — see ``forecast_db_native_engine_adapter``) directly to the v63 run-output tables and
writes it in a single transaction by reusing the existing idempotent
``output_repository.apply_plan``. There is **no** source / context / analysis package, no manifest,
and no CFR package artifact in this path — that package-free property is the whole point of the
DB-native boundary (ADR 313/314/317).

Scope (Phase F, ADR 319):
- v63 only — ``forecast_outputs`` (header), ``forecast_output_budget_codes`` (one row per forecast
  line), ``forecast_output_risks`` (engine-emitted risks only), ``forecast_output_narratives`` (one
  row per assumption), and ``forecast_output_monthly`` (month-by-month actual + even-spread forecast
  rows, when the engine emits them — operator supplied ``forecast_end_date``). The remaining v63
  detail tables (probability / changes / commitment_exposure / staffing / schedule_phasing) stay
  empty: the financial-spine comprehensive result emits none of them. No v66 decision-support rows
  are written.
- A mandatory, package-free certification preflight runs against the *built planned rows* before any
  write. On any failure it returns a coded failure and writes nothing (no partial rows).
- The write is gated by the route (``resolve_run_output_db_write_enabled``); this module assumes the
  caller has already decided the write is authorized and supplies an explicit ``db_path``.

Money values are canonical Decimal strings (passed through from the engine). The header ``raw_json``
holds a *bounded* sanitized envelope (status / window / maturity / confidence / summary / provenance)
— never the source snapshot, context, raw engine input, paths, or package names. Per-line / per-risk
/ per-assumption ``raw_json`` holds the already-sanitized engine detail dict.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.forecast import output_repository as repo
from hb_assistant.store.connection import open_connection, transaction

# Coded, path-free failure reason for a certification-preflight rejection.
FAILURE_CERTIFICATION = "db_native_output_certification_failed"
# Reused from the persistence-service vocabulary for an in-transaction write failure.
FAILURE_DB_PERSISTENCE = "db_persistence_failed"

# The only generator kind that produces a persistable financial-spine result.
SUPPORTED_KIND = "comprehensive"
# Statuses whose result carries valued forecast lines worth persisting.
_GENERATED_STATUSES = frozenset({"generated", "generated_degraded"})
# forecast_outputs.source_package is NOT NULL; DB-native has no package, so a fixed sentinel.
_SOURCE_PACKAGE_SENTINEL = "db_native"

# v63 planned-table keys this module populates; the rest are emitted empty (apply_plan writes 0 rows).
# ``monthly`` is populated for a comprehensive output when the engine emits month-by-month rows
# (operator supplied ``forecast_end_date``); otherwise the engine emits none and it stays empty.
_EMPTY_KEYS = (
    "probability",
    "changes",
    "commitment_exposure",
    "staffing",
    "schedule_phasing",
)

# Cent tolerance for the monthly reconciliation invariants (even-spread is exact; this is a guard).
_CENT = Decimal("0.01")


@dataclass(frozen=True)
class PersistOutcome:
    """Path-free outcome of a DB-native persistence attempt (no paths / raw_json)."""

    db_persisted: bool
    output_id: str | None = None
    run_id: str | None = None
    counts: dict[str, int] = field(default_factory=dict)
    failure_code: str | None = None


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _gen_run_id() -> str:
    return uuid4().hex[:12]


def _row_id(prefix: str, output_id: str, natural_key: str | None) -> str:
    digest = hashlib.sha256(f"{output_id}|{natural_key or ''}".encode()).hexdigest()[:32]
    return f"{prefix}-{digest}"


def derive_output_id(
    *, project_key: str, generator_kind: str, source_snapshot_id: str | None = None
) -> str:
    """Deterministic ``fout-`` output_id from project identity (never the random run_id).

    Repeated requests for the same (project, kind, snapshot) derive the same output_id, so the
    ``forecast_outputs`` UPSERT keeps a single header row (latest-wins) rather than duplicating.
    """
    anchor = source_snapshot_id or ""
    digest = hashlib.sha256(
        f"{project_key}|{generator_kind}|{anchor}".encode()
    ).hexdigest()[:32]
    return f"fout-{digest}"


def _forecast_period(window: dict[str, Any]) -> str | None:
    start = window.get("forecast_start_date")
    end = window.get("forecast_cutoff_date")
    if start and end:
        return f"{start}..{end}"
    return start or end or None


def build_db_native_planned(
    result: dict[str, Any],
    *,
    output_id: str,
    run_id: str,
    project_key: str,
    now_utc: str,
    source_snapshot_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Map ``result.public()`` to the v63 ``planned`` dict consumed by ``apply_plan``.

    Populates header + budget_codes + risks + narratives; every other v63 detail table is emitted
    as an empty list (the financial-spine comprehensive result has no rows for them).
    """
    summary = result.get("summary") or {}
    window = result.get("forecast_window") or {}
    confidence = result.get("confidence") or {}

    header_envelope = {
        "schema_version": result.get("schema_version"),
        "generation_mode": "db_native",
        "generator_kind": result.get("generator_kind"),
        "generation_scope": result.get("generation_scope"),
        "status": result.get("status"),
        "result_code": result.get("result_code"),
        "forecast_window": window,
        "maturity": result.get("maturity") or {},
        "confidence": confidence,
        "summary": summary,
        "provenance": result.get("provenance") or {},
    }

    outputs = [
        {
            "output_id": output_id,
            "run_id": run_id,
            "project_key": project_key,
            "source_package": _SOURCE_PACKAGE_SENTINEL,
            "forecast_period": _forecast_period(window),
            "basis_labels": confidence.get("forecast_basis"),
            "estimated_final_cost": summary.get("total_forecast_final_cost"),
            "forecast_at_completion": summary.get("total_forecast_final_cost"),
            "cost_to_complete": summary.get("total_cost_to_complete"),
            "variance_to_budget": summary.get("variance_to_budget"),
            "variance_to_prior_forecast": None,
            "source_path": None,
            "source_sha256": source_snapshot_id,
            "raw_json": json.dumps(header_envelope, sort_keys=True),
            "created_utc": now_utc,
            "updated_utc": now_utc,
        }
    ]

    budget_codes = [
        {
            "id": _row_id("fobc", output_id, line.get("budget_code_key")),
            "output_id": output_id,
            "project_key": project_key,
            "budget_code_key": line.get("budget_code_key"),
            "cost_code": line.get("cost_code"),
            "category": line.get("category"),
            "forecast_action": line.get("method_code"),
            "recommended_projected_cost": line.get("forecast_final_cost"),
            "recommended_cost_to_complete": line.get("forecast_cost_to_complete"),
            "confidence": line.get("confidence"),
            "source_row_number": i,
            "raw_json": json.dumps(line, sort_keys=True),
            "created_utc": now_utc,
            "updated_utc": now_utc,
        }
        for i, line in enumerate(result.get("forecast_lines") or [], start=1)
    ]

    risks = []
    for i, risk in enumerate(result.get("risks") or [], start=1):
        risk_type = risk.get("risk_type")
        budget_code_key = risk.get("budget_code_key")
        risk_id = f"{budget_code_key}:{risk_type}"
        risks.append(
            {
                "id": _row_id("forsk", output_id, risk_id),
                "output_id": output_id,
                "project_key": project_key,
                "risk_id": risk_id,
                "severity": risk.get("severity"),
                "budget_code_key": budget_code_key,
                "cost_code": None,
                "category": None,
                "risk_type": risk_type,
                "source_row_number": i,
                "raw_json": json.dumps(risk, sort_keys=True),
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )

    narratives = [
        {
            "id": _row_id("forn", output_id, f"{a.get('scope')}:{a.get('budget_code_key')}"),
            "output_id": output_id,
            "project_key": project_key,
            "scope": a.get("scope"),
            "narrative_key": a.get("budget_code_key"),
            "source_row_number": i,
            "raw_json": json.dumps(a, sort_keys=True),
            "created_utc": now_utc,
            "updated_utc": now_utc,
        }
        for i, a in enumerate(result.get("assumptions") or [], start=1)
    ]

    # Month-by-month rows: window-bounded actuals (is_actual=1) + even-spread forecast (is_actual=0).
    # The engine emits none when the operator supplied no forecast horizon, in which case monthly
    # stays empty (no fabricated phasing).
    monthly = [
        {
            "id": _row_id("fomo", output_id, f"{m.get('budget_code_key')}|{m.get('month')}"),
            "output_id": output_id,
            "project_key": project_key,
            "budget_code_key": m.get("budget_code_key"),
            "month": m.get("month"),
            "value": m.get("value"),
            "is_actual": int(m.get("is_actual") or 0),
            "source_row_number": i,
            "raw_json": json.dumps(m, sort_keys=True),
            "created_utc": now_utc,
            "updated_utc": now_utc,
        }
        for i, m in enumerate(result.get("monthly") or [], start=1)
    ]

    planned: dict[str, list[dict[str, Any]]] = {
        "outputs": outputs,
        "budget_codes": budget_codes,
        "risks": risks,
        "narratives": narratives,
        "monthly": monthly,
    }
    for key in _EMPTY_KEYS:
        planned[key] = []
    return planned


def _ensure_run_anchor(
    conn: sqlite3.Connection, *, run_id: str, project_key: str, now_utc: str
) -> None:
    """Insert the ``forecast_runs`` anchor (FK parent for the v63 output rows), idempotently.

    Mirrors the existing CFR live-write convention (``live_db_run_output_projection``): one anchor row
    per run keyed on ``run_id``. ``context_package`` carries the path-free ``db_native`` sentinel
    (DB-native has no package). ``INSERT OR IGNORE`` keeps a re-applied run idempotent.
    """
    conn.execute(
        "INSERT OR IGNORE INTO forecast_runs (run_id, project_key, context_package, status, "
        "created_utc) VALUES (?, ?, ?, ?, ?)",
        (run_id, project_key, _SOURCE_PACKAGE_SENTINEL, "projected", now_utc),
    )


def _is_decimal(value: Any) -> bool:
    if value is None:
        return True
    try:
        Decimal(str(value))
        return True
    except (InvalidOperation, ValueError, TypeError):
        return False


def certify_db_native_result(
    result: dict[str, Any],
    planned: dict[str, list[dict[str, Any]]],
    *,
    request_id: str | None,
    project_key: str | None,
    generator_kind: str | None,
) -> list[str]:
    """Package-free certification preflight. Returns [] when clean, else coded reasons.

    Runs against the *built planned rows* (not just the incoming engine result) so the exact bytes
    that would be persisted are validated. No write may proceed while this returns reasons.
    """
    reasons: list[str] = []

    if not request_id:
        reasons.append("missing_request_id")
    if not project_key:
        reasons.append("missing_project_key")
    if generator_kind != SUPPORTED_KIND:
        reasons.append("generator_kind_unsupported")
    if result.get("status") not in _GENERATED_STATUSES:
        reasons.append("result_not_generated")
    if not (result.get("provenance") or {}):
        reasons.append("missing_provenance")

    lines = result.get("forecast_lines") or []
    if not lines:
        reasons.append("no_forecast_lines")

    for line in lines:
        if not line.get("budget_code_key"):
            reasons.append("budget_code_missing_key")
        final = line.get("forecast_final_cost")
        ctc = line.get("forecast_cost_to_complete")
        actual = line.get("actual_cost_to_date")
        if not (_is_decimal(final) and _is_decimal(ctc) and _is_decimal(actual)):
            reasons.append("money_not_decimal")
            continue
        # Degraded lines carry no values (None) — the numeric invariants apply only to valued rows.
        if final is not None and actual is not None and Decimal(str(final)) < Decimal(str(actual)):
            reasons.append("final_below_actual")
        if ctc is not None and Decimal(str(ctc)) < Decimal("0"):
            reasons.append("cost_to_complete_negative")

    # Header / persisted money columns must Decimal-parse.
    for row in planned.get("outputs", []):
        for col in (
            "estimated_final_cost",
            "forecast_at_completion",
            "cost_to_complete",
            "variance_to_budget",
        ):
            if not _is_decimal(row.get(col)):
                reasons.append("header_money_not_decimal")
                break

    reasons.extend(_certify_monthly(planned))

    leaks = find_redaction_leaks(planned)
    if leaks:
        reasons.append("redaction_leak")

    # Stable, de-duplicated coded reasons.
    return sorted(set(reasons))


def _certify_monthly(planned: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Reconcile the planned monthly rows before any write (empty monthly is a valid degraded state).

    Forecast rows (is_actual=0) per budget code must sum to that code's recommended_cost_to_complete,
    and all forecast rows must sum to the header cost_to_complete. Actual rows (is_actual=1) are
    field-validated but never folded into the CTC reconciliation.
    """
    monthly = planned.get("monthly", [])
    if not monthly:
        return []

    reasons: list[str] = []
    forecast_sum_by_key: dict[str, Decimal] = {}
    for row in monthly:
        if not row.get("output_id") or not row.get("budget_code_key") or not row.get("month"):
            reasons.append("monthly_row_missing_identity")
        value = row.get("value")
        if value is None or not _is_decimal(value):
            reasons.append("monthly_value_not_decimal")
            continue
        is_actual = int(row.get("is_actual") or 0)
        if is_actual not in (0, 1):
            reasons.append("monthly_is_actual_invalid")
        if is_actual == 0:
            key = str(row.get("budget_code_key") or "")
            forecast_sum_by_key[key] = forecast_sum_by_key.get(key, Decimal("0")) + Decimal(str(value))

    # Per budget-code: forecast monthly rows must reconcile to the code's recommended CTC.
    for code in planned.get("budget_codes", []):
        ctc = code.get("recommended_cost_to_complete")
        if not _is_decimal(ctc) or ctc is None:
            continue
        ctc_dec = Decimal(str(ctc))
        if ctc_dec <= Decimal("0"):
            continue
        key = str(code.get("budget_code_key") or "")
        if abs(forecast_sum_by_key.get(key, Decimal("0")) - ctc_dec) > _CENT:
            reasons.append("monthly_forecast_code_ctc_mismatch")

    # Header: all forecast monthly rows must reconcile to the header cost_to_complete.
    header = (planned.get("outputs") or [{}])[0]
    header_ctc = header.get("cost_to_complete")
    if _is_decimal(header_ctc) and header_ctc is not None:
        total_forecast = sum(forecast_sum_by_key.values(), Decimal("0"))
        if abs(total_forecast - Decimal(str(header_ctc))) > _CENT:
            reasons.append("monthly_forecast_header_ctc_mismatch")

    return reasons


def persist_db_native_result(
    *,
    result: dict[str, Any],
    project_key: str,
    generator_kind: str,
    request_id: str,
    db_path: str | Path,
    run_id: str | None = None,
    source_snapshot_id: str | None = None,
) -> PersistOutcome:
    """Certify then atomically persist a DB-native result into the v63 tables.

    Certification runs before the transaction opens; on failure nothing is written. The write is a
    single transaction over ``apply_plan`` — any error rolls back, leaving no partial rows.
    """
    run_id = run_id or _gen_run_id()
    output_id = derive_output_id(
        project_key=project_key,
        generator_kind=generator_kind,
        source_snapshot_id=source_snapshot_id,
    )
    now_utc = _now_utc()
    planned = build_db_native_planned(
        result,
        output_id=output_id,
        run_id=run_id,
        project_key=project_key,
        now_utc=now_utc,
        source_snapshot_id=source_snapshot_id,
    )

    failures = certify_db_native_result(
        result,
        planned,
        request_id=request_id,
        project_key=project_key,
        generator_kind=generator_kind,
    )
    if failures:
        return PersistOutcome(db_persisted=False, failure_code=FAILURE_CERTIFICATION)

    try:
        with open_connection(Path(db_path)) as conn, transaction(conn):
            _ensure_run_anchor(conn, run_id=run_id, project_key=project_key, now_utc=now_utc)
            counts = repo.apply_plan(conn, planned)
    except Exception:
        return PersistOutcome(db_persisted=False, failure_code=FAILURE_DB_PERSISTENCE)

    return PersistOutcome(
        db_persisted=True, output_id=output_id, run_id=run_id, counts=counts
    )
