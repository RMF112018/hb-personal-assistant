#!/usr/bin/env python3
"""Proof: schedule quality evaluation produces DCMA scorecards (metadata only)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import SQLiteMigrator

FIXTURE = Path(__file__).resolve().parents[2] / "tests/fixtures/schedules/xml/minimal_schedule.xml"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "proof.db"
        SQLiteMigrator(db_path=str(db)).apply()
        client = TestClient(create_app(db_path=str(db)))
        headers = {"X-HB-UI-Role": "operator"}
        preview = client.post(
            "/api/schedules/import-preview",
            headers=headers,
            files={"file": (FIXTURE.name, FIXTURE.read_bytes(), "application/xml")},
            data={"project_key": "tropical"},
        )
        commit = client.post(
            "/api/schedules/import-commit",
            headers=headers,
            json={"import_id": preview.json()["import_id"], "project_key": "tropical", "confirm": True},
        )
        svk = commit.json()["schedule_version_key"]
        quality = client.get(f"/api/schedules/versions/{svk}/quality", headers={"X-HB-UI-Role": "viewer"})
        body = quality.json()
        proof = {
            "schedule_version_key": svk,
            "status": body.get("status"),
            "assessment_profile": body.get("assessment_profile"),
            "dcma_metric_count": len(body.get("metrics") or []),
            "not_measurable_cpli": next(
                (
                    m.get("status")
                    for m in body.get("metrics") or []
                    if m.get("metric_code") == "dcma_cpli"
                ),
                None,
            ),
            "disclaimer_present": bool(body.get("disclaimer")),
        }
        print(json.dumps(proof, indent=2))
        return 0 if proof["status"] == "completed" and proof["dcma_metric_count"] >= 14 else 1


if __name__ == "__main__":
    raise SystemExit(main())