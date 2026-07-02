"""Route/role guard matrix for clean-DB phase 0."""

from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics.api import create_app
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_hub_api import _seed_comparable_versions

FIXTURE_XML = Path(__file__).resolve().parents[0] / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"
EVIDENCE_DIR = os.environ.get("PHASE0_EVIDENCE_DIR")


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "roles.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    _seed_comparable_versions(db)
    return db


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _operator() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _response_code(resp: Any) -> str | None:
    try:
        body = resp.json()
    except Exception:
        return None
    if not isinstance(body, dict):
        return None
    detail = body.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            return str(first.get("type") or first.get("msg") or first)
    return None


def _conclude(
    *,
    method: str,
    expected_viewer_status: int,
    viewer_status: int,
    operator_status: int,
) -> str:
    if method == "GET":
        return "not_applicable" if viewer_status != 403 else "unexpected_viewer_access"
    if viewer_status == 403:
        if operator_status == 403:
            return "operator_blocked_by_role_gate"
        return "role_gate_passed"
    if viewer_status == 422 and expected_viewer_status == 403:
        return "route_contract_changed"
    if viewer_status not in {403, 422}:
        return "unexpected_viewer_access"
    return "route_contract_changed"


def _record(
    rows: list[dict[str, Any]],
    *,
    method: str,
    path: str,
    expected_viewer_status: int,
    viewer_resp: Any,
    operator_resp: Any,
) -> None:
    viewer_status = viewer_resp.status_code
    operator_status = operator_resp.status_code
    rows.append(
        {
            "method": method,
            "path": path,
            "expected_viewer_status": expected_viewer_status,
            "viewer_status": viewer_status,
            "viewer_body_code": _response_code(viewer_resp),
            "operator_status": operator_status,
            "operator_body_code": _response_code(operator_resp),
            "operator_gate_passed": operator_status != 403,
            "conclusion": _conclude(
                method=method,
                expected_viewer_status=expected_viewer_status,
                viewer_status=viewer_status,
                operator_status=operator_status,
            ),
        }
    )


def build_role_gate_matrix(client: TestClient) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    _record(
        rows,
        method="GET",
        path="/health",
        expected_viewer_status=200,
        viewer_resp=client.get("/health", headers=_viewer()),
        operator_resp=client.get("/health", headers=_operator()),
    )
    _record(
        rows,
        method="GET",
        path="/api/projects/tropical/schedule",
        expected_viewer_status=200,
        viewer_resp=client.get("/api/projects/tropical/schedule", headers=_viewer()),
        operator_resp=client.get("/api/projects/tropical/schedule", headers=_operator()),
    )
    _record(
        rows,
        method="GET",
        path="/api/projects/tropical/schedule/controls",
        expected_viewer_status=200,
        viewer_resp=client.get("/api/projects/tropical/schedule/controls", headers=_viewer()),
        operator_resp=client.get("/api/projects/tropical/schedule/controls", headers=_operator()),
    )
    _record(
        rows,
        method="GET",
        path="/api/projects/tropical/schedule/review-items",
        expected_viewer_status=200,
        viewer_resp=client.get("/api/projects/tropical/schedule/review-items", headers=_viewer()),
        operator_resp=client.get("/api/projects/tropical/schedule/review-items", headers=_operator()),
    )
    _record(
        rows,
        method="GET",
        path="/api/projects/tropical/schedule/baseline",
        expected_viewer_status=200,
        viewer_resp=client.get("/api/projects/tropical/schedule/baseline", headers=_viewer()),
        operator_resp=client.get("/api/projects/tropical/schedule/baseline", headers=_operator()),
    )
    _record(
        rows,
        method="GET",
        path="/api/projects/tropical/schedule/baselines",
        expected_viewer_status=200,
        viewer_resp=client.get("/api/projects/tropical/schedule/baselines", headers=_viewer()),
        operator_resp=client.get("/api/projects/tropical/schedule/baselines", headers=_operator()),
    )
    _record(
        rows,
        method="GET",
        path="/api/projects/schedule-review-dashboard",
        expected_viewer_status=200,
        viewer_resp=client.get("/api/projects/schedule-review-dashboard", headers=_viewer()),
        operator_resp=client.get("/api/projects/schedule-review-dashboard", headers=_operator()),
    )

    preview_viewer = client.post(
        "/api/schedules/import-preview",
        headers=_viewer(),
        files={"file": ("minimal.xml", FIXTURE_XML.read_bytes(), "application/xml")},
        data={"project_key": "tropical"},
    )
    preview_operator = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": ("minimal.xml", BytesIO(FIXTURE_XML.read_bytes()), "application/xml")},
        data={"project_key": "tropical"},
    )
    _record(
        rows,
        method="POST",
        path="/api/schedules/import-preview",
        expected_viewer_status=403,
        viewer_resp=preview_viewer,
        operator_resp=preview_operator,
    )

    viewer_commit = client.post("/api/schedules/import-commit", headers=_viewer(), json={})
    operator_commit = client.post("/api/schedules/import-commit", headers=_operator(), json={})
    _record(
        rows,
        method="POST",
        path="/api/schedules/import-commit",
        expected_viewer_status=403,
        viewer_resp=viewer_commit,
        operator_resp=operator_commit,
    )

    viewer_review = client.post("/api/projects/tropical/schedule/review-items", headers=_viewer(), json={})
    operator_review = client.post("/api/projects/tropical/schedule/review-items", headers=_operator(), json={})
    _record(
        rows,
        method="POST",
        path="/api/projects/tropical/schedule/review-items",
        expected_viewer_status=403,
        viewer_resp=viewer_review,
        operator_resp=operator_review,
    )

    viewer_promote = client.post(
        "/api/projects/tropical/schedule/review-items/promote", headers=_viewer(), json={}
    )
    operator_promote = client.post(
        "/api/projects/tropical/schedule/review-items/promote", headers=_operator(), json={}
    )
    _record(
        rows,
        method="POST",
        path="/api/projects/tropical/schedule/review-items/promote",
        expected_viewer_status=403,
        viewer_resp=viewer_promote,
        operator_resp=operator_promote,
    )

    viewer_patch = client.patch(
        "/api/projects/tropical/schedule/review-items/r1", headers=_viewer(), json={}
    )
    operator_patch = client.patch(
        "/api/projects/tropical/schedule/review-items/r1", headers=_operator(), json={}
    )
    _record(
        rows,
        method="PATCH",
        path="/api/projects/tropical/schedule/review-items/{review_item_id}",
        expected_viewer_status=403,
        viewer_resp=viewer_patch,
        operator_resp=operator_patch,
    )

    viewer_baseline = client.put("/api/projects/tropical/schedule/baseline", headers=_viewer(), json={})
    operator_baseline = client.put("/api/projects/tropical/schedule/baseline", headers=_operator(), json={})
    _record(
        rows,
        method="PUT",
        path="/api/projects/tropical/schedule/baseline",
        expected_viewer_status=403,
        viewer_resp=viewer_baseline,
        operator_resp=operator_baseline,
    )

    viewer_baselines = client.put("/api/projects/tropical/schedule/baselines", headers=_viewer(), json={})
    operator_baselines = client.put("/api/projects/tropical/schedule/baselines", headers=_operator(), json={})
    _record(
        rows,
        method="PUT",
        path="/api/projects/tropical/schedule/baselines",
        expected_viewer_status=403,
        viewer_resp=viewer_baselines,
        operator_resp=operator_baselines,
    )

    return rows


def _export_matrix(matrix: list[dict[str, Any]], target: Path) -> None:
    target.write_text(json.dumps({"routes": matrix}, indent=2) + "\n", encoding="utf-8")


def test_role_gate_matrix(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    client = TestClient(create_app(db_path=str(db)))
    matrix = build_role_gate_matrix(client)
    for row in matrix:
        if row["method"] == "GET":
            assert row["viewer_status"] != 403
            assert row["conclusion"] == "not_applicable"
        else:
            assert row["viewer_status"] in {403, 422}
            assert row["operator_gate_passed"] is True
    out = tmp_path / "11-role-gate-matrix.json"
    _export_matrix(matrix, out)
    if EVIDENCE_DIR:
        _export_matrix(matrix, Path(EVIDENCE_DIR) / "11-role-gate-matrix.json")
