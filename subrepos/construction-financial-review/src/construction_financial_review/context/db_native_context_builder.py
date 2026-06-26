"""Package-free DB-native forecast context builder (Phase D).

Builds a typed, in-memory forecast context object from the plain dict produced by the HB DB-native
source snapshot (``snapshot.public()``) — with NO source-package files, NO context-package directory,
and NO TWN/Tropical/Synology constants. It sits BESIDE the legacy file-coupled
``generate_forecast_context_package.build_context_package`` (which is untouched).

Scope (Phase D): the builder produces the **financial spine** (budget codes, per-code budget+actuals
context, project totals, validation conclusion, data-quality/gap register, provenance) deterministically
from the three DB-native financial families (budget_details / cost_entries / monthly_actuals). The
owner / Procore / owner-crosswalk families are **not normalized here** — they are not yet DB-native
input rows; the builder records them as structured ``available=false`` blocks + coded
``*_source_unavailable`` warnings (Phase E blockers). This is NOT byte- or full-semantic parity with
the legacy package, and it does NOT wire into the analysis layer (Phase E).

Purity: this module imports no ``hb_assistant`` and references no legacy package constant
(``SRC_FILES`` / ``TWN_DIR`` / ``OWNER_DIR`` / ``PROCORE_DIR`` / ``_DEFAULT_DATA_ROOT``) — it consumes
only the plain snapshot dict. See ADR 316.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

# Per-code budget amount fields surfaced from a budget_details row when present (missing -> null,
# explicit "0.00" -> a real zero). Names mirror the legacy budget_code_forecast_context block.
_BUDGET_AMOUNT_FIELDS = (
    "original_budget_amount",
    "revised_budget",
    "approved_cos",
    "pending_budget_changes",
    "projected_budget",
    "projected_costs",
    "committed_costs",
    "estimated_cost_at_completion",
)

# Optional source families that are not yet DB-native input rows (Phase E). Each becomes an
# available=false block + a coded warning; their absence never fails the build.
_UNAVAILABLE_OPTIONAL_FAMILIES = (
    ("owner_pay_app", "owner_pay_app_source_unavailable"),
    ("procore_pay_app", "procore_pay_app_source_unavailable"),
    ("owner_crosswalk", "owner_crosswalk_unavailable"),
)

_BLOCKING_CODES = ("no_project_identity", "no_financial_basis")


class DbNativeContextError(RuntimeError):
    """Fail-closed: a curated, path-free coded reason the context cannot be built (required basis)."""


def _dec(value: Any) -> Decimal | None:
    """Defensive Decimal parse. None/'' -> None; unparseable -> None (never raises)."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _canon(amount: Decimal) -> str:
    """Canonical 2-dp money string (deterministic)."""
    return str(amount.quantize(Decimal("0.01")))


def _canon_opt(value: Any) -> str | None:
    """Canonical money string for an optional amount: missing/unparseable -> None, '0.00' -> '0.00'."""
    parsed = _dec(value)
    return _canon(parsed) if parsed is not None else None


def _amount_field(row: dict[str, Any], field: str) -> Any:
    """Resolve a per-code money field from the DB-native budget_details row.

    The normalized ``forecast_budget_details`` rows nest every money field under a top-level
    ``amounts`` object (the original cost-forecast JSONL shape) — so read from ``row["amounts"]``
    first. Fall back to a top-level ``row[field]`` for any flattened shape (e.g. legacy-style
    fixtures). ``amounts`` wins when present.
    """
    amounts = row.get("amounts")
    if isinstance(amounts, dict) and field in amounts:
        return amounts.get(field)
    return row.get(field)


# Per-code cost-basis fields carried verbatim from the snapshot's selected BudgetDetails view.
_COST_BASIS_BLOCK_FIELDS = (
    "committed_costs",
    "erp_direct_costs",
    "pending_cost_changes",
    "projected_costs",
    "actual_cost",
    "commitment_invoiced",
    "estimated_cost_at_completion",
    "formula_reconciles",
    "formula_variance",
    "missing_formula_fields",
    "selected_budget_view_id",
    "selection_warnings",
)


def _cost_basis_block(row: dict[str, Any] | None) -> dict[str, Any]:
    """Per-code DB-native BudgetDetails cost-basis block. Absent -> coded unavailable (never raises)."""
    if not row:
        return {"available": False, "reason": "budgetdetails_cost_basis_inputs_unavailable"}
    block: dict[str, Any] = {"available": True, "source": "db_native_budgetdetails"}
    for f in _COST_BASIS_BLOCK_FIELDS:
        block[f] = row.get(f)
    return block


def _matrix_display_block(spine_row: dict[str, Any], cost_basis_row: dict[str, Any] | None) -> dict[str, Any]:
    """Per-code matrix DISPLAY fields, separating the Procore-authoritative display value from the
    financial-spine calculation basis (revision 3).

    - budget_code / cost_code / projected_budget_display come from the selected Procore row when one
      maps to this canonical budget code (cost_type is derived downstream from budget_code).
    - projected_budget_calculation_basis is always the financial-spine projected_budget (engine
      continuity); may be None when the spine lacks it (the persistence layer coalesces for NOT NULL).
    - source_warning is warning-grade: a Procore/spine divergence, a missing Procore projected_budget,
      or no mapped Procore row at all — never a hard failure here.
    """
    spine_cost_code = spine_row.get("cost_code")
    spine_pb = _canon_opt(_amount_field(spine_row, "projected_budget"))
    if cost_basis_row:
        budget_code = cost_basis_row.get("display_budget_code")
        cost_code = cost_basis_row.get("display_cost_code") or spine_cost_code
        procore_pb = cost_basis_row.get("display_projected_budget")
        if procore_pb is not None:
            display_pb = procore_pb
            display_source = "procore_ep_budget_detail_rows"
            warning = (
                "projected_budget_source_mismatch"
                if spine_pb is not None and spine_pb != procore_pb
                else None
            )
        else:
            # Procore row mapped but carries no projected_budget — display the spine value, flagged.
            display_pb = spine_pb
            display_source = "forecast_budget_details"
            warning = "procore_projected_budget_missing"
    else:
        # No Procore row maps to this canonical key — fall back to the spine, flagged not-authoritative.
        budget_code = None
        cost_code = spine_cost_code
        display_pb = spine_pb
        display_source = "forecast_budget_details"
        warning = "display_row_not_procore_authoritative"
    return {
        "budget_code": budget_code,
        "cost_code": cost_code,
        "projected_budget_display": display_pb,
        "projected_budget_display_source": display_source,
        "projected_budget_calculation_basis": spine_pb,
        "projected_budget_calculation_source": "forecast_budget_details",
        "source_warning": warning,
    }


@dataclass(frozen=True)
class DbNativeContextInput:
    """Plain, path-free input to the package-free builder, derived from ``snapshot.public()``.

    Optional ``owner_line_items`` / ``procore_line_items`` are accepted for forward-compatibility
    (Phase E) but are NOT derived in Phase D.
    """

    project_key: str
    display_name: str | None
    project_number: str | None
    procore_project_id: str | None
    forecast_window: dict[str, Any]
    readiness: dict[str, Any]
    budget_details: list[dict[str, Any]]
    cost_entries: list[dict[str, Any]]
    monthly_actuals: list[dict[str, Any]]
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    owner_line_items: list[dict[str, Any]] = field(default_factory=list)
    procore_line_items: list[dict[str, Any]] = field(default_factory=list)
    # DB-native BudgetDetails cost-basis formula inputs (Phase E2), one selected view per budget code.
    budgetdetails_cost_basis_inputs: list[dict[str, Any]] = field(default_factory=list)


def context_input_from_snapshot_public(public: dict[str, Any]) -> DbNativeContextInput:
    """Map a Phase C ``DbNativeSourceSnapshot.public()`` dict into a builder input (plain data only)."""
    fin = public.get("financial_basis") or {}

    def _rows(name: str) -> list[dict[str, Any]]:
        fam = fin.get(name) or {}
        return list(fam.get("rows") or [])

    cost_basis = public.get("budgetdetails_cost_basis_inputs") or {}

    return DbNativeContextInput(
        project_key=str(public.get("project_key") or ""),
        display_name=public.get("display_name"),
        project_number=public.get("project_number"),
        procore_project_id=public.get("procore_project_id"),
        forecast_window=dict(public.get("forecast_window") or {}),
        readiness=dict(public.get("readiness") or {}),
        budget_details=_rows("budget_details"),
        cost_entries=_rows("cost_entries"),
        monthly_actuals=_rows("monthly_actuals"),
        blockers=[str(b) for b in (public.get("blockers") or [])],
        warnings=[str(w) for w in (public.get("warnings") or [])],
        budgetdetails_cost_basis_inputs=list(cost_basis.get("rows") or []),
    )


@dataclass(frozen=True)
class DbNativeForecastContext:
    """Typed, in-memory, package-free forecast context. ``public()`` is the redaction-safe contract."""

    project_key: str
    display_name: str | None
    project_number: str | None
    procore_project_id: str | None
    forecast_window: dict[str, Any]
    readiness: dict[str, Any]
    budget_codes: tuple[str, ...]
    budget_code_context: tuple[dict[str, Any], ...]
    project_totals: dict[str, Any]
    optional_source_availability: dict[str, Any]
    data_quality: dict[str, Any]
    provenance: dict[str, Any]
    conclusion: str

    def public(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "project_key": self.project_key,
            "display_name": self.display_name,
            "project_number": self.project_number,
            "procore_project_id": self.procore_project_id,
            "forecast_window": dict(self.forecast_window),
            "readiness": dict(self.readiness),
            "budget_codes": list(self.budget_codes),
            "budget_code_context": [dict(r) for r in self.budget_code_context],
            "project_totals": dict(self.project_totals),
            "optional_source_availability": dict(self.optional_source_availability),
            "data_quality": dict(self.data_quality),
            "provenance": dict(self.provenance),
            "conclusion": self.conclusion,
        }


def build_db_native_context(source: DbNativeContextInput) -> DbNativeForecastContext:
    """Build the package-free financial-spine context. Fail closed only on required-basis issues."""
    # Fail closed: required basis. Missing optional families never raise (they lower completeness).
    blocking = [b for b in source.blockers if b in _BLOCKING_CODES]
    no_financial_rows = not (source.budget_details or source.cost_entries or source.monthly_actuals)
    if blocking or no_financial_rows:
        reason = blocking[0] if blocking else "no_financial_basis"
        raise DbNativeContextError(f"forecast_context_{reason}")

    warnings: list[str] = list(source.warnings)

    # DB-native BudgetDetails cost-basis formula inputs, indexed by budget_code_key (Phase E2).
    cost_basis_by_key: dict[str, dict[str, Any]] = {
        str(r.get("budget_code_key") or ""): r for r in source.budgetdetails_cost_basis_inputs
    }
    cost_basis_unavailable = 0

    # Index actuals by budget_code_key (Decimal sums; missing amounts -> warning, not a crash).
    actuals_by_key: dict[str, Decimal] = {}
    entry_count_by_key: dict[str, int] = {}
    missing_amount = 0
    for row in source.cost_entries:
        key = str(row.get("budget_code_key") or "")
        entry_count_by_key[key] = entry_count_by_key.get(key, 0) + 1
        amount = _dec(row.get("amount"))
        if amount is None:
            missing_amount += 1
            continue
        actuals_by_key[key] = actuals_by_key.get(key, Decimal("0")) + amount
    if missing_amount:
        warnings.append("cost_entries_missing_amount")

    monthly_by_key: dict[str, list[dict[str, Any]]] = {}
    for row in source.monthly_actuals:
        key = str(row.get("budget_code_key") or "")
        amount = _dec(row.get("amount"))
        monthly_by_key.setdefault(key, []).append(
            {
                "month": row.get("month"),
                "type": row.get("type"),
                "amount": _canon(amount) if amount is not None else None,
            }
        )
    for key in monthly_by_key:
        monthly_by_key[key].sort(key=lambda m: (str(m.get("month") or ""), str(m.get("type") or "")))

    # Per-budget-code financial context (deterministic, sorted by budget_code_key).
    budget_codes: list[str] = []
    code_context: list[dict[str, Any]] = []
    total_revised = Decimal("0")
    total_actual = Decimal("0")
    for row in sorted(source.budget_details, key=lambda r: str(r.get("budget_code_key") or "")):
        key = str(row.get("budget_code_key") or "")
        budget_codes.append(key)
        budget_amounts = {f: _canon_opt(_amount_field(row, f)) for f in _BUDGET_AMOUNT_FIELDS}
        revised = _dec(_amount_field(row, "revised_budget"))
        if revised is not None:
            total_revised += revised
        actual = actuals_by_key.get(key, Decimal("0"))
        total_actual += actual
        code_context.append(
            {
                "budget_code_key": key,
                "cost_code": row.get("cost_code"),
                "category": row.get("category"),
                "budget_amounts": budget_amounts,
                "actuals": {
                    "actual_cost_to_date": _canon(actual),
                    "actual_entry_count": entry_count_by_key.get(key, 0),
                    "monthly_actuals": monthly_by_key.get(key, []),
                },
                # Phase E2: DB-native BudgetDetails cost-basis formula inputs (one selected view).
                "cost_basis_inputs": _cost_basis_block(cost_basis_by_key.get(key)),
                # Monthly-matrix display fields (Procore-authoritative; spine fallback + warnings).
                "matrix_display": _matrix_display_block(row, cost_basis_by_key.get(key)),
                # Phase E: not yet DB-native source rows.
                "owner_pay_app": {"available": False},
                "procore_subcontractor_pay_apps": {"available": False},
                "commitments": {"available": False},
            }
        )
        if key not in cost_basis_by_key:
            cost_basis_unavailable += 1

    # Cost entries whose budget_code_key isn't in the canonical budget universe.
    code_set = set(budget_codes)
    unmatched = sorted(k for k in actuals_by_key if k and k not in code_set)
    if unmatched:
        warnings.append("cost_entries_unmatched_budget_code")

    if cost_basis_unavailable:
        warnings.append("budgetdetails_cost_basis_inputs_unavailable")

    # Optional families unavailable by design in Phase D.
    optional_availability: dict[str, Any] = {}
    for family, code in _UNAVAILABLE_OPTIONAL_FAMILIES:
        optional_availability[family] = {"available": False, "row_count": 0, "reason": code}
        warnings.append(code)

    warnings = _dedup(warnings)

    provenance = {
        "row_counts_by_family": {
            "budget_details": len(source.budget_details),
            "cost_entries": len(source.cost_entries),
            "monthly_actuals": len(source.monthly_actuals),
        },
        "source_families_present": [
            name
            for name, rows in (
                ("budget_details", source.budget_details),
                ("cost_entries", source.cost_entries),
                ("monthly_actuals", source.monthly_actuals),
            )
            if rows
        ],
        "source_families_unavailable": [code for _, code in _UNAVAILABLE_OPTIONAL_FAMILIES],
    }

    data_quality = {
        "warnings": warnings,
        "gaps": [{"reason": code, "severity": "info"} for _, code in _UNAVAILABLE_OPTIONAL_FAMILIES],
        "unmatched_cost_entry_budget_codes": len(unmatched),
        "cost_entries_missing_amount": missing_amount,
    }

    conclusion = (
        "forecast_context_ready_db_native_with_warnings"
        if warnings
        else "forecast_context_ready_db_native"
    )

    return DbNativeForecastContext(
        project_key=source.project_key,
        display_name=source.display_name,
        project_number=source.project_number,
        procore_project_id=source.procore_project_id,
        forecast_window=dict(source.forecast_window),
        readiness=dict(source.readiness),
        budget_codes=tuple(budget_codes),
        budget_code_context=tuple(code_context),
        project_totals={
            "budget_code_count": len(budget_codes),
            "cost_entry_count": len(source.cost_entries),
            "monthly_actual_count": len(source.monthly_actuals),
            "total_revised_budget": _canon(total_revised),
            "total_actual_cost_to_date": _canon(total_actual),
        },
        optional_source_availability=optional_availability,
        data_quality=data_quality,
        provenance=provenance,
        conclusion=conclusion,
    )


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
