"""Phase 08A Prompt 03 — `second-brain status` CLI (deterministic, offline).

Proves the command runs offline, reports the resolved posture, writes a
metadata-only config receipt with every no-raw/no-writeback guard column at 0,
and never emits the API key value.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app

_GUARD_COLUMNS = (
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "retrieved_context_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "arbitrary_sql_allowed",
    "external_writeback_performed",
)

_SECRET = "sk-ant-CLIVALUEMUSTNEVERLEAK"


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "second_brain.sqlite")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _redirect_store_to_tmp(monkeypatch: pytest.MonkeyPatch, db_path: str) -> None:
    from hb_assistant.construction.second_brain import store as sb_store
    from hb_assistant.store import connection as conn_mod
    from hb_assistant.store import migrator as mig_mod

    real = conn_mod.get_connection

    def _get(_: object = None) -> sqlite3.Connection:
        return real(Path(db_path))

    monkeypatch.setattr(sb_store, "get_connection", _get)
    monkeypatch.setattr(mig_mod, "get_connection", _get)


def test_status_offline_default_disabled(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str
) -> None:
    _redirect_store_to_tmp(monkeypatch, db_path)
    monkeypatch.delenv("HB_SECOND_BRAIN_ENABLED", raising=False)
    monkeypatch.delenv("HB_SECOND_BRAIN_MODE", raising=False)

    result = runner.invoke(app, ["second-brain", "status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    assert payload["runtime"]["mode"] == "disabled"
    assert payload["runtime"]["offline"] is True
    assert payload["runtime"]["synthesis_enabled"] is False
    assert payload["schema_version"] == payload["schema_version_expected"]
    assert payload["runtime_contract_version"].startswith("phase_08a_second_brain_runtime")
    assert payload["config_receipt_id"]
    assert payload["config_receipt_error"] is None
    assert payload["guardrails"]["external_writeback"] is False
    assert payload["guardrails"]["network_required_for_status"] is False


def test_status_writes_guarded_receipt(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str
) -> None:
    _redirect_store_to_tmp(monkeypatch, db_path)
    result = runner.invoke(app, ["second-brain", "status", "--json"])
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM second_brain_runtime_config_receipts").fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row["mode"] in ("disabled", "mock", "live")
    for col in _GUARD_COLUMNS:
        assert row[col] == 0, f"guard column {col} must be 0"
    # dependency_status_json is metadata booleans only — no secret/key value.
    assert _SECRET not in (row["dependency_status_json"] or "")
    conn.close()


def test_status_mock_mode(runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str) -> None:
    _redirect_store_to_tmp(monkeypatch, db_path)
    monkeypatch.setenv("HB_SECOND_BRAIN_ENABLED", "1")
    monkeypatch.setenv("HB_SECOND_BRAIN_MODE", "mock")

    result = runner.invoke(app, ["second-brain", "status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["runtime"]["mode"] == "mock"
    assert payload["runtime"]["synthesis_enabled"] is True


def test_status_no_emit_receipt(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str
) -> None:
    _redirect_store_to_tmp(monkeypatch, db_path)
    result = runner.invoke(app, ["second-brain", "status", "--json", "--no-emit-receipt"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["config_receipt_id"] is None
    assert not Path(db_path).exists() or _receipt_count(db_path) == 0


def test_status_never_emits_api_key(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, db_path: str
) -> None:
    _redirect_store_to_tmp(monkeypatch, db_path)
    monkeypatch.setenv("HB_SECOND_BRAIN_ENABLED", "1")
    monkeypatch.setenv("HB_ANTHROPIC_API_KEY", _SECRET)

    result = runner.invoke(app, ["second-brain", "status", "--json"])
    assert result.exit_code == 0, result.output
    assert _SECRET not in result.output
    payload = json.loads(result.output)
    assert payload["dependencies"]["api_key_configured"] is True


def _receipt_count(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM second_brain_runtime_config_receipts").fetchone()[
            0
        ]
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()
