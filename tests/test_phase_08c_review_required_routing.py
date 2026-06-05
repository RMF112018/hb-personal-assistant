"""Phase 08C — review-required financial signal routing (Prompt: review policy).

Covers the deterministic router that turns sensitive/ambiguous financial signals into
persisted review items across all seven policy trigger categories, the V36 confidence
label column, guard invariants, and the redaction-clean evidence proof.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.financial_review_routing import (
    build_financial_review_required_proof,
    run_review_required_routing,
)
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

ALL_TRIGGERS = {
    "amount_parse_ambiguous_or_rejected",
    "missing_source_field_path",
    "missing_or_inconsistent_currency",
    "missing_wbs_cost_code_or_line_item_type",
    "relationship_ambiguity",
    "fail_closed_required_source",
    "determination_attempt",
}


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _seed_fact(
    conn: sqlite3.Connection,
    *,
    pk: str,
    parse_status: str,
    currency_status: str | None = None,
    source_field_path: str = "f1",
    rec: str = "rec",
) -> None:
    conn.execute(
        "INSERT INTO second_brain_financial_amount_facts_normalized "
        "(run_id, project_key, source_family, source_table, source_record_ref, "
        " source_field_path, parse_status, currency_status, confidence_label, review_tier) "
        "VALUES ('seed', ?, 'owner_contracts', 'procore_financial_contracts', ?, ?, ?, ?, "
        " 'deterministic', 'none')",
        (pk, rec, source_field_path, parse_status, currency_status),
    )


def _seed_coverage(
    conn: sqlite3.Connection,
    *,
    pk: str,
    family: str,
    endpoint_id: str,
    coverage_status: str,
    relationship_key_count: int,
) -> None:
    conn.execute(
        "INSERT INTO second_brain_financial_source_coverage_snapshots "
        "(run_id, project_key, source_family, endpoint_id, coverage_status, relationship_key_count) "
        "VALUES ('seed', ?, ?, ?, ?, ?)",
        (pk, family, endpoint_id, coverage_status, relationship_key_count),
    )


def _seed_all(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    try:
        # Amount facts: one per parse/currency/missing-context signal.
        _seed_fact(conn, pk="p1", parse_status="ambiguous")
        _seed_fact(conn, pk="p1", parse_status="rejected")
        _seed_fact(conn, pk="p1", parse_status="stale")
        _seed_fact(conn, pk="p1", parse_status="conflicting")
        _seed_fact(conn, pk="p1", parse_status="parseable", currency_status="missing_currency")
        _seed_fact(conn, pk="p1", parse_status="parseable", source_field_path="")
        # Coverage snapshots: fail-closed dependency + relationship ambiguity.
        _seed_coverage(
            conn,
            pk="p1",
            family="budget",
            endpoint_id="budget-details",
            coverage_status="fail_closed",
            relationship_key_count=2,
        )
        _seed_coverage(
            conn,
            pk="p1",
            family="owner_contracts",
            endpoint_id="contracts",
            coverage_status="covered_ready",
            relationship_key_count=0,
        )
        # Source line items (real V8 table): a row missing WBS.
        conn.execute(
            "INSERT INTO procore_financial_line_items "
            "(line_item_key, project_key, parent_record_key, endpoint_id, line_item_id, "
            " line_item_kind, wbs_code_id, cost_code_id, line_item_type_id, "
            " raw_body_persisted, redaction_applied) "
            "VALUES ('li1', 'p1', 'parent1', 'line-items', 'lid1', 'commitment', "
            " NULL, 'cc1', 'lt1', 0, 1)"
        )
        conn.commit()
    finally:
        conn.close()


def test_v36_confidence_label_column_and_version(tmp_path: Path) -> None:
    db = tmp_path / "v36.db"
    assert _migrate(db) == LATEST_SCHEMA_VERSION
    assert LATEST_SCHEMA_VERSION >= 36
    conn = sqlite3.connect(str(db))
    try:
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(second_brain_financial_review_required_items)")
        }
        assert "confidence_label" in cols
        # idempotent re-apply must not error on the additive ALTER
        assert _migrate(db) == LATEST_SCHEMA_VERSION
    finally:
        conn.close()


def test_routing_covers_all_seven_categories_with_tier_and_confidence(tmp_path: Path) -> None:
    db = tmp_path / "route.db"
    _migrate(db)
    _seed_all(db)

    result = run_review_required_routing(db_path=str(db), project_key=None)

    assert set(result["by_trigger"]) == ALL_TRIGGERS
    assert result["review_required_count"] == sum(result["by_trigger"].values())

    conn = sqlite3.connect(str(db))
    try:
        rows = list(
            conn.execute(
                "SELECT trigger_category, review_tier, confidence_label, advisory_only, "
                " financial_determination_performed, payment_decision_performed "
                "FROM second_brain_financial_review_required_items WHERE run_id=?",
                (result["run_id"],),
            )
        )
    finally:
        conn.close()

    assert rows
    tier_by_trigger: dict[str, str] = {}
    for trigger, tier, confidence, advisory, determination, payment in rows:
        # guard invariants on every routed row
        assert advisory == 1
        assert determination == 0
        assert payment == 0
        assert confidence in {"low", "medium", "high"}
        tier_by_trigger[trigger] = tier

    # deterministic, policy-driven tier mapping
    assert tier_by_trigger["determination_attempt"] == "legal_contract_review"
    assert tier_by_trigger["missing_or_inconsistent_currency"] == "financial_review"
    assert tier_by_trigger["relationship_ambiguity"] == "financial_review"
    assert tier_by_trigger["fail_closed_required_source"] == "financial_review"
    assert tier_by_trigger["amount_parse_ambiguous_or_rejected"] == "operator_review"
    assert tier_by_trigger["missing_source_field_path"] == "operator_review"
    assert tier_by_trigger["missing_wbs_cost_code_or_line_item_type"] == "operator_review"


def test_determination_attempt_never_sets_determination_flag(tmp_path: Path) -> None:
    db = tmp_path / "det.db"
    _migrate(db)
    conn = sqlite3.connect(str(db))
    _seed_fact(conn, pk="p1", parse_status="conflicting")
    conn.commit()
    conn.close()

    result = run_review_required_routing(db_path=str(db))
    assert result["by_trigger"].get("determination_attempt") == 1

    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT review_tier, financial_determination_performed, claim_or_entitlement_decision_performed "
            "FROM second_brain_financial_review_required_items "
            "WHERE run_id=? AND trigger_category='determination_attempt'",
            (result["run_id"],),
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "legal_contract_review"
    assert row[1] == 0
    assert row[2] == 0


def test_runs_are_isolated_no_cross_run_duplication(tmp_path: Path) -> None:
    db = tmp_path / "iso.db"
    _migrate(db)
    _seed_all(db)

    first = run_review_required_routing(db_path=str(db))
    second = run_review_required_routing(db_path=str(db))

    assert first["run_id"] != second["run_id"]
    assert first["review_required_count"] == second["review_required_count"]

    conn = sqlite3.connect(str(db))
    try:
        n_first = conn.execute(
            "SELECT COUNT(*) FROM second_brain_financial_review_required_items WHERE run_id=?",
            (first["run_id"],),
        ).fetchone()[0]
    finally:
        conn.close()
    assert n_first == first["review_required_count"]


def test_proof_generated_and_redaction_clean(tmp_path: Path) -> None:
    db = tmp_path / "proof.db"
    _migrate(db)
    _seed_all(db)
    out_dir = tmp_path / "evidence"

    proof = build_financial_review_required_proof(db_path=str(db), out_dir=str(out_dir))

    md_path = out_dir / "financial-review-required-proof.md"
    json_path = out_dir / "financial-review-required-proof.json"
    assert md_path.exists()
    assert json_path.exists()
    assert proof["review_required_count"] > 0

    md_text = md_path.read_text()
    assert "Financial Review-Required Routing Proof" in md_text
    assert "advisory review aid" in md_text.lower()
    # every category appears in the human proof
    for trigger in ALL_TRIGGERS:
        assert trigger in md_text

    combined = (md_text + json_path.read_text()).lower()
    for forbidden in ("bearer ", "-----begin", "https://", "sig=", "token=", "access_token"):
        assert forbidden not in combined
