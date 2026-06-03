"""Phase 08A Prompt 15 — second-brain no-writeback / no-secret / no-raw-content proof."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.safety import (
    _PHASE_08A_TABLES,
    _check_model_receipt_metadata_only,
    _derive_guard_map,
    _scan_text_for_html_markup,
    build_second_brain_no_writeback_proof,
)
from hb_assistant.construction.store import ConstructionStore


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_proof_passes_on_clean_repo() -> None:
    proof = build_second_brain_no_writeback_proof()
    assert proof["proof_passed"] is True
    assert proof["ok"] is True
    assert proof["no_external_writeback"] is True
    assert proof["no_raw_values_persisted"] is True
    assert proof["no_raw_html_persisted"] is True
    assert proof["guardrails"]["raw_html_persisted"] is False
    for name, check in proof["checks_detail"].items():
        assert check["passed"] is True, f"{name} failed: {check.get('findings')}"


def test_all_checks_present() -> None:
    proof = build_second_brain_no_writeback_proof()
    for check in (
        "static_writeback_scan_08a_modules",
        "no_http_client_or_mutation_imports_08a",
        "module_secret_scan_08a",
        "model_boundary_disclosure",
        "sqlite_guard_checks_v26_second_brain_tables",
        "sqlite_content_leak_scan_08a_tables",
        "evidence_output_scan_08a",
        "obsidian_brief_output_scan",
        "generated_brief_handoff_scan",
        "model_receipt_metadata_only",
        "sqlite_html_markup_scan_08b_tables",
        "generated_brief_handoff_html_scan",
    ):
        assert check in proof["checks_detail"]


def test_model_boundary_disclosed_and_excluded() -> None:
    proof = build_second_brain_no_writeback_proof()
    mb = proof["model_boundary"]
    assert mb["module"] == "construction/second_brain/reasoning.py"
    # The sanctioned model call is disclosed (excluded from writeback aggregation)...
    assert any(".create()" in f for f in mb["writeback_findings_excluded"])
    # ...but the boundary itself has no bad imports or secrets.
    assert mb["bad_imports"] == []
    assert mb["secrets"] == []


def test_model_receipt_is_metadata_only() -> None:
    result = _check_model_receipt_metadata_only()
    assert result["metadata_only"] is True
    assert result["raw_markers_absent"] is True
    assert result["hashes_present"] is True


def test_guard_map_derives_for_migrated_db(tmp_path: Path) -> None:
    db = str(tmp_path / "g.sqlite")
    ConstructionStore(db)  # migrate to V26
    conn = sqlite3.connect(db)
    derived, missing = _derive_guard_map(conn)
    conn.close()
    assert missing == []  # all expected tables present after migration
    # daily_brief_runs carries multiple raw-*_persisted guard columns.
    assert "external_writeback_performed" in derived["daily_brief_runs"]
    assert all(v == 0 for v in derived["daily_brief_runs"].values())


def test_fail_closed_on_absent_expected_table(tmp_path: Path) -> None:
    # A DB missing the V26 tables -> every expected table reported absent (fail-closed).
    db = str(tmp_path / "empty.sqlite")
    sqlite3.connect(db).close()  # empty DB, no migration
    conn = sqlite3.connect(db)
    _derived, missing = _derive_guard_map(conn)
    conn.close()
    assert len(missing) == len(_PHASE_08A_TABLES)
    assert all("expected_table_absent" in m for m in missing)


def test_content_scanner_flags_planted_secret(tmp_path: Path) -> None:
    # The shared content scanner must catch a planted URL/token (fail-closed proof).
    from hb_assistant.construction.data_quality.safety import _scan_table_contents

    db = str(tmp_path / "leak.sqlite")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE daily_brief_runs (x TEXT)")
    conn.execute("INSERT INTO daily_brief_runs (x) VALUES ('see https://evil.example/leak')")
    conn.commit()
    result = _scan_table_contents(conn, ["daily_brief_runs"])
    conn.close()
    assert result["findings"]  # a planted URL is flagged


def test_html_markup_scanner_clean_and_dirty() -> None:
    # Clean receipt-shaped values (incl. a `.html` redacted path) must NOT trip the markup scan.
    for clean in (
        "12_Daily_Brief/2026-06-02_daily_brief.html",
        "html/2026-06-02_daily_brief.html",
        "a3f9" * 16,  # sha256-shaped hex
        "DELIVERY_COMPLETED",
        "Follow up on RFI 042",
        "local_macos",
        "obsidian_vault",
    ):
        assert _scan_text_for_html_markup(clean) == [], clean
    # Actual HTML markup is flagged.
    for dirty in (
        "<!DOCTYPE html>",
        "<html><script>x()</script>",
        '<div class="x">hi</div>',
        "</body>",
    ):
        assert _scan_text_for_html_markup(dirty), dirty


def test_proof_fails_closed_on_planted_html(tmp_path: Path) -> None:
    # A raw HTML blob persisted into a free-text receipt column must fail the proof closed.
    db = str(tmp_path / "planted_html.sqlite")
    ConstructionStore(db)  # migrate to latest
    conn = sqlite3.connect(db)
    with conn:
        conn.execute(
            "INSERT INTO daily_brief_runs (brief_run_id, brief_date, mode, status, generated_utc) "
            "VALUES ('r1','2026-06-02','dry_run','synthesized','2026-06-02T00:00:00+00:00')"
        )
        conn.execute(
            "INSERT INTO daily_brief_delivery_receipts (delivery_receipt_id, brief_run_id, brief_date, "
            " delivery_channel, delivery_status, mode, output_path_redacted) "
            "VALUES (?, 'r1','2026-06-02','obsidian_vault','delivered','apply', "
            " '<!DOCTYPE html><html><body>leak</body></html>')",
            (uuid.uuid4().hex,),
        )
    conn.close()

    proof = build_second_brain_no_writeback_proof(db_path=db)
    assert proof["proof_passed"] is False
    assert proof["no_raw_html_persisted"] is False
    html_check = proof["checks_detail"]["sqlite_html_markup_scan_08b_tables"]
    assert html_check["passed"] is False
    assert any(
        "daily_brief_delivery_receipts.output_path_redacted" in f for f in html_check["findings"]
    )


def test_cli_no_writeback_proof_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "data-quality", "no-writeback-proof", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain data-quality no-writeback-proof"
    assert payload["proof_passed"] is True
    assert payload["no_external_writeback"] is True
    assert payload["no_raw_html_persisted"] is True
