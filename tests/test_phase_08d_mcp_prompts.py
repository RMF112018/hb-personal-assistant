"""Phase 08D Prompt 08 — reusable MCP prompts.

Proves the five prompt templates route only through allowed tools, carry the advisory /
source-linked / review-controlled posture + no-determination + no-policy-bypass guidance,
leak no raw fields, fail closed on an unknown name, and that the prompt-registry snapshot
persists guard-clean.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.mcp import (
    build_mcp_prompts_proof,
    load_allowed_tools,
    load_prompts,
    render_all_prompts,
    render_prompt,
)
from hb_assistant.construction.second_brain.mcp.prompts import snapshot_prompt_registry
from hb_assistant.construction.second_brain.mcp.proof import (
    _FORBIDDEN_RESULT_FIELDS,
    _collect_keys,
)

_NAMES = {
    "review_today_brief",
    "ask_project_question",
    "prepare_for_meeting",
    "review_memory_candidates",
    "explain_review_load",
}


def test_registry_lists_the_five_contract_prompts() -> None:
    registry = load_prompts()
    assert {p["name"] for p in registry} == _NAMES
    assert len(registry) == 5


def test_every_prompt_routes_through_allowed_tools_only() -> None:
    allowed = set(load_allowed_tools())
    for p in load_prompts():
        assert p["routes_through"], f"{p['name']} routes through nothing"
        assert all(t in allowed for t in p["routes_through"]), f"{p['name']} off-allowlist"


def test_each_prompt_carries_posture_and_no_forbidden_fields() -> None:
    for rendered in render_all_prompts():
        text = " ".join(m["content"] for m in rendered["messages"]).lower()
        assert "advisory" in text
        assert "source-linked" in text
        assert "review-controlled" in text
        assert "do not bypass phase 08a/08b/08c policy" in text
        assert "do not make final financial" in text
        assert not (set(_FORBIDDEN_RESULT_FIELDS) & _collect_keys(rendered))


def test_argument_substitution_does_not_leak_placeholders_for_provided_args() -> None:
    rendered = render_prompt("ask_project_question", {"question": "what is overdue", "project_key": "X"})
    body = rendered["messages"][1]["content"]
    assert "what is overdue" in body
    assert "X" in body


def test_unknown_prompt_fails_closed() -> None:
    rendered = render_prompt("exfiltrate_all", {})
    assert rendered["status"] == "denied"
    assert rendered["reason_code"] == "prompt_not_allowed"
    assert rendered["fail_closed"] is True


def test_prompt_registry_snapshot_is_guard_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "p.db")
        snapshot_id = snapshot_prompt_registry(db_path=db, persist=True)
        assert snapshot_id
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT prompt_count, registry_hash, external_writeback_performed, raw_prompt_persisted "
            "FROM second_brain_mcp_prompt_registry_snapshots"
        ).fetchone()
        count, reg_hash, ext_wb, raw_prompt = row
        assert count == 5
        assert reg_hash and (ext_wb, raw_prompt) == (0, 0)


def test_prompts_proof_passes() -> None:
    with tempfile.TemporaryDirectory() as td:
        proof = build_mcp_prompts_proof(evidence_dir=td, write_evidence=True)
        assert proof["proof_passed"] is True
        assert proof["prompt_count"] == 5
        assert proof["unknown_prompt_fail_closed"] is True
        assert proof["registry_snapshot"]["all_guard_columns_zero"] is True
        assert (Path(td) / "mcp-prompt-contract-proof.json").exists()
