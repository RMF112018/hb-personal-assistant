"""Phase 09 Prompt 27 — context budget optimization.

Proves the five required paths: (1) normal — the best-effort optimizer recovers >= baseline items on a
crafted set, never exceeds the budget, preserves all metadata, and surfaces every budget drop as a
coverage warning; (2) missing-policy — fail-closed; (3) stale-schema — fail-closed on a pre-V38 store;
(4) unsafe-source — excluded raw families never enter the packing (denied with a coverage warning);
(5) no-raw / no-writeback — the summary carries no raw excerpt/content/source ref and the build path
performs no DB writes. Plus the proof. The authoritative apply_context_budget is never modified.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.retrieval import context_budget as cb
from hb_assistant.construction.second_brain.retrieval.context_budget import (
    ContextBudgetOptimizationError,
    _synthetic_items,
    build_context_budget_optimization,
    build_context_budget_optimization_proof,
    optimize_context_packing,
)
from hb_assistant.construction.second_brain.retrieval.models import RetrievalItem
from hb_assistant.construction.second_brain.retrieval.policy import (
    apply_context_budget,
    load_context_budget,
)
from hb_assistant.construction.second_brain.retrieval.vector_index import _proof_db

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)


def _total_rows(db: str) -> int:
    conn = sqlite3.connect(db)
    try:
        tables = [
            str(r[0])
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return sum(int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]) for t in tables)
    finally:
        conn.close()


def test_normal_optimizer_recovers_items_and_preserves_metadata() -> None:
    budget = load_context_budget()
    items = _synthetic_items()
    base_kept, _bc, _bt, _bd = apply_context_budget(items, budget)
    opt = optimize_context_packing(items, budget)

    # The baseline breaks at the oversized item; the optimizer skips it and keeps the small one.
    assert len(opt["kept"]) > len(base_kept)
    assert opt["char_count"] <= budget.max_context_chars  # never exceeds budget
    for it in opt["kept"]:
        assert it.source_ref and it.review_tier in (1, 2, 3) and it.confidence_class
    # every drop surfaced as a coverage warning (no silent loss)
    drops = sum(opt["dropped_by_reason"].values())
    assert drops >= 1
    assert len([w for w in opt["coverage_warnings"] if w.startswith("budget_dropped:")]) >= drops
    # priority preserved (kept tiers non-decreasing)
    tiers = [it.review_tier for it in opt["kept"]]
    assert tiers == sorted(tiers)


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise ContextBudgetOptimizationError("contract unavailable")

    monkeypatch.setattr(cb, "load_context_budget_optimization_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        with pytest.raises(ContextBudgetOptimizationError):
            build_context_budget_optimization(db)


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(ContextBudgetOptimizationError):
            build_context_budget_optimization(str(db))


def test_unsafe_source_denied_with_warning() -> None:
    # An explicitly requested excluded raw family is denied with a coverage warning, never packed.
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        result = build_context_budget_optimization(db, families=("raw_email_body",))
        assert "denied_excluded_family:raw_email_body" in result["coverage_warnings"]
        assert result["candidate_item_count"] == 0
        assert result["optimized"]["kept_count"] == 0
        # excluded family never appears as a kept/source family anywhere in the summary
        assert "raw_email_body" not in json.dumps(result["optimized"], default=str)


def test_no_raw_no_writeback() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        before = _total_rows(db)
        result = build_context_budget_optimization(db)
        after = _total_rows(db)
        assert before == after  # read-only: no DB writes
        assert result["read_only"] is True
        assert result["assembles_final_answer"] is False
        assert result["authoritative_packer_unchanged"] is True
        blob = json.dumps(result, default=str)
        assert "content_excerpt" not in blob and "text_redacted" not in blob
        assert "source_ref" not in blob.replace("source_refs", "")
        assert not _SECRET_OR_URL.search(blob)


def test_optimizer_never_exceeds_budget_on_all_oversized() -> None:
    budget = load_context_budget()
    items = [
        RetrievalItem(
            source_family="accepted_long_term_memory",
            source_ref=f"r{i}",
            record_type="m",
            record_ref=str(i),
            confidence_class="high",
            review_tier=1,
            recency="2026-01-01",
            content_excerpt_redacted="X" * budget.max_item_chars,
        )
        for i in range(40)  # 40 * 1800 = 72000 >> 24000 budget
    ]
    opt = optimize_context_packing(items, budget)
    assert opt["char_count"] <= budget.max_context_chars
    assert opt["truncated"] is True


def test_proof_passes_and_is_clean() -> None:
    proof = build_context_budget_optimization_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["items_recovered"] >= 1
    assert proof["within_budget"] is True
    assert proof["metadata_preserved"] is True
    assert proof["every_drop_has_warning"] is True
    assert proof["priority_preserved"] is True
    assert proof["authoritative_packer_unchanged"] is True
    assert proof["build_path_no_db_writes"] is True
    assert proof["no_raw_emitted"] is True
    assert proof["assembles_final_answer"] is False
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_context_budget_optimization_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "context-budget-optimization-proof.json"
    pm = tmp_path / "context-budget-optimization-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())
