"""Test that low-risk advisory (two-step) is allowed for retrieval without blanket, high-impact blocked from promotion."""

import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.review_burden_mart import build_review_burden_proof


def test_advisory_retrieval_gate_shape_and_two_step():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "g.db"
        from hb_assistant.store.migrator import SQLiteMigrator
        SQLiteMigrator(str(db)).apply()
        proof = build_review_burden_proof(str(db))
        gate = proof.get("gate", {})
        # Core flags per refinements
        assert "advisory_retrieval_allowed" in gate
        assert gate.get("blanket_review_block") is False
        assert "financial_review_burden" in proof.get("mart", {})
        # high impact summary present
        assert "high_impact_summary" in proof.get("mart", {})
