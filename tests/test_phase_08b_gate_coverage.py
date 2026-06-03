"""Phase 08B Prompt 13 — data-quality gate-coverage invariants (a meta-gate over the gates).

The Phase 08B data-quality gate framework is built incrementally (one gate per surface). These tests
guard its *completeness* so future schema/gate additions cannot silently escape coverage:

1. Every live receipt/ledger table (``daily_brief_%_receipts`` / ``second_brain_%_receipts``) stays
   in the no-writeback live-data scan scope (``safety._PHASE_08A_TABLES``).
2. The gate set (``PHASE_08B_GATE_NAMES``) stays in lock-step with the gates contract
   ``required_fields``.
3. A fresh-DB gate evaluation is fail-free with exactly one deferred surface and never overstates
   readiness.
4. The no-writeback proof passes at the latest schema and covers the four V31–V34 delivery ledgers.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.contracts import load_phase_08b_contract
from hb_assistant.construction.second_brain.data_quality import (
    PHASE_08B_GATE_NAMES,
    evaluate_phase_08b_data_quality_gates,
)
from hb_assistant.construction.second_brain.safety import (
    _PHASE_08A_TABLES,
    build_second_brain_no_writeback_proof,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_DELIVERY_LEDGERS = (
    "daily_brief_delivery_receipts",
    "daily_brief_html_render_receipts",
    "daily_brief_notification_receipts",
    "daily_brief_open_receipts",
)


def _live_receipt_tables(db: str) -> set[str]:
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND (name LIKE 'daily_brief_%_receipts' OR name LIKE 'second_brain_%_receipts')"
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


def test_every_receipt_table_is_in_no_writeback_scan_scope() -> None:
    # A future receipt ledger that forgets to register in safety._PHASE_08A_TABLES would escape the
    # live-data no-raw / guard-column scan — this fails closed against that.
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "cov.sqlite3")
        ConstructionStore(db)
        receipt_tables = _live_receipt_tables(db)
    assert receipt_tables, "expected receipt/ledger tables in the live schema"
    scope = set(_PHASE_08A_TABLES)
    missing = sorted(receipt_tables - scope)
    assert missing == [], f"receipt tables outside the no-writeback scan scope: {missing}"
    # The four 08B delivery ledgers (V31–V34) are explicitly in scope.
    for ledger in _DELIVERY_LEDGERS:
        assert ledger in scope, f"{ledger} not registered in _PHASE_08A_TABLES"


def test_gate_set_matches_contract_required_fields() -> None:
    contract = load_phase_08b_contract("data_quality_gates_contract")
    assert tuple(sorted(PHASE_08B_GATE_NAMES)) == tuple(sorted(contract["required_fields"]))
    # Post P08 gate flip: automation_execution proven pass; no deferred surfaces remain in 08b contract.
    assert contract["deferred_surfaces"] == []


def test_fresh_db_gate_evaluation_is_fail_free_and_not_overstated() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "gates.sqlite3")
        ConstructionStore(db)
        report = evaluate_phase_08b_data_quality_gates(db_path=db)
    counts = report["status_counts"]
    assert counts["fail_blocking"] == 0
    assert counts["deferred_not_blocking"] == 0
    assert report["required_fields_covered"] is True
    assert report["readiness_overstated"] is False
    assert report["by_field_status"]["automation_execution"] == "pass"
    # Exactly the declared gate names are evaluated (no missing / no extra).
    assert sorted(report["by_field_status"].keys()) == sorted(PHASE_08B_GATE_NAMES)


def test_no_writeback_proof_passes_at_latest_schema() -> None:
    proof = build_second_brain_no_writeback_proof()
    assert proof["proof_passed"] is True
    assert proof["schema_version"] == LATEST_SCHEMA_VERSION
    assert proof["no_raw_values_persisted"] is True
    assert proof["no_external_writeback"] is True
