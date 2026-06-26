"""DB-native source-domain snapshot for forecast generation (Phase C).

A deterministic, path-free, typed source object read **from the local DB only** — the input later
phases' DB-native engine will consume. It reuses the authoritative readiness/maturity read model and
the schedule-date resolver, and the v59 source-domain readers, rather than re-deriving any of them.

Scope boundary (Phase C): the snapshot carries typed rows for the three v59 financial families (the
engine's required basis) and **availability + counts only** for optional ``procore_ep_*`` enrichment
families (commitments / commitment-changes / change-events). Full enrichment-row normalization and
amount math belong to the engine/modeling phases. See ADR 315.

Guardrails: read-only DB access (``mode=ro``); no live-DB mutation; no CFR / package_resolution /
context / analysis imports; no source-package / context / analysis directory dependency and no silent
fallback to source packages. ``source_package`` is used only as an INTERNAL active-batch selector and
is never emitted by ``public()`` (route-facing output stays package/path-free).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from hb_assistant.construction.forecast.source_domain_repository import (
    read_budget_details_from_db,
    read_cost_entries_from_db,
    read_monthly_actuals_from_db,
)

SCHEMA_VERSION = 1

_CENT = Decimal("0.01")

# Canonical BudgetDetails projected-cost formula (forecast_cost_basis): all four must be present and
# reconcile for the cost-basis projected basis to be applicable. pending_cost_changes is COST-side and
# is sourced only from a dynamic row-cell mapped to that role — never from budget-side
# pending_budget_changes.
_FORMULA_FIELDS = ("committed_costs", "erp_direct_costs", "pending_cost_changes", "projected_costs")

# Stable named money columns read from procore_ep_budget_detail_rows (TEXT). pending_budget_changes is
# carried as budget-side context only (never a formula input).
_BUDGETDETAILS_ROW_AMOUNT_FIELDS = (
    "committed_costs",
    "erp_direct_costs",
    "projected_costs",
    "actual_cost",
    "job_to_date_costs",
    "erp_job_to_date_costs",
    "forecast_to_complete",
    "estimated_cost_at_completion",
    "pending_budget_changes",
)

# Dynamic (row-cell) cost-basis roles resolved via budget_column_roles.procore_label_to_role_key.
_DYNAMIC_CELL_ROLES = ("pending_cost_changes", "commitment_invoiced")

# Readiness codes that BLOCK generation (everything else is a non-blocking warning). The read model
# (ForecastGenerationProjectReadModelService) is authoritative; we only split its coded reasons here.
_BLOCKING_READINESS_CODES = ("no_project_identity", "no_financial_basis")

# Optional enrichment families: public family name -> verified v47 primary table. Counts/availability
# only in Phase C. Names verified against a migrated schema (each table has project_key + is_current).
_ENRICHMENT_FAMILIES: dict[str, str] = {
    "commitments": "procore_ep_commitment_contracts",
    "commitment_changes": "procore_ep_commitment_change_orders",
    "change_events": "procore_ep_change_events",
}

# Read-model fields carried verbatim into the snapshot's readiness block (single source of truth).
_READINESS_FIELDS = (
    "readiness_status",
    "forecast_maturity",
    "confidence_level",
    "forecast_basis",
    "basis_limitations",
    "initial_forecast",
    "prior_forecast_available",
)
# Maturity tiers that mean "data exists but is thin" — distinct from blocked/no-basis.
_SPARSE_MATURITIES = ("baseline_only", "cost_informed")


class DbNativeSourceSnapshotError(RuntimeError):
    """Raised only for unrecoverable build inputs (e.g. no DB path configured)."""


@dataclass(frozen=True)
class SourceFamily:
    """A required v59 financial family: typed (normalized) rows + count. ``present`` distinguishes
    missing (no rows) from zero-valued (rows whose amounts are 0 are real input facts)."""

    present: bool
    row_count: int
    rows: tuple[dict[str, Any], ...] = ()

    def public(self) -> dict[str, Any]:
        return {"present": self.present, "row_count": self.row_count, "rows": [dict(r) for r in self.rows]}


@dataclass(frozen=True)
class EnrichmentFamily:
    """An optional procore_ep_* family: availability + count only (no rows in Phase C)."""

    present: bool
    row_count: int

    def public(self) -> dict[str, Any]:
        return {"present": self.present, "row_count": self.row_count}


@dataclass(frozen=True)
class CostBasisInputs:
    """DB-native BudgetDetails cost-basis formula inputs, one deterministically-selected view per
    budget code (Phase E2). Path-free; rows carry only amounts + formula diagnostics + selection
    provenance (never record_key / payload_hash / raw payload)."""

    present: bool
    row_count: int
    rows: tuple[dict[str, Any], ...] = ()

    def public(self) -> dict[str, Any]:
        return {"present": self.present, "row_count": self.row_count, "rows": [dict(r) for r in self.rows]}


@dataclass(frozen=True)
class DbNativeSourceSnapshot:
    """Typed, path-free DB-native source snapshot. ``public()`` is the serializable, redaction-safe
    contract; ``active_source_package`` is INTERNAL (an active-batch selector) and never emitted."""

    schema_version: int
    project_key: str
    display_name: str | None
    project_number: str | None
    procore_project_id: str | None
    forecast_window: dict[str, Any]
    readiness: dict[str, Any]
    budget_details: SourceFamily
    cost_entries: SourceFamily
    monthly_actuals: SourceFamily
    enrichment: dict[str, EnrichmentFamily]
    schedule_summary: dict[str, Any]
    prior_forecast: dict[str, Any]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    # DB-native BudgetDetails cost-basis formula inputs (Phase E2); empty when the structured Procore
    # budget-detail table is absent/unseeded (the financial spine still drives the build).
    budgetdetails_cost_basis_inputs: CostBasisInputs = field(
        default_factory=lambda: CostBasisInputs(present=False, row_count=0)
    )
    # INTERNAL ONLY — used to select the active v59 batch; never surfaced by public().
    active_source_package: str | None = None

    def public(self) -> dict[str, Any]:
        financial_counts = {
            "budget_details": self.budget_details.row_count,
            "cost_entries": self.cost_entries.row_count,
            "monthly_actuals": self.monthly_actuals.row_count,
        }
        enrichment_counts = {name: fam.row_count for name, fam in self.enrichment.items()}
        row_counts_by_family = {**financial_counts, **enrichment_counts}
        families_present = [name for name, count in row_counts_by_family.items() if count > 0]
        return {
            "schema_version": self.schema_version,
            "project_key": self.project_key,
            "display_name": self.display_name,
            "project_number": self.project_number,
            "procore_project_id": self.procore_project_id,
            "forecast_window": dict(self.forecast_window),
            "readiness": dict(self.readiness),
            "financial_basis": {
                # Package/path-free provenance — NO raw source_package value is exposed.
                "active_source_batch_present": self.active_source_package is not None,
                "active_source_batch_row_counts": financial_counts,
                "budget_details": self.budget_details.public(),
                "cost_entries": self.cost_entries.public(),
                "monthly_actuals": self.monthly_actuals.public(),
            },
            "enrichment_families": {name: fam.public() for name, fam in self.enrichment.items()},
            "budgetdetails_cost_basis_inputs": self.budgetdetails_cost_basis_inputs.public(),
            "schedule_summary": dict(self.schedule_summary),
            "prior_forecast": dict(self.prior_forecast),
            "provenance": {
                "row_counts_by_family": row_counts_by_family,
                "source_families_present": families_present,
            },
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
        }


# -- narrow read helpers (no uncontrolled SQL blob) ---------------------------


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _resolve_active_source_package(conn: sqlite3.Connection, project_key: str) -> str | None:
    """The most recent v59 source batch for the project across the three financial tables (or None).

    Deterministic: ties break by source_package descending. Used only to select an internal batch.
    """
    tables = (
        "forecast_budget_details",
        "forecast_cost_entries",
        "forecast_monthly_actuals_by_budget_code",
    )
    present = [t for t in tables if _table_exists(conn, t)]
    if not present:
        return None
    union = " UNION ALL ".join(
        f"SELECT source_package, created_utc FROM {t} WHERE project_key = ?" for t in present
    )
    row = conn.execute(
        f"SELECT source_package FROM ({union}) "
        "GROUP BY source_package ORDER BY MAX(created_utc) DESC, source_package DESC LIMIT 1",
        [project_key] * len(present),
    ).fetchone()
    return str(row[0]) if row else None


def _count_enrichment_family(conn: sqlite3.Connection, table: str, project_key: str) -> int:
    """Current-row count for an optional family; 0 if the table is absent (table from fixed allowlist)."""
    if not _table_exists(conn, table):
        return 0
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE project_key = ? AND is_current = 1", (project_key,)
    ).fetchone()
    return int(row[0]) if row else 0


def _dec(value: Any) -> Decimal | None:
    """Defensive Decimal parse. None/'' -> None; unparseable -> None (never raises)."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _money_opt(value: Any) -> str | None:
    """Canonical 2-dp money string for an optional amount: missing/unparseable -> None, '0.00' kept."""
    parsed = _dec(value)
    return str(parsed.quantize(_CENT)) if parsed is not None else None


def _read_budgetdetails_cost_basis_inputs(
    conn: sqlite3.Connection, project_key: str
) -> tuple[dict[str, Any], ...]:
    """One deterministically-selected BudgetDetails cost-basis input row per budget code (Phase E2).

    Reads stable money columns from ``procore_ep_budget_detail_rows`` and the two dynamic cost-basis
    fields (``pending_cost_changes`` / ``commitment_invoiced``) from ``procore_ep_budget_detail_row_cells``
    via ``budget_column_roles.procore_label_to_role_key``. ``pending_budget_changes`` is budget-side
    context only and is never used as the cost-side ``pending_cost_changes``. Selection is DB-only and
    deterministic; output is path-free (no record_key / payload_hash). Returns ``()`` when the table is
    absent (never raises).
    """
    if not _table_exists(conn, "procore_ep_budget_detail_rows"):
        return ()

    # Lazy (keeps module import light; avoids pulling the procore registry unless this path runs).
    from hb_assistant.forecasting.budget_column_roles import procore_label_to_role_key
    from hb_assistant.procore.structured_analytics import SOURCE_QUALITY_RANK

    select_cols = [
        "canonical_budget_code_key",
        "wbs_flat_code",
        # Matrix display fields (Procore-authoritative): budget_code (drives cost_type = last 3 chars),
        # cost_code, and projected_budget. Carried verbatim/trimmed; cost_type is derived downstream.
        "budget_code",
        "cost_code",
        "projected_budget",
        "budget_view_id",
        "record_key",
        "source_quality",
        "payload_seen_last_utc",
        "updated_utc",
        *_BUDGETDETAILS_ROW_AMOUNT_FIELDS,
    ]
    raw = [
        dict(zip(select_cols, r, strict=True))
        for r in conn.execute(
            f"SELECT {', '.join(select_cols)} FROM procore_ep_budget_detail_rows "
            "WHERE project_key = ? AND is_current = 1",
            (project_key,),
        ).fetchall()
    ]
    if not raw:
        return ()

    # Dynamic cost-basis cells for the candidate rows: record_key -> role -> set(canonical values).
    rec_keys = [r["record_key"] for r in raw if r.get("record_key")]
    cells: dict[str, dict[str, set[str]]] = {}
    if rec_keys and _table_exists(conn, "procore_ep_budget_detail_row_cells"):
        placeholders = ", ".join("?" for _ in rec_keys)
        for rec, label, value_decimal_text in conn.execute(
            "SELECT record_key, column_label, value_decimal_text "
            f"FROM procore_ep_budget_detail_row_cells WHERE is_current = 1 AND record_key IN ({placeholders})",
            tuple(rec_keys),
        ).fetchall():
            role = procore_label_to_role_key(label or "")
            if role not in _DYNAMIC_CELL_ROLES:
                continue
            canon = _money_opt(value_decimal_text)
            if canon is None:
                continue
            cells.setdefault(str(rec), {}).setdefault(role, set()).add(canon)

    def _dynamic(rec: str, role: str) -> tuple[str | None, bool]:
        """(value, conflict). Absent -> (None, False); duplicated-distinct -> (None, True)."""
        values = cells.get(rec, {}).get(role)
        if not values:
            return None, False
        if len(values) > 1:
            return None, True
        return next(iter(values)), False

    candidates_by_code: dict[str, list[dict[str, Any]]] = {}
    for r in raw:
        code = str(r.get("canonical_budget_code_key") or r.get("wbs_flat_code") or "").strip()
        if not code:
            continue
        rec = str(r.get("record_key") or "")
        pending_cost_changes, pcc_conflict = _dynamic(rec, "pending_cost_changes")
        commitment_invoiced, ci_conflict = _dynamic(rec, "commitment_invoiced")

        amounts = {f: _money_opt(r.get(f)) for f in _BUDGETDETAILS_ROW_AMOUNT_FIELDS}
        formula_values = {
            "committed_costs": amounts["committed_costs"],
            "erp_direct_costs": amounts["erp_direct_costs"],
            "pending_cost_changes": pending_cost_changes,
            "projected_costs": amounts["projected_costs"],
        }
        missing = [f for f in _FORMULA_FIELDS if formula_values[f] is None]
        formula_variance: str | None = None
        reconciles = False
        if not missing:
            computed = (
                _dec(formula_values["committed_costs"])  # type: ignore[operator]
                + _dec(formula_values["erp_direct_costs"])
                + _dec(formula_values["pending_cost_changes"])
            )
            projected = _dec(formula_values["projected_costs"])
            formula_variance = str((projected - computed).quantize(_CENT))  # type: ignore[operator]
            reconciles = abs(projected - computed) <= _CENT  # type: ignore[operator]

        display_budget_code = str(r.get("budget_code")).strip() if r.get("budget_code") else None
        display_cost_code = str(r.get("cost_code")).strip() if r.get("cost_code") else None
        candidates_by_code.setdefault(code, []).append(
            {
                "budget_code_key": code,
                # Procore-authoritative matrix display fields (trimmed / canonical money).
                "display_budget_code": display_budget_code or None,
                "display_cost_code": display_cost_code or None,
                "display_projected_budget": _money_opt(r.get("projected_budget")),
                "committed_costs": amounts["committed_costs"],
                "erp_direct_costs": amounts["erp_direct_costs"],
                "pending_cost_changes": pending_cost_changes,
                "projected_costs": amounts["projected_costs"],
                "actual_cost": amounts["actual_cost"],
                "job_to_date_costs": amounts["job_to_date_costs"],
                "erp_job_to_date_costs": amounts["erp_job_to_date_costs"],
                "forecast_to_complete": amounts["forecast_to_complete"],
                "estimated_cost_at_completion": amounts["estimated_cost_at_completion"],
                "commitment_invoiced": commitment_invoiced,
                "pending_budget_changes": amounts["pending_budget_changes"],
                "formula_reconciles": reconciles,
                "formula_variance": formula_variance,
                "missing_formula_fields": missing,
                "selected_budget_view_id": (str(r["budget_view_id"]) if r.get("budget_view_id") else None),
                "selected_source_quality": r.get("source_quality"),
                "selection_method": "db_deterministic",
                # internal-only ranking aids (stripped before public output):
                "_rank_quality": SOURCE_QUALITY_RANK.get(r.get("source_quality") or "", 0),
                "_completeness": len(_FORMULA_FIELDS) - len(missing),
                "_recency": str(r.get("payload_seen_last_utc") or r.get("updated_utc") or ""),
                "_view": str(r.get("budget_view_id") or ""),
                "_rec": rec,
                "_dynamic_conflict": pcc_conflict or ci_conflict,
            }
        )

    out: list[dict[str, Any]] = []
    for code in sorted(candidates_by_code):
        cands = candidates_by_code[code]
        # Deterministic tiebreak first (ascending budget_view_id then record_key), then a stable
        # descending sort on the ranking dimensions — Python's stable sort preserves the tiebreak.
        cands.sort(key=lambda c: (c["_view"], c["_rec"]))
        cands.sort(
            key=lambda c: (c["_rank_quality"], 1 if c["formula_reconciles"] else 0, c["_completeness"], c["_recency"]),
            reverse=True,
        )
        selected = cands[0]
        candidate_view_count = len(cands)
        warnings: list[str] = []
        if selected["_dynamic_conflict"]:
            warnings.append("budgetdetails_dynamic_cell_conflict")
        if candidate_view_count > 1:
            warnings.append("budgetdetails_multiple_budget_views_detected")
            warnings.append("budgetdetails_selected_view_unverified")
        # Display-field conflict: mapped Procore rows for this canonical key disagree on a display
        # value. Selection is still deterministic (above); warn so certification can surface it.
        for fld in ("display_budget_code", "display_cost_code", "display_projected_budget"):
            distinct = {c[fld] for c in cands if c[fld] is not None}
            if len(distinct) > 1:
                warnings.append("budgetdetails_display_fields_conflict")
                break

        row = {k: v for k, v in selected.items() if not k.startswith("_")}
        row["candidate_view_count"] = candidate_view_count
        row["selected_formula_reconciles"] = selected["formula_reconciles"]
        row["selection_warnings"] = warnings
        out.append(row)

    return tuple(out)


def _find_project(listing: dict[str, Any], project_key: str) -> dict[str, Any] | None:
    for proj in listing.get("projects", []):
        if proj.get("project_key") == project_key:
            return proj
    return None


def _dedup(items: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)


def build_db_native_source_snapshot(
    project_key: str,
    *,
    db_path: str | Path | None = None,
    source_package: str | None = None,
) -> DbNativeSourceSnapshot:
    """Build the DB-native source snapshot for ``project_key`` from the local DB (read-only).

    Reuses the authoritative readiness/maturity read model and the schedule-date resolver; reads the
    three v59 financial families directly; reports optional enrichment families by availability/count.
    Never reads source packages and never falls back to them.
    """
    from hb_assistant.construction.analytics.forecast_generation_date_defaults import (
        ForecastGenerationDateDefaultsService,
    )
    from hb_assistant.construction.analytics.forecast_generation_project_readmodel import (
        ForecastGenerationProjectReadModelService,
    )
    from hb_assistant.construction.analytics.forecast_runtime_config import resolve_db_path

    resolved = resolve_db_path(str(db_path) if db_path is not None else None)
    if not resolved:
        raise DbNativeSourceSnapshotError("no db_path configured for DB-native source snapshot")

    # 1) Identity + readiness + maturity — authoritative; never recomputed here.
    listing = ForecastGenerationProjectReadModelService(db_path=resolved).list_generation_projects()
    proj = _find_project(listing, project_key)
    if proj is None:
        return _blocked_snapshot(project_key)

    # 2) Forecast window + schedule summary.
    defaults = ForecastGenerationDateDefaultsService(db_path=resolved).resolve(project_key)

    # 3) Read-only connection for the v59 financial reads + enrichment counts.
    conn = sqlite3.connect(f"{Path(resolved).resolve().as_uri()}?mode=ro", uri=True)
    try:
        active_pkg = source_package or _resolve_active_source_package(conn, project_key)
        budget_rows = tuple(
            read_budget_details_from_db(conn, project_key=project_key, source_package=active_pkg)
        )
        cost_rows = tuple(
            read_cost_entries_from_db(conn, project_key=project_key, source_package=active_pkg)
        )
        monthly_rows = tuple(
            read_monthly_actuals_from_db(conn, project_key=project_key, source_package=active_pkg)
        )
        enrichment: dict[str, EnrichmentFamily] = {}
        enrichment_warnings: list[str] = []
        for family, table in _ENRICHMENT_FAMILIES.items():
            count = _count_enrichment_family(conn, table, project_key)
            enrichment[family] = EnrichmentFamily(present=count > 0, row_count=count)
            if count == 0:
                enrichment_warnings.append(f"enrichment_family_unavailable:{family}")
        cost_basis_rows = _read_budgetdetails_cost_basis_inputs(conn, project_key)
    finally:
        conn.close()

    # Readiness carried verbatim from the read model; sparse derives from its maturity (no amount math).
    readiness = {field: proj.get(field) for field in _READINESS_FIELDS}
    readiness["sparse"] = proj.get("forecast_maturity") in _SPARSE_MATURITIES

    reasons = [str(r) for r in (proj.get("readiness_reasons") or [])]
    is_blocked = proj.get("readiness_status") == "blocked"
    blockers = tuple(r for r in reasons if r in _BLOCKING_READINESS_CODES) if is_blocked else ()
    warnings = _dedup(
        [r for r in reasons if r not in _BLOCKING_READINESS_CODES]
        + list(defaults.warnings)
        + enrichment_warnings
    )

    return DbNativeSourceSnapshot(
        schema_version=SCHEMA_VERSION,
        project_key=project_key,
        display_name=proj.get("display_name"),
        project_number=proj.get("project_number"),
        procore_project_id=proj.get("procore_project_id"),
        forecast_window={
            "forecast_start_date": defaults.forecast_start_date,
            "forecast_start_date_basis": defaults.forecast_start_date_basis,
            "forecast_cutoff_date": defaults.forecast_cutoff_date,
            "forecast_cutoff_date_basis": defaults.forecast_cutoff_date_basis,
            "schedule_version_key": defaults.schedule_version_key,
            "schedule_source_status": defaults.schedule_source_status,
        },
        readiness=readiness,
        budget_details=SourceFamily(present=bool(budget_rows), row_count=len(budget_rows), rows=budget_rows),
        cost_entries=SourceFamily(present=bool(cost_rows), row_count=len(cost_rows), rows=cost_rows),
        monthly_actuals=SourceFamily(
            present=bool(monthly_rows), row_count=len(monthly_rows), rows=monthly_rows
        ),
        enrichment=enrichment,
        schedule_summary={
            "schedule_version_key": defaults.schedule_version_key,
            "schedule_data_date": defaults.schedule_data_date,
            "schedule_data_date_basis": defaults.schedule_data_date_basis,
            "schedule_source_status": defaults.schedule_source_status,
        },
        prior_forecast={
            "available": bool(proj.get("has_prior_forecast_output")),
            "latest_status": proj.get("latest_forecast_status"),
            "latest_display": proj.get("latest_forecast_display"),
        },
        warnings=warnings,
        blockers=blockers,
        budgetdetails_cost_basis_inputs=CostBasisInputs(
            present=bool(cost_basis_rows), row_count=len(cost_basis_rows), rows=cost_basis_rows
        ),
        active_source_package=active_pkg,
    )


def _blocked_snapshot(project_key: str) -> DbNativeSourceSnapshot:
    """Snapshot for a project absent from the read model: no identity → explicit blocker."""
    empty = SourceFamily(present=False, row_count=0)
    return DbNativeSourceSnapshot(
        schema_version=SCHEMA_VERSION,
        project_key=project_key,
        display_name=None,
        project_number=None,
        procore_project_id=None,
        forecast_window={
            "forecast_start_date": None,
            "forecast_start_date_basis": None,
            "forecast_cutoff_date": None,
            "forecast_cutoff_date_basis": None,
            "schedule_version_key": None,
            "schedule_source_status": "missing",
        },
        readiness={
            "readiness_status": "blocked",
            "forecast_maturity": "no_financial_basis",
            "confidence_level": "none",
            "forecast_basis": "none",
            "basis_limitations": [],
            "initial_forecast": True,
            "prior_forecast_available": False,
            "sparse": False,
        },
        budget_details=empty,
        cost_entries=empty,
        monthly_actuals=empty,
        enrichment={name: EnrichmentFamily(present=False, row_count=0) for name in _ENRICHMENT_FAMILIES},
        schedule_summary={
            "schedule_version_key": None,
            "schedule_data_date": None,
            "schedule_data_date_basis": None,
            "schedule_source_status": "missing",
        },
        prior_forecast={"available": False, "latest_status": None, "latest_display": None},
        warnings=(),
        blockers=("no_project_identity",),
        active_source_package=None,
    )
