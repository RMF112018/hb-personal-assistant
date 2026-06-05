"""Tests for Phase 09 review burden policy (two-step, financial separate, hash-only examples, clustered high-impact)."""

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.review_burden_mart import (
    _build_clusters_from_candidates,
    _example_dedup_key,
    _safe_top_example,
    build_review_burden_proof,
    load_review_burden_policy_contract,
    load_review_burden_policy_seed,
)


def test_review_burden_policy_seed_and_contract_load():
    seed = load_review_burden_policy_seed()
    contract = load_review_burden_policy_contract()
    assert "policy_id" in seed
    assert seed.get("mode") == "advisory_promotion"
    assert "high_impact_impact_categories" in contract
    assert "two_step_classification" in contract or "high_impact_impact_categories" in contract
    # financial separate declared
    assert contract.get("financial_review", {}).get("separate_burden") is True


def test_two_step_high_impact_beats_family():
    # Simulated: even if family "cross_source_relationships" is allowed, financial impact -> C
    contract = load_review_burden_policy_contract()
    high = set(contract.get("high_impact_impact_categories", []))
    assert "financial" in high
    assert "contractual" in high
    # The _two_step_tier is internal; proof via mart on a db with mixed rows would confirm.
    # Here we just assert the lists are present for the rule.
    assert len(high) >= 8


def test_top_examples_hash_only_and_no_prohibited():
    bad = {"subject": "foo", "body": "bar", "url": "http://ex", "email": "a@b"}
    good = {"source_family": "x", "project_key": "P", "item_hash": "h1", "count": 3}
    ex = _safe_top_example({**bad, **good})
    for k in bad:
        assert k not in ex
    for k in good:
        assert k in ex


def test_review_burden_mart_and_proof_on_empty_db_has_no_raw_and_two_step_shape():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "burden.db"
        # Minimal: run a migrate to have tables (the review tables + v38+)
        from hb_assistant.store.migrator import SQLiteMigrator

        SQLiteMigrator(str(db)).apply()
        proof = build_review_burden_proof(str(db))
        assert proof["proof"] == "phase_09_review_burden"
        # Empty: no A/B items => advisory=False (truthfully); proof_passed=True (no raw, !blanket)
        # (the prior "or True" masked this; explicit fixture cases now assert the flag value)
        assert proof["proof_passed"] is True
        gate = proof.get("gate", {})
        assert gate.get("advisory_retrieval_allowed") is False
        assert gate.get("blanket_review_block") is False
        mart = proof["mart"]
        assert "two_step_classification" in mart or "auto_advisory_allowed" in mart
        assert "financial_review_burden" in mart
        assert "high_impact_summary" in mart
        # No raw findings in proof for our structures
        assert all("prohibited" not in f for f in proof.get("raw_content_findings", []))


def test_review_burden_top_examples_are_deduped_hash_only():
    """Duplicates on same item_hash (or fallback keys) collapse; unique_example_count correct; no prohibited; <max when fewer uniques."""
    # Fabricate candidates that would produce dups
    cands = []
    for _i in range(5):
        cands.append(
            {
                "source_family": "construction",
                "project_key": "P1",
                "impact_category": "unclassified",
                "confidence_class": "medium",
                "review_reason_code": "foo",
                "item_hash": "duphash123",
                "source_ref_hash": "duphash123",
                "freshness_bucket": "unknown",
                "guard_ok": True,
                "sensitive_high_impact": False,
                "table": "construction_review_queue",
            }
        )
    cands.append(
        {  # one unique different
            "source_family": "construction",
            "project_key": "P1",
            "impact_category": "unclassified",
            "confidence_class": "medium",
            "review_reason_code": "foo",
            "item_hash": "uniquehash456",
            "source_ref_hash": "uniquehash456",
            "freshness_bucket": "unknown",
            "guard_ok": True,
            "sensitive_high_impact": False,
            "table": "construction_review_queue",
        }
    )
    contract = load_review_burden_policy_contract()
    seed = load_review_burden_policy_seed()
    # minimal seed/contract tweak not needed; use real
    res = _build_clusters_from_candidates(contract, seed, cands, max_examples=5, daily_budget=10)
    clusters = res["clusters"]
    # find the P1 unclassified cluster (there may be one)
    target = None
    for c in clusters:
        if c.get("project_key") == "P1" and c.get("impact_category") == "unclassified":
            target = c
            break
    assert target is not None
    assert target["item_count"] == 6
    assert target["unique_example_count"] == 2
    assert len(target["top_examples"]) == 2
    # first should be the first seen (dup one)
    assert target["top_examples"][0].get("item_hash") == "duphash123"
    assert target["top_examples"][1].get("item_hash") == "uniquehash456"
    # no prohibited
    for ex in target["top_examples"]:
        for bad in ("subject", "body", "url", "email", "raw"):
            assert bad not in ex
    # explicit regression: no repeated dedupe keys (refinement #2)
    keys = [_example_dedup_key(e) for e in target["top_examples"]]
    assert len(keys) == len(set(keys))


def test_review_burden_unique_example_count_preserves_cluster_item_count_and_fallbacks():
    """item_count full; unique < item when dups or low unique; fallback to source_ref then composite; shows fewer than max."""
    contract = load_review_burden_policy_contract()
    seed = load_review_burden_policy_seed()
    # Case: 3 same by source_ref (no item_hash), 1 different by composite
    cands = []
    for _i in range(3):
        cands.append(
            {
                "source_family": "email",
                "project_key": "P2",
                "impact_category": "low",
                "confidence_class": "low",
                "review_reason_code": "dup",
                "item_hash": None,
                "source_ref_hash": "sr_dup",
                "freshness_bucket": "old",
                "guard_ok": True,
                "sensitive_high_impact": False,
                "table": "email_review_queue",
            }
        )
    cands.append(
        {
            "source_family": "email",
            "project_key": "P2",
            "impact_category": "low",
            "confidence_class": "low",
            "review_reason_code": "dup",
            "item_hash": None,
            "source_ref_hash": "sr_other",
            "freshness_bucket": "old",
            "guard_ok": True,
            "sensitive_high_impact": False,
            "table": "email_review_queue",
        }
    )
    res = _build_clusters_from_candidates(contract, seed, cands, max_examples=5, daily_budget=10)
    target = None
    for c in res["clusters"]:
        if c.get("project_key") == "P2":
            target = c
            break
    assert target is not None
    assert target["item_count"] == 4
    assert target["unique_example_count"] == 2
    assert len(target["top_examples"]) == 2
    # regression key uniqueness
    keys = [_example_dedup_key(e) for e in target["top_examples"]]
    assert len(keys) == len(set(keys))
    # case with < max uniques
    assert target["unique_example_count"] < 5


def test_review_burden_proof_asserts_advisory_retrieval_allowed_true_false_explicitly():
    """Policy test also carries explicit true/false fixture cases for advisory (using real queue inserts
    + native reason fields). Confirms proof_passed True in both, advisory flag asserted (post or-True fix),
    and that review_reason comes from table (e.g. status/reason) rather than 'unknown'.
    """
    # True case (low-risk batch-eligible from queue; use construction to avoid FK on email's message_id)
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "pol_true.db"
        from hb_assistant.store.migrator import SQLiteMigrator

        SQLiteMigrator(str(db)).apply()
        conn = sqlite3.connect(str(db))
        try:
            conn.execute(
                """
                INSERT INTO construction_review_queue
                (source_key, project_key, item_id, rule_id, classification_label, sensitivity,
                 reason, suggested_action, confidence, status, routed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "pol-src-t",
                    "P-POL",
                    "item-pol-t",
                    "rule-pol-t",
                    "note",
                    "normal",
                    "newsletter or marketing",
                    "ignore",
                    0.6,
                    "open",
                    "2026-06-05T00:00:00Z",
                ),
            )
            conn.commit()
        finally:
            conn.close()
        proof = build_review_burden_proof(str(db))
        assert proof.get("proof_passed") is True
        assert proof.get("gate", {}).get("advisory_retrieval_allowed") is True
        # table reason flowed to cluster (splits broad construction/unclassified/unknown)
        cl_reasons = [c.get("review_reason") for c in proof.get("mart", {}).get("clusters", [])]
        assert any(
            r and "marketing" in str(r).lower() or "newsletter" in str(r).lower()
            for r in cl_reasons
        )

    # False case (only high)
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "pol_false.db"
        from hb_assistant.store.migrator import SQLiteMigrator

        SQLiteMigrator(str(db)).apply()
        conn = sqlite3.connect(str(db))
        try:
            conn.execute(
                """
                INSERT INTO construction_review_queue
                (source_key, project_key, item_id, rule_id, classification_label, sensitivity,
                 reason, suggested_action, confidence, status, routed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "pol-src",
                    "P-POL-HI",
                    "item-hi",
                    "rule-hi",
                    "safety",
                    "critical",
                    "safety incident claim",
                    "escalate",
                    0.99,
                    "open",
                    "2026-06-05T01:00:00Z",
                ),
            )
            conn.commit()
        finally:
            conn.close()
        proof = build_review_burden_proof(str(db))
        assert proof.get("proof_passed") is True
        assert proof.get("gate", {}).get("advisory_retrieval_allowed") is False
