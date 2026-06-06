"""Phase 09 Addendum Prompt 04 — memory quality and supersession controls.

Proves deterministic duplicate detection/suppression, metadata-only supersession with retrieval
exclusion, freshness labeling, source-ref preservation, review-status transition validation, and no
raw / no writeback.
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
from hb_assistant.construction.second_brain.memory.curator import propose_memory_candidate
from hb_assistant.construction.second_brain.memory.models import MemoryItem
from hb_assistant.construction.second_brain.memory.quality_controls import (
    ALLOWED_STATUS_TRANSITIONS,
    build_memory_quality_controls_proof,
    detect_duplicate_accepted,
    normalize_statement,
    statement_fingerprint,
    supersede_accepted_memory,
    validate_status_transition,
)
from hb_assistant.construction.second_brain.memory.store import (
    set_memory_item_status,
    write_memory_item,
)
from hb_assistant.construction.second_brain.retrieval.memory_loader import (
    load_reviewed_memory_nodes,
)
from hb_assistant.store.migrator import SQLiteMigrator


def _accepted(db: str, mid: str, statement: str) -> None:
    write_memory_item(
        MemoryItem(
            memory_id=mid,
            memory_type="project_context",
            statement_redacted=statement,
            project_key="proj-a",
            confidence_class="high",
            review_status="accepted",
            source_refs=[
                {
                    "source_family": "approved_read_models",
                    "source_ref": f"ref-{mid}",
                    "evidence_ref": f"ev-{mid}",
                }
            ],
        ),
        db_path=db,
    )


def _migrated(tmp_path: Path) -> str:
    db = str(tmp_path / "qc.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def test_normalize_and_fingerprint_match_equivalent_statements() -> None:
    assert normalize_statement("  Hello   World ") == "hello world"
    a = statement_fingerprint(
        statement_redacted="Hello World",
        project_key="p",
        memory_type="fact",
        source_family="f",
    )
    b = statement_fingerprint(
        statement_redacted="hello   world",
        project_key="p",
        memory_type="fact",
        source_family="f",
    )
    assert a == b


def test_detect_duplicate_accepted(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    _accepted(db, "m1", "Submittal turnaround is tracked locally.")
    dup = detect_duplicate_accepted(
        statement_redacted="submittal   turnaround is TRACKED locally.",
        project_key="proj-a",
        memory_type="project_context",
        source_family="approved_read_models",
        db_path=db,
    )
    assert dup["is_duplicate"] is True and dup["existing_memory_id"] == "m1"


def test_duplicate_suppressed_at_acceptance(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    _accepted(db, "m1", "Submittal turnaround is tracked locally.")
    cand = propose_memory_candidate(
        statement_redacted="Submittal turnaround is tracked locally.",
        proposed_memory_type="project_context",
        origin_id="o",
        source_refs=[{"source_family": "approved_read_models", "source_ref": "ref-x"}],
        confidence_class="high",
        project_key="proj-a",
        db_path=db,
        emit=True,
    )
    result = accept_memory_candidate(cand.candidate_id, db_path=db, confirm=True)
    assert result["accepted"] is False
    assert "DUPLICATE_ACCEPTED" in result["blocks"]
    assert result["duplicate_of_memory_id"] == "m1"


def test_supersession_excludes_from_retrieval(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    _accepted(db, "old", "old fact")
    _accepted(db, "new", "new fact")
    res = supersede_accepted_memory(
        old_memory_id="old", new_memory_id="new", db_path=db, confirm=True
    )
    assert res["superseded"] is True
    loaded = {str(n["source_ref"]) for n in load_reviewed_memory_nodes(db)}
    assert "old" not in loaded and "new" in loaded
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT review_status FROM long_term_memory_items WHERE memory_id='old'"
        ).fetchone()
        link = conn.execute(
            "SELECT supersedes_memory_id FROM long_term_memory_items WHERE memory_id='new'"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "superseded"
    assert link[0] == "old"


def test_supersede_dry_run_persists_nothing(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    _accepted(db, "old", "old fact")
    _accepted(db, "new", "new fact")
    res = supersede_accepted_memory(old_memory_id="old", new_memory_id="new", db_path=db)
    assert res["superseded"] is False and res["persisted"] is False
    assert len(load_reviewed_memory_nodes(db)) == 2  # both still accepted


def test_supersede_blocks_non_accepted(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    _accepted(db, "new", "new fact")
    res = supersede_accepted_memory(
        old_memory_id="missing", new_memory_id="new", db_path=db, confirm=True
    )
    assert res["superseded"] is False and "OLD_NOT_FOUND" in res["blocks"]


def test_transition_matrix() -> None:
    assert validate_status_transition("pending_review", "accepted")["ok"] is True
    assert validate_status_transition("pending_review", "rejected")["ok"] is True
    assert validate_status_transition("accepted", "superseded")["ok"] is True
    assert validate_status_transition("accepted", "rejected")["ok"] is False
    assert validate_status_transition("accepted", "pending_review")["ok"] is False
    assert validate_status_transition("rejected", "accepted")["ok"] is False
    assert validate_status_transition("accepted", "bogus")["reason"] == "UNKNOWN_STATUS"
    assert ALLOWED_STATUS_TRANSITIONS["accepted"] == frozenset({"superseded"})


def test_source_refs_preserved_and_guard_clean(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    _accepted(db, "m1", "a fact")
    conn = sqlite3.connect(db)
    try:
        fam, ref, ev = conn.execute(
            "SELECT source_family, source_ref, evidence_trail_id FROM long_term_memory_source_refs "
            "WHERE memory_id='m1'"
        ).fetchone()
        guard = conn.execute(
            "SELECT raw_prompt_persisted + raw_response_persisted + retrieved_context_persisted "
            "FROM long_term_memory_items WHERE memory_id='m1'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert fam == "approved_read_models" and ref and ev
    assert int(guard) == 0


def test_set_memory_item_status_metadata_only(tmp_path: Path) -> None:
    db = _migrated(tmp_path)
    _accepted(db, "m1", "a fact")
    set_memory_item_status("m1", review_status="superseded", db_path=db)
    conn = sqlite3.connect(db)
    try:
        status = conn.execute(
            "SELECT review_status FROM long_term_memory_items WHERE memory_id='m1'"
        ).fetchone()[0]
        guard = conn.execute(
            "SELECT raw_prompt_persisted + raw_response_persisted + retrieved_context_persisted "
            "FROM long_term_memory_items WHERE memory_id='m1'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert status == "superseded" and int(guard) == 0


def test_proof_passes_and_writes_clean(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.financial_review_routing import _assert_no_raw

    ed = tmp_path / "ev"
    proof = build_memory_quality_controls_proof(evidence_dir=str(ed), write_evidence=True)
    assert proof["proof_passed"] is True
    for name in (
        "accepted-memory-quality-controls-proof.json",
        "accepted-memory-quality-controls-proof.md",
    ):
        _assert_no_raw((ed / name).read_text(encoding="utf-8"), name)


def test_cli_quality_controls_proof() -> None:
    result = CliRunner().invoke(
        app, ["second-brain", "memory", "quality-controls-proof", "--no-evidence", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["proof_passed"] is True


def test_cli_supersede(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _migrated(tmp_path)
    _accepted(db, "old", "old fact")
    _accepted(db, "new", "new fact")
    monkeypatch.setattr(PathPolicy, "get_db_path", lambda self: Path(db))
    # dry run
    dry = CliRunner().invoke(
        app, ["second-brain", "memory", "supersede", "--old-id", "old", "--new-id", "new", "--json"]
    )
    assert dry.exit_code == 0, dry.output
    assert json.loads(dry.output)["superseded"] is False
    # confirm
    done = CliRunner().invoke(
        app,
        [
            "second-brain",
            "memory",
            "supersede",
            "--old-id",
            "old",
            "--new-id",
            "new",
            "--confirm",
            "--json",
        ],
    )
    assert done.exit_code == 0, done.output
    assert json.loads(done.output)["superseded"] is True
