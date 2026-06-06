"""Phase 09 Addendum Prompt 01 — memory candidate preview (advisory, read-only).

Proves the preview surfaces possible long-term memory candidates from safe, redacted, source-linked
records while never accepting or persisting accepted memory, rejecting unsafe inputs, and emitting
metadata-only evidence.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.second_brain.contracts import load_phase_09_contract
from hb_assistant.construction.second_brain.financial_review_routing import _assert_no_raw
from hb_assistant.construction.second_brain.memory.candidate_preview import (
    MemoryCandidatePreviewError,
    _evaluate_input,
    _seed_proof_db,
    build_memory_candidate_preview,
    build_memory_candidate_preview_proof,
)
from hb_assistant.store.migrator import SQLiteMigrator


def _seed(tmp_path: Path) -> str:
    db = str(tmp_path / "mcp.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _seed_proof_db(db)
    return db


def _ltm(db: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM long_term_memory_items").fetchone()[0])
    finally:
        conn.close()


def test_build_from_safe_fixture(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    result = build_memory_candidate_preview(db)
    assert result["status"] == "built"
    types = {c["memory_type"] for c in result["candidates"]}
    assert {
        "system_config_fact",
        "workflow_preference",
        "retrieval_preference",
        "team_context",
    }.issubset(types)

    required = load_phase_09_contract("memory_candidate_preview_contract")[
        "required_candidate_fields"
    ]
    for c in result["candidates"]:
        for field in required:
            assert field in c, field
        assert c["review_status"] == "pending_review"
        assert c["raw_prompt_persisted"] is False
        assert c["raw_response_persisted"] is False
        assert c["retrieved_context_persisted"] is False
        assert c["source_ref_hash"] and len(c["source_ref_hash"]) == 48
        assert len(c["statement_redacted"]) <= 280


def test_raw_shaped_value_rejected(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    result = build_memory_candidate_preview(db)
    reasons = {r["reason_code"] for r in result["rejected"]}
    assert "REJECTED_RAW_SHAPED" in reasons
    # the raw-shaped preference never appears as a candidate
    assert all("https://" not in c["statement_redacted"] for c in result["candidates"])


def test_unsourced_candidate_rejected() -> None:
    outcome = _evaluate_input(
        {
            "memory_type": "operator_preference",
            "source_family": "operator_preference_profiles",
            "source_ref": "",
            "statement_redacted": "a preference with no source link",
        },
        determination_terms=[],
        max_chars=280,
    )
    assert outcome["surfaced"] is False
    assert outcome["reason_code"] == "REJECTED_UNSOURCED"


def test_determination_implying_rejected(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    result = build_memory_candidate_preview(db)
    reasons = {r["reason_code"] for r in result["rejected"]}
    assert "REJECTED_DETERMINATION" in reasons


def test_tier3_surfaced_preview_only_never_accepted(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    result = build_memory_candidate_preview(db)
    tier3 = [c for c in result["candidates"] if c["review_tier"] >= 3]
    assert tier3, "expected a low-confidence tier-3 candidate to surface"
    for c in tier3:
        assert c["non_acceptance_preview_only"] is True
        assert c["review_status"] == "pending_review"
    # nothing is ever auto-accepted
    assert all(c["review_status"] == "pending_review" for c in result["candidates"])


def test_not_repeated_preference_excluded(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    result = build_memory_candidate_preview(db)
    surfaced_refs = {c["source_ref"] for c in result["candidates"]}
    assert "pref-single" not in surfaced_refs  # signal_count 1 filtered before validation


def test_preview_writes_no_accepted_memory(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    before = _ltm(db)
    result = build_memory_candidate_preview(db)
    after = _ltm(db)
    assert before == after == 0
    assert result["writes_accepted_memory"] is False
    assert result["accepted_memory_written"] == 0
    assert result["read_only"] is True


def test_preview_is_deterministic(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    a = build_memory_candidate_preview(db)
    b = build_memory_candidate_preview(db)
    assert a["candidates"] == b["candidates"]
    assert a["rejected"] == b["rejected"]


def test_fail_closed_on_unready_schema(tmp_path: Path) -> None:
    with pytest.raises(MemoryCandidatePreviewError):
        build_memory_candidate_preview(str(tmp_path / "absent.sqlite"))


def test_evidence_is_metadata_only(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    evidence_dir = tmp_path / "evidence"
    build_memory_candidate_preview(db, evidence_dir=str(evidence_dir), write_evidence=True)
    raw = (evidence_dir / "accepted-memory-candidate-preview.json").read_text(encoding="utf-8")
    _assert_no_raw(raw, "preview evidence json")  # raises if any raw pattern leaked
    doc = json.loads(raw)
    assert doc["metadata_only"] is True
    for s in doc["candidate_summaries"]:
        assert "statement_redacted" not in s
        assert "source_ref" not in s
        assert "statement_hash" in s
    assert (evidence_dir / "accepted-memory-candidate-preview.md").exists()


def test_proof_passes_and_is_clean() -> None:
    proof = build_memory_candidate_preview_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["raw_shaped_rejected"] is True
    assert proof["unsourced_rejected"] is True
    assert proof["determination_rejected"] is True
    assert proof["tier3_surfaced_preview_only"] is True
    assert proof["accepted_memory_unchanged"] is True
    assert proof["evidence_metadata_only"] is True


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    proof = build_memory_candidate_preview_proof(
        evidence_dir=str(evidence_dir), write_evidence=True
    )
    assert proof["proof_passed"] is True
    for name in (
        "accepted-memory-candidate-preview.json",
        "accepted-memory-candidate-preview.md",
        "accepted-memory-candidate-preview-proof.json",
        "accepted-memory-candidate-preview-proof.md",
    ):
        text = (evidence_dir / name).read_text(encoding="utf-8")
        _assert_no_raw(text, name)


def test_cli_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _seed(tmp_path)
    monkeypatch.setattr(PathPolicy, "get_db_path", lambda self: Path(db))
    result = CliRunner().invoke(app, ["second-brain", "memory", "candidates", "build", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "built"
    assert payload["writes_accepted_memory"] is False
    assert payload["candidate_count"] >= 4


def test_cli_proof(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["second-brain", "memory", "candidates", "proof", "--no-evidence", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["proof_passed"] is True
