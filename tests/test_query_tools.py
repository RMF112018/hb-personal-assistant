"""Phase 08A Prompt 06 — allowlisted read-only SQLite query tools against a seeded DB.

Proves: backed tools return bounded, source-linked, review-tier-labeled rows; the
relationship split (candidates vs accepted) filters by derived state; unbacked tools
degrade gracefully (no_read_model); the read-only connection blocks writes; results
emit no raw source fields; the query-tool receipt persists with guard columns 0;
results are bounded by max_rows; and the synthetic proof passes.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.query_tools import (
    QueryToolResult,
    build_sqlite_query_tool_proof,
    read_only_connection,
    run_query_tool,
)
from hb_assistant.construction.store import ConstructionStore

_FORBIDDEN = (
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "secret",
    "token",
)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "query_tools.sqlite")


def _seed(db_path: str) -> ConstructionStore:
    store = ConstructionStore(db_path)  # runs migrator to V26
    store.upsert_cross_source_relationship(
        relationship_id="rel-accepted",
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
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO project_risk_digest_items "
        "(risk_digest_id, project_key, risk_indicator_type, risk_source_class, "
        " summary_redacted, confidence_class, review_required, created_utc) "
        "VALUES ('rd1','P1','schedule_slip','source_stated','schedule slip amber',"
        "'medium',0,'2026-06-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO project_risk_digest_items "
        "(risk_digest_id, project_key, risk_indicator_type, risk_source_class, "
        " summary_redacted, confidence_class, review_required, created_utc) "
        "VALUES ('rd2','P1','cost_exposure','review_required','cost exposure red',"
        "'low',1,'2026-05-20T00:00:00Z')"
    )
    conn.commit()
    conn.close()
    return store


def test_backed_tool_returns_source_linked_tier_labeled_rows(db_path: str) -> None:
    _seed(db_path)
    result = run_query_tool("risk_digest", project_key="P1", db_path=db_path, emit_receipt=False)
    assert result.status == "ok"
    assert result.row_count == 2
    assert result.source_refs and len(result.source_refs) == 2
    for ref in result.source_refs:
        assert ref["source_family"] == "project_risk_digest_items"
        assert ref["source_ref"]
        assert ref["review_tier"] in {"1", "2", "3"}
        assert ref["review_status"]
    # Tier-3 (review_required) item is visible but never auto-concluded.
    tier3 = [it for it in result.items if it.review_tier == 3]
    assert tier3 and all(it.review_required for it in tier3)
    assert result.review_tier_summary["2"] == 1
    assert result.review_tier_summary["3"] == 1


def test_relationship_split_candidates_vs_accepted(db_path: str) -> None:
    _seed(db_path)
    accepted = run_query_tool(
        "accepted_relationships", project_key="P1", db_path=db_path, emit_receipt=False
    )
    assert accepted.row_count == 1
    assert accepted.items[0].relationship_state == "accepted_human_promoted"
    # The promoted relationship is not in a candidate state -> no candidate rows.
    candidates = run_query_tool(
        "relationship_candidates", project_key="P1", db_path=db_path, emit_receipt=False
    )
    assert candidates.row_count == 0
    assert candidates.status == "empty"


@pytest.mark.parametrize("tool", ["project_context", "source_coverage", "meeting_prep_briefs"])
def test_unbacked_tool_degrades_gracefully(tool: str, db_path: str) -> None:
    _seed(db_path)
    result = run_query_tool(tool, project_key="P1", db_path=db_path, emit_receipt=False)
    assert result.status == "no_read_model"
    assert result.items == []
    assert any(w.startswith("no_read_model:") for w in result.warnings)


def test_read_only_connection_blocks_writes(db_path: str) -> None:
    _seed(db_path)
    with read_only_connection(db_path) as conn:
        cur = conn.execute("PRAGMA query_only")
        assert cur.fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE _probe (x INTEGER)")
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE project_risk_digest_items SET confidence_class = 'high'")


def test_no_raw_fields_in_result(db_path: str) -> None:
    _seed(db_path)
    result = run_query_tool("risk_digest", project_key="P1", db_path=db_path, emit_receipt=False)
    blob = result.model_dump_json()
    for forbidden in _FORBIDDEN:
        assert forbidden not in blob


def test_source_refs_reject_forbidden_field_names() -> None:
    with pytest.raises(ValueError, match="forbidden raw field"):
        QueryToolResult(
            tool_name="risk_digest",
            source_refs=[{"source_family": "x", "download_url": "http-ish"}],
        )


def test_receipt_persisted_with_guards_zero(db_path: str) -> None:
    _seed(db_path)
    run_query_tool("risk_digest", project_key="P1", db_path=db_path, emit_receipt=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM query_tool_receipts").fetchall()
    assert len(rows) == 1
    row = dict(rows[0])
    assert row["tool_name"] == "risk_digest"
    assert row["row_count"] == 2
    assert row["status"] == "ok"
    assert row["arbitrary_sql_allowed"] == 0
    assert row["external_writeback_performed"] == 0
    conn.close()


def test_results_are_bounded_by_max_rows(db_path: str) -> None:
    _seed(db_path)
    result = run_query_tool(
        "risk_digest", project_key="P1", db_path=db_path, max_rows=1, emit_receipt=False
    )
    assert result.row_count == 1
    assert result.truncated is True


def test_v25_rows_unchanged_after_query(db_path: str) -> None:
    store = _seed(db_path)
    before = store.list_cross_source_relationships(project_key="P1")
    run_query_tool("accepted_relationships", project_key="P1", db_path=db_path, emit_receipt=False)
    after = store.list_cross_source_relationships(project_key="P1")
    assert before == after


def test_build_sqlite_query_tool_proof_passes() -> None:
    proof = build_sqlite_query_tool_proof()
    assert proof["proof_passed"] is True
    assert proof["arbitrary_sql_rejected"] is True
    assert proof["read_only_posture_enforced"] is True
    assert proof["no_raw_content"] is True
    assert proof["no_read_model_graceful_degradation"] is True
