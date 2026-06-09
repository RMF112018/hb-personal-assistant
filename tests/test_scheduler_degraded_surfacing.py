"""Scheduler degraded-surfacing tests: a degraded source-refresh must be operator-visible.

Covers the Procore-live-refresh degradation fix:
- the receipt carries honest `status` ("degraded", never silently "ok"),
- redacted `failures[]` + `failure_count` + per-stage `stages` + `next_operator_action`,
- the full orchestrator summary is persisted to evidence (`evidence_summary_path`),
- secrets/token-shaped values never leak into the receipt,
- manual runs exit nonzero (2) on degraded; clean runs exit 0.

All tests use the `isolated_hb_pa_config` fixture (temp config + temp app-support) so they never
touch the real production DB and are immune to a developer's local `config/config.yml`.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
from typer.testing import CliRunner

import hb_assistant.scheduler.daily_source_refresh as dsr_mod
from hb_assistant.cli.main import app
from hb_assistant.launcher.profiles import resolve_profile
from hb_assistant.scheduler.daily_source_refresh import DailySourceRefreshJob
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()


def _degraded_summary(*, reason: str = "ProcoreAuthRequired: live calls require auth") -> dict[str, Any]:
    return {
        "status": "degraded",
        "failures": [
            {"stage": "procore.tropical", "status": "failed", "reason": reason},
            {"stage": "procore.the-wellington", "status": "failed", "reason": reason},
        ],
        "warnings": [],
        "next_operator_action": "Review failures[] and warnings[], then re-run.",
        "preflight": {"status": "ok"},
        "procore_auth_status": "env_present",
        "procore_sync_summary": {
            "status": "degraded",
            "auth_status": "env_present",
            "counts": {"failed": 2, "planned": 0},
        },
        "graph_sync_summary": {"status": "live_disabled"},
        "retrieval_rebuild_summary": {"status": "ok"},
        "sqlite_upsert_summary": {
            "total": {"inserted": 0, "updated": 0, "skipped": 0, "failed": 2, "planned": 0}
        },
        "guardrails": {"no_procore_writeback": True},
    }


def _run_job(monkeypatch: pytest.MonkeyPatch, summary: dict[str, Any]) -> Any:
    monkeypatch.setattr(
        dsr_mod.SourceRefreshOrchestrator, "run", lambda self, *, options: summary
    )
    profile = resolve_profile("production")
    SQLiteMigrator(profile.db_path).apply()
    return DailySourceRefreshJob(profile).execute(schedule_date=date(2026, 6, 8), trigger="manual")


@pytest.mark.usefixtures("isolated_hb_pa_config")
def test_degraded_receipt_surfaces_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    receipt = _run_job(monkeypatch, _degraded_summary())
    # Honest status — never silently "ok".
    assert receipt.status == "degraded"
    assert receipt.orchestrator_status == "degraded"
    # Operator-visible failure detail.
    assert receipt.failure_count == 2
    assert len(receipt.failures) == 2
    assert receipt.failures[0]["stage"].startswith("procore.")
    assert receipt.failures[0]["status"] == "failed"
    assert receipt.failures[0]["reason"]
    assert receipt.stages["procore"] == "degraded"
    assert receipt.procore_auth_status == "env_present"
    assert receipt.next_operator_action
    # Full summary persisted to evidence for diagnosis without re-running.
    assert receipt.evidence_summary_path and receipt.evidence_summary_path.endswith(".json")


@pytest.mark.usefixtures("isolated_hb_pa_config")
def test_degraded_receipt_redacts_token_shaped_values(monkeypatch: pytest.MonkeyPatch) -> None:
    leaky = "ProcoreAuthRequired access_token=eyJabc123def456ghi789 refresh_token=zz"
    receipt = _run_job(monkeypatch, _degraded_summary(reason=leaky))
    blob = json.dumps(receipt.model_dump(), default=str)
    assert "eyJabc123def456ghi789" not in blob
    assert "access_token=eyJ" not in blob
    assert "[REDACTED]" in receipt.failures[0]["reason"]


@pytest.mark.usefixtures("isolated_hb_pa_config")
def test_failed_status_not_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    summary = _degraded_summary()
    summary["status"] = "failed"
    receipt = _run_job(monkeypatch, summary)
    assert receipt.status == "failed"
    assert receipt.orchestrator_status == "failed"


@pytest.mark.usefixtures("isolated_hb_pa_config")
def test_ok_run_still_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    summary = {
        "status": "ok",
        "failures": [],
        "sqlite_upsert_summary": {"total": {"inserted": 0, "updated": 0}},
        "guardrails": {"no_procore_writeback": True},
        "next_operator_action": "none",
    }
    receipt = _run_job(monkeypatch, summary)
    assert receipt.status == "ok"
    assert receipt.failure_count == 0


@pytest.mark.usefixtures("isolated_hb_pa_config")
def test_manual_degraded_run_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        dsr_mod.SourceRefreshOrchestrator, "run", lambda self, *, options: _degraded_summary()
    )
    profile = resolve_profile("production")
    SQLiteMigrator(profile.db_path).apply()
    result = runner.invoke(
        app,
        ["scheduler", "run", "daily-source-refresh", "--environment", "production", "--date", "2026-06-08", "--json"],
    )
    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "degraded"
    assert payload["orchestrator_status"] == "degraded"
    assert payload["failure_count"] == 2


@pytest.mark.usefixtures("isolated_hb_pa_config")
def test_manual_ok_run_exits_0(monkeypatch: pytest.MonkeyPatch) -> None:
    ok_summary = {
        "status": "ok",
        "failures": [],
        "sqlite_upsert_summary": {"total": {"inserted": 0, "updated": 0}},
        "guardrails": {},
        "next_operator_action": "none",
    }
    monkeypatch.setattr(
        dsr_mod.SourceRefreshOrchestrator, "run", lambda self, *, options: ok_summary
    )
    profile = resolve_profile("production")
    SQLiteMigrator(profile.db_path).apply()
    result = runner.invoke(
        app,
        ["scheduler", "run", "daily-source-refresh", "--environment", "production", "--date", "2026-06-08", "--json"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "ok"
