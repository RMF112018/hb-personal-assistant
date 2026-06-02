"""Phase 07D Prompt 13 — no-writeback / no-secret / no-raw-content proof (07D coverage)."""

from __future__ import annotations

import contextlib
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.data_quality.safety import (
    _PHASE_07D_MODULES,
    _scan_module_set,
    build_data_quality_no_writeback_proof,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_07D_KEYS = (
    "static_writeback_scan_07d_modules",
    "no_http_client_or_mutation_imports_07d",
    "module_secret_scan_07d",
    "sqlite_guard_checks_07d_cross_source_tables",
    "sqlite_content_leak_scan_07d_cross_source_tables",
    "evidence_output_scan_07d",
    "obsidian_output_scan_07d",
)
_V25_TABLES = {
    "cross_source_relationship_candidates",
    "cross_source_relationships",
    "source_evidence_trails",
    "meeting_prep_brief_runs",
    "meeting_prep_brief_sections",
    "project_issue_history_items",
    "project_risk_digest_items",
    "aging_exposure_report_items",
    "cross_source_intelligence_obsidian_runs",
    "phase_07d_validation_runs",
}


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_07d_nwb_")
    import os

    os.close(fd)
    with contextlib.suppress(Exception):
        SQLiteMigrator(db_path=db).apply()
    return db


def _seed_clean(db: str) -> None:
    store = ConstructionStore(db)
    store.upsert_cross_source_relationship_candidate(
        candidate_id="c0", source_family="email", source_record_type="m", source_record_ref="m0",
        target_family="procore", target_record_type="rfi", target_record_ref="r0",
        relationship_type="references", confidence_score=1.0, confidence_class="deterministic",
        source_reference_json=json.dumps({"r": "m0"}), review_required=False, project_key="tropical",
        evidence_trail_id="et0",
    )
    store.upsert_source_evidence_trail(
        evidence_trail_id="et0", evidence_kind="x", source_refs_json=json.dumps({"refs": ["m0"]}),
        confidence_class="deterministic", project_key="tropical",
    )
    store.upsert_project_risk_digest_item(
        risk_digest_id="r0", project_key="tropical", risk_indicator_type="x",
        risk_source_class="source_stated", summary_redacted=json.dumps({"count": 2}),
        confidence_class="deterministic",
    )


def test_clean_07d_surfaces_pass_proof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app-support"))
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(tmp_path / "vault"))
    db = _fresh_db()
    try:
        _seed_clean(db)
        report = build_data_quality_no_writeback_proof(db_path=db)
        checks = report["checks_detail"]
        for key in _07D_KEYS:
            assert key in checks, key
            assert checks[key]["passed"] is True, (key, checks[key]["findings"])
        assert report["proof_passed"] is True
        assert len(report["scanned_modules_07d"]) == 9
        guarded = {t["table"] for t in checks["sqlite_guard_checks_07d_cross_source_tables"]["tables"]}
        assert guarded >= _V25_TABLES
        assert "phase_07d_cross_source_meeting_prep" in report["no_raw_values_persisted_scope"]
        assert report["no_raw_values_persisted"] is True
    finally:
        Path(db).unlink(missing_ok=True)


def test_fail_closed_on_signed_url_in_07d_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app-support"))
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(tmp_path / "vault"))
    db = _fresh_db()
    try:
        _seed_clean(db)
        # Inject a signed/tokenized URL into a safe text column via raw SQL (bypassing the
        # guarded upsert) to prove the 07D content scan fails the proof closed.
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE cross_source_relationship_candidates "
            "SET source_reference_json = ? WHERE candidate_id = 'c0'",
            ('{"u":"https://host/download?sig=ABCDEFGHIJKLMNOP1234"}',),
        )
        conn.commit()
        conn.close()
        report = build_data_quality_no_writeback_proof(db_path=db)
        assert report["proof_passed"] is False
        content = report["checks_detail"]["sqlite_content_leak_scan_07d_cross_source_tables"]
        assert content["passed"] is False
        assert content["findings"]  # labels only (table.column: label)
        assert "ABCDEFGHIJKLMNOP1234" not in " ".join(content["findings"])
    finally:
        Path(db).unlink(missing_ok=True)


def test_guard_probe_covers_all_v25_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The guard-CHECK probe must cover every one of the ten V25 tables (the eight guard columns
    # are CHECK(=0)-enforced on write, so a clean pass here means full coverage, not a no-op).
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app-support"))
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(tmp_path / "vault"))
    db = _fresh_db()
    try:
        _seed_clean(db)
        report = build_data_quality_no_writeback_proof(db_path=db)
        guard = report["checks_detail"]["sqlite_guard_checks_07d_cross_source_tables"]
        assert guard["passed"] is True
        assert {t["table"] for t in guard["tables"]} >= _V25_TABLES
    finally:
        Path(db).unlink(missing_ok=True)


def test_module_scanner_is_not_vacuous() -> None:
    # The 07D module scan must actually flag a writeback verb / dangerous import — prove it on a
    # synthetic module so a clean 07D pass is meaningful (not a no-op).
    repo_root = PathPolicy().resolve_repo_root()
    import os

    rel = "construction/_synthetic_proof_probe.py"
    target = repo_root / "src" / "hb_assistant" / rel
    target.write_text("import requests\n\ndef go(c):\n    return c.post('x')\n", encoding="utf-8")
    try:
        results = _scan_module_set(repo_root, [rel])
        res = results[rel]
        assert res.get("writeback"), "scanner failed to flag a .post() writeback verb"
        assert res.get("bad_imports"), "scanner failed to flag 'import requests'"
    finally:
        with contextlib.suppress(Exception):
            os.unlink(target)


def test_idempotent() -> None:
    db = _fresh_db()
    try:
        _seed_clean(db)
        r1 = build_data_quality_no_writeback_proof(db_path=db)
        r2 = build_data_quality_no_writeback_proof(db_path=db)
        assert r1["proof_passed"] == r2["proof_passed"]
        assert set(r1["checks_detail"]) == set(r2["checks_detail"])
        assert _PHASE_07D_MODULES  # constant is populated
    finally:
        Path(db).unlink(missing_ok=True)
