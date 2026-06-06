"""Phase 09 Addendum Prompt 02 — explicit memory acceptance workflow.

Proves explicit operator acceptance converts a vetted candidate into an accepted long_term_memory_items
row, that unsafe candidates cannot be accepted, that rejected/deferred/superseded items never load into
retrieval, that no acceptance happens without explicit confirmation, and that guard columns stay false.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.second_brain.memory.acceptance import (
    MemoryAcceptanceError,
    _seed_proof_db,
    accept_memory_candidate,
    build_memory_acceptance_proof,
    decide_memory_candidate,
    list_accepted_memory,
)
from hb_assistant.construction.second_brain.retrieval.memory_loader import (
    load_reviewed_memory_nodes,
)
from hb_assistant.store.migrator import SQLiteMigrator


def _seed(tmp_path: Path) -> tuple[str, dict[str, str]]:
    db = str(tmp_path / "acc.sqlite")
    SQLiteMigrator(db_path=db).apply()
    ids = _seed_proof_db(db)
    return db, ids


def _count(db: str, status: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM long_term_memory_items WHERE review_status = ?", (status,)
            ).fetchone()[0]
        )
    finally:
        conn.close()


def _guard_sum(db: str) -> int:
    conn = sqlite3.connect(db)
    try:
        cols = [str(r[1]) for r in conn.execute("PRAGMA table_info(long_term_memory_items)")]
        guards = [c for c in cols if c.endswith("_persisted")]
        return int(
            conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guards)}), 0) FROM long_term_memory_items"
            ).fetchone()[0]
            or 0
        )
    finally:
        conn.close()


def test_accept_persists_as_accepted(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    result = accept_memory_candidate(ids["clean"], db_path=db, confirm=True)
    assert result["accepted"] is True
    assert result["review_status"] == "accepted"
    assert result["memory_id"]
    assert _count(db, "accepted") == 1


def test_dry_run_persists_nothing(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    result = accept_memory_candidate(ids["clean"], db_path=db, confirm=False)
    assert result["accepted"] is False
    assert result["would_accept"] is True
    assert result["persisted"] is False
    assert _count(db, "accepted") == 0


def test_raw_shaped_cannot_be_accepted(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    result = accept_memory_candidate(ids["raw"], db_path=db, confirm=True)
    assert result["accepted"] is False
    assert "RAW_CONTENT_FINDING" in result["blocks"]
    assert _count(db, "accepted") == 0


def test_unsourced_cannot_be_accepted(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    result = accept_memory_candidate(ids["unsourced"], db_path=db, confirm=True)
    assert result["accepted"] is False
    assert "NO_SOURCE_REF" in result["blocks"]


def test_unresolved_high_impact_cannot_be_accepted(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    result = accept_memory_candidate(ids["sensitive"], db_path=db, confirm=True)
    assert result["accepted"] is False
    assert "UNRESOLVED_HIGH_IMPACT" in result["blocks"]


def test_determination_cannot_be_accepted(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    result = accept_memory_candidate(ids["determination"], db_path=db, confirm=True)
    assert result["accepted"] is False
    assert "FINAL_DETERMINATION" in result["blocks"]


def test_rejected_and_superseded_do_not_load(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    accepted = accept_memory_candidate(ids["clean"], db_path=db, confirm=True)
    rej = decide_memory_candidate(
        ids["raw"], decision="rejected", reason="not durable", db_path=db, confirm=True
    )
    assert rej["created_memory_item"] is False
    nodes = load_reviewed_memory_nodes(db)
    loaded = {str(n.get("source_ref")) for n in nodes}
    assert accepted["memory_id"] in loaded  # accepted loads
    assert ids["superseded_memory_id"] not in loaded  # superseded excluded


def test_guard_columns_remain_false(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    accept_memory_candidate(ids["clean"], db_path=db, confirm=True)
    assert _guard_sum(db) == 0


def test_no_external_writeback_flag(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    result = accept_memory_candidate(ids["clean"], db_path=db, confirm=True)
    assert result["writes_external"] is False


def test_not_found_fail_closed(tmp_path: Path) -> None:
    db, _ = _seed(tmp_path)
    with pytest.raises(MemoryAcceptanceError):
        accept_memory_candidate("no-such-candidate", db_path=db, confirm=True)


def test_list_is_metadata_only(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    accept_memory_candidate(ids["clean"], db_path=db, confirm=True)
    listing = list_accepted_memory(db_path=db, status="accepted")
    assert listing["count"] == 1
    assert listing["metadata_only"] is True
    item = listing["items"][0]
    assert item["review_status"] == "accepted"
    assert "statement_redacted" not in item
    assert "memory_id" in item


def test_proof_passes_and_writes_clean_artifacts(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.financial_review_routing import _assert_no_raw

    evidence_dir = tmp_path / "evidence"
    proof = build_memory_acceptance_proof(evidence_dir=str(evidence_dir), write_evidence=True)
    assert proof["proof_passed"] is True
    for name in ("accepted-memory-acceptance-proof.json", "accepted-memory-acceptance-proof.md"):
        _assert_no_raw((evidence_dir / name).read_text(encoding="utf-8"), name)


def test_cli_accept_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, ids = _seed(tmp_path)
    monkeypatch.setattr(PathPolicy, "get_db_path", lambda self: Path(db))
    result = CliRunner().invoke(
        app, ["second-brain", "memory", "accept", "--candidate-id", ids["clean"], "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["accepted"] is False
    assert payload["requires_confirm"] is True
    assert payload["would_accept"] is True


def test_cli_accept_confirm_and_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, ids = _seed(tmp_path)
    monkeypatch.setattr(PathPolicy, "get_db_path", lambda self: Path(db))
    acc = CliRunner().invoke(
        app,
        ["second-brain", "memory", "accept", "--candidate-id", ids["clean"], "--confirm", "--json"],
    )
    assert acc.exit_code == 0, acc.output
    assert json.loads(acc.output)["accepted"] is True
    listing = CliRunner().invoke(
        app, ["second-brain", "memory", "list", "--status", "accepted", "--json"]
    )
    assert listing.exit_code == 0, listing.output
    assert json.loads(listing.output)["count"] == 1


def test_cli_reject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, ids = _seed(tmp_path)
    monkeypatch.setattr(PathPolicy, "get_db_path", lambda self: Path(db))
    result = CliRunner().invoke(
        app,
        [
            "second-brain",
            "memory",
            "reject",
            "--candidate-id",
            ids["raw"],
            "--reason",
            "not durable",
            "--confirm",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["decision"] == "rejected"
    assert payload["creates_accepted_memory"] is False


def test_cli_proof(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["second-brain", "memory", "proof", "--no-evidence", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["proof_passed"] is True
