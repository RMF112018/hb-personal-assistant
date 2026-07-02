"""Schedule metric formula proof export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hb_assistant.construction.analytics.schedule_cpm_formula_trace import (
    ROW_COUNT_TABLES,
    assert_db_unchanged,
    snapshot_db_row_counts,
)
from hb_assistant.construction.analytics.schedule_metric_formula_registry import (
    build_metric_registry,
)
from hb_assistant.construction.analytics.schedule_metric_formula_service import (
    ScheduleMetricFormulaService,
    build_activation_proof,
)
from hb_assistant.construction.analytics.schedule_metric_shadow_evaluator import (
    ScheduleMetricShadowEvaluator,
)

ROW_COUNT_TABLES_METRIC = ROW_COUNT_TABLES


class ScheduleMetricFormulaProofExporter:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._service = ScheduleMetricFormulaService(db_path=db_path)
        self._shadow = ScheduleMetricShadowEvaluator()

    def export(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        out_dir: Path,
        comparison_basis: str = "prior_update",
        weighting_basis: str = "duration_weighted",
        tolerance: float = 1e-4,
    ) -> tuple[dict[str, Any], int]:
        out_dir.mkdir(parents=True, exist_ok=True)
        before = snapshot_db_row_counts(self._db_path)
        package = self._service.compute_all(
            project_key,
            schedule_version_key,
            comparison_basis=comparison_basis,
            weighting_basis=weighting_basis,
        )
        snapshot = self._service.build_input_snapshot(project_key, schedule_version_key)
        diff = self._shadow.diff_against_service(
            package["metrics"], snapshot, tolerance=tolerance
        )
        activation = build_activation_proof(project_key=project_key)
        registry = build_metric_registry()
        traces = diff.get("shadow_traces", [])
        after = snapshot_db_row_counts(self._db_path)
        assert_db_unchanged(before, after)
        (out_dir / "metric-formula-registry.json").write_text(
            json.dumps(registry, indent=2) + "\n", encoding="utf-8"
        )
        (out_dir / "metric-input-snapshot.json").write_text(
            json.dumps(snapshot, indent=2, default=str) + "\n", encoding="utf-8"
        )
        with (out_dir / "metric-computation-trace.jsonl").open("w", encoding="utf-8") as fh:
            for row in traces:
                fh.write(json.dumps(row) + "\n")
        (out_dir / "metric-api-activation-proof.json").write_text(
            json.dumps(activation, indent=2) + "\n", encoding="utf-8"
        )
        (out_dir / "metric-independent-recompute-diff.json").write_text(
            json.dumps(diff, indent=2) + "\n", encoding="utf-8"
        )
        (out_dir / "metric-proof-audit.md").write_text(self._audit(package, diff), encoding="utf-8")
        exit_code = 0 if diff.get("status") in {"pass_fixture", "pass_with_policy_limitations"} else 1
        return {"package": package, "diff": diff, "activation": activation}, exit_code

    @staticmethod
    def _audit(package: dict[str, Any], diff: dict[str, Any]) -> str:
        lines = [
            "# Schedule metric proof audit",
            "",
            f"- project: `{package.get('project_key')}`",
            f"- schedule version: `{package.get('schedule_version_key')}`",
            f"- formula version: `{package.get('formula_version')}`",
            f"- diff status: **{diff.get('status')}**",
            "",
            "## Policy note",
            "",
            "Health, feasibility, compression analog, and critical indices composites are "
            "arithmetically provable but weights require PM/business validation.",
            "",
            "## Conclusion",
            "",
            "Formula trace export completed for operator review. "
            "This report does not assert contractual schedule authority or causation.",
            "",
        ]
        return "\n".join(lines) + "\n"


__all__ = ["ScheduleMetricFormulaProofExporter"]
