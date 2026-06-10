"""Phase 10 — Procore monitoring read-model (read-only, degraded-honest, no writeback).

Proves the consolidated monitor reports the endpoint contract status from the registry, an honest
no_data verdict when a project has no persisted procore_live rows, a current/partial verdict when a
watermark is fresh, the pure verdict logic, raw-free output, and that the `procore live monitor` CLI
verb works — all without any live HTTP call.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.local_ai.procore_monitor import (
    _project_verdict,
    build_procore_monitoring_report,
    render_procore_monitoring_markdown,
)
from hb_assistant.procore import endpoints as _ep
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()
NOW = "2026-06-09T12:00:00+00:00"


def _fresh_db(tmp: Path) -> str:
    db = str(tmp / "p.db")
    SQLiteMigrator(db).apply()
    return db


def _seed_watermark(db: str, project_key: str, endpoint_id: str, ts: str | None) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT OR REPLACE INTO procore_live_sync_watermarks "
        "(company_id, project_key, procore_project_id, endpoint_id, last_success_at_utc) "
        "VALUES (?, ?, ?, ?, ?)",
        ("5280", project_key, "999", endpoint_id, ts),
    )
    conn.commit()
    conn.close()


def test_verdict_logic() -> None:
    # signature: _project_verdict(current, stale, never)
    assert _project_verdict(0, 0, 0) == "no_data"
    assert _project_verdict(0, 0, 10) == "no_data"  # all never-synced
    assert _project_verdict(10, 0, 0) == "healthy"
    assert _project_verdict(3, 5, 2) == "partial_stale"
    assert _project_verdict(0, 8, 2) == "stale"


def test_endpoint_contract_and_no_data(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    report = build_procore_monitoring_report(now_utc=NOW, project_keys=["PRJ-A"], db_path=db)
    c = report["endpoint_contract"]
    assert c["total_endpoints"] == len(_ep.list_all())
    assert c["live_verified"] == len(_ep.list_verified())
    assert c["degraded_or_unverified"] == c["total_endpoints"] - c["live_verified"]
    # No persisted rows -> honest no_data verdict.
    assert report["projects"][0]["verdict"] == "no_data"
    assert report["overall_verdict"] == "no_data"
    assert report["guardrails"]["no_writeback"] is True
    assert report["guardrails"]["no_live_call_performed"] is True
    # Raw-free.
    blob = json.dumps(report) + render_procore_monitoring_markdown(report)
    for bad in ("Bearer ", "https://", "-----BEGIN", '"token"', '"secret"'):
        assert bad not in blob


def test_fresh_watermark_is_not_no_data(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    verified_id = _ep.list_verified()[0].endpoint_id
    _seed_watermark(db, "PRJ-A", verified_id, NOW)  # fresh
    report = build_procore_monitoring_report(now_utc=NOW, project_keys=["PRJ-A"], db_path=db)
    p = report["projects"][0]
    # At least one current endpoint → no longer no_data (partial_stale, since others never synced).
    assert p["verdict"] in ("healthy", "partial_stale")
    assert p["refresh_summary"]["current"] >= 1


def test_cli_monitor_emits_json(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    res = runner.invoke(app, ["procore", "live", "monitor", "--db", db,
                              "--project", "PRJ-A", "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["command"] == "procore live monitor"
    assert "endpoint_contract" in payload
    assert payload["guardrails"]["read_only"] is True
