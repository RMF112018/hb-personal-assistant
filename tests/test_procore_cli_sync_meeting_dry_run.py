"""Phase 04 Prompt 07 — CLI dry-run for the meeting + meeting-topic endpoints.

Both endpoints ship as ``verification_status: candidate`` → ``is_live_eligible:
false``. ``apply()`` therefore emits ``skipped_not_live_eligible`` until a
future prompt promotes the verification status. The dry-run path still
surfaces both endpoints with full normalization metadata.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from hb_assistant.cli.procore import app


def _run(args: list[str]) -> tuple[int, dict]:
    runner = CliRunner()
    result = runner.invoke(app, args)
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.exit_code, payload


def test_sync_run_dry_run_list_meetings_only() -> None:
    exit_code, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "--endpoints",
            "list-meetings",
            "--json",
        ]
    )
    assert exit_code == 0
    assert payload["mode"] == "dry_run"
    entries = payload.get("per_endpoint", [])
    assert len(entries) == 1
    entry = entries[0]
    assert entry["endpoint_id"] == "list-meetings"
    assert entry["category"] == "meetings"
    assert entry["normalization_schema_version"] >= 1
    assert entry["live_eligible"] is False
    assert entry["verification_status"] == "candidate"


def test_sync_run_dry_run_list_meeting_topics_only() -> None:
    exit_code, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "--endpoints",
            "list-meeting-topics",
            "--json",
        ]
    )
    assert exit_code == 0
    entries = payload.get("per_endpoint", [])
    assert len(entries) == 1
    entry = entries[0]
    assert entry["endpoint_id"] == "list-meeting-topics"
    assert entry["category"] == "meeting-topics"
    assert entry["normalization_schema_version"] >= 1
    assert entry["live_eligible"] is False
    assert entry["verification_status"] == "candidate"


def test_sync_run_dry_run_both_meeting_endpoints_filter() -> None:
    _, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "-e",
            "list-meetings",
            "-e",
            "list-meeting-topics",
            "--json",
        ]
    )
    endpoint_ids = sorted(e["endpoint_id"] for e in payload.get("per_endpoint", []))
    assert endpoint_ids == ["list-meeting-topics", "list-meetings"]


def test_sync_run_dry_run_meeting_filter_excludes_other_endpoints() -> None:
    _, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "-e",
            "list-meetings",
            "--json",
        ]
    )
    endpoint_ids = [e["endpoint_id"] for e in payload.get("per_endpoint", [])]
    assert endpoint_ids == ["list-meetings"]


def test_sync_run_dry_run_meeting_emits_no_raw_body_text() -> None:
    _, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "-e",
            "list-meetings",
            "-e",
            "list-meeting-topics",
            "--json",
        ]
    )
    serialized = json.dumps(payload)
    assert "Bearer" not in serialized
    assert "client_secret" not in serialized.lower()
    assert "access_token" not in serialized.lower()
