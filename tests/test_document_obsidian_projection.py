"""Phase 07C Prompt 10 — document-intelligence Obsidian projector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.construction.document import DocumentObsidianProjector
from hb_assistant.construction.store.repositories import ConstructionStore

_REGISTER_START = "<!-- HB-DOCS-DOCUMENT_REGISTER:START -->"
_REGISTER_END = "<!-- HB-DOCS-DOCUMENT_REGISTER:END -->"
_REVIEW_START = "<!-- HB-DOCS-DOCUMENT_REVIEW:START -->"


def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app-support"))
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(tmp_path / "vault"))


def _seed(db: str, *, with_preview: bool = True) -> ConstructionStore:
    store = ConstructionStore(db)
    for i, dt in enumerate(["rfi", "contract", "unknown_needs_review"]):
        key = f"c{i}"
        store.upsert_inventory_item(
            source_key="sp", drive_id="d", item_id=key, name="raw_" + key, web_url="https://x/" + key,
            parent_path="/General", size_bytes=1024, is_folder=False, last_modified=None, etag="e",
        )
        store.upsert_document_card(
            card_id=key, document_card_id=key, source_id="sp", drive_item_id=key,
            file_extension="pdf", project_key="alpha", review_required=True, size_class="small",
            extraction_eligibility="manual_approval_required",
        )
        store.upsert_document_classification_candidate(
            candidate_id="clf_" + key, document_card_id=key, document_type=dt,
            classifier_name="deterministic_v1", signal_class="deterministic", confidence=0.9,
            confidence_class="deterministic" if dt != "unknown_needs_review" else "unknown",
            review_required=(dt == "unknown_needs_review"),
        )
    store.upsert_document_relationship_candidate(
        candidate_id="rel_c0", document_card_id="c0", target_system="procore",
        target_record_type="rfi", target_record_key_hash="hh", relationship_type="x",
        candidate_type="heuristic", confidence=0.55, confidence_class="moderate_heuristic",
        review_required=True,
    )
    if with_preview:
        warnings_json = json.dumps(
            {
                "warnings": ["1 of 3 documents are unclassified — pending review."],
                "source_reference": {
                    "project_key": "alpha", "document_count": 3, "distinct_sources": 1,
                },
                "review": {"documents_pending_review": 3, "candidate_items_pending_review": 2},
            }
        )
        store.upsert_document_intelligence_preview(
            preview_id="pv_alpha", project_key="alpha",
            preview_kind="project_document_intelligence", confidence_class="weak_heuristic",
            preview_redacted="Project alpha preview (counts only)", warnings_json=warnings_json,
            document_card_id=None, review_required=True,
        )
    return store


def test_dry_run_is_grouped_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, tmp_path)
    store = _seed(str(tmp_path / "db.sqlite"))
    report = DocumentObsidianProjector(store).project(dry_run=True)
    assert report["mode"] == "dry_run"
    assert report["summary"]["notes_planned"] == 2  # register + review (not one-per-document)
    assert report["summary"]["notes_written"] == 0
    for p in report["paths"]:
        assert not Path(p).exists()
    reg = report["rendered"]["alpha"]["register"]
    assert "# Project Document Register" in reg
    assert "## Guardrails" in reg
    assert "rfi: 1" in reg and "contract: 1" in reg
    # No raw names / paths / URLs leaked into the rendered notes.
    assert "raw_c0" not in reg and "https://" not in reg
    assert report["guardrails"]["one_note_per_document"] is False
    assert report["guardrails"]["marker_bounded_writes"] is True
    assert report["guardrails"]["full_text_persisted"] is False


def test_apply_writes_marker_bounded_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, tmp_path)
    store = _seed(str(tmp_path / "db.sqlite"))
    report = DocumentObsidianProjector(store).project(dry_run=False)
    assert report["summary"]["notes_written"] == 2
    register_path = Path(report["paths"][0])
    review_path = Path(report["paths"][1])
    assert register_path.exists() and review_path.exists()
    text = register_path.read_text(encoding="utf-8")
    assert text.count(_REGISTER_START) == 1 and text.count(_REGISTER_END) == 1
    assert _REVIEW_START in review_path.read_text(encoding="utf-8")

    # Re-apply: markers stay singular (bounded region replaced, not appended).
    DocumentObsidianProjector(store).project(dry_run=False)
    text2 = register_path.read_text(encoding="utf-8")
    assert text2.count(_REGISTER_START) == 1 and text2.count(_REGISTER_END) == 1


def test_no_preview_yields_no_notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, tmp_path)
    store = _seed(str(tmp_path / "db.sqlite"), with_preview=False)
    report = DocumentObsidianProjector(store).project(dry_run=True)
    assert report["summary"]["notes_planned"] == 0
    assert report["rendered"] == {}
