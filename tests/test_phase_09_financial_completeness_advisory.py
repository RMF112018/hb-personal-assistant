"""Phase 09 Prompt 06 — advisory financial data-completeness mart tests.

Exercises the read-only advisory completeness mart: a seeded fact population with null
currency / period and WBS orphans (→ advisory recommendations, no determination), the
dominant-currency advisory path when a source currency IS present, an empty/stale-schema
database, and a no-raw / advisory-only scan.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.financial_completeness_advisory import (
    build_financial_completeness_advisory,
    build_financial_completeness_advisory_proof,
)
from hb_assistant.construction.store import ConstructionStore


def _seed_facts(db_path: str, *, with_currency: bool = False) -> None:
    """Seed procore_financial_amount_facts with null currency/period + a WBS orphan."""
    ConstructionStore(db_path)
    conn = sqlite3.connect(db_path)
    base_cols = (
        "project_key, record_key, endpoint_id, amount_name, amount_value, source_field_path, "
        "created_at_utc, currency_iso_code, period_start, period_end, wbs_code_id, cost_code_id"
    )
    cur = "USD" if with_currency else None
    # Two facts: one fully sparse (null currency/period/wbs), one with wbs present. amount_value
    # is canonical decimal TEXT (never a float, never read by the mart).
    conn.execute(
        f"INSERT INTO procore_financial_amount_facts ({base_cols}) "
        "VALUES ('P1', 'rk-1', 'ep', 'total', '0.00', 'sfp', '2026-01-01T00:00:00Z', "
        "?, NULL, NULL, NULL, NULL)",
        (cur,),
    )
    conn.execute(
        f"INSERT INTO procore_financial_amount_facts ({base_cols}) "
        "VALUES ('P1', 'rk-2', 'ep', 'total', '0.00', 'sfp', '2026-01-01T00:00:00Z', "
        "?, '2026-01-01', '2026-01-31', 'wbs-9', 'cc-9')",
        (cur,),
    )
    conn.commit()
    conn.close()


def test_advisory_mart_profiles_gaps_without_determination(tmp_path: Path) -> None:
    db = str(tmp_path / "fin.sqlite3")
    _seed_facts(db)
    mart = build_financial_completeness_advisory(db)

    assert mart["advisory_only"] is True
    assert mart["normalized_layer_populated"] is False
    cur = mart["currency"]
    assert cur["currency_null"] == 2  # both facts null currency
    assert cur["currency_null_rate"] == 1.0
    # No source currency → project-default required (not derivable, never assigned).
    rec = cur["per_project_recommendation"]["P1"]
    assert rec["recommendation"] == "project_default_currency_required"
    assert rec["dominant_currency"] is None
    assert rec["eligible_for_evidence_backed_default"] is False
    # Period sparse; WBS orphan present (one of the two facts).
    assert mart["period"]["period_null"] == 1
    assert mart["wbs_cost_code"]["wbs_orphan_or_missing_total"] >= 1
    assert mart["wbs_cost_code"]["recommendation"] == "wbs_cost_code_context_required"


def test_dominant_currency_recommendation_when_present(tmp_path: Path) -> None:
    db = str(tmp_path / "fin2.sqlite3")
    _seed_facts(db, with_currency=True)
    mart = build_financial_completeness_advisory(db)
    rec = mart["currency"]["per_project_recommendation"]["P1"]
    assert rec["recommendation"] == "advisory_use_dominant_source_currency"
    assert rec["dominant_currency"] == "USD"  # advisory recommendation only, never assigned
    assert rec["eligible_for_evidence_backed_default"] is True


def test_proof_passes_and_is_advisory_clean(tmp_path: Path) -> None:
    db = str(tmp_path / "fin3.sqlite3")
    _seed_facts(db)
    proof = build_financial_completeness_advisory_proof(db)
    assert proof["proof_passed"] is True
    assert proof["advisory_only"] is True
    assert proof["no_determination_attested"] is True
    assert proof["raw_content_findings"] == []
    assert proof["guard_columns"]["violation"] is False


def test_empty_db_has_no_fact_tables_present(tmp_path: Path) -> None:
    db = str(tmp_path / "empty.sqlite3")
    ConstructionStore(db)  # migrated, no financial facts
    mart = build_financial_completeness_advisory(db)
    # Fact tables exist (migrated) but hold 0 rows; the mart still computes a clean profile.
    assert mart["currency"]["currency_null"] == 0
    assert mart["wbs_cost_code"]["wbs_orphan_or_missing_total"] == 0


def test_stale_schema_is_handled_gracefully(tmp_path: Path) -> None:
    db = str(tmp_path / "stale.sqlite3")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_migrations (version INTEGER)")
    conn.execute("INSERT INTO schema_migrations (version) VALUES (5)")
    conn.commit()
    conn.close()

    proof = build_financial_completeness_advisory_proof(db)
    assert proof["schema_version"] == 5
    assert proof["proof_passed"] is False  # below V37; fact tables absent
    assert proof["mart"]["present_fact_tables"] == []
