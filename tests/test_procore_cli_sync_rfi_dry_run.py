"""Phase 04 Prompt 04 — CLI dry-run for the RFI endpoint."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from hb_assistant.cli.procore import app


def _run(args: list[str]) -> tuple[int, dict]:
    runner = CliRunner()
    result = runner.invoke(app, args)
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.exit_code, payload


def test_sync_run_dry_run_with_endpoints_filter_emits_only_list_rfis() -> None:
    exit_code, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "--endpoints",
            "list-rfis",
            "--json",
        ]
    )
    assert exit_code == 0
    assert payload["mode"] == "dry_run"
    assert payload["audit_prerequisite_passed"] is True
    endpoint_entries = payload.get("per_endpoint", [])
    assert len(endpoint_entries) == 1
    entry = endpoint_entries[0]
    assert entry["endpoint_id"] == "list-rfis"
    assert entry["category"] == "rfis"
    assert entry["normalization_schema_version"] >= 1
    assert entry["would_persist_children_separately"] is True
    # Live eligibility carries through Prompt 03 metadata.
    assert entry["live_eligible"] is True
    assert entry["verification_status"] == "official_docs_verified"


def test_sync_run_dry_run_endpoint_filter_excludes_other_endpoints() -> None:
    _, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "-e",
            "list-rfis",
            "--json",
        ]
    )
    endpoint_ids = [e["endpoint_id"] for e in payload.get("per_endpoint", [])]
    assert endpoint_ids == ["list-rfis"]


def test_sync_run_dry_run_no_endpoint_filter_emits_full_contract() -> None:
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
    assert "list-rfis" in endpoint_ids
    assert len(endpoint_ids) > 1


def test_sync_run_dry_run_emits_no_raw_body_text() -> None:
    _, payload = _run(
        [
            "sync",
            "run",
            "--project",
            "tropical",
            "--dry-run",
            "--endpoints",
            "list-rfis",
            "--json",
        ]
    )
    serialized = json.dumps(payload)
    # Common sensitive substrings should never appear in dry-run output.
    assert "Bearer" not in serialized
    assert "client_secret" not in serialized.lower()
    assert "access_token" not in serialized.lower()
