"""Phase 07C Prompt 10 — `graph files document-obsidian` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.store.repositories import ConstructionStore

runner = CliRunner()


def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app-support"))
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(tmp_path / "vault"))


def _seed(store: ConstructionStore) -> None:
    for i, dt in enumerate(["rfi", "contract"]):
        key = f"c{i}"
        store.upsert_inventory_item(
            source_key="sp", drive_id="d", item_id=key, name="raw_" + key, web_url="https://x/" + key,
            parent_path="/General", size_bytes=1024, is_folder=False, last_modified=None, etag="e",
        )
        store.upsert_document_card(
            card_id=key, document_card_id=key, source_id="sp", drive_item_id=key,
            file_extension="pdf", project_key="alpha", review_required=True, size_class="small",
        )
        store.upsert_document_classification_candidate(
            candidate_id="clf_" + key, document_card_id=key, document_type=dt,
            classifier_name="deterministic_v1", signal_class="deterministic", confidence=0.9,
            confidence_class="deterministic", review_required=False,
        )
    warnings_json = json.dumps(
        {"warnings": [], "source_reference": {"project_key": "alpha", "document_count": 2,
         "distinct_sources": 1}, "review": {"documents_pending_review": 2,
         "candidate_items_pending_review": 0}}
    )
    store.upsert_document_intelligence_preview(
        preview_id="pv_alpha", project_key="alpha",
        preview_kind="project_document_intelligence", confidence_class="moderate_heuristic",
        warnings_json=warnings_json, review_required=True,
    )


def test_dry_run_then_apply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, tmp_path)
    db = str(tmp_path / "cli.sqlite")
    _seed(ConstructionStore(db))
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )

    result = runner.invoke(app, ["files", "document-obsidian", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files document-obsidian"
    assert payload["mode"] == "dry_run"
    assert payload["summary"]["notes_planned"] == 2
    assert payload["summary"]["notes_written"] == 0
    assert payload["guardrails"]["one_note_per_document"] is False

    result = runner.invoke(app, ["files", "document-obsidian", "--apply", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "apply"
    assert payload["summary"]["notes_written"] == 2
    for p in payload["paths"]:
        assert Path(p).exists()
