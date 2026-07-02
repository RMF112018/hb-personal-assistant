"""Import preview DB mutation probe."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics.api import create_app
from hb_assistant.construction.schedule_clean_db.schema_audit import build_schema_audit_report


def _schedule_counts(report: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in report.get("discovered_by_heuristic", []):
        if row.get("preserve_catalog"):
            continue
        val = row.get("row_count_for_project")
        if isinstance(val, int):
            counts[row["table"]] = val
    return counts


def run_import_preview_mutation_probe(
    db_path: str | Path,
    *,
    project_key: str,
    fixture_path: str | Path,
) -> dict[str, Any]:
    fixture = Path(fixture_path)
    before_report = build_schema_audit_report(db_path, project_key=project_key)
    before_counts = _schedule_counts(before_report)

    app = create_app(db_path=str(db_path))
    client = TestClient(app)
    content = fixture.read_bytes()
    filename = fixture.name
    media = "application/xml" if filename.endswith(".xml") else "application/octet-stream"
    resp = client.post(
        "/api/schedules/import-preview",
        headers={"X-HB-UI-Role": "operator"},
        files={"file": (filename, BytesIO(content), media)},
        data={"project_key": project_key},
    )

    after_report = build_schema_audit_report(db_path, project_key=project_key)
    after_counts = _schedule_counts(after_report)
    all_keys = set(before_counts) | set(after_counts)
    diff = {k: after_counts.get(k, 0) - before_counts.get(k, 0) for k in all_keys}
    schedule_diff = {k: v for k, v in diff.items() if v != 0}
    classification = "preview_records_written" if schedule_diff else "db_neutral"

    return {
        "mode": "schedule_import_preview_mutation_probe",
        "project_key": project_key,
        "fixture": str(fixture.resolve()),
        "preview_status_code": resp.status_code,
        "classification": classification,
        "before_counts": before_counts,
        "after_counts": after_counts,
        "diff_counts": diff,
        "commit_executed": False,
    }
