"""Phase 04 Prompt 06 — CLI dry-run for the observation endpoint.

The endpoint ships as ``verification_status: candidate`` → ``is_live_eligible:
false``. ``apply()`` therefore emits ``skipped_not_live_eligible`` until a
future prompt promotes the verification status. The dry-run path still
surfaces the endpoint with full normalization metadata.
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


def test_sync_run_dry_run_with_endpoints_filter_emits_only_list_observations() -> None:
    exit_code, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "--endpoints",
            "list-observations",
            "--json",
        ]
    )
    assert exit_code == 0
    assert payload["mode"] == "dry_run"
    assert payload["audit_prerequisite_passed"] is True
    endpoint_entries = payload.get("per_endpoint", [])
    assert len(endpoint_entries) == 1
    entry = endpoint_entries[0]
    assert entry["endpoint_id"] == "list-observations"
    assert entry["category"] == "observations"
    assert entry["normalization_schema_version"] >= 1
    assert entry["would_persist_children_separately"] is True
    # Candidate endpoint stays blocked from live execution.
    assert entry["live_eligible"] is False
    assert entry["verification_status"] == "candidate"


def test_sync_run_dry_run_filter_excludes_other_endpoints() -> None:
    _, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "-e",
            "list-observations",
            "--json",
        ]
    )
    endpoint_ids = [e["endpoint_id"] for e in payload.get("per_endpoint", [])]
    assert endpoint_ids == ["list-observations"]


def test_sync_run_dry_run_emits_no_raw_body_text() -> None:
    _, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "--endpoints",
            "list-observations",
            "--json",
        ]
    )
    serialized = json.dumps(payload)
    assert "Bearer" not in serialized
    assert "client_secret" not in serialized.lower()
    assert "access_token" not in serialized.lower()
