"""Phase 09 Addendum — explicit candidate staging bridge (preview -> durable candidate store).

Proves a previewed candidate can be staged into memory_update_candidates (id preserved), that
`memory accept` succeeds after staging, that staging itself creates no accepted memory, and that a
missing id fails closed — all metadata-only with guard columns false.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.second_brain.memory.acceptance import accept_memory_candidate
from hb_assistant.construction.second_brain.memory.candidate_preview import (
    MemoryCandidatePreviewError,
    build_memory_candidate_preview,
    build_memory_candidate_stage_proof,
    stage_memory_candidate,
)
from hb_assistant.construction.second_brain.memory.store import read_memory_candidate
from hb_assistant.store.migrator import SQLiteMigrator


def _migrated(tmp_path: Path) -> str:
    db = str(tmp_path / "stage.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def _first_tier1_id(db: str) -> str:
    preview = build_memory_candidate_preview(db, write_evidence=False)
    cand = next(c for c in preview["candidates"] if int(c["review_tier"]) == 1)
    return str(cand["candidate_id"])


def test_stage_persists_and_preserves_id(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    cid = _first_tier1_id(db)
    result = stage_memory_candidate(cid, db_path=db, confirm=True)
    assert result["staged"] is True and result["persisted"] is True
    assert result["candidate_id"] == cid
    row = read_memory_candidate(cid, db_path=db)
    assert row is not None and row["candidate_id"] == cid
    assert row["status"] == "proposed"


def test_stage_dry_run_persists_nothing(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    cid = _first_tier1_id(db)
    result = stage_memory_candidate(cid, db_path=db, confirm=False)
    assert result["staged"] is False and result["persisted"] is False
    assert result["would_stage"] is True
    assert read_memory_candidate(cid, db_path=db) is None


def test_stage_not_found_fails_closed(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    with pytest.raises(MemoryCandidatePreviewError):
        stage_memory_candidate("mcp_not_a_real_candidate", db_path=db, confirm=True)


def test_stage_is_idempotent(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    cid = _first_tier1_id(db)
    stage_memory_candidate(cid, db_path=db, confirm=True)
    again = stage_memory_candidate(cid, db_path=db, confirm=True)
    assert again["staged"] is True
    assert again["already_staged"] is True
    assert again["persisted"] is False


def test_staged_row_guard_columns_false(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    cid = _first_tier1_id(db)
    stage_memory_candidate(cid, db_path=db, confirm=True)
    conn = sqlite3.connect(db)
    try:
        cols = [str(r[1]) for r in conn.execute("PRAGMA table_info(memory_update_candidates)")]
        guards = [c for c in cols if c.endswith("_persisted")]
        guard_sum = conn.execute(
            f"SELECT COALESCE(SUM({'+'.join(guards)}), 0) FROM memory_update_candidates"
        ).fetchone()[0]
    finally:
        conn.close()
    assert int(guard_sum) == 0


def test_stage_then_accept_end_to_end(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    cid = _first_tier1_id(db)

    def _accepted_count() -> int:
        conn = sqlite3.connect(db)
        try:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM long_term_memory_items WHERE review_status='accepted'"
                ).fetchone()[0]
            )
        finally:
            conn.close()

    # staging alone creates no accepted memory
    stage_memory_candidate(cid, db_path=db, confirm=True)
    assert _accepted_count() == 0
    # accept now succeeds (it could not before staging)
    result = accept_memory_candidate(cid, db_path=db, confirm=True)
    assert result["accepted"] is True
    assert _accepted_count() == 1


def test_accept_before_staging_fails(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.memory.acceptance import MemoryAcceptanceError

    db = _migrated(tmp_path)
    cid = _first_tier1_id(db)
    with pytest.raises(MemoryAcceptanceError):  # candidate not found until staged
        accept_memory_candidate(cid, db_path=db, confirm=True)


def test_stage_proof_passes_and_writes_clean(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.financial_review_routing import _assert_no_raw

    ed = tmp_path / "ev"
    proof = build_memory_candidate_stage_proof(evidence_dir=str(ed), write_evidence=True)
    assert proof["proof_passed"] is True
    for name in (
        "accepted-memory-candidate-stage-proof.json",
        "accepted-memory-candidate-stage-proof.md",
    ):
        _assert_no_raw((ed / name).read_text(encoding="utf-8"), name)


def test_cli_stage_dry_run_and_confirm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _migrated(tmp_path)
    cid = _first_tier1_id(db)
    monkeypatch.setattr(PathPolicy, "get_db_path", lambda self: Path(db))
    dry = CliRunner().invoke(
        app, ["second-brain", "memory", "candidates", "stage", "--candidate-id", cid, "--json"]
    )
    assert dry.exit_code == 0, dry.output
    assert json.loads(dry.output)["staged"] is False
    done = CliRunner().invoke(
        app,
        [
            "second-brain",
            "memory",
            "candidates",
            "stage",
            "--candidate-id",
            cid,
            "--confirm",
            "--json",
        ],
    )
    assert done.exit_code == 0, done.output
    assert json.loads(done.output)["staged"] is True


def test_cli_stage_not_found_exit_3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    monkeypatch.setattr(PathPolicy, "get_db_path", lambda self: Path(db))
    result = CliRunner().invoke(
        app,
        [
            "second-brain",
            "memory",
            "candidates",
            "stage",
            "--candidate-id",
            "mcp_nope",
            "--confirm",
            "--json",
        ],
    )
    assert result.exit_code == 3, result.output


def test_cli_stage_proof() -> None:
    result = CliRunner().invoke(
        app, ["second-brain", "memory", "candidates", "stage-proof", "--no-evidence", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["proof_passed"] is True
