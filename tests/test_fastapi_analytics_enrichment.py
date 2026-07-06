"""N8C-5 — /api/assistant/enrichment/* read-only endpoints (local UI surface).

The enrichment queue is exposed READ-ONLY on the local API only; write operations are CLI/service
driven and there is no remote MCP enrichment tool. GET-only, all-roles, guardrailed, bounded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = ("access_token", "refresh_token", "client_secret", "Bearer ", "eyJ", "BEGIN PRIVATE KEY")


def _assert_safe(payload: Any) -> None:
    text = str(payload)
    for bad in FORBIDDEN:
        assert bad not in text


@pytest.fixture()
def client_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    repo = EnrichmentRepository(db)
    q = repo.queue_job(job_type="source_summary", source_id="s1", source_digest="d1")
    job = repo.claim_next_job("w1", 300)
    repo.mark_running(job["job_id"], "w1")
    repo.complete_job(job["job_id"], "w1", status="completed", result_json='{"summary":"ok"}',
                      applied_status="stored_only",
                      receipt_metadata={"worker_id": "w1", "runtime": "fake",
                                        "model_name": "qwen2.5:14b", "prompt_version": "v1",
                                        "input_digest": "i", "output_digest": "o"})
    repo.queue_job(job_type="claim_extraction", source_id="s2", source_digest="d2")
    return {"client": TestClient(create_app(db_path=db)), "db": db, "job_id": q["job_id"]}


def test_list_jobs(client_env) -> None:
    r = client_env["client"].get("/api/assistant/enrichment/jobs", headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2 and body["guardrails"]["read_only"] is True
    _assert_safe(body)


def test_list_jobs_filtered_by_status(client_env) -> None:
    r = client_env["client"].get("/api/assistant/enrichment/jobs", params={"status": "queued"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["jobs"][0]["job_type"] == "claim_extraction"


def test_get_job_and_404(client_env) -> None:
    r = client_env["client"].get(f"/api/assistant/enrichment/jobs/{client_env['job_id']}")
    assert r.status_code == 200 and r.json()["job"]["status"] == "completed"
    assert client_env["client"].get("/api/assistant/enrichment/jobs/nope").status_code == 404


def test_list_receipts(client_env) -> None:
    r = client_env["client"].get("/api/assistant/enrichment/receipts")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    rec = body["receipts"][0]
    assert rec["applied_status"] == "stored_only" and rec["model_name"] == "qwen2.5:14b"
    _assert_safe(body)


def test_no_enrichment_write_route_exists(client_env) -> None:
    # Write verbs on the enrichment surface must not exist (read-only local API).
    c = client_env["client"]
    assert c.post("/api/assistant/enrichment/jobs", json={}).status_code in (404, 405)
    assert c.delete(f"/api/assistant/enrichment/jobs/{client_env['job_id']}").status_code in (404, 405)
