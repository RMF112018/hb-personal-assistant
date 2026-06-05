"""Test that low-risk advisory (two-step) is allowed for retrieval without blanket, high-impact blocked from promotion."""

import sqlite3
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


def test_advisory_retrieval_allowed_true_for_low_risk_queue_item():
    """Explicit True case: open low-risk (non-high impact) review queue row from non-allowed family
    produces batch (B) or A, thus advisory_retrieval_allowed=True and proof_passed=True.
    Uses construction_review_queue (no FKs) + table-native reason/project/status so that
    review_reason_code is the real value (not default 'unknown'), proving cluster usefulness split.
    """
    with tempfile.TemporaryDirectory() as td:
        dbp = Path(td) / "adv_true.db"
        from hb_assistant.store.migrator import SQLiteMigrator

        SQLiteMigrator(str(dbp)).apply()
        conn = sqlite3.connect(str(dbp))
        try:
            # Insert a low-risk open construction review item (family=construction not allowed -> B)
            # Use table's reason + project_key + status so extraction picks native (splits unclassified/unknown)
            conn.execute(
                """
                INSERT INTO construction_review_queue
                (source_key, project_key, item_id, rule_id, classification_label, sensitivity,
                 reason, suggested_action, confidence, status, routed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "testsrc",
                    "P-ADV-TRUE",
                    "item-adv-true",
                    "rule-low-1",
                    "note",
                    "normal",
                    "routine follow-up item",
                    "batch_review",
                    0.7,
                    "open",
                    "2026-06-01T10:00:00Z",
                ),
            )
            conn.commit()
        finally:
            conn.close()
        proof = build_review_burden_proof(str(dbp))
        gate = proof.get("gate", {})
        assert gate.get("advisory_retrieval_allowed") is True
        assert gate.get("blanket_review_block") is False
        assert proof.get("proof_passed") is True
        # Verify that review_reason used the table's native value (not 'unknown'), for usefulness
        mart = proof.get("mart", {})
        reasons = {c.get("review_reason") for c in mart.get("clusters", [])}
        assert "routine follow-up item" in reasons or any(
            r and "routine" in str(r).lower() for r in reasons
        )
        assert "unknown" not in reasons  # the default was replaced by table field


def test_advisory_retrieval_allowed_false_for_only_high_impact():
    """Explicit False case: only high-impact (C) items (no safe A/B after two-step) yields
    advisory_retrieval_allowed=False , while proof_passed remains True (guards + no blanket).
    This is the case the old 'or True' was masking; now truthfully asserted.
    """
    with tempfile.TemporaryDirectory() as td:
        dbp = Path(td) / "adv_false.db"
        from hb_assistant.store.migrator import SQLiteMigrator

        SQLiteMigrator(str(dbp)).apply()
        conn = sqlite3.connect(str(dbp))
        try:
            # High-impact row: reason contains contractual (in high_impact list) -> C even from construction
            conn.execute(
                """
                INSERT INTO construction_review_queue
                (source_key, project_key, item_id, rule_id, classification_label, sensitivity,
                 reason, suggested_action, confidence, status, routed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "testsrc2",
                    "P-ADV-FALSE",
                    "item-adv-high",
                    "rule-c-1",
                    "issue",
                    "high",
                    "contractual change order dispute",
                    "manual_review",
                    0.95,
                    "open",
                    "2026-06-01T11:00:00Z",
                ),
            )
            conn.commit()
        finally:
            conn.close()
        proof = build_review_burden_proof(str(dbp))
        gate = proof.get("gate", {})
        assert gate.get("advisory_retrieval_allowed") is False
        assert gate.get("blanket_review_block") is False
        assert proof.get("proof_passed") is True
        # Still has high summary, promotion blocked etc.
        mart = proof.get("mart", {})
        assert mart.get("mandatory_review", 0) >= 1 or any(
            c.get("tier") == "C" for c in mart.get("clusters", [])
        )
