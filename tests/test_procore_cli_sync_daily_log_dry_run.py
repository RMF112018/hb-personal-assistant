"""Phase 04 Prompt 08 — CLI dry-run for the daily log endpoint."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from hb_assistant.cli.procore import app


def _run(args: list[str]) -> tuple[int, dict]:
    runner = CliRunner()
    result = runner.invoke(app, args)
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.exit_code, payload


def test_sync_run_dry_run_list_daily_logs_only() -> None:
    exit_code, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "--endpoints",
            "list-daily-logs",
            "--json",
        ]
    )
    assert exit_code == 0
    entries = payload.get("per_endpoint", [])
    assert len(entries) == 1
    entry = entries[0]
    assert entry["endpoint_id"] == "list-daily-logs"
    assert entry["category"] == "daily-logs"
    assert entry["normalization_schema_version"] >= 1
    assert entry["live_eligible"] is True
    assert entry["verification_status"] == "official_docs_verified"
    assert entry["would_persist_sections_separately"] is True
    # Daily-logs uses sections, not nested children, so children flag is False.
    assert entry["would_persist_children_separately"] is False


def test_sync_run_dry_run_daily_log_filter_excludes_other_endpoints() -> None:
    _, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "-e",
            "list-daily-logs",
            "--json",
        ]
    )
    endpoint_ids = [e["endpoint_id"] for e in payload.get("per_endpoint", [])]
    assert endpoint_ids == ["list-daily-logs"]


def test_sync_run_dry_run_daily_log_emits_no_raw_body_text() -> None:
    _, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "-e",
            "list-daily-logs",
            "--json",
        ]
    )
    serialized = json.dumps(payload)
    assert "Bearer" not in serialized
    assert "client_secret" not in serialized.lower()
    assert "access_token" not in serialized.lower()


def test_sync_run_dry_run_no_filter_still_includes_daily_logs() -> None:
    _, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "--json",
        ]
    )
    endpoint_ids = [e["endpoint_id"] for e in payload.get("per_endpoint", [])]
    assert "list-daily-logs" in endpoint_ids
