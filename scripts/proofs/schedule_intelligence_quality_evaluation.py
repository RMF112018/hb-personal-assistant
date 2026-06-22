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

GMA = Path(__file__).resolve().parents[2] / "tests/fixtures/schedules/xml/gma_sample.xml"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "proof.db"
        SQLiteMigrator(db_path=str(db)).apply()
        client = TestClient(create_app(db_path=str(db)))
        headers = {"X-HB-UI-Role": "operator"}
        preview = client.post(
            "/api/schedules/import-preview",
            headers=headers,
            files={"file": (GMA.name, GMA.read_bytes(), "application/xml")},
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
        metrics = {m.get("metric_code"): m.get("status") for m in body.get("metrics") or []}
        proof = {
            "schedule_version_key": svk,
            "status": body.get("status"),
            "assessment_profile": body.get("assessment_profile"),
            "dcma_metric_count": len(body.get("metrics") or []),
            "high_float_status": metrics.get("dcma_high_float"),
            "negative_float_status": metrics.get("dcma_negative_float"),
            "critical_path_test_status": metrics.get("dcma_critical_path_test"),
            "not_measurable_cpli": metrics.get("dcma_cpli"),
            "disclaimer_present": bool(body.get("disclaimer")),
            "derived_float_disclaimer": "not a full Primavera recalculation"
            in str(body.get("disclaimer") or ""),
        }
        print(json.dumps(proof, indent=2))
        ok = (
            proof["status"] == "completed"
            and proof["dcma_metric_count"] >= 14
            and proof["high_float_status"] == "measured_from_derived_finish_float"
            and proof["negative_float_status"] == "measured_from_derived_finish_float"
            and proof["critical_path_test_status"] == "not_measurable_requires_recalculation"
            and proof["derived_float_disclaimer"]
        )
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())