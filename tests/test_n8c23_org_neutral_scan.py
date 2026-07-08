"""N8C-23 amendment #7 — organization-neutral scan over generated content + new docs.

No new *user-facing* card/tag/path/manifest/receipt/doc/template/generated content may
contain employer-specific names or abbreviations. Pre-existing legacy identifiers elsewhere
in the repo are out of scope; this scan covers only what N8C-23 generates and documents.
"""

from __future__ import annotations

import re
from pathlib import Path

from hb_assistant.obsidian_mcp.artifact_card_renderer import (
    render_artifact_card,
    render_canonical_manifest_md,
    render_receipt_card,
)
from hb_assistant.obsidian_mcp.client_tool_manifest import build_manifest, render_manifest_md

_REPO = Path(__file__).resolve().parents[1]

# Employer-specific tokens that must never appear in newly generated N8C-23 content or docs.
_ORG_TOKENS = (
    "tropical world", "tropical", "twn", "procore", "vankirk", "van kirk",
    "hb intel", "hbc", "harbor", "harbour",
)


def _assert_neutral(text: str, where: str) -> None:
    low = text.lower()
    hits = [tok for tok in _ORG_TOKENS if re.search(rf"\b{re.escape(tok)}\b", low)]
    assert not hits, f"organization-specific token(s) {hits} found in {where}"


def _neutral_card() -> str:
    card, _ = render_artifact_card(
        {"canonical_id": "DEC-20260708-ABC", "artifact_type": "decision", "title": "Adopt staged promotion",
         "summary": "The team will stage all canonical writes behind operator approval.",
         "body_markdown": "Rationale: keep the server as records authority.",
         "domain": "work", "source_client": "chatgpt", "source_session_id": "SESSION-20260708-001",
         "status": "canonical", "version": 1},
        promotion_receipt_id="PROMO-20260708-001", related_artifacts=["PREF-20260708-001"],
        review_history=[{"decision": "approve", "created_at": "t", "review_notes": ""}],
        future_use_guidance="Reference before adding any new write surface.")
    return card


def test_generated_cards_manifests_receipts_are_org_neutral() -> None:
    _assert_neutral(_neutral_card(), "artifact card")
    _assert_neutral(
        render_receipt_card({"promotion_receipt_id": "PROMO-1", "promotion_bundle_id": "PROMOB-1",
                             "session_id": "SESSION-1", "status": "promoted", "created_count": 2,
                             "validation_hash": "h", "created_at": "t"},
                            created_paths=["Work/03 Decisions/DEC-1 - x.md"]),
        "receipt card")
    _assert_neutral(
        render_canonical_manifest_md([{"canonical_id": "DEC-1", "artifact_type": "decision",
                                       "status": "canonical", "domain": "work", "vault_path": "p"}],
                                     generated_at="t", runtime_commit="vX"),
        "canonical manifest")


def test_client_tool_operating_manifest_is_org_neutral() -> None:
    idx = {n: {} for n in ("pa_session_capture_stage", "pa_artifact_promotion_apply",
                           "pa_tool_manifest_get", "hb_mcp_status")}
    md = render_manifest_md(build_manifest(idx, runtime_commit="vT", now="2026-07-08T00:00:00+00:00"))
    _assert_neutral(md, "client tool operating manifest")


def test_new_n8c23_docs_are_org_neutral() -> None:
    docs = sorted((_REPO / "docs" / "architecture").glob("n8c-23-*.md")) + \
        sorted((_REPO / "docs" / "architecture").glob("canonical-artifact-promotion-workflow.md")) + \
        sorted((_REPO / "docs" / "architecture").glob("obsidian-card-materialization.md")) + \
        sorted((_REPO / "docs" / "architecture").glob("client-tool-operating-manifest.md"))
    # Docs are written as part of this phase; scan whichever exist.
    for doc in docs:
        _assert_neutral(doc.read_text(), str(doc.relative_to(_REPO)))


def test_new_source_modules_have_no_org_tokens_in_string_literals() -> None:
    for mod in ("obsidian_mcp/vault_path_resolver.py", "obsidian_mcp/artifact_card_renderer.py",
                "obsidian_mcp/client_tool_manifest.py"):
        _assert_neutral((_REPO / "src" / "hb_assistant" / mod).read_text(), mod)
