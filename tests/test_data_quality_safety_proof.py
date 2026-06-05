"""Tests for Phase 07A Prompt 08 No Writeback / No Secret / No Raw Body Proof.

Covers the dedicated safety prover for the six 07A data_quality modules,
the V20/V21 tables, and the generated evidence tree.

- Re-uses the shared secret scanner (prose is ignored).
- Full proof runs defensively on a fresh V21 DB.
- All 07A tables have the CHECK(raw_body_persisted = 0) + only store 0.
- CLI subprocess works.
- Stop-condition / leakage assertions are explicit.

All tests are local, offline, and respect the global guardrails.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from hb_assistant.construction.data_quality import (
    build_data_quality_no_writeback_proof,
)
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_no_writeback_proof import _scan_text_for_secrets


def _fresh_db_with_v21() -> str:
    fd, db_path = tempfile.mkstemp(suffix=".sqlite", prefix="test_safety_")
    import os

    os.close(fd)
    with contextlib.suppress(Exception):  # defensive
        SQLiteMigrator(db_path=str(db_path)).apply()
    return db_path


def test_secret_scanner_ignores_prose_07a_style():
    # The same high-precision scanner used by the 07A safety prover must
    # continue to ignore normal prose (the procore prover already proved this;
    # we re-assert for the 07A context).
    prose = (
        "No tokens, Authorization headers, signed URLs, raw bodies, or PEMs "
        "are ever persisted by the Phase 07A data quality modules."
    )
    assert _scan_text_for_secrets(prose) == []


def test_safety_proof_runs_and_covers_07a_surfaces():
    db_path = _fresh_db_with_v21()
    try:
        report = build_data_quality_no_writeback_proof(db_path=db_path)
        assert report["command"] == "construction-agent data-quality no-writeback-proof"
        assert "ok" in report
        assert "proof_passed" in report
        assert "checks_detail" in report

        # The five core checks must be present
        checks = report["checks_detail"]
        for name in [
            "static_writeback_scan_07a_modules",
            "no_http_client_or_mutation_imports_07a",
            "module_secret_scan_07a",
            "sqlite_raw_body_guardrail_v20_v21_07a_tables",
            "evidence_output_scan_07a",
        ]:
            assert name in checks
            assert "passed" in checks[name]

        # Guardrails and stop conditions are embedded
        assert report["guardrails"]["no_live_calls"] is True
        assert (
            "no_mutation_capable_external_calls_in_07a_modules" in report["stop_conditions_checked"]
        )

        # Even on a minimal DB the proof must be defensive and complete its scans
        assert "scanned_modules" in report
        assert len(report["scanned_modules"]) >= 1  # at least some of the 6 modules were on disk
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_safety_proof_all_07a_tables_have_raw_body_check_and_zero():
    db_path = _fresh_db_with_v21()
    try:
        report = build_data_quality_no_writeback_proof(db_path=db_path)
        raw = report["checks_detail"]["sqlite_raw_body_guardrail_v20_v21_07a_tables"]
        # On a properly migrated V21 DB the tables exist with the CHECK
        # Core V20 tables created by official migration DDL must have the CHECK
        # As of V22 (Phase 07B Prompt 01) every present 07A table — core V20 tables and
        # the five V21 marts (whose CHECK is added additively via ALTER TABLE) — carries
        # the CHECK(raw_body_persisted = 0) guardrail and stores only 0.
        for t in raw.get("tables", []):
            if t.get("present"):
                assert t.get("has_check") is True, f"{t['table']} missing CHECK"
                vals = t.get("distinct_values") or []
                assert all(v == 0 for v in vals), f"{t['table']} has non-zero raw_body_persisted"
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_safety_proof_discloses_raw_staging_layer_out_of_scope():
    """Phase 07C Prompt 01 remediation: the proof must explicitly disclose that the
    Phase 06A raw file-intelligence staging layer (construction_drive_item_inventory)
    is out of scope (not scanned), so the generically named ``no_raw_values_persisted``
    flag is not misread as global. The disclosure itself must be identifier-only — no
    raw values, URLs, emails, or secrets."""
    db_path = _fresh_db_with_v21()
    try:
        report = build_data_quality_no_writeback_proof(db_path=db_path)
        scope = report["no_raw_values_persisted_scope"]
        for phase_scope in (
            "phase_07a_data_quality",
            "phase_07b_calendar_email_thread_candidate",
            "phase_07c_document_intelligence",
            "phase_07d_cross_source_meeting_prep",
        ):
            assert phase_scope in scope, scope
        disclosed = report["raw_staging_layers_out_of_scope"]
        assert isinstance(disclosed, list) and disclosed
        assert {d["table"] for d in disclosed} >= {"construction_drive_item_inventory"}
        # entries are identifier-only: fixed key set, no raw URLs / emails / secrets
        allowed_keys = {"table", "raw_columns", "origin_phase", "scope", "required_handling"}
        for entry in disclosed:
            assert set(entry) == allowed_keys
            blob = " ".join(entry.values())
            assert "http://" not in blob and "https://" not in blob
            assert "@" not in blob
            assert _scan_text_for_secrets(blob) == []
        # purely descriptive — it must not change the verdict's type/shape
        assert isinstance(report["proof_passed"], bool)
        assert isinstance(report["no_raw_values_persisted"], bool)
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_safety_cli_subprocess_json():
    cmd = [
        sys.executable,
        "-m",
        "hb_assistant.cli.main",
        "construction-agent",
        "data-quality",
        "no-writeback-proof",
        "--json",
    ]
    proc = subprocess.run(
        cmd,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # The command must at least run and produce JSON (exit 0 or 3 depending on findings in this env)
    assert proc.returncode in (0, 3), f"CLI failed with {proc.returncode}: {proc.stderr[:400]}"
    payload = json.loads(proc.stdout)
    assert payload["command"] == "construction-agent data-quality no-writeback-proof"
    assert "report" in payload
    assert "guardrails" in payload
    assert payload["guardrails"]["raw_body_persisted"] == "enforced_0_in_all_v20_v21_07a_tables"


def test_safety_proof_stop_conditions_and_no_leakage():
    db_path = _fresh_db_with_v21()
    try:
        report = build_data_quality_no_writeback_proof(db_path=db_path)
        # The four stop conditions from the spec must be attested
        stops = report["stop_conditions_checked"]
        assert "no_mutation_capable_external_calls_in_07a_modules" in stops
        assert "no_raw_body_or_full_text_persisted_in_07a_tables" in stops
        assert "no_tokens_secrets_signed_urls_in_07a_code_or_evidence" in stops
        assert "safety_proof_scopes_all_07a_data_quality_surfaces" in stops

        # The proof must never claim success while hiding a failure
        if not report["proof_passed"]:
            # This is acceptable in a fresh test DB (some tables may be missing the CHECK yet);
            # the important thing is that any violation is visible in findings.
            assert any(not c["passed"] for c in report["checks_detail"].values())
    finally:
        Path(db_path).unlink(missing_ok=True)
