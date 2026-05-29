"""CLI surface tests for `hb-assistant procore obsidian register`."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.procore import app
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_repositories import (
    record_sync_run_start,
    upsert_procore_live_record,
)

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


def _new_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _seed_rfi(db: Path) -> None:
    record_sync_run_start(
        sync_run_id="run-cli",
        endpoint_id="rfis",
        command_endpoint="rfis",
        legacy_endpoint_alias="list-rfis",
        project_key="tropical",
        procore_project_id="2525840",
        company_id="5280",
        mode="live_apply",
        started_at_utc="2026-05-29T00:00:00+00:00",
        db_path=db,
    )
    upsert_procore_live_record(
        project_key="tropical", procore_project_id="2525840",
        endpoint_id="rfis", procore_record_id="100", parent_procore_id=None,
        normalized_fields={"number": "RFI-100", "subject": "subj", "status": "open"},
        review_required=False, sensitive_reason=None,
        source_url_redacted="/rest/v1.0/projects/2525840/rfis",
        last_sync_run_id="run-cli",
        now_utc="2026-05-29T00:00:00+00:00",
        db_path=db,
    )


def _invoke(args: list[str]) -> tuple[int, dict]:
    runner = CliRunner()
    result = runner.invoke(app, args)
    payload: dict = {}
    if result.stdout.strip():
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            payload = {"_raw": result.stdout}
    return result.exit_code, payload


def test_cli_missing_from_sqlite_flag_exits_2() -> None:
    code, payload = _invoke([
        "obsidian", "register",
        "--project", "tropical", "--endpoint", "rfis",
        "--dry-run", "--json",
    ])
    assert code == 2
    assert payload["ok"] is False
    assert payload["status"] == "missing_required_flag"


def test_cli_unknown_endpoint_alias_exits_2() -> None:
    code, payload = _invoke([
        "obsidian", "register",
        "--project", "tropical", "--endpoint", "totally-unknown",
        "--from-sqlite", "--dry-run", "--json",
    ])
    assert code == 2
    assert payload["ok"] is False
    assert payload["status"] == "endpoint_alias_unknown"


def test_cli_unsupported_register_endpoint_exits_2() -> None:
    db = _new_db()
    with patch("hb_assistant.procore.obsidian.get_connection") as p:
        import sqlite3
        p.return_value = sqlite3.connect(str(db))
        code, payload = _invoke([
            "obsidian", "register",
            "--project", "tropical", "--endpoint", "punch-items",
            "--from-sqlite", "--dry-run", "--json",
        ])
    assert code == 2
    assert payload["ok"] is False
    assert payload["status"] == "unsupported_endpoint"
    assert "next_steps" in payload


def test_cli_dry_run_returns_ok_with_rendered_section() -> None:
    db = _new_db()
    _seed_rfi(db)
    with patch("hb_assistant.procore.obsidian.get_connection") as p:
        import sqlite3
        p.return_value = sqlite3.connect(str(db))
        code, payload = _invoke([
            "obsidian", "register",
            "--project", "tropical", "--endpoint", "rfis",
            "--from-sqlite", "--dry-run", "--json",
        ])
    assert code == 0
    assert payload["ok"] is True
    assert payload["family_template"] == "rfi_register"
    assert payload["count_from_sqlite"] == 1
    assert "RFI-100" in payload["rendered"]
    assert payload["written_paths"] == []


def test_cli_apply_with_confirm_writes_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = tmp_path / "construction-vault"
    vault.mkdir()
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(vault))
    db = _new_db()
    _seed_rfi(db)
    with patch("hb_assistant.procore.obsidian.get_connection") as p:
        import sqlite3
        p.return_value = sqlite3.connect(str(db))
        code, payload = _invoke([
            "obsidian", "register",
            "--project", "tropical", "--endpoint", "rfis",
            "--from-sqlite", "--apply", "--confirm", "--json",
        ])
    assert code == 0, payload
    assert payload["ok"] is True
    assert payload["mode"] == "apply"
    assert len(payload["written_paths"]) == 1
    written = Path(payload["written_paths"][0])
    assert written.exists()
    assert "RFI-100" in written.read_text(encoding="utf-8")


def test_cli_apply_without_confirm_in_non_tty_exits_1() -> None:
    # CliRunner is non-TTY by default; --apply without --confirm must reject.
    code, payload = _invoke([
        "obsidian", "register",
        "--project", "tropical", "--endpoint", "rfis",
        "--from-sqlite", "--apply", "--json",
    ])
    assert code == 1
