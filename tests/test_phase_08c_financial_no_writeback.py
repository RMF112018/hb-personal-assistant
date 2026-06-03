"""Phase 08C — financial no-writeback / no-raw attestation proof generator.

Runs the real generator against an isolated DB + evidence dir and asserts the
guard-column, money-not-float, and evidence-redaction checks plus the written
artifacts. Also verifies a raw value in the evidence dir fails the proof.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.financial_no_writeback import (
    build_financial_no_writeback_proof,
)
from hb_assistant.store.migrator import SQLiteMigrator


def _migrate(db: Path) -> None:
    SQLiteMigrator(db_path=str(db)).apply()


def _seed_clean_fact(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO second_brain_financial_amount_facts_normalized "
            "(run_id, project_key, source_family, source_table, source_record_ref, "
            " source_field_path, parse_status, canonical_decimal_text, minor_units, "
            " confidence_label, review_tier) "
            "VALUES ('seed', 'p1', 'owner_contracts', 'procore_financial_contracts', 'rec', "
            " 'grand_total', 'parseable', '100.00', 10000, 'deterministic', 'none')"
        )
        conn.commit()
    finally:
        conn.close()


def test_no_writeback_proof_passes_on_clean_state(tmp_path: Path) -> None:
    db = tmp_path / "nw.db"
    _migrate(db)
    _seed_clean_fact(db)
    ev = tmp_path / "evidence"
    ev.mkdir()
    (ev / "sample-proof.json").write_text('{"advisory_only": true, "amount_ref": "amount_fact:1"}')

    proof = build_financial_no_writeback_proof(
        db_path=str(db), out_dir=str(ev), evidence_dir=str(ev)
    )

    assert proof["proof_passed"] is True
    checks = proof["checks_detail"]
    assert checks["guard_columns"]["passed"] is True
    assert checks["money_not_float"]["passed"] is True
    assert checks["money_not_float"]["canonical_decimal_text_is_text"] is True
    assert checks["money_not_float"]["minor_units_is_integer"] is True
    assert checks["money_not_float"]["real_typed_money_columns"] == []
    assert checks["evidence_redaction"]["passed"] is True

    # attestations are all-false; advisory only
    assert proof["advisory_only"] is True
    assert all(v is False for v in proof["attestations"].values())

    md_path = ev / "financial-no-writeback-proof.md"
    json_path = ev / "financial-no-writeback-proof.json"
    assert md_path.exists() and json_path.exists()
    md = md_path.read_text()
    assert "No-Writeback" in md
    assert "advisory review aid only" in md.lower()
    # the generator's own artifacts must be redaction-clean
    combined = (md + json_path.read_text()).lower()
    for forbidden in ("bearer ", "-----begin", "https://", "sig=", "access_token"):
        assert forbidden not in combined


def test_no_writeback_proof_flags_raw_value_in_evidence(tmp_path: Path) -> None:
    db = tmp_path / "nw2.db"
    _migrate(db)
    ev = tmp_path / "evidence"
    ev.mkdir()
    # a forbidden raw pattern (URL) in an evidence file must fail the redaction check
    (ev / "leaky.json").write_text('{"download_url": "https://example.com/file"}')

    proof = build_financial_no_writeback_proof(
        db_path=str(db), out_dir=str(ev), evidence_dir=str(ev)
    )

    assert proof["checks_detail"]["evidence_redaction"]["passed"] is False
    assert proof["proof_passed"] is False
    # finding records the filename only (not the matched raw text)
    findings = proof["checks_detail"]["evidence_redaction"]["findings"]
    assert any(f.startswith("leaky.json:") for f in findings)
    # written proof JSON still parses and never echoes the raw URL
    written = json.loads((ev / "financial-no-writeback-proof.json").read_text())
    assert written["proof_passed"] is False
    assert "https://example.com" not in json.dumps(written)
