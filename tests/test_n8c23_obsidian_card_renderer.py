"""N8C-23 — card / receipt / manifest rendering (frontmatter, tags, backlinks, redaction)."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.artifact_card_renderer import (
    render_artifact_card,
    render_canonical_manifest_md,
    render_receipt_card,
    required_tags,
)


def test_required_tags() -> None:
    tags = required_tags("decision", "chatgpt", "work", "approved")
    assert tags == ["second-brain/canonical", "artifact/decision", "status/approved", "source/chatgpt",
                    "domain/work"]


def test_render_artifact_card_frontmatter_tags_backlinks() -> None:
    card, redacted = render_artifact_card(
        {"canonical_id": "DEC-20260708-ABC", "artifact_type": "decision", "title": "Use staging",
         "summary": "A summary.", "body_markdown": "The decision body.", "domain": "work",
         "source_client": "chatgpt", "source_session_id": "SESSION-20260708-001", "status": "canonical",
         "version": 1},
        promotion_receipt_id="PROMO-20260708-001", related_artifacts=["PREF-20260708-001"],
        review_history=[{"decision": "approve", "created_at": "t", "review_notes": ""}])
    assert "canonical_id: DEC-20260708-ABC" in card
    assert "second-brain/canonical" in card and "artifact/decision" in card
    assert "[[SESSION-20260708-001]]" in card and "[[PREF-20260708-001]]" in card
    assert "[[PROMO-20260708-001]]" in card
    assert redacted is False


def test_render_card_redacts_secrets() -> None:
    card, redacted = render_artifact_card(
        {"canonical_id": "DEC-1", "artifact_type": "decision", "title": "t",
         "body_markdown": "token access_token=SEKRET_VALUE end", "domain": "work", "source_client": "x"},
        promotion_receipt_id="PROMO-1")
    assert redacted is True
    assert "SEKRET_VALUE" not in card and "[REDACTED_TOKEN_FIELD]" in card


def test_render_receipt_and_manifest() -> None:
    rc = render_receipt_card({"promotion_receipt_id": "PROMO-1", "promotion_bundle_id": "PROMOB-1",
                              "session_id": "SESSION-1", "status": "promoted", "created_count": 2,
                              "validation_hash": "h", "created_at": "t"},
                             created_paths=["Work/03 Decisions/DEC-1 - x.md"])
    assert "Promotion Receipt" in rc and "created: 2" in rc
    md = render_canonical_manifest_md([{"canonical_id": "DEC-1", "artifact_type": "decision",
                                        "status": "canonical", "domain": "work", "vault_path": "p"}],
                                      generated_at="t", runtime_commit="vX")
    assert "Canonical Artifact Manifest" in md and "DEC-1" in md
