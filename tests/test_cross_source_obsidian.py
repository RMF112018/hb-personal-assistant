"""Phase 07D Prompt 11 — marker-bounded Obsidian cross-source intelligence outputs.

Covers dry-run preview/markers, apply-to-(temp)-vault with user-content preservation, empty source,
review-required surfacing, no-raw-content/output-fence, idempotency, and status coverage. Evidence
dir and vault root are injected as temp paths to avoid repo/vault pollution.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from hb_assistant.construction.obsidian import (
    ObsidianCrossSourceRenderer,
    cross_source_obsidian_status,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_LEAK = re.compile(
    r"https?://|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|BEGIN:V|-----BEGIN|Bearer |eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}",
    re.IGNORECASE,
)
_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_VAULT_SUBDIR = ("Construction Intelligence", "Phase 07D Cross-Source Intelligence")
_GUARDS = (
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
)


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_csobs_")
    os.close(fd)
    SQLiteMigrator(db_path=db).apply()
    return db


def _seed(store: ConstructionStore) -> None:
    store.upsert_cross_source_relationship_candidate(
        candidate_id="c0",
        source_family="email",
        source_record_type="m",
        source_record_ref="m0",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="r0",
        relationship_type="references",
        confidence_score=0.5,
        confidence_class="weak_heuristic",
        source_reference_json="{}",
        review_required=True,
        project_key="tropical",
        evidence_trail_id="et0",
    )
    store.upsert_project_risk_digest_item(
        risk_digest_id="r0",
        project_key="tropical",
        risk_indicator_type="invoice_payment_due",
        risk_source_class="source_stated",
        summary_redacted=json.dumps({"count": 2}),
        confidence_class="deterministic",
        review_required=True,
    )


def _notes_dir(vault: Path) -> Path:
    return vault.joinpath(*_VAULT_SUBDIR)


def _assert_guards_zero(db: str) -> None:
    raw = sqlite3.connect(db)
    try:
        cols = ", ".join(_GUARDS)
        for row in raw.execute(f"SELECT {cols} FROM cross_source_intelligence_obsidian_runs"):
            assert set(row) <= {0}, "obsidian run record has a non-zero guard column"
    finally:
        raw.close()


# ---------------------------------------------------------------------------


def test_dry_run_renders_markers_and_preview() -> None:
    db = _fresh_db()
    ev = Path(tempfile.mkdtemp())
    try:
        store = ConstructionStore(db_path=db)
        _seed(store)
        report = ObsidianCrossSourceRenderer(store).render(
            dry_run=True, project_filter="tropical", evidence_dir=ev, now_utc=_NOW
        )
        assert report["mode"] == "dry_run"
        assert report["notes_written"] == 0
        assert report["applied_to_vault"] is False
        assert set(report["rendered_excerpts"].keys()) == {
            "relationships",
            "meeting_prep",
            "issue_history",
            "risk_digest",
            "aging_exposure",
            "correspondence",
        }
        assert Path(report["evidence_preview_path"]).exists()
        assert (ev / "obsidian-cross-source-dry-run.json").exists()
        # markers present in the rendered preview
        preview = Path(report["evidence_preview_path"]).read_text(encoding="utf-8")
        assert "Cross-Source Relationships" in preview
    finally:
        Path(db).unlink(missing_ok=True)


def test_apply_writes_marker_bounded_vault_notes_preserving_user_content() -> None:
    db = _fresh_db()
    vault = Path(tempfile.mkdtemp())
    try:
        store = ConstructionStore(db_path=db)
        _seed(store)
        renderer = ObsidianCrossSourceRenderer(store)
        report = renderer.render(
            dry_run=False, apply=True, project_filter="tropical", vault_root=vault, now_utc=_NOW
        )
        assert report["mode"] == "apply"
        assert report["applied_to_vault"] is True
        assert report["notes_written"] == 6
        note = _notes_dir(vault) / "Risk Digest.md"
        assert note.exists()
        assert "HB-CROSS-SOURCE-RISK-DIGEST:START" in note.read_text(encoding="utf-8")
        # add user content outside markers; re-apply must preserve it and replace only inner
        note.write_text(
            note.read_text(encoding="utf-8") + "\n## My notes\nuser content\n", encoding="utf-8"
        )
        renderer.render(
            dry_run=False, apply=True, project_filter="tropical", vault_root=vault, now_utc=_NOW
        )
        after = note.read_text(encoding="utf-8")
        assert "user content" in after
        assert after.count("HB-CROSS-SOURCE-RISK-DIGEST:START") == 1
        _assert_guards_zero(db)
    finally:
        Path(db).unlink(missing_ok=True)


def test_empty_source_renders_without_crash() -> None:
    db = _fresh_db()
    ev = Path(tempfile.mkdtemp())
    try:
        store = ConstructionStore(db_path=db)
        report = ObsidianCrossSourceRenderer(store).render(
            dry_run=True, evidence_dir=ev, now_utc=_NOW
        )
        assert report["ok"] is True
        assert report["notes_written"] == 0
        assert len(report["rendered_excerpts"]) == 6
    finally:
        Path(db).unlink(missing_ok=True)


def test_review_required_surfaced_in_run_record() -> None:
    db = _fresh_db()
    ev = Path(tempfile.mkdtemp())
    try:
        store = ConstructionStore(db_path=db)
        _seed(store)
        report = ObsidianCrossSourceRenderer(store).render(
            dry_run=True, project_filter="tropical", evidence_dir=ev, now_utc=_NOW
        )
        assert report["review_required_count"] >= 2  # weak relationship + risk item
        run = store.list_cross_source_intelligence_obsidian_runs()[0]
        assert run["review_required_count"] >= 2
    finally:
        Path(db).unlink(missing_ok=True)


def test_no_raw_content_in_notes_and_report() -> None:
    db = _fresh_db()
    vault = Path(tempfile.mkdtemp())
    try:
        store = ConstructionStore(db_path=db)
        _seed(store)
        report = ObsidianCrossSourceRenderer(store).render(
            dry_run=False, apply=True, project_filter="tropical", vault_root=vault, now_utc=_NOW
        )
        assert _LEAK.search(json.dumps(report, default=str)) is None
        blob = "".join(p.read_text(encoding="utf-8") for p in _notes_dir(vault).glob("*.md"))
        assert _LEAK.search(blob) is None
    finally:
        Path(db).unlink(missing_ok=True)


def test_idempotent_run_record() -> None:
    db = _fresh_db()
    ev = Path(tempfile.mkdtemp())
    try:
        store = ConstructionStore(db_path=db)
        _seed(store)
        renderer = ObsidianCrossSourceRenderer(store)
        r1 = renderer.render(dry_run=True, project_filter="tropical", evidence_dir=ev, now_utc=_NOW)
        r2 = renderer.render(dry_run=True, project_filter="tropical", evidence_dir=ev, now_utc=_NOW)
        # same mode + project -> one run record (idempotent on obsidian_run_id)
        assert store.count_cross_source_intelligence_obsidian_runs() == 1
        assert r1["rendered_excerpts"] == r2["rendered_excerpts"]
        _assert_guards_zero(db)
    finally:
        Path(db).unlink(missing_ok=True)


def test_status_reports_coverage() -> None:
    db = _fresh_db()
    ev = Path(tempfile.mkdtemp())
    try:
        store = ConstructionStore(db_path=db)
        _seed(store)
        ObsidianCrossSourceRenderer(store).render(
            dry_run=True, project_filter="tropical", evidence_dir=ev, now_utc=_NOW
        )
        status = cross_source_obsidian_status(store, project_filter="tropical")
        assert status["ok"] is True
        assert status["summary"]["runs"] == 1
        assert status["summary"]["by_mode"] == {"dry_run": 1}
    finally:
        Path(db).unlink(missing_ok=True)
