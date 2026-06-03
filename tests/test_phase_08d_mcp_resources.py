"""Phase 08D Prompt 07 — safe MCP resources.

Proves the five read-only resources are generated from approved workflows only, return a
bounded structured payload with freshness + policy posture, fail closed on an unknown URI,
leak no raw fields, and that the resource-registry snapshot persists guard-clean.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.mcp import (
    build_mcp_resources_proof,
    load_resources,
    read_all_resources,
    read_resource,
)
from hb_assistant.construction.second_brain.mcp.proof import (
    _FORBIDDEN_RESULT_FIELDS,
    _collect_keys,
)
from hb_assistant.construction.second_brain.mcp.resources import snapshot_resource_registry

_URIS = {
    "hb://status/system",
    "hb://brief/today",
    "hb://review/load",
    "hb://research/latest",
    "hb://validation/latest",
}
_NAMES = {
    "hb://status/system": "mcp_status_resource",
    "hb://brief/today": "mcp_today_brief_resource",
    "hb://review/load": "mcp_review_load_resource",
    "hb://research/latest": "mcp_latest_research_resource",
    "hb://validation/latest": "mcp_latest_validation_resource",
}


def test_registry_lists_the_five_contract_resources() -> None:
    registry = load_resources()
    assert {r["uri"] for r in registry} == _URIS
    assert len(registry) == 5


def test_each_resource_returns_bounded_approved_workflow_payload() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "r.db")
        for res in read_all_resources(db_path=db):
            uri = res["uri"]
            assert res["resource_name"] == _NAMES[uri]
            assert res["source"]
            assert isinstance(res["content"], list)
            assert isinstance(res["freshness"], dict)
            assert res["freshness"]["basis"] == "computed_live"
            assert res["policy_posture"]["read_only"] is True
            assert not (set(_FORBIDDEN_RESULT_FIELDS) & _collect_keys(res)), f"{uri} leaked a field"


def test_unknown_uri_fails_closed() -> None:
    res = read_resource("hb://secrets/everything")
    assert res["status"] == "denied"
    assert res["reason_code"] == "resource_not_allowed"
    assert res["fail_closed"] is True


def test_resource_registry_snapshot_is_guard_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "r.db")
        snapshot_id = snapshot_resource_registry(db_path=db, persist=True)
        assert snapshot_id
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT resource_count, registry_hash, external_writeback_performed, "
            "raw_prompt_persisted FROM second_brain_mcp_resource_registry_snapshots"
        ).fetchone()
        count, reg_hash, ext_wb, raw_prompt = row
        assert count == 5
        assert reg_hash and (ext_wb, raw_prompt) == (0, 0)


def test_resources_proof_passes() -> None:
    with tempfile.TemporaryDirectory() as td:
        proof = build_mcp_resources_proof(evidence_dir=td, write_evidence=True)
        assert proof["proof_passed"] is True
        assert proof["resource_count"] == 5
        assert proof["unknown_uri_fail_closed"] is True
        assert proof["registry_snapshot"]["all_guard_columns_zero"] is True
        assert (Path(td) / "mcp-resource-contract-proof.json").exists()
