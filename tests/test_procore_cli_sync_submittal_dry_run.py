"""Phase 04 Prompt 05 — CLI dry-run for the submittal endpoint."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from hb_assistant.cli.procore import app


def _run(args: list[str]) -> tuple[int, dict]:
    runner = CliRunner()
    result = runner.invoke(app, args)
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.exit_code, payload


def test_sync_run_dry_run_with_endpoints_filter_emits_only_list_submittals() -> None:
    exit_code, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "--endpoints",
            "list-submittals",
            "--json",
        ]
    )
    assert exit_code == 0
    assert payload["mode"] == "dry_run"
    assert payload["audit_prerequisite_passed"] is True
    endpoint_entries = payload.get("per_endpoint", [])
    assert len(endpoint_entries) == 1
    entry = endpoint_entries[0]
    assert entry["endpoint_id"] == "list-submittals"
    assert entry["category"] == "submittals"
    assert entry["normalization_schema_version"] >= 1
    assert entry["would_persist_children_separately"] is True
    assert entry["live_eligible"] is True
    assert entry["verification_status"] == "official_docs_verified"


def test_sync_run_dry_run_filter_excludes_other_endpoints() -> None:
    _, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "-e",
            "list-submittals",
            "--json",
        ]
    )
    endpoint_ids = [e["endpoint_id"] for e in payload.get("per_endpoint", [])]
    assert endpoint_ids == ["list-submittals"]


def test_sync_run_dry_run_emits_no_raw_body_text() -> None:
    _, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "--endpoints",
            "list-submittals",
            "--json",
        ]
    )
    serialized = json.dumps(payload)
    assert "Bearer" not in serialized
    assert "client_secret" not in serialized.lower()
    assert "access_token" not in serialized.lower()
