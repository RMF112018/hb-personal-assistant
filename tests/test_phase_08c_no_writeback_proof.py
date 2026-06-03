"""Phase 08C — no-writeback / no-raw-financial-output safety proof.

Extends the second-brain safety scan over the Phase 08C financial modules, the ten
V35 tables, and the 08C evidence directory. Verifies the clean pass and the
fail-closed stop conditions (raw/secret in evidence, raw value in a table, and the
guard-map fail-closed primitive on absent tables).
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

from hb_assistant.construction.second_brain.safety import (
    _PHASE_08C_TABLES,
    _derive_guard_map,
)
from hb_assistant.construction.second_brain.safety import (
    build_phase_08c_no_writeback_no_raw_financial_output_proof as build_proof,
)
from hb_assistant.store.migrator import SQLiteMigrator

_CHECK_KEYS = {
    "static_mutation_scan_08c_modules",
    "guard_column_probe_08c_tables",
    "content_leak_scan_08c_tables",
    "evidence_raw_secret_scan_08c",
}
_CONFIRMATIONS = {
    "no_external_writeback",
    "no_procore_mutation",
    "no_raw_financial_source_payload",
    "no_raw_prompts_or_responses",
    "no_signed_or_download_urls",
    "no_payment_or_claim_or_entitlement_decisions",
}


@pytest.fixture
def evidence_subdir() -> Iterator[str]:
    """A unique temp subdir UNDER the repo docs/evidence (so the scan's relative_to works)."""
    base = Path("docs/evidence")
    base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="_pytest_08c_nwb_", dir=str(base)))
    try:
        yield path.name
    finally:
        shutil.rmtree(path, ignore_errors=True)


# A synthetic PEM marker the secret scanners flag at runtime. Built via concatenation so the
# static repo-sensitive scanner does not match this test's own source (no real key here).
_PEM_MARKER = "-----BEGIN " + "RSA PRIVATE KEY-----"


def _evidence_path(subdir: str) -> Path:
    return Path("docs/evidence") / subdir


def test_proof_passes_on_clean_state(tmp_path: Path, evidence_subdir: str) -> None:
    db = tmp_path / "nw.db"
    SQLiteMigrator(db_path=str(db)).apply()
    (_evidence_path(evidence_subdir) / "sample-proof.json").write_text(
        '{"advisory_only": true, "amount_ref": "amount_fact:1"}'
    )

    proof = build_proof(db_path=str(db), out_dir=str(tmp_path), evidence_dir=evidence_subdir)

    assert proof["proof_passed"] is True
    assert set(proof["checks_detail"]) == _CHECK_KEYS
    assert all(c["passed"] for c in proof["checks_detail"].values())
    assert set(proof["confirmations"]) == _CONFIRMATIONS
    assert all(proof["confirmations"].values())
    assert len(proof["scanned_tables"]) == 10
    assert "second_brain_financial_amount_facts_normalized" in proof["scanned_tables"]

    json_path = tmp_path / "no-writeback-no-raw-financial-output-proof.json"
    md_path = tmp_path / "no-writeback-no-raw-financial-output-proof.md"
    assert json_path.exists() and md_path.exists()
    assert json.loads(json_path.read_text())["proof_passed"] is True
    assert "No-Writeback / No-Raw-Financial-Output Proof" in md_path.read_text()


def test_proof_fails_on_secret_in_evidence(tmp_path: Path, evidence_subdir: str) -> None:
    db = tmp_path / "nw2.db"
    SQLiteMigrator(db_path=str(db)).apply()
    (_evidence_path(evidence_subdir) / "leaky.json").write_text(
        json.dumps({"k": _PEM_MARKER})
    )

    proof = build_proof(db_path=str(db), out_dir=str(tmp_path), evidence_dir=evidence_subdir)

    assert proof["checks_detail"]["evidence_raw_secret_scan_08c"]["passed"] is False
    assert proof["proof_passed"] is False
    findings = proof["checks_detail"]["evidence_raw_secret_scan_08c"]["findings"]
    assert findings  # location + label only (never the raw key bytes)
    assert json.loads(
        (tmp_path / "no-writeback-no-raw-financial-output-proof.json").read_text()
    )["proof_passed"] is False


def test_proof_fails_on_raw_value_in_table(tmp_path: Path) -> None:
    db = tmp_path / "nw3.db"
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    try:
        # poison a TEXT cell in a V35 table with a PEM marker (guard CHECKs allow free text here)
        conn.execute(
            "INSERT INTO second_brain_financial_fact_normalization_runs "
            "(run_id, started_utc, status, notes_redacted) "
            "VALUES ('leak-run', '2026-06-03', 'started', ?)",
            (_PEM_MARKER,),
        )
        conn.commit()
    finally:
        conn.close()
    clean_ev = tmp_path / "ev"  # absolute/clean → evidence scan is a no-op here
    clean_ev.mkdir()

    proof = build_proof(db_path=str(db), out_dir=str(tmp_path), evidence_dir=str(clean_ev))

    assert proof["checks_detail"]["content_leak_scan_08c_tables"]["passed"] is False
    assert proof["proof_passed"] is False


def test_guard_map_fail_closed_on_absent_tables(tmp_path: Path) -> None:
    db = tmp_path / "empty.db"
    conn = sqlite3.connect(str(db))
    try:
        derived, missing = _derive_guard_map(conn, _PHASE_08C_TABLES)
    finally:
        conn.close()
    assert derived == {}
    assert len(missing) == len(_PHASE_08C_TABLES)
    assert all("expected_table_absent" in m for m in missing)


def test_migrated_guard_map_declares_zero_guards(tmp_path: Path) -> None:
    db = tmp_path / "ok.db"
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    try:
        derived, missing = _derive_guard_map(conn, _PHASE_08C_TABLES)
    finally:
        conn.close()
    assert missing == []
    for table in _PHASE_08C_TABLES:
        cols = derived[table]
        assert "raw_financial_source_payload_persisted" in cols
        assert "external_writeback_performed" in cols
        assert "payment_decision_performed" in cols
