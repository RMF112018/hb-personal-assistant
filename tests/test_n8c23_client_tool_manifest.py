"""N8C-23 — Client Tool Operating Manifest (build, classify, freshness, staged refresh)."""

from __future__ import annotations

from pathlib import Path

from hb_assistant.obsidian_mcp.client_tool_manifest import (
    ClientToolManifestRepository,
    build_manifest,
    classify_tool,
    render_manifest_md,
)
from tests.n8c23_helpers import make_env


def _index() -> dict:
    idx = {n: {"group": "nav"} for n in ("assistant_search_sources", "assistant_list_decisions")}
    idx.update({n: {} for n in ("pa_session_capture_stage", "pa_artifact_promotion_apply", "pa_tool_manifest_get",
                                "hb_mcp_status", "hb_db_select", "raw_sql", "ai_outputs_card_upsert")})
    return idx


def test_classification() -> None:
    assert classify_tool("pa_artifact_promotion_apply", None) == (
        "canonical_promotion", "canonical_promotion_requires_explicit_approval", "canonical_write")
    assert classify_tool("pa_session_capture_stage", None) == (
        "staged_write", "staged_write_requires_review", "staged_write")
    assert classify_tool("raw_sql", None) == ("blocked_or_deprecated", "blocked", "blocked")
    assert classify_tool("assistant_search_sources", "nav")[2] == "read_only"


def test_build_includes_recipes_replacement_and_negatives() -> None:
    m = build_manifest(_index(), runtime_commit="vT", now="2026-07-08T00:00:00+00:00")
    assert m["tool_count"] == len(_index()) and m["workflow_count"] >= 4 and m["mapping_count"] >= 3
    assert any(r["workflow_name"] == "document_session" for r in m["workflow_recipes"])
    assert m["replacement_map"] and m["negative_instructions"]
    md = render_manifest_md(m)
    assert "Client Tool Operating Manifest" in md and "Do not" in md and "document_session" in md


def test_freshness_detects_missing_and_extra(tmp_path: Path) -> None:
    repo = ClientToolManifestRepository(make_env(tmp_path)["db"])
    m = build_manifest(_index(), runtime_commit="vT", now="2026-07-08T00:00:00+00:00")
    repo.save_manifest(m)
    assert repo.freshness_check(set(_index()))["tool_manifest_stale"] is False
    fr_missing = repo.freshness_check(set(_index()) | {"pa_brand_new"})
    assert fr_missing["tool_manifest_missing_tools"] == ["pa_brand_new"] and fr_missing["tool_manifest_stale"]
    fr_extra = repo.freshness_check(set(_index()) - {"hb_db_select"})
    assert fr_extra["tool_manifest_extra_tools"] == ["hb_db_select"]


def test_freshness_no_active_manifest_is_stale(tmp_path: Path) -> None:
    repo = ClientToolManifestRepository(make_env(tmp_path)["db"])
    fr = repo.freshness_check({"a", "b"})
    assert fr["tool_manifest_stale"] and fr["staleness_state"] == "stale"


def test_staged_refresh_mints_approval_and_is_not_silent(tmp_path: Path) -> None:
    repo = ClientToolManifestRepository(make_env(tmp_path)["db"])
    m = build_manifest(_index(), runtime_commit="vT", now="2026-07-08T00:00:00+00:00", manifest_version=2)
    stg = repo.stage_refresh(m, {"tool_manifest_stale": True})
    assert stg["status"] == "staged" and stg["writes"] is False and stg["operator_approval_id"]
    fetched = repo.get_refresh(stg["refresh_proposal_id"])
    assert fetched["status"] == "staged" and fetched["operator_approval_id"] == stg["operator_approval_id"]
