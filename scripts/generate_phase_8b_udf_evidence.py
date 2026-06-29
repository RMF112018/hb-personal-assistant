#!/usr/bin/env python3
"""Generate Phase 8B UDF normalization evidence package."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
SUBREPO_SRC = REPO / "subrepos" / "construction-financial-review" / "src"
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
EVIDENCE = REPO / "docs" / "evidence" / "project-schedule-hub" / f"phase-8b-udf-normalization-{TIMESTAMP}"


def _run(cmd: list[str], *, cwd: Path | None = None) -> str:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{SRC}:{SUBREPO_SRC}"
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        env=env,
        capture_output=True,
        text=True,
    )
    return (proc.stdout or "") + (proc.stderr or "")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_json(path: Path, payload: object) -> None:
    _write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _seed_evidence_db(db_path: Path) -> None:
    sys.path.insert(0, str(REPO))
    from hb_assistant.store.migrator import SQLiteMigrator
    from tests.schedule_project_test_helpers import seed_named_schedule_udfs, seed_procore_ep_project
    from tests.test_project_schedule_hub_api import _seed_comparable_versions

    SQLiteMigrator(db_path=str(db_path)).apply()
    seed_procore_ep_project(db_path, project_key="tropical", display_name="Tropical Wind")
    _seed_comparable_versions(db_path)
    seed_named_schedule_udfs(
        db_path,
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        import_id="imp-current",
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO schedule_version_diff_detail_facts (
              detail_id, diff_id, project_key, from_schedule_version_key, to_schedule_version_key,
              activity_id, change_domain, change_type, field_name, day_delta, wbs_code
            ) VALUES (
              'evidence-diff-1', 1, 'tropical', 'tropical|S1|2026-06-01', 'tropical|S1|2026-07-01',
              'A100', 'activity', 'changed', 'finish_date', 5, 'WBS-A'
            )
            """
        )
        conn.commit()


def main() -> int:
    sys.path.insert(0, str(SRC))
    sys.path.insert(0, str(SUBREPO_SRC))

    from hb_assistant.construction.analytics.project_schedule_trend_aggregation_service import (
        ProjectScheduleTrendAggregationService,
    )
    from hb_assistant.construction.analytics.project_schedule_udf_normalization_service import (
        ProjectScheduleUdfNormalizationService,
    )
    from hb_assistant.construction.analytics.project_schedule_visualization_metric_contract import (
        ProjectScheduleVisualizationMetricContractService,
    )

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "repo").mkdir(exist_ok=True)
    (EVIDENCE / "db").mkdir(exist_ok=True)
    (EVIDENCE / "metrics").mkdir(exist_ok=True)
    (EVIDENCE / "notes").mkdir(exist_ok=True)
    (EVIDENCE / "tests").mkdir(exist_ok=True)

    _write(EVIDENCE / "repo" / "branch.txt", _run(["git", "branch", "--show-current"]))
    _write(EVIDENCE / "repo" / "head.txt", _run(["git", "rev-parse", "HEAD"]).strip() + "\n")
    _write(EVIDENCE / "repo" / "status-short.txt", _run(["git", "status", "--short"]))
    _write(EVIDENCE / "repo" / "changed-files.txt", _run(["git", "diff", "--name-only", "HEAD"]))

    db_path = EVIDENCE / "db" / "phase-8b-evidence.db"
    if db_path.exists():
        db_path.unlink()
    _seed_evidence_db(db_path)

    with sqlite3.connect(db_path) as conn:
        schema = "\n".join(
            row[0]
            for row in conn.execute(
                "SELECT sql FROM sqlite_master WHERE name='procore_ep_schedule_udf_values'"
            ).fetchall()
            if row[0]
        )
    _write(EVIDENCE / "db" / "udf-source-schema.txt", schema + "\n")

    version_key = "tropical|S1|2026-07-01"
    udf_service = ProjectScheduleUdfNormalizationService(db_path=str(db_path))
    contract_service = ProjectScheduleVisualizationMetricContractService(db_path=str(db_path))
    trend_service = ProjectScheduleTrendAggregationService(db_path=str(db_path))

    _write_json(EVIDENCE / "db" / "udf-name-inventory.json", udf_service.get_udf_name_inventory(
        project_key="tropical", version_key=version_key
    ))
    _write_json(EVIDENCE / "db" / "udf-sparsity-summary.json", udf_service.get_udf_sparsity_summary(
        "tropical", version_key
    ))
    _write_json(EVIDENCE / "db" / "udf-activity-join-proof.json", udf_service.get_udf_join_proof(
        "tropical", version_key
    ))

    readiness = udf_service.get_udf_metric_readiness("tropical", version_key)
    _write(
        EVIDENCE / "metrics" / "udf-dependent-metric-readiness.md",
        "# UDF-Dependent Metric Readiness\n\n"
        + json.dumps(readiness, indent=2)
        + "\n",
    )

    samples = {
        "window_start_accuracy": trend_service.build_trend("tropical", "window_start_accuracy", as_of=__import__("datetime").date(2026, 7, 3)),
        "window_finish_accuracy": trend_service.build_trend("tropical", "window_finish_accuracy", as_of=__import__("datetime").date(2026, 7, 3)),
        "should_have_finished_status": trend_service.build_trend("tropical", "should_have_finished_status", as_of=__import__("datetime").date(2026, 7, 10)),
        "delay_analysis": trend_service.build_trend("tropical", "delay_analysis", as_of=__import__("datetime").date(2026, 7, 3)),
        "critical_issues_category_model": trend_service.build_trend("tropical", "critical_issues_category_model", as_of=__import__("datetime").date(2026, 7, 3)),
    }
    for key, payload in samples.items():
        _write_json(EVIDENCE / "metrics" / f"sample-{key.replace('_', '-')}.json", payload)

    _write_json(
        EVIDENCE / "metrics" / "sample-delay-analysis-readiness.json",
        {"metric": "delay_analysis", **readiness["metrics"]["delay_analysis"]},
    )
    _write_json(
        EVIDENCE / "metrics" / "sample-critical-issues-readiness.json",
        {"metric": "critical_issues_category_model", **readiness["metrics"]["critical_issues_category_model"]},
    )

    backend_tests = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_project_schedule_visualization_metric_contract.py",
            "tests/test_project_schedule_trend_aggregation_api.py",
            "tests/test_project_schedule_hub_api.py",
            "tests/test_project_schedule_hub_drilldowns.py",
            "tests/test_project_schedule_driver_analysis.py",
            "tests/test_project_schedule_review_workbench.py",
            "tests/test_project_schedule_baseline_selection.py",
            "tests/test_project_schedule_udf_normalization.py",
            "-q",
        ]
    )
    _write(EVIDENCE / "tests" / "backend-pytest-results.txt", backend_tests)

    frontend_tests = _run(["npm", "run", "test", "--", "ProjectSchedulePage"], cwd=REPO / "frontend")
    _write(EVIDENCE / "tests" / "frontend-test-results.txt", frontend_tests)
    typecheck = _run(["npm", "run", "typecheck"], cwd=REPO / "frontend")
    _write(EVIDENCE / "tests" / "typecheck-results.txt", typecheck)
    build = _run(["npm", "run", "build"], cwd=REPO / "frontend")
    _write(EVIDENCE / "tests" / "build-results.txt", build)

    _write(
        EVIDENCE / "notes" / "migration-decision.md",
        "# Migration Decision\n\n"
        "- Migration added: **No**\n"
        "- Approach: read-through `ProjectScheduleUdfNormalizationService`\n"
        "- Raw UDF table preserved: `procore_ep_schedule_udf_values`\n"
        "- Backfill required: **No**\n",
    )
    _write(
        EVIDENCE / "notes" / "non-causation-guardrails.md",
        "# Non-Causation Guardrails\n\n"
        "- `delay_analysis` and `critical_issues_category_model` include review-cue-only caveats.\n"
        "- No responsibility, entitlement, compensability, or causation findings are emitted.\n"
        "- Review item creation remains deferred.\n",
    )
    _write(
        EVIDENCE / "notes" / "phase-8b-findings.md",
        "# Phase 8B Findings\n\n"
        f"- Evidence DB version: `{version_key}`\n"
        f"- Join success rate: {readiness['join_proof']['join_success_rate']}\n"
        f"- UDF normalization proven: {contract_service.udf_availability_summary()['stable_named_udf_normalization_proven']}\n"
        "- Metrics unlocked when schedule + UDF support exists: window start/finish accuracy, should-have-finished, partial delay/critical issues.\n"
        "- Metrics may remain unavailable when diff evidence or in-window activities are missing.\n"
        "- Frontend updated minimally to render backend availability and partial dimension notes.\n",
    )

    files = sorted(p for p in EVIDENCE.rglob("*") if p.is_file())
    index_lines = [str(p.relative_to(EVIDENCE)) for p in files]
    _write(EVIDENCE / "evidence-index.txt", "\n".join(index_lines) + "\n")

    sha_lines: list[str] = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        sha_lines.append(f"{digest}  {path.relative_to(EVIDENCE)}")
    _write(EVIDENCE / "evidence-sha256.txt", "\n".join(sha_lines) + "\n")

    print(str(EVIDENCE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
