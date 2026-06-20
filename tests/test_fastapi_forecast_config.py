"""FastAPI route tests for the read-only forecast configuration viewer (Implementation Phase 2).

Asserts the routes are role-aware and read-only, carry honest guardrails (no_db_write), leak
no dev-internals (incl. the project domain), fail closed when the DB is unavailable, and 404
on unknown snapshot/item.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402

SNAP = "c3b4a67d22db47c74e696ae562fbf1c555e365fc66bb003a7b3312754415b698"

_PROJECT_RAW = {
    "project_key": "tropical",
    "project_name": "Tropical World Nursery",
    "job_reference": "23-435-01",
    "forecast_period": "2026-June",
    "materiality_absolute": "25000.00",
    "budget_details": {"budget_view_id": "713474"},
    "default_data_root": "/Users/bobbyfetting/Library/CloudStorage/x/2026-June",
    "forecast_context_package": "forecast_context_package_tropical_20260614_084510",
    "llm": {"endpoint": "http://localhost:11434"},
}
_CONTROL_RAW = {"project_key": "tropical", "cost_code": "10-01-340", "accepted_final_cost": "123456.78"}
_OWNER_RAW = {"crosswalk_id": "TROPICAL-OWNER-SOV-0001", "owner_sov_code": "10-XX-XXX"}


def _seed(db: Path) -> None:
    """Migrate a temp DB and seed one synthetic v60 config snapshot (project/controls/owner-SOV)."""
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    try:
        for i, (sid, domain, fmt) in enumerate(
            [("src-p", "project", "json"), ("src-c", "forecast_controls", "jsonl"),
             ("src-oj", "owner_sov_crosswalk", "jsonl"), ("src-oc", "owner_sov_crosswalk", "csv")]
        ):
            conn.execute(
                "INSERT INTO forecast_config_sources (config_source_id, project_key, config_domain, "
                "config_name, source_path, source_format, source_sha256, content_sha256, row_count, "
                "imported_at_utc, import_run_id, is_active, created_utc, updated_utc) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sid, "tropical", domain, domain, "config/x", fmt, f"s{i}", f"c{i}", 1,
                 "2026-06-19T08:00:00+00:00", "run-1", 1, "2026-06-19T08:00:00+00:00",
                 "2026-06-19T08:00:00+00:00"),
            )
        items = [
            ("it-project", "project", _PROJECT_RAW, 0),
            ("it-ctrl-1", "forecast_controls", _CONTROL_RAW, 0),
            ("it-owner-1", "owner_sov_crosswalk", _OWNER_RAW, 0),
            ("it-owner-2", "owner_sov_crosswalk", {**_OWNER_RAW, "crosswalk_id": "o2"}, 1),
        ]
        conn.execute(
            "INSERT INTO forecast_config_snapshots (config_snapshot_id, project_key, snapshot_name, "
            "snapshot_created_utc, snapshot_reason, source_mode, item_count, snapshot_sha256, created_by, "
            "created_utc) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (SNAP, "tropical", "tropical-live-config", "2026-06-19T08:54:42+00:00", "live import",
             "db_current", len(items), "snap-sha", None, "2026-06-19T08:54:42+00:00"),
        )
        for iid, domain, raw, order in items:
            conn.execute(
                "INSERT INTO forecast_config_snapshot_items (config_snapshot_id, config_item_id, "
                "project_key, config_domain, config_name, item_key, item_order, raw_json, "
                "canonical_json_sha256) VALUES (?,?,?,?,?,?,?,?,?)",
                (SNAP, iid, "tropical", domain, domain, iid, order, json.dumps(raw), f"h-{iid}"),
            )
        conn.commit()
    finally:
        conn.close()


def _client(db_path: str) -> TestClient:
    return TestClient(create_app(db_path=db_path))


def _h(role: str = "viewer") -> dict[str, str]:
    return {"X-HB-UI-Role": role}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db = tmp_path / "config.sqlite"
    _seed(db)
    return _client(str(db))


def test_full_config_flow_read_only(client: TestClient) -> None:
    snaps = client.get("/api/forecast/config/snapshots", headers=_h()).json()
    assert snaps["guardrails"]["read_only"] is True
    assert snaps["guardrails"]["no_db_write"] is True
    sid = snaps["snapshots"][0]["snapshot_id"]

    snap = client.get(f"/api/forecast/config/snapshots/{sid}", headers=_h())
    assert snap.status_code == 200
    assert find_redaction_leaks(snap.json()) == []

    for domain in ("project", "forecast_controls", "owner_sov_crosswalk"):
        resp = client.get(f"/api/forecast/config/snapshots/{sid}/domains/{domain}", headers=_h())
        assert resp.status_code == 200, domain
        body = resp.json()
        assert body["guardrails"]["no_db_write"] is True
        assert find_redaction_leaks(body) == [], f"leak in {domain}"

    item = client.get(f"/api/forecast/config/snapshots/{sid}/items/it-project", headers=_h())
    assert item.status_code == 200
    assert find_redaction_leaks(item.json()) == []


def test_project_domain_redacted_via_route(client: TestClient) -> None:
    body = client.get(
        f"/api/forecast/config/snapshots/{SNAP}/domains/project", headers=_h()
    ).text
    assert "/Users/" not in body
    assert "localhost" not in body
    assert "default_data_root" not in body


def test_not_available_when_db_missing(tmp_path: Path) -> None:
    client = _client(str(tmp_path / "missing.sqlite"))
    resp = client.get("/api/forecast/config/snapshots", headers=_h())
    assert resp.status_code == 503
    assert resp.json()["detail"] == "forecast_config_not_available"


def test_unknown_snapshot_and_item_404(client: TestClient) -> None:
    r1 = client.get("/api/forecast/config/snapshots/nope", headers=_h())
    assert r1.status_code == 404
    assert r1.json()["detail"] == "forecast_config_snapshot_not_found"
    r2 = client.get(f"/api/forecast/config/snapshots/{SNAP}/items/nope", headers=_h())
    assert r2.status_code == 404
    assert r2.json()["detail"] == "forecast_config_item_not_found"


def test_invalid_role_rejected(client: TestClient) -> None:
    resp = client.get("/api/forecast/config/snapshots", headers={"X-HB-UI-Role": "root"})
    assert resp.status_code == 403
