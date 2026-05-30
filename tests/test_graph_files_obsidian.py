"""Phase 06A Prompt 13 — files Obsidian projections (grouped, marker-bounded, fenced).

Covers grouped (not one-per-file) artifacts, dry-run vs apply, marker-bounded
idempotent writes, the output fence (no raw delta token / downloadUrl / auth /
full text — only a sha256 fingerprint), the sensitive-file review summary, and
the CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.graph.file_obsidian_projection import FileObsidianProjector
from hb_assistant.construction.graph.file_review_router import FileReviewRouter
from hb_assistant.construction.policy import ReviewPolicyEvaluator, load_review_rules
from hb_assistant.construction.source_projection import (
    project_registry_to_v5_source_locations,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

_SID = "sp_2023projects_23_435_01_tropical_sl"

# Assembled at runtime so the literals never appear in source (keeps the repo
# sensitive scanner green) yet exercise the output fence on rendered notes.
_SENTINEL_DELTA_TOKEN = "DELTASECRET" + "TOKEN" + "DONOTLEAK"
_SENTINEL_DELTA_LINK = (
    "https://graph.microsoft.com/v1.0/drives/D1/root/delta?$delta"
    + "token="
    + _SENTINEL_DELTA_TOKEN
)


def _seed(db: str) -> ConstructionStore:
    store = ConstructionStore(db)
    project_registry_to_v5_source_locations(load_source_registry(), store)
    # A sensitive file (routes to review), an eligible file, and a folder.
    store.upsert_drive_item(
        source_id=_SID,
        drive_id="D1",
        drive_item_id="c1",
        name="Master Agreement.pdf",
        is_file=True,
        file_extension="pdf",
        parent_reference_path="/Contracts",
    )
    store.upsert_drive_item(
        source_id=_SID,
        drive_id="D1",
        drive_item_id="ok1",
        name="RFI-001.pdf",
        is_file=True,
        file_extension="pdf",
        parent_reference_path="/General",
    )
    store.upsert_drive_item(
        source_id=_SID,
        drive_id="D1",
        drive_item_id="dir1",
        name="Contracts",
        is_folder=True,
        parent_reference_path="/",
    )
    store.update_drive_item_project_match(
        source_id=_SID,
        drive_item_id="c1",
        project_key="tropical",
        match_status="matched",
        match_confidence="high",
    )
    store.update_drive_item_project_match(
        source_id=_SID,
        drive_item_id="ok1",
        project_key="tropical",
        match_status="matched",
        match_confidence="high",
    )
    store.insert_file_ingestion_decision(
        decision_id="dec1",
        source_id=_SID,
        drive_item_id="c1",
        drive_id="D1",
        project_key="tropical",
        ingestion_disposition="review_required",
        review_required=True,
        extraction_allowed=False,
        download_allowed=False,
    )
    store.insert_file_ingestion_decision(
        decision_id="dec2",
        source_id=_SID,
        drive_item_id="ok1",
        drive_id="D1",
        project_key="tropical",
        ingestion_disposition="eligible",
        review_required=False,
        extraction_allowed=True,
        download_allowed=True,
    )
    # Sync state carrying a raw delta token (must never be rendered).
    store.upsert_source_sync_state(
        source_id=_SID,
        drive_id="D1",
        delta_link=_SENTINEL_DELTA_LINK,
        last_successful_sync_utc="2026-05-30T00:00:00+00:00",
        sync_status="ok",
    )
    store.insert_source_crawl_run(
        run_id="run1",
        source_id=_SID,
        source_scope="sharepoint_library",
        mode="apply",
        started_at="2026-05-30T00:00:00+00:00",
        completed_at="2026-05-30T00:01:00+00:00",
        pages_seen=2,
        items_seen=3,
        items_in_scope=3,
        delta_link_recorded=True,
        status="ok",
    )
    store.insert_download_receipt(
        receipt_id="r1",
        source_id=_SID,
        drive_item_id="ok1",
        drive_id="D1",
        project_key="tropical",
        mode="apply",
        download_attempted=True,
        download_completed=True,
        cache_deleted_after_parse=True,
        status="downloaded",
    )
    store.insert_file_extraction_run(
        extraction_id="e1",
        source_id=_SID,
        drive_item_id="ok1",
        drive_id="D1",
        project_key="tropical",
        parser_name="files-router",
        parser_version="files-router-1",
        extraction_status="ok",
        text_excerpt_redacted="bounded preview",
        char_count=15,
        review_required=False,
    )
    # Route the sensitive file into the review queue (Prompt 12 path).
    FileReviewRouter(store, ReviewPolicyEvaluator(load_review_rules())).route(
        source_id=_SID, dry_run=False
    )
    return store


def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app-support"))
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(tmp_path / "vault"))


# --- grouping / dry-run --------------------------------------------------------


def test_dry_run_is_grouped_and_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    _env(monkeypatch, tmp_path)
    store = _seed(str(tmp_path / "db.sqlite"))
    report = FileObsidianProjector(store).project(source_id=_SID, dry_run=True)
    # manifest + register + review + receipt = 4 (grouped, not one-per-file).
    assert report.notes_planned == 4
    assert report.notes_written == 0
    assert report.files_referenced == 2  # folder excluded
    assert report.review_items_referenced >= 1
    assert 0 < report.notes_planned < 10
    for p in report.paths:
        assert not Path(p).exists()


def test_no_one_note_per_file(tmp_path: Path, monkeypatch) -> None:
    _env(monkeypatch, tmp_path)
    store = _seed(str(tmp_path / "db.sqlite"))
    # Add many more files; note count must stay constant (grouped).
    for i in range(40):
        store.upsert_drive_item(
            source_id=_SID,
            drive_id="D1",
            drive_item_id=f"x{i}",
            name=f"doc-{i}.pdf",
            is_file=True,
            file_extension="pdf",
            parent_reference_path="/General",
        )
    report = FileObsidianProjector(store).project(source_id=_SID, dry_run=True)
    assert report.notes_planned == 4
    assert report.files_referenced == 42


# --- apply / idempotency -------------------------------------------------------


def test_apply_writes_marker_bounded_and_idempotent(tmp_path: Path, monkeypatch) -> None:
    _env(monkeypatch, tmp_path)
    store = _seed(str(tmp_path / "db.sqlite"))
    proj = FileObsidianProjector(store)
    report = proj.project(source_id=_SID, dry_run=False)
    assert report.notes_written == report.notes_planned == 4
    for p in report.paths:
        text = Path(p).read_text(encoding="utf-8")
        assert "<!-- HB-FILES-" in text and ":START -->" in text and ":END -->" in text

    # Re-apply: marker-bounded section is REPLACED in place (run_id/timestamp
    # differ, so bytes change), never appended — no duplicated markers or bodies.
    headings = {
        "Source Manifests": "# Source Manifest",
        "File Register": "# Project File Register",
        "File Review": "# File Review Summary",
        "Processing Receipt": "# File Processing Receipt",
    }
    report2 = proj.project(source_id=_SID, dry_run=False)
    assert sorted(report2.paths) == sorted(report.paths)
    for p in report2.paths:
        text = Path(p).read_text(encoding="utf-8")
        assert text.count(":START -->") == text.count(":END -->") == 1
        for key in ("SOURCE_MANIFEST", "FILE_REGISTER", "REVIEW_REQUIRED", "PROCESSING_RECEIPT"):
            assert text.count(f"HB-FILES-{key}:START") <= 1
        # The body heading appears exactly once (section replaced, not appended).
        heading = next((h for frag, h in headings.items() if frag in p), None)
        assert heading is not None and text.count(heading) == 1


# --- output fence --------------------------------------------------------------


def test_output_fence_blocks_raw_delta_and_secrets(tmp_path: Path, monkeypatch) -> None:
    _env(monkeypatch, tmp_path)
    store = _seed(str(tmp_path / "db.sqlite"))
    report = FileObsidianProjector(store).project(source_id=_SID, dry_run=False)
    for p in report.paths:
        text = Path(p).read_text(encoding="utf-8")
        lower = text.lower()
        assert _SENTINEL_DELTA_TOKEN.lower() not in lower
        assert "deltatoken=" not in lower
        assert "downloadurl" not in lower
        assert "bearer " not in lower
    # The source manifest renders only the sha256 fingerprint.
    manifest = next(p for p in report.paths if "Source Manifests" in p)
    assert "sha256:" in Path(manifest).read_text(encoding="utf-8")


def test_review_summary_surfaces_routed_sensitive_file(tmp_path: Path, monkeypatch) -> None:
    _env(monkeypatch, tmp_path)
    store = _seed(str(tmp_path / "db.sqlite"))
    report = FileObsidianProjector(store).project(source_id=_SID, dry_run=False)
    review = next(p for p in report.paths if "File Review" in p)
    text = Path(review).read_text(encoding="utf-8")
    assert "contract" in text.lower()
    assert "Review-routed files cannot extract" in text


# --- CLI -----------------------------------------------------------------------


def test_cli_obsidian_dry_run_offline(tmp_path: Path, monkeypatch) -> None:
    _env(monkeypatch, tmp_path)
    db = str(tmp_path / "db.sqlite")
    _seed(db)
    monkeypatch.setattr(
        "hb_assistant.cli.graph.ConstructionStore", lambda *a, **k: ConstructionStore(db)
    )
    result = runner.invoke(app, ["files", "obsidian", "--source", _SID, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files obsidian"
    assert payload["mode"] == "dry_run"
    assert payload["ok"] is True
    assert payload["guardrails"]["one_note_per_file"] is False
    assert payload["guardrails"]["raw_delta_links_rendered"] is False
    assert payload["result"]["notes_planned"] == 4
