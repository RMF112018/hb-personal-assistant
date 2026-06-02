"""Phase 08B Prompt 02 — persisted agent receipts (model-call + agent-run).

Proves the receipt models + writers persist metadata-only rows (hashes + token counts + structured
reason codes; no raw content), guard columns stay zero, and persistence is emit-gated via
``run_daily_brief`` (success / blocked / stale / dry-run paths).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.daily_brief import run_daily_brief
from hb_assistant.construction.second_brain.reasoning import (
    MockClaudeAdapter,
    build_agent_run_receipt,
    build_model_call_receipt,
)
from hb_assistant.construction.second_brain.store import (
    write_agent_model_receipt,
    write_agent_run_receipt,
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
)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "receipts.sqlite")


def _seed(db_path: str, *, stale: bool = False) -> None:
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
    store.upsert_project_issue_history_item(
        issue_family_id="iss-1",
        project_key="P1",
        status="open",
        source_families_json=json.dumps(["procore"]),
        confidence_class="medium",
        issue_kind="rfi",
        age_days=30,
        review_required=False,
        stale_unknown_flags_json=json.dumps(["stale_status"]) if stale else json.dumps([]),
    )


def _run(db_path: str, vault: Path, *, mode: str = "apply", emit: bool = True):
    return run_daily_brief(
        brief_date="2026-06-02",
        project_key="P1",
        db_path=db_path,
        mode=mode,
        adapter=MockClaudeAdapter(),
        emit_receipt=emit,
        vault_brief_dir=str(vault),
    )


def test_writer_roundtrip_metadata_only(db_path: str) -> None:
    run = build_agent_run_receipt(
        agent_id="daily_brief_agent",
        run_kind="daily_brief",
        status="synthesized",
        reason_code="T1_SOURCE_BACKED",
        review_tier=1,
        model_receipt_count=1,
    )
    write_agent_run_receipt(run, db_path=db_path)
    model = build_model_call_receipt(
        model_profile_id="daily_brief_synthesis",
        model_id=None,
        input_context="question text",
        output_text="answer text",
        agent_run_id=run.agent_run_id,
        review_tier_reason_code="T1_SOURCE_BACKED",
    )
    write_agent_model_receipt(model, db_path=db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rr = dict(conn.execute("SELECT * FROM second_brain_agent_run_receipts").fetchone())
    mr = dict(conn.execute("SELECT * FROM second_brain_agent_model_receipts").fetchone())
    assert rr["agent_id"] == "daily_brief_agent" and rr["status"] == "synthesized"
    assert mr["agent_run_id"] == run.agent_run_id
    assert len(mr["input_context_hash"]) == 64 and mr["input_token_count"] > 0
    # Guard columns zero; scan VALUES only (column names legitimately contain raw_*).
    for row in (rr, mr):
        for col, value in dict(row).items():
            if col.endswith("_persisted") or col == "external_writeback_performed":
                assert value == 0, f"guard {col} must be 0"
    values_blob = " ".join(str(v) for v in {**rr, **mr}.values())
    for forbidden in _FORBIDDEN:
        assert forbidden not in values_blob
    # The receipt models themselves carry no raw content.
    for forbidden in _FORBIDDEN:
        assert forbidden not in (run.model_dump_json() + model.model_dump_json())


def test_emit_persists_receipts_success(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    _run(db_path, tmp_path / "v", emit=True)
    conn = sqlite3.connect(db_path)
    rr = conn.execute(
        "SELECT agent_run_id, agent_id, status, reason_code FROM second_brain_agent_run_receipts"
    ).fetchone()
    assert rr is not None
    run_id, agent_id, status, reason_code = rr
    assert agent_id == "daily_brief_agent"
    assert status == "synthesized"
    assert reason_code  # a structured reason code is recorded
    # exactly one model receipt, linked to the run receipt
    model_run_ids = [
        r[0]
        for r in conn.execute(
            "SELECT agent_run_id FROM second_brain_agent_model_receipts"
        ).fetchall()
    ]
    assert model_run_ids == [run_id]


def test_dry_run_no_emit_persists_no_receipts(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    _run(db_path, tmp_path / "v", mode="dry_run", emit=False)
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM second_brain_agent_run_receipts").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM second_brain_agent_model_receipts").fetchone()[0] == 0


def test_blocked_run_records_receipt_with_reason(tmp_path: Path, db_path: str) -> None:
    # Empty store -> blocked synthesis; an emit-gated run still records an agent-run receipt.
    ConstructionStore(db_path)
    result = _run(db_path, tmp_path / "v", emit=True)
    assert result.applied is False
    conn = sqlite3.connect(db_path)
    rr = conn.execute("SELECT status, reason_code FROM second_brain_agent_run_receipts").fetchone()
    assert rr is not None
    assert rr[0] == "blocked"
    assert rr[1]  # a structured review-tier reason code is recorded


def test_stale_run_emits_receipts_no_raw(tmp_path: Path, db_path: str) -> None:
    _seed(db_path, stale=True)
    _run(db_path, tmp_path / "v", emit=True)
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT * FROM second_brain_agent_model_receipts").fetchall()
    blob = " ".join(str(v) for row in rows for v in row)
    for forbidden in _FORBIDDEN:
        assert forbidden not in blob
