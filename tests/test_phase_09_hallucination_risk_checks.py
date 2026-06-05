"""Phase 09 Prompt 29 — hallucination risk checks.

Proves the five required paths: (1) normal — the risk + overconfidence indicators fire on a synthetic
envelope and the risk band reflects them; (2) missing-policy — fail-closed; (3) stale-schema — fail-closed
on a pre-V38 store; (4) unsafe-source — an excluded raw family claim is unsupported and drives the
fabrication indicator / high risk band; (5) no-raw / no-writeback — the read-only build performs no DB
writes and emits no raw content/source ref. Plus the proof. The surface makes no determination and blocks
nothing.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.retrieval import hallucination_risk as hr
from hb_assistant.construction.second_brain.retrieval.hallucination_risk import (
    HallucinationRiskError,
    _synthetic_envelope,
    assess_hallucination_risk,
    build_hallucination_risk_checks,
    build_hallucination_risk_checks_proof,
)
from hb_assistant.construction.second_brain.retrieval.models import RetrievalEnvelope, RetrievalItem
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


def test_normal_indicators_fire() -> None:
    a = assess_hallucination_risk(_synthetic_envelope())
    assert a["risk_band"] == "high"  # unsupported claim present
    assert a["hallucination_indicators"]["unsupported_count"] == 1
    assert a["overconfidence_indicators"]["overconfident_count"] >= 1
    assert a["overconfidence_indicators"]["high_confidence_tier3_count"] >= 1
    assert "unsupported_claims" in a["indicators"]
    assert "overconfidence" in a["indicators"]
    # all bands are bucketed labels, not raw floats
    assert isinstance(a["hallucination_indicators"]["unsupported_rate_band"], str)


def test_low_risk_clean_corpus() -> None:
    env = RetrievalEnvelope(
        items=[
            RetrievalItem(
                source_family="approved_obsidian_generated_outputs",
                source_ref="r1",
                record_type="note",
                record_ref="1",
                confidence_class="high",
                review_tier=1,
            )
        ],
        degradation_mode="none",
        tier_distribution={"1": 1, "2": 0, "3": 0},
        coverage_warnings=[],
    )
    a = assess_hallucination_risk(env)
    assert a["risk_band"] == "low"
    assert a["indicators"] == []


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise HallucinationRiskError("contract unavailable")

    monkeypatch.setattr(hr, "load_hallucination_risk_checks_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        with pytest.raises(HallucinationRiskError):
            build_hallucination_risk_checks(db)


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(HallucinationRiskError):
            build_hallucination_risk_checks(str(db))


def test_unsafe_source_drives_fabrication_indicator() -> None:
    env = RetrievalEnvelope(
        items=[
            RetrievalItem(
                source_family="raw_email_body",  # excluded -> unsupported
                source_ref="x",
                record_type="email",
                record_ref="e",
                confidence_class="high",
                review_tier=1,
            )
        ],
        degradation_mode="none",
        tier_distribution={"1": 1, "2": 0, "3": 0},
        coverage_warnings=[],
    )
    a = assess_hallucination_risk(env)
    assert a["hallucination_indicators"]["unsupported_count"] == 1
    assert "unsupported_claims" in a["indicators"]
    assert a["risk_band"] == "high"


def test_no_raw_no_writeback() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        before = _total_rows(db)
        result = build_hallucination_risk_checks(db)
        after = _total_rows(db)
        assert before == after  # read-only: no DB writes
        assert result["read_only"] is True
        assert result["assembles_final_answer"] is False
        assert result["makes_determination"] is False
        blob = json.dumps(result, default=str)
        assert "content_excerpt" not in blob and "text_redacted" not in blob
        assert "source_ref" not in blob.replace("source_refs", "")
        assert not _SECRET_OR_URL.search(blob)


def test_proof_passes_and_is_clean() -> None:
    proof = build_hallucination_risk_checks_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["risk_band"] == "high"
    assert proof["unsupported_count"] >= 1
    assert proof["overconfident_count"] >= 1
    assert proof["fabrication_indicator_present"] is True
    assert proof["overconfidence_indicator_present"] is True
    assert proof["makes_determination"] is False
    assert proof["assembles_final_answer"] is False
    assert proof["build_path_no_db_writes"] is True
    assert proof["no_raw_emitted"] is True
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_hallucination_risk_checks_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "hallucination-risk-checks-proof.json"
    pm = tmp_path / "hallucination-risk-checks-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())
