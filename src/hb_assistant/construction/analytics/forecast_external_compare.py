"""Comparison + accuracy engine for external-forecast evaluation (Implementation Phase 4).

Takes the validated, mapped external rows and compares the external forecast (per canonical
budget code) against each available baseline — actuals / current budget / ERP-JTD (v59 DB),
backend model EAC / P50 / P80 (selected backend package), and the most recent prior external
forecast. Emits per-code comparison rows and per-baseline accuracy metrics. Pure composition over
``forecast_external_metrics`` and ``forecast_external_baselines``; never writes anything.

External value per code: the EAC if any mapped row carries one (an EAC is a per-code total, so the
max across that code's monthly rows is taken), otherwise the sum of the row values.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from hb_assistant.construction.analytics import forecast_external_baselines as bl
from hb_assistant.construction.analytics.forecast_external_dto import BASELINE_LABELS
from hb_assistant.construction.analytics.forecast_external_metrics import (
    aligned_pairs,
    compute_metrics,
    gap,
    to_decimal,
)

# Baselines emitted in this deterministic order.
BASELINE_ORDER = (
    bl.BASELINE_ACTUALS,
    bl.BASELINE_CURRENT_BUDGET,
    bl.BASELINE_ERP_JTD,
    bl.BASELINE_MODEL_EAC,
    bl.BASELINE_MODEL_P50,
    bl.BASELINE_MODEL_P80,
    bl.BASELINE_PRIOR_EXTERNAL,
)


def external_value_by_code(mapped_rows: list[dict[str, Any]]) -> dict[str, Decimal]:
    """Aggregate mapped rows to one external forecast value per canonical budget code."""
    eac_by_code: dict[str, Decimal] = {}
    value_sum_by_code: dict[str, Decimal] = {}
    for row in mapped_rows:
        code = str(row.get("budget_code_key") or "").strip()
        if not code:
            continue
        eac = to_decimal(row.get("eac"))
        if eac is not None:
            prev = eac_by_code.get(code)
            eac_by_code[code] = eac if prev is None or eac > prev else prev
        val = to_decimal(row.get("value"))
        if val is not None:
            value_sum_by_code[code] = value_sum_by_code.get(code, Decimal(0)) + val
    out: dict[str, Decimal] = {}
    for code in set(eac_by_code) | set(value_sum_by_code):
        out[code] = eac_by_code.get(code, value_sum_by_code.get(code, Decimal(0)))
    return out


class ForecastExternalCompareService:
    """Compares mapped external forecasts against all available baselines."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path_override = db_path

    def load_baselines(
        self,
        project_key: str,
        package_dir: Path | None,
        prior_external: dict[str, Decimal] | None,
    ) -> dict[str, dict[str, Decimal]]:
        db = bl.resolve_db_path(self._db_path_override)
        actuals = bl.load_actuals(db, project_key)
        budget, erp = bl.load_budget_and_erp(db, project_key)
        model = bl.load_model_baselines(package_dir)
        model_eac = {c: v[bl.BASELINE_MODEL_EAC] for c, v in model.items() if bl.BASELINE_MODEL_EAC in v}
        model_p50 = {c: v[bl.BASELINE_MODEL_P50] for c, v in model.items() if bl.BASELINE_MODEL_P50 in v}
        model_p80 = {c: v[bl.BASELINE_MODEL_P80] for c, v in model.items() if bl.BASELINE_MODEL_P80 in v}
        return {
            bl.BASELINE_ACTUALS: actuals,
            bl.BASELINE_CURRENT_BUDGET: budget,
            bl.BASELINE_ERP_JTD: erp,
            bl.BASELINE_MODEL_EAC: model_eac,
            bl.BASELINE_MODEL_P50: model_p50,
            bl.BASELINE_MODEL_P80: model_p80,
            bl.BASELINE_PRIOR_EXTERNAL: dict(prior_external or {}),
        }

    def compare(
        self,
        mapped_rows: list[dict[str, Any]],
        project_key: str = "tropical",
        package_dir: Path | None = None,
        prior_external: dict[str, Decimal] | None = None,
    ) -> dict[str, Any]:
        external = external_value_by_code(mapped_rows)
        baselines = self.load_baselines(project_key, package_dir, prior_external)
        return self.compare_maps(external, baselines)

    def compare_maps(
        self,
        external: dict[str, Decimal],
        baselines: dict[str, dict[str, Decimal]],
    ) -> dict[str, Any]:
        """Pure comparison over already-loaded external + baseline maps (shared with anomaly detection)."""
        comparison_results: list[dict[str, Any]] = []
        accuracy_results: list[dict[str, Any]] = []
        baselines_compared: list[str] = []

        for baseline_id in BASELINE_ORDER:
            base_map = baselines.get(baseline_id) or {}
            if not base_map:
                continue
            # Per-code comparison rows over codes present in BOTH maps (deterministic order).
            shared = sorted(set(external) & set(base_map))
            if not shared:
                continue
            baselines_compared.append(baseline_id)
            for code in shared:
                ext_val = external[code]
                base_val = base_map[code]
                gap_abs, gap_pct = gap(ext_val, base_val)
                comparison_results.append(
                    {
                        "budget_code_key": code,
                        "baseline": baseline_id,
                        "baseline_label": BASELINE_LABELS.get(baseline_id, baseline_id),
                        "external_value": str(ext_val.quantize(Decimal("0.01"))),
                        "baseline_value": str(base_val.quantize(Decimal("0.01"))),
                        "gap_absolute": gap_abs,
                        "gap_percent": gap_pct,
                    }
                )
            pairs = aligned_pairs(
                {c: external[c] for c in shared}, {c: base_map[c] for c in shared}
            )
            metrics = compute_metrics(pairs)
            for metric_name, metric_value in metrics.items():
                accuracy_results.append(
                    {
                        "baseline": baseline_id,
                        "baseline_label": BASELINE_LABELS.get(baseline_id, baseline_id),
                        "metric": metric_name,
                        "metric_value": metric_value,
                        "sample_n": len(pairs),
                    }
                )
        return {
            "external_by_code": {c: str(v) for c, v in external.items()},
            "baselines_compared": baselines_compared,
            "comparison_results": comparison_results,
            "accuracy_results": accuracy_results,
        }
