"""Phase 07C Prompt 04 — `graph files materialize-document-cards` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.store.repositories import ConstructionStore

runner = CliRunner()


def _seed_compliant_inventory(store: ConstructionStore) -> None:
    # Use the real registry's compliant SharePoint source key so the live policy
    # marks it compliant. Two active files + one folder.
    from hb_assistant.construction.config import load_source_registry

    sp = next(
        s for s in load_source_registry().sources
        if str(s.kind) == "sharepoint_project_drive_folder"
    )
    store.upsert_inventory_item(
        source_key=sp.source_key, drive_id="d1", item_id="f1", name="a.pdf",
        web_url="https://x/a", parent_path="/p", size_bytes=2048, is_folder=False,
        last_modified="2026-05-01T00:00:00Z", etag="e1",
    )
    store.upsert_inventory_item(
        source_key=sp.source_key, drive_id="d1", item_id="f2", name="b.dwg",
        web_url="https://x/b", parent_path="/p", size_bytes=4096, is_folder=False,
        last_modified=None, etag="e2",
    )
    store.upsert_inventory_item(
        source_key=sp.source_key, drive_id="d1", item_id="dir", name="d",
        web_url="https://x/d", parent_path="/p", size_bytes=None, is_folder=True,
        last_modified=None, etag="e3",
    )


def test_dry_run_then_apply_then_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = str(tmp_path / "cli.sqlite")
    _seed_compliant_inventory(ConstructionStore(db))
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )

    # Dry-run: reports counts, writes nothing.
    result = runner.invoke(app, ["files", "materialize-document-cards", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files materialize-document-cards"
    assert payload["mode"] == "dry_run"
    assert payload["summary"]["cards_written"] == 2
    assert payload["guardrails"]["local_sqlite_write"] is False
    assert ConstructionStore(db).count_document_cards() == 0

    # Apply: persists.
    result = runner.invoke(app, ["files", "materialize-document-cards", "--apply", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "apply"
    assert payload["summary"]["cards_written"] == 2
    assert ConstructionStore(db).count_document_cards() == 2

    # Re-apply: idempotent.
    runner.invoke(app, ["files", "materialize-document-cards", "--apply", "--json"])
    assert ConstructionStore(db).count_document_cards() == 2
