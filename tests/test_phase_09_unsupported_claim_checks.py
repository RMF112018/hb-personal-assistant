"""Phase 09 Prompt 28 — unsupported claim checks + review routing.

Proves the five required paths: (1) normal — unsupported claims are detected and routed to
review_required, supported-but-flagged claims route to review_recommended, and no claim/entitlement
determination is made; (2) missing-policy — fail-closed; (3) stale-schema — fail-closed on a pre-V38
store; (4) unsafe-source — an excluded raw family claim is classified unsupported and routed to review
(never auto-supported); (5) no-raw / no-writeback — the summary carries no raw claim text/source ref and
persists nothing by default; the persisted receipt is metadata-only + guard-clean. Plus the proof.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.retrieval import unsupported_claim_checks as uc
from hb_assistant.construction.second_brain.retrieval.models import RetrievalItem
from hb_assistant.construction.second_brain.retrieval.unsupported_claim_checks import (
    UnsupportedClaimCheckError,
    _synthetic_claims,
    build_unsupported_claim_checks,
    build_unsupported_claim_checks_proof,
    detect_and_route_claims,
)
from hb_assistant.construction.second_brain.retrieval.vector_index import _proof_db

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)

_TABLE = "second_brain_retrieval_unsupported_claim_checks"


def _rows(db: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0])
    finally:
        conn.close()


def test_normal_detects_and_routes() -> None:
    cc = detect_and_route_claims(_synthetic_claims(), unsupported_review_tier=3)
    assert cc["claim_count"] == 4
    assert cc["unsupported_count"] == 1
    assert (
        cc["status"] == "blocked"
    )  # zero tolerance: an unsupported claim blocks fact-presentation
    # unsupported -> review_required; supported-but-flagged -> review_recommended
    statuses = {r["review_status"] for r in cc["routing_records"]}
    assert "review_required" in statuses and "review_recommended" in statuses
    reasons = {r["reason"] for r in cc["routing_records"]}
    assert "unsupported_no_source_link" in reasons and "supported_review_flagged" in reasons
    # routing records carry only hashed refs — never the raw source ref
    for r in cc["routing_records"]:
        assert "source_ref" not in r or "source_ref_hash" in r
        assert r["review_tier"] in (1, 2, 3)


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise UnsupportedClaimCheckError("contract unavailable")

    monkeypatch.setattr(uc, "load_unsupported_claim_checks_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        with pytest.raises(UnsupportedClaimCheckError):
            build_unsupported_claim_checks(db)
        assert _rows(db) == 0


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(UnsupportedClaimCheckError):
            build_unsupported_claim_checks(str(db))


def test_unsafe_source_excluded_family_routed() -> None:
    # An excluded raw family claim is unsupported and routed to review (never auto-supported).
    claims = [
        RetrievalItem(
            source_family="raw_email_body",
            source_ref="x",
            record_type="email",
            record_ref="e",
            confidence_class="high",
            review_tier=1,
        )
    ]
    cc = detect_and_route_claims(claims, unsupported_review_tier=3)
    assert cc["unsupported_count"] == 1 and cc["status"] == "blocked"
    rec = cc["routing_records"][0]
    assert rec["reason"] == "unsupported_excluded_family"
    assert rec["review_status"] == "review_required"


def test_no_raw_no_writeback_and_receipt_guard_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        # default build persists nothing; no raw claim text / source ref in the summary
        result = build_unsupported_claim_checks(db)
        blob = json.dumps(result, default=str)
        assert "content_excerpt" not in blob and "text_redacted" not in blob
        assert "source_ref" not in blob.replace("source_ref_hash", "")
        assert not _SECRET_OR_URL.search(blob)
        assert result["read_only"] is True
        assert result["assembles_final_answer"] is False
        assert result["claim_determination_made"] is False
        assert _rows(db) == 0

        # emit_receipt: a guard-clean metadata-only row is persisted
        result2 = build_unsupported_claim_checks(db, emit_receipt=True)
        assert result2["receipt_emitted"] is True
        conn = sqlite3.connect(db)
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0]
            cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({_TABLE})")]
            guard_cols = [
                g
                for g in cols
                if g.endswith(("_persisted", "_performed")) or g.endswith("_bypassed_policy")
            ]
            gsum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_TABLE}"
            ).fetchone()[0]
            assert gsum == 0
        finally:
            conn.close()
        assert n == 1


def test_proof_passes_and_is_clean() -> None:
    proof = build_unsupported_claim_checks_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["unsupported_count"] >= 1
    assert proof["status"] == "blocked"
    assert proof["unsupported_routed_to_review_required"] is True
    assert proof["flagged_routed_to_review_recommended"] is True
    assert proof["claim_determination_made"] is False
    assert proof["receipt_guard_clean"] is True
    assert proof["claim_or_entitlement_decision_performed"] == 0
    assert proof["unsupported_claim_performed"] == 0
    assert proof["read_only_default_no_persist"] is True
    assert proof["no_raw_emitted"] is True
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_unsupported_claim_checks_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "unsupported-claim-checks-proof.json"
    pm = tmp_path / "unsupported-claim-checks-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())
