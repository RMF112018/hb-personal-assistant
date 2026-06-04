"""Phase 09 Prompt 03 — generated-output population proof tests.

Exercises ``build_generated_output_population_proof`` over controlled offline
populations: a normal guard-clean population (research packet + daily-brief run +
source refs + handoff + evaluation, all in mock/dry-run with no vault write), an empty
DB, a fail-closed no-raw injection, and a stale-schema DB. No live model call, no vault
write, no external writeback.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.daily_brief import run_daily_brief
from hb_assistant.construction.second_brain.generated_output_proof import (
    build_generated_output_population_proof,
)
from hb_assistant.construction.second_brain.reasoning import MockClaudeAdapter
from hb_assistant.construction.second_brain.research import RetrievalOrchestrator
from hb_assistant.construction.store import ConstructionStore


def _seed(db_path: str) -> None:
    """Seed one promoted cross-source relationship for project P1."""
    store = ConstructionStore(db_path)
    store.upsert_cross_source_relationship(
        relationship_id="rel-1",
        source_family="email",
        source_record_type="message",
        source_record_ref="m1",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi1",
        relationship_type="references",
        confidence_class="human_promoted",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=False,
    )


def _populate(db_path: str) -> None:
    """Controlled offline population (mock adapter, dry-run, no vault)."""
    run_daily_brief(
        brief_date="2026-06-04",
        project_key="P1",
        db_path=db_path,
        mode="dry_run",
        emit_receipt=True,
        adapter=MockClaudeAdapter(),
    )
    RetrievalOrchestrator(db_path=db_path).orchestrate(
        packet_type="interactive_query", project_key="P1", emit_receipt=True
    )


def test_normal_population_is_guard_clean_and_source_linked(tmp_path: Path) -> None:
    db = str(tmp_path / "seeded.sqlite3")
    _seed(db)
    _populate(db)
    proof = build_generated_output_population_proof(db)

    assert proof["proof_passed"] is True
    assert proof["populated"] is True
    assert proof["total_rows"] > 0
    assert proof["guard_violation"] is False
    assert proof["raw_content_findings"] == []
    assert proof["source_linked"] is True
    assert proof["confidence_present"] is True
    # All generated-output families populated and guard-clean.
    packets = proof["tables"]["second_brain_research_packets"]
    assert packets["row_count"] >= 1
    assert packets["guard_sum"] == 0
    assert proof["tables"]["daily_brief_runs"]["row_count"] >= 1
    assert proof["tables"]["daily_brief_source_refs"]["row_count"] >= 1
    assert proof["tables"]["second_brain_evaluation_runs"]["guard_sum"] == 0


def test_empty_db_is_not_populated_but_does_not_crash(tmp_path: Path) -> None:
    db = str(tmp_path / "empty.sqlite3")
    ConstructionStore(db)  # migrate to current schema, no rows
    proof = build_generated_output_population_proof(db)

    assert proof["populated"] is False
    assert proof["proof_passed"] is False
    assert proof["total_rows"] == 0
    assert proof["guard_violation"] is False  # vacuously clean
    assert proof["missing_tables"] == []


def test_raw_content_injection_fails_closed(tmp_path: Path) -> None:
    db = str(tmp_path / "tainted.sqlite3")
    _seed(db)
    _populate(db)
    # Inject a tokenized URL into a safe redacted column on one populated row.
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE second_brain_research_packets SET summary_redacted = ? "
        "WHERE packet_id = (SELECT packet_id FROM second_brain_research_packets LIMIT 1)",
        ("https://example.com/file?sig=abcdef0123456789abcdef",),
    )
    conn.commit()
    conn.close()

    proof = build_generated_output_population_proof(db)
    assert proof["proof_passed"] is False
    assert "second_brain_research_packets.summary_redacted" in proof["raw_content_findings"]
    # The offending value is never echoed back — only the table.column location.
    assert "sig=abcdef" not in json.dumps(proof)


def test_stale_schema_is_handled_gracefully(tmp_path: Path) -> None:
    db = str(tmp_path / "stale.sqlite3")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_migrations (version INTEGER)")
    conn.execute("INSERT INTO schema_migrations (version) VALUES (5)")
    conn.commit()
    conn.close()

    proof = build_generated_output_population_proof(db)
    assert proof["schema_version"] == 5
    assert proof["proof_passed"] is False
    assert proof["populated"] is False
    # Generated-output tables absent on a stale schema — reported, not crashed.
    assert set(proof["missing_tables"]) == set(
        build_generated_output_population_proof.__globals__["GENERATED_OUTPUT_TABLES"]
    )
