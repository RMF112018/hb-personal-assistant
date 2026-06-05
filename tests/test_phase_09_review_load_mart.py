"""Phase 09 Prompt 05 — review-load mart + promotion-gate tests.

Exercises the read-only review-load mart and the fail-closed review-required promotion gate:
a normal seeded population (incl. a financial append-only ledger whose raw rows exceed
distinct items, and a high-impact item), the fail-closed gate under review_not_performed, a
stale-schema database, and a no-raw scan of the mart output.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.review_load_mart import (
    HIGH_IMPACT_CATEGORIES,
    build_review_load_mart,
    build_review_load_proof,
    evaluate_review_promotion_gate,
)
from hb_assistant.construction.store import ConstructionStore


def _seed_review_rows(db_path: str) -> None:
    """Seed a financial review ledger (duplicate run_ids) + an email high-impact item."""
    ConstructionStore(db_path)  # migrate to current schema
    conn = sqlite3.connect(db_path)
    # Financial append-only ledger: same distinct item logged under two run_ids → distinct < raw.
    for run_id in ("run-a", "run-b"):
        for src in ("ref-1", "ref-2"):
            conn.execute(
                "INSERT INTO second_brain_financial_review_required_items "
                "(run_id, project_key, trigger_category, source_ref, amount_ref, "
                " review_tier, advisory_only, confidence_label) "
                "VALUES (?, 'P1', 'missing_or_inconsistent_currency', ?, ?, "
                "'financial_review', 1, 'low')",
                (run_id, src, f"amt-{src}"),
            )
    # An unresolved email review item with a high-impact (claim) category.
    conn.execute(
        "INSERT INTO email_review_queue "
        "(review_id, message_id, project_key, category, sensitivity, reason, suggested_action, "
        " confidence, status) "
        "VALUES ('er-1', 'msg-1', 'P1', 'claim', 'restricted', 'lien dispute', "
        "'route_for_review', 0.9, 'open')"
    )
    conn.commit()
    conn.close()


def test_mart_distinct_ledger_reframe_and_high_impact(tmp_path: Path) -> None:
    db = str(tmp_path / "review.sqlite3")
    _seed_review_rows(db)
    mart = build_review_load_mart(db)

    fin = mart["tables"]["second_brain_financial_review_required_items"]
    assert fin["append_only_ledger"] is True
    assert fin["raw_rows"] == 4  # 2 runs x 2 refs
    assert fin["distinct_items"] == 2  # de-duplicated by natural key
    assert fin["distinct_run_ids"] == 2
    # The email claim item is classified high-impact.
    email = mart["tables"]["email_review_queue"]
    assert email["high_impact_distinct"] >= 1
    assert "claim" in email["by_impact_category"]
    assert mart["total_distinct_review_items"] < mart["total_raw_rows"]
    assert mart["review_not_performed"] is True  # no human-review decisions seeded


def test_promotion_gate_fail_closed_under_no_review(tmp_path: Path) -> None:
    db = str(tmp_path / "review2.sqlite3")
    _seed_review_rows(db)
    mart = build_review_load_mart(db)
    gate = evaluate_review_promotion_gate(mart)

    assert gate["fail_closed"] is True
    assert gate["review_not_performed"] is True
    assert gate["promotable_review_ready"] == 0  # nothing promotes until human review
    assert gate["unresolved_high_impact_promotable"] == 0
    assert gate["blocked_from_promotion"] == mart["total_distinct_review_items"]

    # Refinements: the proof now carries the new burden policy view (two-step, no blanket for advisory)
    proof2 = build_review_load_proof(db)
    assert "advisory_retrieval_allowed" in proof2
    assert proof2.get("blanket_review_block") is False
    assert "financial_review_burden" in proof2
    assert "high_impact_summary" in proof2


def test_proof_passes_and_is_raw_clean(tmp_path: Path) -> None:
    db = str(tmp_path / "review3.sqlite3")
    _seed_review_rows(db)
    proof = build_review_load_proof(db)
    assert proof["proof_passed"] is True
    assert proof["gate_fail_closed_ok"] is True
    assert proof["raw_content_findings"] == []


def test_high_impact_categories_cover_the_eight() -> None:
    assert (
        frozenset(
            {
                "legal",
                "claim",
                "contractual",
                "safety",
                "personnel",
                "financial",
                "schedule_impact",
                "cost_impact",
            }
        )
        == HIGH_IMPACT_CATEGORIES
    )


def test_stale_schema_is_handled_gracefully(tmp_path: Path) -> None:
    db = str(tmp_path / "stale.sqlite3")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_migrations (version INTEGER)")
    conn.execute("INSERT INTO schema_migrations (version) VALUES (5)")
    conn.commit()
    conn.close()

    proof = build_review_load_proof(db)
    assert proof["schema_version"] == 5
    assert proof["proof_passed"] is False  # below V37; review tables absent
    assert proof["mart"]["present_review_tables"] == 0


def test_review_load_proof_attaches_burden_fields_including_unique_example_count(
    tmp_path: Path,
) -> None:
    """The legacy review-load proof now carries burden keys (including unique_example_count post-dedup)."""
    db = str(tmp_path / "rlm.db")
    # minimal schema
    from hb_assistant.store.migrator import SQLiteMigrator

    SQLiteMigrator(db).apply()
    proof = build_review_load_proof(db)
    # promoted fields from burden
    for k in (
        "advisory_retrieval_allowed",
        "blanket_review_block",
        "financial_review_burden",
        "high_impact_summary",
        "operator_visible_count",
        "suppressed_noise_count",
    ):
        assert k in proof
    # unique_example_count lives on the attached burden mart clusters (when present)
    burden = proof.get("review_burden_proof") or {}
    for c in (burden.get("mart", {}).get("clusters") or burden.get("clusters") or [])[:1]:
        if "item_count" in c:
            assert "unique_example_count" in c
            assert isinstance(c["unique_example_count"], int)
