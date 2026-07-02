"""Tests for obsidian_schedule_note_graph CLI gates (Phase 20)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from hb_assistant.obsidian_mcp.schedule_obsidian_note_writer import apply_schedule_note_write
from hb_assistant.obsidian_mcp.schedule_review_note_generator import render_note_markdown


def _load_cli():
    path = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_schedule_note_graph.py"
    spec = importlib.util.spec_from_file_location("obsidian_schedule_note_graph", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _payload(**overrides):
    base = {
        "note_type": "schedule_update",
        "project_key": "tropical",
        "project_label": "Tropical Wind",
        "schedule_data_date": "2026-07-03",
        "comparison_basis": "prior_update",
        "comparison_label": "Prior Update",
        "analytics_trust_status": "ready",
        "identity_trust_status": "ready",
        "cpm_trust_status": "ready",
        "quality_trust_status": "ready",
        "as_of": "2026-07-03",
        "safe_links": {},
        "recommended_actions": [],
        "capability_limitations": ["Advisory only."],
        "review_status": {"headline": "Review pending"},
        "quality_controls": {"headline": "Controls available"},
    }
    base.update(overrides)
    return base


def _seed_vault(vault: Path) -> str:
    rel = "Work/HB Personal Assistant/Schedule Review/Projects/tropical/note.md"
    apply_schedule_note_write(vault_root=vault, relative_path=rel, payload=_payload(), dry_run=False)
    rel2 = "Work/HB Personal Assistant/Schedule Review/Projects/tropical/note2.md"
    apply_schedule_note_write(
        vault_root=vault,
        relative_path=rel2,
        payload=_payload(schedule_data_date="2026-07-08"),
        dry_run=False,
    )
    return rel


def test_cli_dry_run_default_zero_writes(tmp_path: Path) -> None:
    cli = _load_cli()
    vault = tmp_path / "fixture-vault"
    vault.mkdir(parents=True)
    _seed_vault(vault)
    out = tmp_path / "review.json"
    code = cli.run(
        [
            "--vault-path",
            str(vault),
            "--project-key",
            "tropical",
            "--json-output",
            str(out),
        ]
    )
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["apply"]["dry_run"] is True
    assert payload["apply"]["notes_modified"] == 0
    assert payload["apply"]["write_attempts"] == 0
    assert payload["ollama_calls"] == 0


def test_cli_apply_requires_confirm(tmp_path: Path) -> None:
    cli = _load_cli()
    vault = tmp_path / "fixture-vault"
    vault.mkdir(parents=True)
    _seed_vault(vault)
    assert cli.run(["--vault-path", str(vault), "--apply-links"]) == 3


def test_cli_fixture_apply_and_idempotent(tmp_path: Path) -> None:
    cli = _load_cli()
    vault = tmp_path / "fixture-vault"
    vault.mkdir(parents=True)
    _seed_vault(vault)
    args = [
        "--vault-path",
        str(vault),
        "--project-key",
        "tropical",
        "--apply-links",
        "--confirm-graph-apply",
        "--json-output",
        str(tmp_path / "apply1.json"),
    ]
    assert cli.run(args) == 0
    note = next(vault.rglob("note.md"))
    before = note.read_text(encoding="utf-8")
    assert "<!-- hb-schedule-graph:begin managed -->" in before
    assert cli.run(args) == 0
    after = note.read_text(encoding="utf-8")
    assert before == after


def test_cli_live_vault_apply_blocked_without_explicit_confirmation(tmp_path: Path) -> None:
    cli = _load_cli()
    vault = tmp_path / "live-vault"
    vault.mkdir(parents=True)
    _seed_vault(vault)
    code = cli.run(
        [
            "--vault-path",
            str(vault),
            "--apply-links",
            "--confirm-graph-apply",
        ]
    )
    assert code == 3


def test_cli_suggest_links_requires_confirm_local_llm(tmp_path: Path) -> None:
    cli = _load_cli()
    vault = tmp_path / "fixture-vault"
    vault.mkdir(parents=True)
    _seed_vault(vault)
    assert cli.run(["--vault-path", str(vault), "--suggest-links"]) == 3
