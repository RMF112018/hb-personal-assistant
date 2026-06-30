#!/usr/bin/env python3
"""Generate Phase 8C review workbench expansion evidence package."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
SUBREPO_SRC = REPO / "subrepos" / "construction-financial-review" / "src"
TIMESTAMP = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y%m%dT%H%M%S")
EVIDENCE = REPO / "docs" / "evidence" / "project-schedule-hub" / f"phase-8c-review-workbench-expansion-{TIMESTAMP}"


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
    from tests.schedule_project_test_helpers import (
        seed_named_schedule_udfs,
        seed_procore_ep_project,
        seed_schedule_quality_findings,
    )
    from tests.test_project_schedule_review_workbench import _seed_driver_chain
    from hb_assistant.store.migrator import SQLiteMigrator

    SQLiteMigrator(db_path=str(db_path)).apply()
    seed_procore_ep_project(db_path, project_key="tropical", display_name="Tropical Wind")
    _seed_driver_chain(db_path)
    seed_named_schedule_udfs(
        db_path,
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        import_id="imp-current",
        activity_ids=["DRV-A", "SUCC-B", "SUCC-C"],
    )
    seed_schedule_quality_findings(
        db_path,
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        import_id="imp-current",
        activity_id="DRV-A",
    )


def main() -> int:
    sys.path.insert(0, str(SRC))
    sys.path.insert(0, str(SUBREPO_SRC))

    from fastapi.testclient import TestClient

    from hb_assistant.construction.analytics import create_app
    from hb_assistant.construction.analytics.project_schedule_review_cue_service import (
        ProjectScheduleReviewCueService,
    )
    from hb_assistant.construction.analytics.project_schedule_summary_service import (
        ProjectScheduleSummaryService,
    )

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for sub in ("repo", "db", "api", "metrics", "notes", "tests"):
        (EVIDENCE / sub).mkdir(exist_ok=True)

    _write(EVIDENCE / "repo" / "branch.txt", _run(["git", "branch", "--show-current"]))
    _write(EVIDENCE / "repo" / "head.txt", _run(["git", "rev-parse", "HEAD"]).strip() + "\n")
    _write(EVIDENCE / "repo" / "status-short.txt", _run(["git", "status", "--short"]))

    db_path = EVIDENCE / "db" / "phase-8c-evidence.db"
    if db_path.exists():
        db_path.unlink()
    _seed_evidence_db(db_path)

    with sqlite3.connect(db_path) as conn:
        for table in ("project_schedule_review_items", "project_schedule_review_item_events"):
            schema = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name=?",
                (table,),
            ).fetchone()
            if schema and schema[0]:
                _write(EVIDENCE / "db" / f"{table}-schema.txt", schema[0] + "\n")

    cue_service = ProjectScheduleReviewCueService(db_path=str(db_path))
    summary_service = ProjectScheduleSummaryService(db_path=str(db_path))
    as_of = date(2026, 7, 3)
    context = summary_service._review_workbench_context("tropical", as_of=as_of)
    assert context is not None
    cues = cue_service.collect_materializable_cues(
        project_key="tropical",
        schedule_version_key=context["schedule_version_key"],
        as_of_date=as_of,
        driver_analysis=context["driver_analysis"],
        milestones=context["milestones"],
        remaining_health=context["remaining_health"],
        cpm_summary=context["cpm_summary"],
        change_impact=context["change_impact"],
        remaining_activities=context["remaining_activities"],
        baseline_summary=context["baseline_summary"],
    )
    _write_json(EVIDENCE / "metrics" / "materializable-cue-sample.json", cues[:10])
    _write(
        EVIDENCE / "metrics" / "review-cue-source-map.md",
        "# Review Cue Source Map\n\n```json\n"
        + json.dumps(cue_service.cue_source_map(), indent=2)
        + "\n```\n",
    )

    os.environ["HB_ASSISTANT_DB_PATH"] = str(db_path)
    app = create_app(db_path=str(db_path))
    client = TestClient(app)
    headers_viewer = {"X-HB-UI-Role": "viewer"}
    headers_operator = {"X-HB-UI-Role": "operator"}

    get_items = client.get(
        f"/api/projects/tropical/schedule/review-items?as_of={as_of.isoformat()}",
        headers=headers_viewer,
    )
    _write_json(EVIDENCE / "api" / "get-review-items.json", get_items.json())

    sync = client.post(
        f"/api/projects/tropical/schedule/review-items?as_of={as_of.isoformat()}",
        headers=headers_operator,
    )
    _write_json(EVIDENCE / "api" / "post-sync-review-items.json", sync.json())

    item_id = sync.json()["workbench"]["items"][0]["review_item_id"]
    patch = client.patch(
        f"/api/projects/tropical/schedule/review-items/{item_id}",
        headers=headers_operator,
        json={"review_status": "watching", "pm_notes": "phase-8c evidence"},
    )
    _write_json(EVIDENCE / "api" / "patch-review-item.json", patch.json())

    detail = client.get(
        f"/api/projects/tropical/schedule/review-items/{item_id}",
        headers=headers_viewer,
    )
    _write_json(EVIDENCE / "api" / "get-review-item-detail.json", detail.json())

    events = client.get(
        f"/api/projects/tropical/schedule/review-items/{item_id}/events",
        headers=headers_viewer,
    )
    _write_json(EVIDENCE / "api" / "get-review-item-events.json", events.json())

    filtered = client.get(
        "/api/projects/tropical/schedule/review-items?source_metric=schedule_quality_findings",
        headers=headers_viewer,
    )
    _write_json(EVIDENCE / "api" / "get-review-items-filtered.json", filtered.json())

    sync2 = client.post(
        f"/api/projects/tropical/schedule/review-items?as_of={as_of.isoformat()}",
        headers=headers_operator,
    )
    keys1 = {item["stable_item_key"] for item in sync.json()["workbench"]["items"]}
    keys2 = {item["stable_item_key"] for item in sync2.json()["workbench"]["items"]}
    _write(
        EVIDENCE / "notes" / "dedupe-proof.md",
        "# Dedupe Proof\n\n"
        f"- First sync item count: {len(keys1)}\n"
        f"- Second sync item count: {len(keys2)}\n"
        f"- Stable keys unchanged: {keys1 == keys2}\n",
    )
    _write(
        EVIDENCE / "notes" / "filter-proof.md",
        "# Filter Proof\n\n"
        f"- Filter `source_metric=schedule_quality_findings` returned {filtered.json()['count']} item(s).\n",
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
            "tests/test_project_schedule_review_cue_workflow.py",
            "-q",
        ]
    )
    _write(EVIDENCE / "tests" / "backend-pytest-results.txt", backend_tests)

    frontend_tests = _run(["npm", "run", "test", "--", "ProjectScheduleWorkbenchPage"], cwd=REPO / "frontend")
    _write(EVIDENCE / "tests" / "frontend-test-results.txt", frontend_tests)
    typecheck = _run(["npm", "run", "typecheck"], cwd=REPO / "frontend")
    _write(EVIDENCE / "tests" / "typecheck-results.txt", typecheck)
    build = _run(["npm", "run", "build"], cwd=REPO / "frontend")
    _write(EVIDENCE / "tests" / "build-results.txt", build)

    _write(
        EVIDENCE / "notes" / "migration-decision.md",
        "# Migration Decision\n\n"
        "- Migration added: **No**\n"
        "- Cue metadata stored in existing `evidence_json` on V91 review items.\n"
        "- Event history uses existing V92 `project_schedule_review_item_events`.\n",
    )
    _write(
        EVIDENCE / "notes" / "non-causation-guardrails.md",
        "# Non-Causation Guardrails\n\n"
        "- Review cues include PM-facing non-causation caveats in evidence.\n"
        "- Delay analysis emits period-level cues only; no per-activity causation.\n"
        "- Frontend displays backend evidence only; no React cue computation.\n",
    )
    _write(
        EVIDENCE / "notes" / "ui-render-notes.md",
        "# UI Render Notes\n\n"
        "- Workbench adds filter bar, expandable detail, caveats, event history, and PM notes editor.\n"
        "- Operator sync/mutate controls remain gated by UI role.\n"
        "- Screenshot: open `/projects/tropical/schedule/workbench?as_of=2026-07-03` after sync.\n",
    )
    _write(
        EVIDENCE / "notes" / "event-history-notes.md",
        "# Event History Notes\n\n"
        "- `GET /api/projects/{project_key}/schedule/review-items/{review_item_id}/events` returns V92 audit rows.\n"
        "- Detail route includes item envelope plus embedded events for convenience.\n",
    )
    _write(
        EVIDENCE / "notes" / "deferred-items.md",
        "# Deferred Items (Phase 9 candidates)\n\n"
        "- Auto-sync on import\n"
        "- Multi-user assignment\n"
        "- Executive PDF export from workbench\n"
        "- Activity drilldown deep-links from hub preview rows\n",
    )

    files = sorted(p for p in EVIDENCE.rglob("*") if p.is_file())
    _write(EVIDENCE / "evidence-index.txt", "\n".join(str(p.relative_to(EVIDENCE)) for p in files) + "\n")
    sha_lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(EVIDENCE)}" for path in files]
    _write(EVIDENCE / "evidence-sha256.txt", "\n".join(sha_lines) + "\n")

    print(str(EVIDENCE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
