"""Tests for Prompt 11 `procore validate` CLI surface (100% mocked, no live Procore).

Covers: help shape, envelope keys, --strict semantics, redacted per-check exception
handling, fresh-DB tolerance, exit-code parity with `ok`.

All tests use typer.testing.CliRunner + tmp_path. No HTTP. No vault writes.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.procore.validate import run_procore_validate
from hb_assistant.store.migrator import SQLiteMigrator

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


_FAKE_TOKEN = "abc" + "DEF" * 12 + "xyz"  # 20+ char token-shaped string for redaction proof


def _prepared_db_path(tmp_path: Path) -> Path:
    db_path = tmp_path / "validate.sqlite"
    SQLiteMigrator(str(db_path)).apply()
    return db_path


def test_validate_help_lists_command() -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["procore", "validate", "--help"], catch_exceptions=False)
    assert res.exit_code == 0
    assert "validate" in res.output
    assert "--strict" in res.output
    assert "--json" in res.output


def test_validate_default_json_envelope_keys() -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["procore", "validate", "--json"], catch_exceptions=False)
    assert res.exit_code in (0, 1)  # ok depends on local env; envelope shape is the contract
    payload = json.loads(res.output)
    for key in ("command", "schema_version", "started_at", "completed_at", "strict", "ok", "summary", "checks", "guardrails"):
        assert key in payload, f"missing top-level key: {key}"
    assert payload["command"] == "hb-assistant procore validate"
    assert isinstance(payload["checks"], list) and len(payload["checks"]) == 25
    assert {"total", "passed", "failed"} <= set(payload["summary"].keys())
    assert payload["guardrails"]["external_systems_called"] is False
    assert payload["guardrails"]["writeback"] is False
    for check in payload["checks"]:
        assert {"name", "ok"} <= set(check.keys())


def test_validate_strict_flips_not_configured_to_fail() -> None:
    from hb_assistant.procore.models import AuthStatusReport

    not_configured = AuthStatusReport(
        status="env_absent",
        env_keys_present=[],
        env_keys_missing=["PROCORE_CLIENT_ID", "PROCORE_CLIENT_SECRET", "PROCORE_REFRESH_TOKEN"],
        token_cache_present=False,
        ready_for_live_calls=False,
        hint="(test) no creds",
    )

    with patch("hb_assistant.procore.validate.check_auth_status", return_value=not_configured):
        non_strict = run_procore_validate(strict=False)
        strict = run_procore_validate(strict=True)

    auth_non_strict = next(c for c in non_strict["checks"] if c["name"] == "auth_status_present")
    auth_strict = next(c for c in strict["checks"] if c["name"] == "auth_status_present")
    assert auth_non_strict["ok"] is True
    assert auth_strict["ok"] is False


def test_validate_redacts_check_exceptions() -> None:
    boom = RuntimeError(f"contract load blew up with token {_FAKE_TOKEN}")
    with patch("hb_assistant.procore.validate.load_endpoint_contract", side_effect=boom):
        envelope = run_procore_validate(strict=False)

    failed = next(c for c in envelope["checks"] if c["name"] == "seed_endpoint_contract_loadable")
    assert failed["ok"] is False
    assert "error_redacted" in failed
    serialized = json.dumps(envelope)
    assert _FAKE_TOKEN not in serialized, "raw token-shaped exception text leaked into envelope"


def test_validate_handles_fresh_db_without_procore_tables(tmp_path: Path) -> None:
    db_path = _prepared_db_path(tmp_path)

    non_strict = run_procore_validate(strict=False, db_path=db_path)
    strict = run_procore_validate(strict=True, db_path=db_path)

    tables_non_strict = next(c for c in non_strict["checks"] if c["name"] == "procore_tables_present")
    tables_strict = next(c for c in strict["checks"] if c["name"] == "procore_tables_present")

    assert tables_non_strict["ok"] is True
    assert tables_non_strict["detail"]["all_present"] is False
    assert tables_strict["ok"] is False
    assert tables_strict["detail"]["all_present"] is False


def test_validate_exit_code_matches_ok() -> None:
    runner = CliRunner()
    envelope_ok = {"command": "x", "ok": True, "checks": [{"name": "noop", "ok": True}], "summary": {"total": 1, "passed": 1, "failed": 0}, "guardrails": {}, "schema_version": 1, "started_at": "x", "completed_at": "x", "strict": False}
    envelope_fail = {**envelope_ok, "ok": False, "checks": [{"name": "noop", "ok": False}], "summary": {"total": 1, "passed": 0, "failed": 1}}

    with patch("hb_assistant.procore.validate.run_procore_validate", return_value=envelope_ok):
        res = runner.invoke(app, ["procore", "validate", "--json"], catch_exceptions=False)
        assert res.exit_code == 0

    with patch("hb_assistant.procore.validate.run_procore_validate", return_value=envelope_fail):
        res = runner.invoke(app, ["procore", "validate", "--json"], catch_exceptions=False)
        assert res.exit_code == 1


def test_validate_no_json_emits_compact_summary() -> None:
    runner = CliRunner()
    envelope = {
        "command": "hb-assistant procore validate",
        "ok": True,
        "schema_version": 1,
        "started_at": "x",
        "completed_at": "x",
        "strict": False,
        "checks": [
            {"name": "alpha", "ok": True},
            {"name": "beta", "ok": True},
        ],
        "summary": {"total": 2, "passed": 2, "failed": 0},
        "guardrails": {},
    }
    with patch("hb_assistant.procore.validate.run_procore_validate", return_value=envelope):
        res = runner.invoke(app, ["procore", "validate", "--no-json"], catch_exceptions=False)
    assert res.exit_code == 0
    assert "[ok] alpha" in res.output
    assert "[ok] beta" in res.output
    assert "overall: ok" in res.output
