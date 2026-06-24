"""Project a CFR forecast ANALYSIS package's model-run outputs into the v63 tables.

``plan_run_output_projection`` builds planned rows purely from an explicit analysis-package
directory read as plain JSON (no DB access, no CFR import, no latest-glob — explicit path
only), so a dry-run never requires a migrated DB. ``project_run_output`` returns that plan
for a dry-run, or writes it inside a single transaction (idempotent UPSERTs) for ``apply``,
and can optionally read the rows back and prove canonical DB↔package row-equivalence.

Safety (mirrors the v59 source-domain projector): ``apply`` requires an explicit ``db_path``
AND refuses any path that resolves to the live/default DB (``PathPolicy().get_db_path()``);
if path resolution fails, it fails closed rather than risk a live write. The original package
row is stored verbatim in ``raw_json`` and is the authoritative shape for read-parity.

Coverage this phase: the header (``forecast_outputs``), per-code recommendations
(``forecast_output_budget_codes``) from ``forecast_recommendations_by_budget_code.jsonl``, and
the risk register (``forecast_output_risks``) from ``forecast_risk_register.jsonl``. The other
v63 tables ship empty until a follow-on slice.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import open_connection, transaction

from . import output_narrative_builder
from . import output_repository as repo
from .source_domain_engine import is_live_db_path  # reuse the fail-closed live-DB guard

GUARDRAILS = {
    "scope": "v63_run_output_projection_only",
    "tables": "forecast_outputs/forecast_output_budget_codes/forecast_output_risks/forecast_output_narratives",
    "external_systems": "none",
    "forecast_reads": "file_backed_unchanged",
    "cfr_import": False,
    "dry_run_touches_db": False,
    "apply_requires_explicit_db_path": True,
    "apply_refuses_live_db": True,
}

_PLAN_KEYS = (
    "outputs",
    "budget_codes",
    "risks",
    "monthly",
    "probability",
    "changes",
    "staffing",
    "commitment_exposure",
    "schedule_phasing",
    "narratives",
)

RECOMMENDATIONS_FILE = "forecast_recommendations_by_budget_code.jsonl"
RISK_REGISTER_FILE = "forecast_risk_register.jsonl"
PROJECT_SUMMARY_FILE = "summaries/project_forecast_analysis.json"
MANIFEST_FILE = "manifest.json"

# Phase 2c coverage source files (each in its own downstream package).
MONTHLY_FILE = "monthly_forecast_by_budget_code.jsonl"
PROBABILITY_FILE = "probabilistic_final_cost_by_budget_code.jsonl"
CHANGES_FILE = "integrated_change_explanation.jsonl"
STAFFING_FILE = "staffing_plan_monthly_by_budget_code.jsonl"
# Phase 6 coverage source files.
BUDGET_CODES_CANONICAL_FILE = "canonical/budget_codes.jsonl"  # in the context package
SCHEDULE_PHASING_FILE = "schedule_monthly_phasing_by_budget_code.jsonl"  # in the monthly package


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def _money_2dp(value: Any) -> str | None:
    """Quantize a money value (number or string) to a 2dp Decimal string. None passes through."""
    if value is None or value == "":
        return None
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _money_sub(a: Any, b: Any) -> str | None:
    """a - b as a 2dp Decimal string (null treated as 0); None if a is unusable."""
    try:
        da = Decimal(str(a)) if a not in (None, "") else None
        if da is None:
            return None
        db = Decimal(str(b)) if b not in (None, "") else Decimal("0")
        return str((da - db).quantize(Decimal("0.01")))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _money_sum(values: Iterable[Any]) -> tuple[str | None, int]:
    """Sum the parseable money values as a 2dp Decimal string. Returns ``(total, skipped)``.

    Only values that parse as ``Decimal`` contribute; null/blank/unparseable entries are
    skipped and counted. Returns ``(None, skipped)`` when nothing parsed — never fabricates a
    ``0.00`` total from an empty set (no-fuzzy-fill).
    """
    total = Decimal("0")
    parsed = 0
    skipped = 0
    for value in values:
        if value is None or value == "":
            skipped += 1
            continue
        try:
            total += Decimal(str(value))
            parsed += 1
        except (InvalidOperation, TypeError, ValueError):
            skipped += 1
    if parsed == 0:
        return None, skipped
    return str(total.quantize(Decimal("0.01"))), skipped


def _positive_weight(w: Any) -> bool:
    try:
        return Decimal(str(w)) > 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def _output_id(project_key: str, source_package: str) -> str:
    return f"fout-{_hash(f'{project_key}|{source_package}')[:32]}"


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _empty_planned() -> dict[str, list[dict[str, Any]]]:
    return {key: [] for key in _PLAN_KEYS}


# P8 sha-chain. Source files that constitute the analysis package's authoritative content.
_ANALYSIS_SHA_FILES = (MANIFEST_FILE, RECOMMENDATIONS_FILE, RISK_REGISTER_FILE)


def _package_files_sha256(package: Path, files: tuple[str, ...]) -> str | None:
    """sha256 over the named package files (in the given order), or None if none are present.

    A missing file contributes nothing; an empty result (no file found) returns None so the chain
    records the absence rather than a hash of nothing (degraded-not-fatal).
    """
    digest = hashlib.sha256()
    present = False
    for name in files:
        path = package / name
        if path.is_file():
            present = True
            digest.update(path.read_bytes())
    return digest.hexdigest() if present else None


# Per-row fields excluded from the output content sha: the absolute source path (location, not
# content) and the run timestamps (every run differs). Excluding them makes the output sha a stable
# hash of the projected OUTPUT content, identical across runs of the same inputs.
_OUTPUT_SHA_VOLATILE_KEYS = frozenset({"source_path", "created_utc", "updated_utc"})


def _output_content_sha256(planned: dict[str, list[dict[str, Any]]]) -> str:
    """Content sha256 over the projected output detail rows, EXCLUDING the audit-trail narratives.

    Excluding ``narratives`` avoids the lineage row hashing the sibling narratives it sits beside;
    excluding the volatile path/timestamp keys makes it a pure content hash.
    """
    canonical = sorted(
        json.dumps(
            {k: v for k, v in row.items() if k not in _OUTPUT_SHA_VOLATILE_KEYS},
            sort_keys=True,
        )
        for key, rows in planned.items()
        if key != "narratives"
        for row in rows
    )
    return hashlib.sha256("\n".join(canonical).encode("utf-8", "replace")).hexdigest()


# P2b: reserved operator assumption_types that override per-code dollar values, mapped to the
# budget-code typed column they replace.
_OVERRIDE_TYPES = {
    "projected_cost_override": "recommended_projected_cost",
    "cost_to_complete_override": "recommended_cost_to_complete",
}


def _apply_value_overrides(planned, operator_assumptions, output_id, project_key, budget_sum,
                           warnings, now_utc) -> None:
    """Apply operator dollar overrides to per-code typed columns, re-aggregate, record changes.

    Mutates only the matching ``planned["budget_codes"]`` typed column (raw_json untouched ->
    parity-safe), re-derives the header EAC/CTC/variance from the now-effective per-code values,
    and appends one ``operator_value_override`` change row per applied override. Degraded-not-fatal:
    a null/unmatched ``budget_code_key`` or an unparseable value is skipped with a warning.
    """
    by_key: dict[str, dict[str, Any]] = {}
    for code_row in planned["budget_codes"]:
        k = code_row.get("budget_code_key")
        if k is not None and k not in by_key:
            by_key[k] = code_row

    applied = 0
    for a in operator_assumptions:
        column = _OVERRIDE_TYPES.get(a.get("assumption_type") or "")
        if column is None:
            continue  # not an override assumption
        atype = a.get("assumption_type")
        key = a.get("budget_code_key")
        if not key:
            warnings.append(f"operator override '{atype}' skipped: no budget_code_key (not applied project-wide)")
            continue
        code_row = by_key.get(key)
        if code_row is None:
            warnings.append(f"operator override '{atype}' skipped: budget_code_key {key} not in recommendations")
            continue
        new_value = _money_2dp(a.get("value"))
        if new_value is None:
            warnings.append(f"operator override '{atype}' for {key} skipped: value not a parseable amount")
            continue
        original = code_row.get(column)
        code_row[column] = new_value  # typed column only; raw_json stays the original source echo
        planned["changes"].append(
            {
                "id": f"foch-{_hash(f'{output_id}|{key}|operator_value_override')[:32]}",
                "output_id": output_id,
                "project_key": project_key,
                "budget_code_key": key,
                "change_type": "operator_value_override",
                "delta_amount": _money_sub(new_value, original),
                "prior_run_id": None,
                "source_row_number": len(planned["changes"]) + 1,
                "raw_json": json.dumps(
                    {
                        "change_type": "operator_value_override",
                        "assumption_type": atype,
                        "budget_code_key": key,
                        "column": column,
                        "original": original,
                        "override": new_value,
                        "source": a.get("source"),
                    },
                    sort_keys=True,
                ),
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )
        applied += 1

    if not applied:
        return
    # Re-aggregate the header from the now-effective per-code values (budget_sum unchanged).
    eac, _ = _money_sum(r.get("recommended_projected_cost") for r in planned["budget_codes"])
    ctc, _ = _money_sum(r.get("recommended_cost_to_complete") for r in planned["budget_codes"])
    header = planned["outputs"][0]
    header["estimated_final_cost"] = eac
    header["forecast_at_completion"] = eac
    header["cost_to_complete"] = ctc
    header["variance_to_budget"] = (
        _money_sub(eac, budget_sum) if eac is not None and budget_sum is not None else None
    )


def _hydrate_operator_assumptions(
    *, project_key: str, assumptions_db_path: Path | None
) -> list[dict[str, Any]]:
    """Read operator assumptions read-only when value-overrides are enabled.

    Returns ``[]`` when the flag is off, no DB is available, or the read fails (degraded-not-fatal;
    never blocks a run). Assumptions live in the LIVE managed DB (where the operator write surface
    puts them); this opens it ``mode=ro`` only. ``assumptions_db_path`` lets tests point at a seeded
    temp DB (no live access). Mirrors ``decision_support_engine._hydrate_assumptions``.
    """
    from hb_assistant.construction.analytics.forecast_runtime_config import (
        resolve_assumption_overrides_enabled,
    )

    if not resolve_assumption_overrides_enabled():
        return []
    src = assumptions_db_path
    if src is None:
        from hb_assistant.config.path_policy import PathPolicy

        src = PathPolicy().get_db_path()
    try:
        conn = sqlite3.connect(f"file:{Path(src)}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        from . import assumptions_repository as assumptions_repo

        return assumptions_repo.read_operator_assumptions_from_db(conn, project_key=project_key)
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def plan_run_output_projection(
    *,
    analysis_package: Path,
    project_key: str,
    run_id: str | None = None,
    now_utc: str | None = None,
    monthly_package: Path | None = None,
    probability_package: Path | None = None,
    comprehensive_package: Path | None = None,
    staffing_package: Path | None = None,
    context_package: Path | None = None,
    operator_assumptions: list[dict[str, Any]] | None = None,
    explainability_enabled: bool = False,
) -> dict[str, Any]:
    """Build planned v63 run-output rows from an explicit analysis package. No DB access.

    The analysis package is the spine (it mints the header + ``output_id``). When the optional
    downstream package paths are supplied (explicit only, no latest-glob), their per-row outputs
    are projected as child rows under the same ``output_id``: monthly / probability / changes /
    staffing. Omitting a package leaves that table unpopulated — today's behavior.
    """
    now_utc = now_utc or _now()
    analysis_package = Path(analysis_package)
    warnings: list[str] = []
    planned = _empty_planned()

    if not analysis_package.is_dir():
        return {
            "ok": False,
            "reason": "analysis_package_not_found",
            "project_key": project_key,
            "source_package": analysis_package.name,
            "source_package_path": str(analysis_package),
            "run_id": run_id,
            "planned": planned,
            "counts": dict.fromkeys(_PLAN_KEYS, 0),
            "warnings": [f"analysis package directory not found: {analysis_package}"],
        }

    source_package = analysis_package.name
    output_id = _output_id(project_key, source_package)

    manifest = _read_json(analysis_package / MANIFEST_FILE) or {}
    summary = _read_json(analysis_package / PROJECT_SUMMARY_FILE)
    if summary is None:
        warnings.append(f"{PROJECT_SUMMARY_FILE} not found; header raw_json falls back to manifest")
    header_payload = {"manifest": manifest, "project_summary": summary}
    planned["outputs"].append(
        {
            "output_id": output_id,
            "run_id": run_id,
            "project_key": project_key,
            "source_package": source_package,
            "forecast_period": manifest.get("forecast_period") or manifest.get("stamp"),
            "basis_labels": None,
            "estimated_final_cost": None,
            "forecast_at_completion": None,
            "cost_to_complete": None,
            "variance_to_budget": None,
            "variance_to_prior_forecast": None,
            "source_path": str(analysis_package),
            "source_sha256": None,
            "raw_json": json.dumps(header_payload, sort_keys=True),
            "created_utc": now_utc,
            "updated_utc": now_utc,
        }
    )

    rec_rows = _read_jsonl(analysis_package / RECOMMENDATIONS_FILE)
    if not rec_rows:
        warnings.append(f"{RECOMMENDATIONS_FILE} not found or empty; no budget-code outputs")
    for n, row in enumerate(rec_rows, start=1):
        key = row.get("budget_code_key")
        planned["budget_codes"].append(
            {
                "id": f"fobc-{_hash(f'{output_id}|{key or n}')[:32]}",
                "output_id": output_id,
                "project_key": project_key,
                "budget_code_key": key,
                "cost_code": row.get("cost_code"),
                "category": row.get("category"),
                "forecast_action": row.get("forecast_action"),
                "recommended_projected_cost": row.get("recommended_projected_cost"),
                "recommended_cost_to_complete": row.get("recommended_cost_to_complete"),
                "confidence": row.get("confidence"),
                "source_row_number": n,
                "raw_json": json.dumps(row, sort_keys=True),
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )

    # P1: aggregate per-code totals into the header. These are pure functions of the in-memory
    # per-code rows (Decimal, no float) and are persisted to DB on apply; the prior-run delta is
    # added later in the DB-aware apply path. Header raw_json stays a faithful manifest+summary
    # echo (totals live in dedicated columns only).
    eac, eac_skipped = _money_sum(r.get("recommended_projected_cost") for r in rec_rows)
    ctc, ctc_skipped = _money_sum(r.get("recommended_cost_to_complete") for r in rec_rows)
    budget_sum, _budget_skipped = _money_sum(r.get("budget_amount") for r in rec_rows)
    header = planned["outputs"][0]
    header["estimated_final_cost"] = eac
    header["forecast_at_completion"] = eac
    header["cost_to_complete"] = ctc
    header["variance_to_budget"] = (
        _money_sub(eac, budget_sum) if eac is not None and budget_sum is not None else None
    )
    if rec_rows:
        if eac is None:
            warnings.append(
                f"no parseable recommended_projected_cost across {len(rec_rows)} budget codes; "
                "header EAC left null"
            )
        elif eac_skipped:
            warnings.append(
                f"{eac_skipped}/{len(rec_rows)} budget codes missing recommended_projected_cost; "
                "header EAC aggregates the remainder"
            )
        if ctc is None:
            warnings.append(
                f"no parseable recommended_cost_to_complete across {len(rec_rows)} budget codes; "
                "header cost_to_complete left null"
            )
        elif ctc_skipped:
            warnings.append(
                f"{ctc_skipped}/{len(rec_rows)} budget codes missing recommended_cost_to_complete; "
                "header cost_to_complete aggregates the remainder"
            )

    # P2b: operator DOLLAR value-overrides (pre-hydrated; empty/None = no-op). Applied as a guarded
    # post-pass so the no-override path above is byte-identical. Overrides mutate the per-code TYPED
    # columns only (raw_json stays the original source echo -> DB<->package parity unaffected),
    # re-aggregate the header, and append an auditable operator_value_override change row each.
    if operator_assumptions:
        _apply_value_overrides(
            planned, operator_assumptions, output_id, project_key, budget_sum, warnings, now_utc
        )

    risk_rows = _read_jsonl(analysis_package / RISK_REGISTER_FILE)
    if not risk_rows:
        warnings.append(f"{RISK_REGISTER_FILE} not found or empty; no risk outputs")
    for n, row in enumerate(risk_rows, start=1):
        rid = row.get("risk_id")
        planned["risks"].append(
            {
                "id": f"forsk-{_hash(f'{output_id}|{rid or n}')[:32]}",
                "output_id": output_id,
                "project_key": project_key,
                "risk_id": rid,
                "severity": row.get("severity"),
                "budget_code_key": row.get("budget_code_key"),
                "cost_code": row.get("cost_code"),
                "category": row.get("category"),
                "risk_type": row.get("risk_type"),
                "source_row_number": n,
                "raw_json": json.dumps(row, sort_keys=True),
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )

    # ---- Phase 2c coverage: optional downstream packages, projected under output_id -------
    if monthly_package is not None:
        rows = _read_jsonl(Path(monthly_package) / MONTHLY_FILE)
        if not rows:
            warnings.append(f"{MONTHLY_FILE} not found or empty; no monthly outputs")
        for n, row in enumerate(rows, start=1):
            key = row.get("budget_code_key")
            month = row.get("forecast_month")
            planned["monthly"].append(
                {
                    "id": f"fomo-{_hash(f'{output_id}|{key}|{month}')[:32]}",
                    "output_id": output_id,
                    "project_key": project_key,
                    "budget_code_key": key,
                    "month": month,
                    "value": row.get("recommended_month_cost"),
                    "is_actual": 0,
                    "source_row_number": n,
                    "raw_json": json.dumps(row, sort_keys=True),
                    "created_utc": now_utc,
                    "updated_utc": now_utc,
                }
            )

    if probability_package is not None:
        rows = _read_jsonl(Path(probability_package) / PROBABILITY_FILE)
        if not rows:
            warnings.append(f"{PROBABILITY_FILE} not found or empty; no probability outputs")
        for n, row in enumerate(rows, start=1):
            key = row.get("budget_code_key")
            planned["probability"].append(
                {
                    "id": f"fopb-{_hash(f'{output_id}|budget_code|{key}')[:32]}",
                    "output_id": output_id,
                    "project_key": project_key,
                    "scope": "budget_code",
                    "budget_code_key": key,
                    "p10": row.get("simulated_p10"),
                    "p50": row.get("simulated_p50"),
                    "p90": row.get("simulated_p90"),
                    "source_row_number": n,
                    "raw_json": json.dumps(row, sort_keys=True),
                    "created_utc": now_utc,
                    "updated_utc": now_utc,
                }
            )

    if comprehensive_package is not None:
        rows = _read_jsonl(Path(comprehensive_package) / CHANGES_FILE)
        if not rows:
            warnings.append(f"{CHANGES_FILE} not found or empty; no change outputs")
        for n, row in enumerate(rows, start=1):
            key = row.get("budget_code_key")
            planned["changes"].append(
                {
                    "id": f"foch-{_hash(f'{output_id}|{key}|integrated_vs_accepted')[:32]}",
                    "output_id": output_id,
                    "project_key": project_key,
                    "budget_code_key": key,
                    "change_type": "integrated_vs_accepted",
                    "delta_amount": row.get("change_amount"),
                    "prior_run_id": None,
                    "source_row_number": n,
                    "raw_json": json.dumps(row, sort_keys=True),
                    "created_utc": now_utc,
                    "updated_utc": now_utc,
                }
            )

    if staffing_package is not None:
        staffing_rows = _read_jsonl(Path(staffing_package) / STAFFING_FILE)
        if not staffing_rows:
            warnings.append(f"{STAFFING_FILE} not found or empty; no staffing outputs")
        seq = 0
        for row in staffing_rows:
            key = row.get("budget_code_key")
            for item in row.get("staffing_plan_implied_monthly_forecast") or []:
                seq += 1
                month = item.get("forecast_month")
                planned["staffing"].append(
                    {
                        "id": f"fost-{_hash(f'{output_id}|{key}|{month}')[:32]}",
                        "output_id": output_id,
                        "project_key": project_key,
                        "budget_code_key": key,
                        "role": None,
                        "month": month,
                        "headcount": None,
                        "cost_amount": item.get("amount"),
                        "source_row_number": seq,
                        "raw_json": json.dumps({"budget_code_key": key, **item}, sort_keys=True),
                        "created_utc": now_utc,
                        "updated_utc": now_utc,
                    }
                )

    # Phase 6: schedule phasing (month-weights x final cost) — also from the monthly package.
    if monthly_package is not None:
        phasing_rows = _read_jsonl(Path(monthly_package) / SCHEDULE_PHASING_FILE)
        final_cost_by_code: dict[str, Any] = {}
        for mrow in _read_jsonl(Path(monthly_package) / MONTHLY_FILE):
            k = mrow.get("budget_code_key")
            if k is not None and k not in final_cost_by_code:
                final_cost_by_code[k] = mrow.get("recommended_final_cost")
        seq = 0
        for row in phasing_rows:
            if not row.get("used_for_budget_code_phasing"):
                continue
            dist = [
                d
                for d in (row.get("monthly_schedule_weight_distribution") or [])
                if d.get("month") and _positive_weight(d.get("weight"))
            ]
            if not dist:
                continue
            seq += 1
            key = row.get("budget_code_key")
            phase = row.get("schedule_association_type")
            months = sorted(d["month"] for d in dist)
            planned["schedule_phasing"].append(
                {
                    "id": f"fosp-{_hash(f'{output_id}|{key}|{phase}')[:32]}",
                    "output_id": output_id,
                    "project_key": project_key,
                    "budget_code_key": key,
                    "phase": phase,
                    "start_month": months[0],
                    "end_month": months[-1],
                    "amount": _money_2dp(final_cost_by_code.get(key)),
                    "source_row_number": seq,
                    "raw_json": json.dumps(
                        {
                            "budget_code_key": key,
                            "phase": phase,
                            "monthly_schedule_weight_distribution": row.get(
                                "monthly_schedule_weight_distribution"
                            ),
                            "recommended_final_cost": final_cost_by_code.get(key),
                        },
                        sort_keys=True,
                    ),
                    "created_utc": now_utc,
                    "updated_utc": now_utc,
                }
            )

    # Phase 6: commitment exposure (committed - invoiced) from the context budget-code amounts.
    if context_package is not None:
        bc_rows = _read_jsonl(Path(context_package) / BUDGET_CODES_CANONICAL_FILE)
        if not bc_rows:
            warnings.append(
                f"{BUDGET_CODES_CANONICAL_FILE} not found or empty; no commitment exposure"
            )
        seq = 0
        for row in bc_rows:
            amounts = row.get("amounts") or {}
            committed = amounts.get("committed_costs")
            if committed in (None, ""):
                continue
            seq += 1
            key = row.get("budget_code_key")
            invoiced = amounts.get("commitment_invoiced")
            planned["commitment_exposure"].append(
                {
                    "id": f"foce-{_hash(f'{output_id}|{key}')[:32]}",
                    "output_id": output_id,
                    "project_key": project_key,
                    "budget_code_key": key,
                    "committed_amount": _money_2dp(committed),
                    "exposure_amount": _money_sub(committed, invoiced),
                    "source_row_number": seq,
                    "raw_json": json.dumps(
                        {
                            "budget_code_key": key,
                            "committed_costs": committed,
                            "commitment_invoiced": invoiced,
                        },
                        sort_keys=True,
                    ),
                    "created_utc": now_utc,
                    "updated_utc": now_utc,
                }
            )

    # P8 (Gap 9): when explainability is on, set the analysis-package sha on the header (the only
    # place source_sha256 is written) and build the per-output explainability narratives from the
    # now-effective plan (after the override pass + downstream coverage). Flag-off -> none of this
    # runs, so source_sha256 stays None and no narrative rows are planned (byte-identical output).
    # The ``lineage`` narrative needs a DB connection (methodology sha + prior_run_id) and is added
    # later in the apply path.
    if explainability_enabled and planned["outputs"]:
        planned["outputs"][0]["source_sha256"] = _package_files_sha256(
            analysis_package, _ANALYSIS_SHA_FILES
        )
        planned["narratives"].extend(
            output_narrative_builder.build_output_narratives(
                planned=planned,
                output_id=output_id,
                project_key=project_key,
                now_utc=now_utc,
                warning_count=len(warnings),
            )
        )

    counts = {key: len(rows) for key, rows in planned.items()}
    return {
        "ok": True,
        "project_key": project_key,
        "source_package": source_package,
        "source_package_path": str(analysis_package),
        "output_id": output_id,
        "run_id": run_id,
        "planned": planned,
        "counts": counts,
        "warnings": warnings,
    }


def _augment_prior_deltas(
    conn: sqlite3.Connection,
    *,
    planned: dict[str, list[dict[str, Any]]],
    project_key: str,
    output_id: str,
) -> None:
    """DB-aware header augmentation: prior-run delta + a project-level ``current_vs_prior`` row.

    Runs inside the apply transaction BEFORE the current output is written, so the prior-run
    query (most recent ``forecast_outputs`` for the project, excluding the current ``output_id``)
    returns the genuine prior run. No-op when no prior run exists (first run -> delta stays null).
    Patches only dedicated columns + appends one change row, so DB↔package parity (raw_json-only)
    is unaffected.
    """
    if not planned["outputs"]:
        return
    header = planned["outputs"][0]
    current_eac = header.get("estimated_final_cost")
    prior = conn.execute(
        "SELECT run_id, estimated_final_cost FROM forecast_outputs "
        "WHERE project_key = ? AND output_id != ? "
        "ORDER BY created_utc DESC LIMIT 1",
        (project_key, output_id),
    ).fetchone()
    if prior is None:
        return
    prior_run_id, prior_eac = prior[0], prior[1]
    variance = _money_sub(current_eac, prior_eac)
    header["variance_to_prior_forecast"] = variance
    now_utc = header.get("created_utc") or _now()
    payload = {
        "change_type": "current_vs_prior",
        "delta_amount": variance,
        "prior_run_id": prior_run_id,
    }
    planned["changes"].append(
        {
            "id": f"foch-{_hash(f'{output_id}|__current_vs_prior__')[:32]}",
            "output_id": output_id,
            "project_key": project_key,
            "budget_code_key": None,
            "change_type": "current_vs_prior",
            "delta_amount": variance,
            "prior_run_id": prior_run_id,
            "source_row_number": len(planned["changes"]) + 1,
            "raw_json": json.dumps(payload, sort_keys=True),
            "created_utc": now_utc,
            "updated_utc": now_utc,
        }
    )


def _augment_lineage_narrative(
    conn: sqlite3.Connection,
    *,
    plan: dict[str, Any],
    run_id: str | None,
    context_package: Path | None,
    output_sha256: str,
) -> None:
    """Append + write the P8 ``lineage`` narrative (the context→analysis→output sha chain).

    Runs in the apply transaction AFTER ``apply_plan``, so it can read the prior-run linkage (the
    ``current_vs_prior`` change row added by ``_augment_prior_deltas``) and the model-version
    provenance (``forecast_run_model_versions``, populated only when P6 governance ran into this
    same temp DB). Every upstream sha / stamp degrades to ``None`` when its package or provenance is
    absent — never blocks the run.
    """
    planned = plan["planned"]
    if not planned["outputs"]:
        return
    header = planned["outputs"][0]
    now_utc = header.get("created_utc") or _now()

    context_sha = (
        _package_files_sha256(Path(context_package), (BUDGET_CODES_CANONICAL_FILE,))
        if context_package is not None
        else None
    )
    prior_run_id = next(
        (
            c.get("prior_run_id")
            for c in planned["changes"]
            if c.get("change_type") == "current_vs_prior"
        ),
        None,
    )
    methodology_sha256: str | None = None
    accuracy_package_stamp: str | None = None
    if run_id is not None:
        try:
            row = conn.execute(
                "SELECT methodology_sha256, accuracy_package_stamp "
                "FROM forecast_run_model_versions WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        except sqlite3.Error:
            row = None
        if row is not None:
            methodology_sha256, accuracy_package_stamp = row[0], row[1]

    lineage = output_narrative_builder.build_lineage_narrative(
        output_id=plan["output_id"],
        project_key=header["project_key"],
        now_utc=now_utc,
        source_row_number=len(planned["narratives"]) + 1,
        context_sha256=context_sha,
        analysis_sha256=header.get("source_sha256"),
        output_sha256=output_sha256,
        methodology_sha256=methodology_sha256,
        accuracy_package_stamp=accuracy_package_stamp,
        prior_run_id=prior_run_id,
    )
    planned["narratives"].append(lineage)
    repo.upsert_output_narrative(conn, lineage)


def project_run_output(
    *,
    analysis_package: Path,
    project_key: str,
    db_path: Path | None = None,
    apply: bool = False,
    parity: bool = False,
    run_id: str | None = None,
    now_utc: str | None = None,
    monthly_package: Path | None = None,
    probability_package: Path | None = None,
    comprehensive_package: Path | None = None,
    staffing_package: Path | None = None,
    context_package: Path | None = None,
    assumptions_db_path: Path | None = None,
) -> dict[str, Any]:
    """Plan (dry-run) or plan+write (apply) run-output rows; optionally prove DB parity.

    P2b: when ``HB_FORECAST_ASSUMPTION_OVERRIDES_ENABLED`` is set, operator dollar overrides are read
    read-only (``mode=ro``) from ``assumptions_db_path`` or, by default, the live managed DB, and
    threaded into the planner — in both dry-run and apply paths (so a dry-run previews the effect).
    The flag is off by default, in which case nothing is read and output is byte-identical. The
    ``apply``/``is_live_db_path`` write-guards on ``db_path`` are unchanged; this read is a separate
    read-only connection.
    """
    from hb_assistant.construction.analytics.forecast_runtime_config import (
        resolve_explainability_enabled,
    )

    explainability_enabled = resolve_explainability_enabled()
    operator_assumptions = _hydrate_operator_assumptions(
        project_key=project_key, assumptions_db_path=assumptions_db_path
    )
    plan = plan_run_output_projection(
        analysis_package=analysis_package,
        project_key=project_key,
        run_id=run_id,
        now_utc=now_utc,
        monthly_package=monthly_package,
        probability_package=probability_package,
        comprehensive_package=comprehensive_package,
        staffing_package=staffing_package,
        context_package=context_package,
        operator_assumptions=operator_assumptions,
        explainability_enabled=explainability_enabled,
    )
    plan["guardrails"] = GUARDRAILS

    if not apply:
        plan["mode"] = "dry_run"
        if parity:
            # Fail closed: a dry-run wrote nothing, so there is no DB to compare against.
            plan["ok"] = False
            plan["parity"] = {
                "requested": True,
                "proven": False,
                "reason": "parity_requires_applied_db",
            }
            plan["warnings"].append(
                "--parity needs --apply against an explicit temp DB; dry-run proves no DB parity"
            )
        return plan

    if db_path is None:
        plan["mode"] = "apply"
        plan["ok"] = False
        plan["reason"] = "apply_requires_explicit_db_path"
        plan["warnings"].append(
            "--apply refuses the default live DB; pass --db-path to a temp v63 DB"
        )
        return plan

    if is_live_db_path(db_path):
        plan["mode"] = "apply"
        plan["ok"] = False
        plan["reason"] = "apply_refuses_live_db"
        plan["warnings"].append(
            "--db-path resolves to the live/default DB (or could not be resolved); refusing to write"
        )
        return plan

    written: dict[str, int] = dict.fromkeys(_PLAN_KEYS, 0)
    if plan["ok"]:
        with open_connection(Path(db_path)) as conn, transaction(conn):
            # DB-aware: resolve the prior-run delta before writing the current output.
            _augment_prior_deltas(
                conn,
                planned=plan["planned"],
                project_key=project_key,
                output_id=plan["output_id"],
            )
            written = repo.apply_plan(conn, plan["planned"])
            # P8: the lineage narrative needs the written rows (output sha) + the prior-run linkage,
            # so it is built and written here, after apply_plan, and folded into the plan + counts.
            if explainability_enabled:
                _augment_lineage_narrative(
                    conn,
                    plan=plan,
                    run_id=run_id,
                    context_package=context_package,
                    output_sha256=_output_content_sha256(plan["planned"]),
                )
                written["narratives"] = len(plan["planned"]["narratives"])
    plan["mode"] = "apply"
    plan["written"] = written

    if parity:
        plan["parity"] = _prove_parity(
            db_path=Path(db_path),
            output_id=plan["output_id"],
            planned=plan["planned"],
        )
        if not plan["parity"]["proven"]:
            plan["ok"] = False
    return plan


def _norm(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(json.dumps(r, sort_keys=True) for r in rows)


def _prove_parity(
    *,
    db_path: Path,
    output_id: str,
    planned: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Read rows back and compare (order-independent) to the projected package rows."""
    readers = {
        "outputs": repo.read_output_header_from_db,
        "budget_codes": repo.read_output_budget_codes_from_db,
        "risks": repo.read_output_risks_from_db,
        "monthly": repo.read_output_monthly_from_db,
        "probability": repo.read_output_probability_from_db,
        "changes": repo.read_output_changes_from_db,
        "staffing": repo.read_output_staffing_from_db,
        "commitment_exposure": repo.read_output_commitment_exposure_from_db,
        "schedule_phasing": repo.read_output_schedule_phasing_from_db,
        "narratives": repo.read_output_narratives_from_db,
    }
    per_table: dict[str, Any] = {}
    proven = True
    with open_connection(db_path) as conn:
        for kind, reader in readers.items():
            db_rows = reader(conn, output_id=output_id)
            src_rows = [json.loads(p["raw_json"]) for p in planned.get(kind, [])]
            match = _norm(db_rows) == _norm(src_rows)
            per_table[kind] = {
                "db_rows": len(db_rows),
                "source_rows": len(src_rows),
                "match": match,
            }
            proven = proven and match
    return {"requested": True, "proven": proven, "by_table": per_table}
