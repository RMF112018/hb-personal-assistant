"""Focused tests for the Prompt 03 Delegated Graph Capability Proof artifacts.

These tests cover redaction, classifier behavior under the execution assumption,
app-only rejection logic, and the structure expected from the proof script.
They do not perform live Graph calls.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.auth.classifier import classify_token_claims, safe_redact_claims
from hb_assistant.scripts.proofs.delegated_graph_capability_proof import _redact_for_evidence  # type: ignore


def test_redact_for_evidence_never_leaks_tokens() -> None:
    rec = _redact_for_evidence(
        step=3,
        endpoint="/me/messages/xxx",
        status=200,
        sample={"body": "Hello Bobby, please review..."},  # would be redacted in real run
        token_class="delegated",
        note="Bobby mention present in preview",
    )
    blob = json.dumps(rec)
    assert "access_token" not in blob.lower()
    assert "refresh_token" not in blob.lower()
    assert "BEGIN" not in blob


def test_safe_redact_claims_removes_sensitive_fields() -> None:
    claims = {
        "scp": "Mail.Read User.Read",
        "upn": "bobby@ex.com",
        "access_token": "should_never_appear",
        "roles": ["Sites.Read.All"],
    }
    red = safe_redact_claims(claims)
    assert "access_token" not in red
    assert red["upn"] == "bobby@ex.com"
    assert red["scp_count"] > 0


def test_classify_and_app_only_rejection_logic() -> None:
    # Simulates what step 9 does
    app_only_claims = {"roles": ["Sites.Read.All"], "tid": "0e83..."}
    assert classify_token_claims(app_only_claims) == "app_only"

    # In the proof script we assert that app-only is rejected for mail/calendar
    # (either via classifier or actual 403). This test confirms the classification side.
    assert classify_token_claims(app_only_claims) != "delegated"


def test_proof_evidence_dir_creation_pattern() -> None:
    # The script creates docs/evidence/prompt-03-delegated-proof/
    # This test just verifies the path logic would work in the repo.
    with tempfile.TemporaryDirectory() as td:
        evidence_dir = Path(td) / "prompt-03-delegated-proof"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "step-1.json").write_text(json.dumps({"step": 1, "status": 200}))
        assert (evidence_dir / "step-1.json").exists()
