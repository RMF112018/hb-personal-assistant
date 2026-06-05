"""Phase 08A Prompt 12 — Daily Brief Agent (daily_brief_agent) generate/evaluate/apply."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.second_brain.daily_brief import (
    build_daily_brief_agent_proof,
    build_daily_brief_delivery_handoff_proof,
    run_daily_brief,
)
from hb_assistant.construction.second_brain.reasoning import MockClaudeAdapter
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "agent.sqlite")


def _seed(db_path: str) -> None:
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


def test_dry_run_does_not_write_or_apply(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    vault = tmp_path / "briefs"
    result = run_daily_brief(
        brief_date="2026-06-02",
        project_key="P1",
        db_path=db_path,
        mode="dry_run",
        adapter=MockClaudeAdapter(),
        emit_receipt=False,
        vault_brief_dir=str(vault),
    )
    assert result.applied is False
    assert result.output_written is False
    assert not vault.exists()
    assert result.evaluation["passed"] is True
    assert result.eligible_for_delivery is True


def test_repeated_dry_run_emit_receipt_is_idempotent(db_path: str) -> None:
    _seed(db_path)
    first = run_daily_brief(
        brief_date="2026-06-02",
        project_key="P1",
        db_path=db_path,
        mode="dry_run",
        adapter=MockClaudeAdapter(),
        emit_receipt=True,
    )
    second = run_daily_brief(
        brief_date="2026-06-02",
        project_key="P1",
        db_path=db_path,
        mode="dry_run",
        adapter=MockClaudeAdapter(),
        emit_receipt=True,
    )
    assert first.applied is False and second.applied is False
    assert first.evaluation_run_id and second.evaluation_run_id
    assert first.brief_run_id and second.brief_run_id

    conn = sqlite3.connect(db_path)
    packet_count = conn.execute("SELECT COUNT(*) FROM second_brain_research_packets").fetchone()[0]
    run_count = conn.execute("SELECT COUNT(*) FROM daily_brief_runs").fetchone()[0]
    conn.close()
    assert packet_count == 1
    assert run_count == 2


def test_cli_repeated_dry_run_emit_receipt_is_idempotent() -> None:
    db_path = str(PathPolicy().get_db_path())
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    _seed(db_path)
    args = [
        "daily-brief",
        "generate",
        "--date",
        "2026-06-02",
        "--project-key",
        "P1",
        "--mode",
        "dry_run",
        "--emit-receipt",
        "--json",
    ]
    first = runner.invoke(app, args)
    second = runner.invoke(app, args)
    assert first.exit_code == 0, first.stdout
    assert second.exit_code == 0, second.stdout
    assert "IntegrityError" not in first.stdout + second.stdout

    conn = sqlite3.connect(db_path)
    packet_count = conn.execute("SELECT COUNT(*) FROM second_brain_research_packets").fetchone()[0]
    conn.close()
    assert packet_count == 1


def test_apply_without_receipt_writes_output_only(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    vault = tmp_path / "briefs"
    result = run_daily_brief(
        brief_date="2026-06-02",
        project_key="P1",
        db_path=db_path,
        mode="apply",
        adapter=MockClaudeAdapter(),
        emit_receipt=False,
        vault_brief_dir=str(vault),
    )
    assert result.applied is True
    assert result.output_written is True
    assert (vault / "2026-06-02_daily_brief.md").exists()
    assert result.evaluation_run_id is None
    assert result.brief_run_id is None

    conn = sqlite3.connect(db_path)
    packet_count = conn.execute("SELECT COUNT(*) FROM second_brain_research_packets").fetchone()[0]
    run_count = conn.execute("SELECT COUNT(*) FROM daily_brief_runs").fetchone()[0]
    eval_count = conn.execute("SELECT COUNT(*) FROM second_brain_evaluation_runs").fetchone()[0]
    conn.close()
    assert packet_count == 0
    assert run_count == 0
    assert eval_count == 0


def test_apply_writes_output_and_persists_links(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    vault = tmp_path / "briefs"
    result = run_daily_brief(
        brief_date="2026-06-02",
        project_key="P1",
        db_path=db_path,
        mode="apply",
        adapter=MockClaudeAdapter(),
        emit_receipt=True,
        vault_brief_dir=str(vault),
    )
    assert result.applied is True
    assert result.output_written is True
    assert (vault / "2026-06-02_daily_brief.md").exists()
    assert result.evaluation_run_id
    assert result.brief_run_id

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    run_row = dict(conn.execute("SELECT * FROM daily_brief_runs").fetchone())
    eval_count = conn.execute("SELECT COUNT(*) FROM second_brain_evaluation_runs").fetchone()[0]
    conn.close()

    assert run_row["mode"] == "apply"
    assert run_row["evaluation_run_id"] == result.evaluation_run_id
    assert run_row["output_path_redacted"]
    assert run_row["output_path_hash"]
    assert eval_count == 1
    guards = [c for c in run_row if c.endswith("_persisted")] + ["external_writeback_performed"]
    for col in guards:
        assert run_row[col] == 0, f"guard {col} must be 0"


def test_repeated_apply_emit_receipt_is_idempotent(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    vault = tmp_path / "briefs"
    for _ in range(2):
        result = run_daily_brief(
            brief_date="2026-06-02",
            project_key="P1",
            db_path=db_path,
            mode="apply",
            adapter=MockClaudeAdapter(),
            emit_receipt=True,
            vault_brief_dir=str(vault),
        )
        assert result.applied is True
        assert result.output_written is True

    conn = sqlite3.connect(db_path)
    packet_count = conn.execute("SELECT COUNT(*) FROM second_brain_research_packets").fetchone()[0]
    run_count = conn.execute("SELECT COUNT(*) FROM daily_brief_runs").fetchone()[0]
    eval_count = conn.execute("SELECT COUNT(*) FROM second_brain_evaluation_runs").fetchone()[0]
    conn.close()
    assert packet_count == 1
    assert run_count == 2
    assert eval_count == 2
    assert (vault / "2026-06-02_daily_brief.md").exists()


def test_apply_blocked_when_evaluation_fails(tmp_path: Path, db_path: str) -> None:
    ConstructionStore(db_path)  # migrate only -> empty -> evaluation fails
    vault = tmp_path / "briefs"
    result = run_daily_brief(
        brief_date="2026-06-02",
        project_key="P1",
        db_path=db_path,
        mode="apply",
        adapter=MockClaudeAdapter(),
        emit_receipt=True,
        vault_brief_dir=str(vault),
    )
    assert result.applied is False
    assert result.output_written is False
    assert result.apply_blocked_reason == "evaluation_failed"
    assert result.eligible_for_delivery is False
    assert not vault.exists()

    conn = sqlite3.connect(db_path)
    run_row = conn.execute("SELECT mode, output_path_redacted FROM daily_brief_runs").fetchone()
    conn.close()
    assert run_row[0] == "dry_run"  # persisted as dry_run, not apply
    assert run_row[1] is None  # no output path recorded


def test_handoff_is_local_only_and_source_linked(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    result = run_daily_brief(
        brief_date="2026-06-02",
        project_key="P1",
        db_path=db_path,
        mode="dry_run",
        adapter=MockClaudeAdapter(),
        emit_receipt=False,
    )
    h = result.delivery_handoff
    assert h.phase == "08B"
    assert h.local_only is True
    assert h.external_delivery_performed is False
    assert h.notification_summary.emitted is False
    assert h.notification_summary.channel == "local_only"
    assert h.html_rendering.rendered is False
    assert h.source_refs  # source-linked


def test_output_carries_no_raw_content(db_path: str) -> None:
    _seed(db_path)
    result = run_daily_brief(
        brief_date="2026-06-02",
        project_key="P1",
        db_path=db_path,
        mode="dry_run",
        adapter=MockClaudeAdapter(),
        emit_receipt=False,
    )
    blob = result.model_dump_json()
    for forbidden in (
        "signed_url",
        "download_url",
        "raw_body",
        "raw_prompt",
        "raw_response",
        "secret",
    ):
        assert forbidden not in blob


def test_daily_brief_agent_proof_passes() -> None:
    proof = build_daily_brief_agent_proof()
    assert proof["proof_passed"] is True
    assert proof["applied_run"]["applied"] is True
    assert proof["apply_blocked_run"]["apply_blocked_reason"] == "evaluation_failed"
    assert proof["no_output_when_apply_blocked"] is True
    assert proof["guard_columns_zero"] is True


def test_delivery_handoff_proof_passes() -> None:
    proof = build_daily_brief_delivery_handoff_proof()
    assert proof["proof_passed"] is True
    assert proof["local_only"] is True
    assert proof["external_delivery_performed"] is False
    assert proof["handoff_source_linked"] is True
