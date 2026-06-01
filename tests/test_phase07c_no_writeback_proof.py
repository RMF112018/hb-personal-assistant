"""Phase 07C Prompt 12 — no-writeback / no-secret / no-raw-document-text proof (07C coverage)."""

from __future__ import annotations

import contextlib
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.data_quality.safety import build_data_quality_no_writeback_proof
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_07C_KEYS = (
    "static_writeback_scan_07c_modules",
    "no_http_client_or_mutation_imports_07c",
    "module_secret_scan_07c",
    "sqlite_guard_checks_07c_document_tables",
    "sqlite_content_leak_scan_07c_document_tables",
    "evidence_output_scan_07c",
    "obsidian_output_scan_07c",
)
_V24_TABLES = {
    "construction_document_cards",
    "construction_document_classification_candidates",
    "construction_document_project_match_candidates",
    "construction_document_relationship_candidates",
    "construction_document_intelligence_previews",
    "construction_document_projection_runs",
}


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_07c_nwb_")
    import os

    os.close(fd)
    with contextlib.suppress(Exception):
        SQLiteMigrator(db_path=db).apply()
    return db


def _seed_clean_chain(db: str) -> None:
    store = ConstructionStore(db)
    store.upsert_inventory_item(
        source_key="sp", drive_id="d", item_id="c0", name="raw_c0", web_url="https://x/c0",
        parent_path="/General", size_bytes=1024, is_folder=False, last_modified=None, etag="e",
    )
    store.upsert_document_card(
        card_id="c0", document_card_id="c0", source_id="sp", drive_item_id="c0",
        file_extension="pdf", project_key="alpha", document_type="unknown", size_class="small",
        extraction_eligibility="manual_approval_required",
    )
    store.upsert_document_classification_candidate(
        candidate_id="clf_c0", document_card_id="c0", document_type="rfi",
        classifier_name="deterministic_v1", signal_class="deterministic", confidence=0.9,
        confidence_class="deterministic",
    )
    store.upsert_document_project_match_candidate(
        candidate_id="pm_c0", document_card_id="c0", project_key="alpha",
        candidate_type="deterministic", confidence=0.95, confidence_class="deterministic",
        deterministic=True, review_required=False,
    )
    store.upsert_document_relationship_candidate(
        candidate_id="rel_c0", document_card_id="c0", target_system="procore",
        target_record_type="rfi", target_record_key_hash="hh", relationship_type="x",
        candidate_type="heuristic", confidence=0.55, confidence_class="moderate_heuristic",
        review_required=True,
    )
    store.upsert_document_intelligence_preview(
        preview_id="pv_alpha", project_key="alpha",
        preview_kind="project_document_intelligence", confidence_class="weak_heuristic",
        warnings_json='{"warnings": [], "source_reference": {"project_key": "alpha"}}',
        review_required=True,
    )


def test_clean_07c_chain_passes_proof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point the vault root at an empty tmp dir so the Obsidian scan finds nothing to scan.
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app-support"))
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(tmp_path / "vault"))
    db = _fresh_db()
    try:
        _seed_clean_chain(db)
        report = build_data_quality_no_writeback_proof(db_path=db)
        checks = report["checks_detail"]
        for key in _07C_KEYS:
            assert key in checks, key
            assert checks[key]["passed"] is True, (key, checks[key]["findings"])
        assert report["proof_passed"] is True
        assert len(report["scanned_modules_07c"]) == 9
        guarded = {t["table"] for t in checks["sqlite_guard_checks_07c_document_tables"]["tables"]}
        assert guarded >= _V24_TABLES
        assert "phase_07c_document_intelligence" in report["no_raw_values_persisted_scope"]
    finally:
        Path(db).unlink(missing_ok=True)


def test_fail_closed_on_signed_url_in_07c_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app-support"))
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(tmp_path / "vault"))
    db = _fresh_db()
    try:
        _seed_clean_chain(db)
        # Inject a signed/tokenized URL into a safe text column via raw SQL (bypassing the
        # guarded upsert) to prove the content scan fails the proof closed.
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE construction_document_classification_candidates "
            "SET signals_json = ? WHERE candidate_id = 'clf_c0'",
            ('{"u":"https://host/download?sig=ABCDEFGHIJKLMNOP1234"}',),
        )
        conn.commit()
        conn.close()
        report = build_data_quality_no_writeback_proof(db_path=db)
        assert report["proof_passed"] is False
        content = report["checks_detail"]["sqlite_content_leak_scan_07c_document_tables"]
        assert content["passed"] is False
        assert content["findings"]  # labels only (table.column: label)
        # The proof never echoes the offending value.
        blob = " ".join(content["findings"])
        assert "ABCDEFGHIJKLMNOP1234" not in blob
    finally:
        Path(db).unlink(missing_ok=True)
