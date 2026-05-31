"""Phase 07C Prompt 07 — `graph files evaluate-extraction-eligibility` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.store.repositories import ConstructionStore

runner = CliRunner()


def _seed(store: ConstructionStore) -> None:
    for key, ext, size_class in [
        ("k1", "pdf", "small"),     # review-required (default) -> manual_approval_required
        ("k2", "dwg", "small"),     # metadata_only extension
        ("k3", "pdf", "oversize"),  # blocked (oversize)
    ]:
        store.upsert_inventory_item(
            source_key="sp", drive_id="d", item_id=key, name="raw_" + key, web_url="https://x/" + key,
            parent_path="/General", size_bytes=1024, is_folder=False, last_modified=None, etag="e",
        )
        store.upsert_document_card(
            card_id=key, document_card_id=key, source_id="sp", drive_item_id=key,
            file_extension=ext, size_class=size_class, review_required=True,
        )


def test_dry_run_then_apply_then_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = str(tmp_path / "cli.sqlite")
    _seed(ConstructionStore(db))
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )

    result = runner.invoke(app, ["files", "evaluate-extraction-eligibility", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files evaluate-extraction-eligibility"
    assert payload["mode"] == "dry_run"
    assert payload["summary"]["evaluated"] == 3
    assert payload["summary"]["eligible"] == 0
    assert payload["guardrails"]["download_performed"] is False
    cards = ConstructionStore(db).list_document_cards()
    assert all(c["extraction_eligibility"] == "not_evaluated" for c in cards)

    result = runner.invoke(app, ["files", "evaluate-extraction-eligibility", "--apply", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["mode"] == "apply"
    applied = {c["card_id"]: c["extraction_eligibility"] for c in ConstructionStore(db).list_document_cards()}
    assert applied == {"k1": "manual_approval_required", "k2": "metadata_only", "k3": "blocked"}

    runner.invoke(app, ["files", "evaluate-extraction-eligibility", "--apply", "--json"])
    reapplied = {c["card_id"]: c["extraction_eligibility"] for c in ConstructionStore(db).list_document_cards()}
    assert reapplied == applied
