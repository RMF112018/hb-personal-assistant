"""P8 (Gap 9): build the explainability / audit-trail narrative rows for a forecast run.

Pure and deterministic — no DB access, no LLM, no CFR import. Every row is derived from the
already-planned v63 rows (``planned``) the output projector built, so turning the P8 flag on adds
an audit trail without changing any other table's ``raw_json`` (DB↔package parity unaffected).

Five narrative ``scope``s land in ``forecast_output_narratives``:

* ``project``       — one header row: effective EAC/FAC/CTC/variance + code/risk/override/warning counts.
* ``budget_code``   — one row per recommendation: the per-code numbers, action, confidence, risk count.
* ``human_override``— one row per operator dollar override (projected from the ``operator_value_override``
                      change rows already in ``planned["changes"]``).
* ``source_qa``     — one summary row: null / zero / duplicate budget-code checks + staleness signal.
* ``lineage``       — one row: the context→analysis→output package-sha256 chain (built by the engine in
                      the apply path, since it needs a DB connection — see ``build_lineage_narrative``).

The first four are pure functions of ``planned`` and are built in the planning phase; ``lineage`` is
assembled separately because it needs DB-side provenance. All share the deterministic id scheme and a
single monotonic ``source_row_number`` sequence so the parity read order is total.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any

_OVERRIDE_CHANGE_TYPE = "operator_value_override"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def _narrative_id(output_id: str, scope: str, narrative_key: str) -> str:
    return f"fonr-{_hash(f'{output_id}|{scope}|{narrative_key}')[:32]}"


def _is_zero(value: Any) -> bool:
    try:
        return Decimal(str(value)) == 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def _is_blank(value: Any) -> bool:
    return value is None or value == ""


def _row(
    *,
    output_id: str,
    project_key: str,
    scope: str,
    narrative_key: str,
    source_row_number: int,
    payload: dict[str, Any],
    now_utc: str,
) -> dict[str, Any]:
    """Assemble one narrative row; ``raw_json`` carries the structured payload (sorted keys)."""
    return {
        "id": _narrative_id(output_id, scope, narrative_key),
        "output_id": output_id,
        "project_key": project_key,
        "scope": scope,
        "narrative_key": narrative_key,
        "source_row_number": source_row_number,
        "raw_json": json.dumps(payload, sort_keys=True),
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }


def build_output_narratives(
    *,
    planned: dict[str, list[dict[str, Any]]],
    output_id: str,
    project_key: str,
    now_utc: str,
    warning_count: int,
) -> list[dict[str, Any]]:
    """Build the project / budget_code / human_override / source_qa narrative rows (pure).

    ``warning_count`` is the planner's warning total (surfaced in the project narrative). Reads only
    ``planned`` — must be called AFTER the operator override pass so the header + change rows are
    already effective.
    """
    rows: list[dict[str, Any]] = []
    seq = 0

    header = planned["outputs"][0] if planned["outputs"] else {}
    budget_codes = planned["budget_codes"]
    risks = planned["risks"]
    override_changes = [
        c for c in planned["changes"] if c.get("change_type") == _OVERRIDE_CHANGE_TYPE
    ]

    risk_count_by_code: dict[str, int] = {}
    for r in risks:
        k = r.get("budget_code_key")
        if k is not None:
            risk_count_by_code[k] = risk_count_by_code.get(k, 0) + 1
    overridden_keys = {c.get("budget_code_key") for c in override_changes}

    # ---- project narrative -----------------------------------------------------------------
    seq += 1
    rows.append(
        _row(
            output_id=output_id,
            project_key=project_key,
            scope="project",
            narrative_key="header",
            source_row_number=seq,
            now_utc=now_utc,
            payload={
                "scope": "project",
                "estimated_final_cost": header.get("estimated_final_cost"),
                "forecast_at_completion": header.get("forecast_at_completion"),
                "cost_to_complete": header.get("cost_to_complete"),
                "variance_to_budget": header.get("variance_to_budget"),
                "budget_code_count": len(budget_codes),
                "risk_count": len(risks),
                "override_count": len(override_changes),
                "warning_count": warning_count,
                "narrative": (
                    f"Forecast EAC {header.get('estimated_final_cost')} across "
                    f"{len(budget_codes)} budget code(s); variance to budget "
                    f"{header.get('variance_to_budget')}; {len(risks)} risk(s); "
                    f"{len(override_changes)} operator override(s); {warning_count} warning(s)."
                ),
            },
        )
    )

    # ---- per-budget-code narratives --------------------------------------------------------
    for code in budget_codes:
        key = code.get("budget_code_key")
        narrative_key = key if key is not None else f"__row_{code.get('source_row_number')}__"
        seq += 1
        rows.append(
            _row(
                output_id=output_id,
                project_key=project_key,
                scope="budget_code",
                narrative_key=narrative_key,
                source_row_number=seq,
                now_utc=now_utc,
                payload={
                    "scope": "budget_code",
                    "budget_code_key": key,
                    "recommended_projected_cost": code.get("recommended_projected_cost"),
                    "recommended_cost_to_complete": code.get("recommended_cost_to_complete"),
                    "forecast_action": code.get("forecast_action"),
                    "confidence": code.get("confidence"),
                    "risk_count": risk_count_by_code.get(key, 0),
                    "overridden": key in overridden_keys,
                    "narrative": (
                        f"Budget code {key}: projected cost "
                        f"{code.get('recommended_projected_cost')}, action "
                        f"{code.get('forecast_action')}, confidence {code.get('confidence')}"
                        + (", operator-overridden" if key in overridden_keys else "")
                        + "."
                    ),
                },
            )
        )

    # ---- human-override audit narratives ---------------------------------------------------
    for change in override_changes:
        detail = json.loads(change.get("raw_json") or "{}")
        key = change.get("budget_code_key")
        narrative_key = key if key is not None else f"__override_{change.get('source_row_number')}__"
        seq += 1
        rows.append(
            _row(
                output_id=output_id,
                project_key=project_key,
                scope="human_override",
                narrative_key=narrative_key,
                source_row_number=seq,
                now_utc=now_utc,
                payload={
                    "scope": "human_override",
                    "budget_code_key": key,
                    "assumption_type": detail.get("assumption_type"),
                    "column": detail.get("column"),
                    "original": detail.get("original"),
                    "override": detail.get("override"),
                    "delta_amount": change.get("delta_amount"),
                    "source": detail.get("source"),
                    "applied_utc": now_utc,
                    "narrative": (
                        f"Operator override on {key}: {detail.get('column')} "
                        f"{detail.get('original')} -> {detail.get('override')} "
                        f"(delta {change.get('delta_amount')}, source {detail.get('source')})."
                    ),
                },
            )
        )

    # ---- source-data QA rationale ----------------------------------------------------------
    null_cost = sum(1 for c in budget_codes if _is_blank(c.get("recommended_projected_cost")))
    zero_cost = sum(1 for c in budget_codes if _is_zero(c.get("recommended_projected_cost")))
    seen: dict[str, int] = {}
    for c in budget_codes:
        k = c.get("budget_code_key")
        if k is not None:
            seen[k] = seen.get(k, 0) + 1
    dup_keys = sorted(k for k, n in seen.items() if n > 1)
    forecast_period = header.get("forecast_period")
    seq += 1
    rows.append(
        _row(
            output_id=output_id,
            project_key=project_key,
            scope="source_qa",
            narrative_key="analysis_package",
            source_row_number=seq,
            now_utc=now_utc,
            payload={
                "scope": "source_qa",
                "budget_code_count": len(budget_codes),
                "null_projected_cost_count": null_cost,
                "zero_projected_cost_count": zero_cost,
                "duplicate_budget_code_keys": dup_keys,
                "forecast_period": forecast_period,
                "narrative": (
                    f"Source QA over {len(budget_codes)} budget code(s): {null_cost} null "
                    f"and {zero_cost} zero projected-cost value(s), {len(dup_keys)} duplicate "
                    f"budget-code key(s); forecast period {forecast_period}."
                ),
            },
        )
    )

    return rows


def build_lineage_narrative(
    *,
    output_id: str,
    project_key: str,
    now_utc: str,
    source_row_number: int,
    context_sha256: str | None,
    analysis_sha256: str | None,
    output_sha256: str,
    methodology_sha256: str | None,
    accuracy_package_stamp: str | None,
    prior_run_id: str | None,
) -> dict[str, Any]:
    """Build the single ``lineage`` narrative: the context→analysis→output package-sha256 chain.

    Called by the engine in the apply path (the methodology sha + prior_run_id need a DB read).
    Missing upstream shas pass through as ``None`` (degraded-not-fatal).
    """
    return _row(
        output_id=output_id,
        project_key=project_key,
        scope="lineage",
        narrative_key="package_sha256_chain",
        source_row_number=source_row_number,
        now_utc=now_utc,
        payload={
            "scope": "lineage",
            "context_sha256": context_sha256,
            "analysis_sha256": analysis_sha256,
            "output_sha256": output_sha256,
            "methodology_sha256": methodology_sha256,
            "accuracy_package_stamp": accuracy_package_stamp,
            "prior_run_id": prior_run_id,
            "narrative": (
                "Package sha256 chain context="
                f"{context_sha256} analysis={analysis_sha256} output={output_sha256}"
                + (f" methodology={methodology_sha256}" if methodology_sha256 else "")
                + (f" prior_run={prior_run_id}" if prior_run_id else "")
                + "."
            ),
        },
    )
