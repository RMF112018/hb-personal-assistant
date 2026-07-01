"""Phase 17 export review status section tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.project_schedule_narrative_qa import validate_rendered_text
from tests.test_project_schedule_review_workbench import _fresh_db, _seed_driver_chain


def test_export_includes_schedule_review_status_section(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    client = TestClient(create_app(db_path=str(db)))
    response = client.get(
        "/api/projects/tropical/schedule/export",
        params={"format": "markdown", "as_of": "2026-07-03"},
    )
    assert response.status_code == 200
    text = response.text
    assert "## Schedule Review Status" in text
    assert "Preview cues:" in text
    assert "Persisted review items:" in text
    qa = validate_rendered_text(text, surface="export")
    assert qa["passed"] is True
    forbidden_ids = ("schedule_version_key", "import_id", "cpm_run_id")
    for token in forbidden_ids:
        assert token not in text
