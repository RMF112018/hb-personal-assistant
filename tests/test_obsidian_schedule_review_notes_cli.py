"""Tests for obsidian_schedule_review_notes CLI."""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_review_workbench import _seed_driver_chain


def _load_cli():
    path = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_schedule_review_notes.py"
    spec = importlib.util.spec_from_file_location("obsidian_schedule_review_notes", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _seed_db(tmp_path: Path) -> Path:
    db = tmp_path / "cli.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    _seed_driver_chain(db)
    return db


def test_cli_dry_run_default(tmp_path: Path, monkeypatch) -> None:
    cli = _load_cli()
    db = _seed_db(tmp_path)
    vault = tmp_path / "obsidian-vault"
    vault.mkdir(parents=True, exist_ok=True)
    argv = [
        "--db-path",
        str(db),
        "--vault-path",
        str(vault),
        "--project-key",
        "tropical",
        "--note-type",
        "schedule_update",
        "--as-of",
        "2026-07-03",
    ]
    monkeypatch.setattr("sys.argv", ["obsidian_schedule_review_notes.py", *argv])
    assert cli.main() == 0
    assert list(vault.rglob("*.md")) == []


def test_cli_write_requires_confirm(tmp_path: Path, capsys) -> None:
    cli = _load_cli()
    db = _seed_db(tmp_path)
    vault = tmp_path / "obsidian-vault"
    vault.mkdir(parents=True, exist_ok=True)
    code = cli.run(
        [
            "--db-path",
            str(db),
            "--vault-path",
            str(vault),
            "--project-key",
            "tropical",
            "--write-notes",
        ]
    )
    assert code == 3


def test_cli_fixture_vault_write_and_idempotent(tmp_path: Path) -> None:
    cli = _load_cli()
    db = _seed_db(tmp_path)
    vault = tmp_path / "obsidian-vault"
    vault.mkdir(parents=True, exist_ok=True)
    base_args = [
        "--db-path",
        str(db),
        "--vault-path",
        str(vault),
        "--project-key",
        "tropical",
        "--note-type",
        "schedule_update",
        "--as-of",
        "2026-07-03",
        "--write-notes",
        "--confirm-vault-write",
        "--json-output",
        str(tmp_path / "summary.json"),
    ]
    assert cli.run(base_args) == 0
    written = list(vault.rglob("*.md"))
    assert len(written) == 1
    before = written[0].read_text(encoding="utf-8")
    assert cli.run(base_args) == 0
    after = written[0].read_text(encoding="utf-8")
    assert before == after
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["ollama_calls"] == 0


def test_cli_summarize_requires_confirm_local_llm(tmp_path: Path) -> None:
    cli = _load_cli()
    db = _seed_db(tmp_path)
    vault = tmp_path / "obsidian-vault"
    vault.mkdir(parents=True, exist_ok=True)
    code = cli.run(
        [
            "--db-path",
            str(db),
            "--vault-path",
            str(vault),
            "--project-key",
            "tropical",
            "--summarize",
        ]
    )
    assert code == 3
