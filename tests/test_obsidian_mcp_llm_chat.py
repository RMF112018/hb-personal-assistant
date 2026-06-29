"""LLM chat memory tools for the UI-managed Obsidian MCP server."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import llm_chat as llm_chat_module
from hb_assistant.obsidian_mcp import llm_chat_plan_store
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfigPatch, apply_patch, load_config
from hb_assistant.obsidian_mcp.llm_chat import (
    llm_chat_classify,
    llm_chat_ingest,
    llm_chat_link_existing_notes,
    llm_chat_select_template,
    llm_chat_to_note_apply,
    llm_chat_to_note_plan,
    llm_chat_update_topic_memory_apply,
    llm_chat_update_topic_memory_plan,
)
from hb_assistant.obsidian_mcp.llm_chat_classify import classify_session
from hb_assistant.obsidian_mcp.llm_chat_redaction import ingest_text
from hb_assistant.obsidian_mcp.llm_chat_templates import _load_template_body, render_template, select_template
from hb_assistant.obsidian_mcp.mutations import recent_mutations, sha256_file
from hb_assistant.obsidian_mcp.tools import (
    ObsidianMcpToolError,
    missing_required_tools,
    required_tool_names,
    tool_registry,
)

_UNIVERSAL_TEMPLATE = """---
title: "{{conversation_title}}"
type: "llm-session"
---

# {{conversation_title}}

## Executive Summary

{{executive_summary}}

## Commands That Worked

{{commands_that_worked}}

## Root Cause Analysis

{{root_cause_analysis}}
"""

_FATHERHOOD_TEMPLATE = """---
title: "{{conversation_title}}"
type: "llm-session"
---

# {{conversation_title}}

## Summary

{{summary}}

> **Non-professional advice caveat:** Conversation-derived notes only.

## Parenting Context

{{parenting_context}}
"""

_HEALTH_TEMPLATE = """---
title: "{{conversation_title}}"
---

# {{conversation_title}}

## Summary

{{summary}}

> **Health disclaimer:** Not medical advice.
"""

_TRANSCRIPTS = {
    "fatherhood": "# Bedtime routine\n\nParenting my toddler is hard. We decided to start a calm bedtime routine with books.",
    "research": "What is quantum entanglement? I am curious how particles stay correlated across distance.",
    "software": "Python pytest failure with ImportError in src/hb_assistant module. Stack trace shows missing import. Root cause was wrong path.",
    "health": "I have been having sleep issues and anxiety. Doctor mentioned stress management techniques.",
    "purchase": "Should I buy the Dyson vacuum or the cheaper Shark model? Compare price and reviews.",
    "travel": "Planning a family trip to Japan. Need itinerary for Tokyo and Kyoto hotels and flights.",
    "creative": "Brainstorm ideas for a short story about a lighthouse keeper and time travel.",
    "legal": "Reviewing my estate will with attorney. Contract terms for beneficiary updates.",
}


def _write_config(tmp_path: Path, vault: Path) -> Path:
    app_support = tmp_path / "app-support"
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        "\n".join(
            [
                "paths:",
                f"  application_support_root: {app_support.as_posix()!r}",
                f"  obsidian_vault: {vault.as_posix()!r}",
            ]
        ),
        encoding="utf-8",
    )
    return cfg


def _setup_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, enable_writes: bool = False):
    vault = tmp_path / "vault"
    templates = vault / "Templates"
    templates.mkdir(parents=True)
    (templates / "Template - LLM Session.md").write_text(_UNIVERSAL_TEMPLATE, encoding="utf-8")
    (templates / "Template - LLM Session - Fatherhood Parenting.md").write_text(
        _FATHERHOOD_TEMPLATE, encoding="utf-8"
    )
    (templates / "Template - LLM Session - Health Wellness.md").write_text(_HEALTH_TEMPLATE, encoding="utf-8")
    (templates / "Template - LLM Session - Research Curiosity.md").write_text(_UNIVERSAL_TEMPLATE, encoding="utf-8")
    (templates / "Template - LLM Session - Software Troubleshooting.md").write_text(
        _UNIVERSAL_TEMPLATE, encoding="utf-8"
    )
    (templates / "Template - LLM Session - Purchase Decision.md").write_text(_UNIVERSAL_TEMPLATE, encoding="utf-8")
    (templates / "Template - LLM Session - Travel.md").write_text(_UNIVERSAL_TEMPLATE, encoding="utf-8")
    (templates / "Template - LLM Session - Creative Ideation.md").write_text(_UNIVERSAL_TEMPLATE, encoding="utf-8")
    (templates / "Template - LLM Session - Legal Financial Admin.md").write_text(_UNIVERSAL_TEMPLATE, encoding="utf-8")
    (vault / "Topic").mkdir()
    (vault / "Topic" / "Parenting.md").write_text("# Parenting\n\nExisting note.\n", encoding="utf-8")
    (vault / ".obsidian").mkdir()
    (vault / ".hidden.md").write_text("# Hidden\n", encoding="utf-8")

    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    if enable_writes:
        apply_patch(
            ObsidianMcpConfigPatch(
                writes_enabled=True,
                vault_markdown_write_enabled=True,
            )
        )
    return load_config(), vault


@pytest.mark.parametrize(
    ("key", "expected_domain"),
    [
        ("fatherhood", "fatherhood_parenting"),
        ("research", "random_research"),
        ("software", "software_dev"),
        ("health", "personal_health"),
        ("purchase", "shopping_products"),
        ("travel", "travel"),
        ("creative", "creative_ideation"),
        ("legal", "legal_admin"),
    ],
)
def test_classify_domains(key: str, expected_domain: str) -> None:
    result = classify_session(_TRANSCRIPTS[key])
    assert result.primary_domain == expected_domain


def test_ingest_redacts_secrets_and_truncates() -> None:
    text = "token=abc123\nBearer sk-testtoken12345678901234567890\n" + ("x" * 200)
    result = ingest_text(text, max_chars=100)
    assert result.redaction_count >= 1
    assert "[REDACTED]" in result.text
    assert result.truncated is True


def test_template_selection_fatherhood(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    classification = classify_session(_TRANSCRIPTS["fatherhood"])
    selection = select_template(config, classification)
    assert "Fatherhood Parenting" in selection.template_name
    assert selection.target_folder == "LLM Sessions/Fatherhood"
    assert selection.source_tier == "templates_root"


def test_non_dev_sessions_strip_dev_sections() -> None:
    body = render_template(
        _UNIVERSAL_TEMPLATE,
        {
            "conversation_title": "Test",
            "executive_summary": "Summary",
            "commands_that_worked": "none",
            "root_cause_analysis": "none",
        },
        strip_dev_sections=True,
    )
    assert "Commands That Worked" not in body
    assert "Root Cause Analysis" not in body


def test_health_template_caveat_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    from hb_assistant.obsidian_mcp.llm_chat_extract import extract_memory

    classification = classify_session(_TRANSCRIPTS["health"])
    extraction = extract_memory(_TRANSCRIPTS["health"], classification)
    selection = select_template(config, classification)
    from hb_assistant.obsidian_mcp.llm_chat_templates import render_session_note

    body = render_session_note(
        config,
        plan_id="llm_chat_test",
        classification=classification,
        extraction=extraction,
        selection=selection,
        source={"platform": "test", "model": "test"},
        related_notes=[],
        redaction_summary="none",
        classification_summary="health",
    )
    assert "Health disclaimer" in body or "not medical advice" in body.lower()


def test_plan_generation_no_vault_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, vault = _setup_vault(tmp_path, monkeypatch)
    before = list(vault.rglob("*.md"))
    plan = llm_chat_to_note_plan(config, transcript=_TRANSCRIPTS["fatherhood"])
    after = list(vault.rglob("*.md"))
    assert len(before) == len(after)
    assert plan["plan_id"].startswith("llm_chat_")
    stored = llm_chat_plan_store.load_plan(plan["plan_id"])
    assert stored is not None
    assert stored["actions"][0]["payload"]


def test_apply_creates_note_and_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, vault = _setup_vault(tmp_path, monkeypatch, enable_writes=True)
    plan = llm_chat_to_note_plan(config, transcript=_TRANSCRIPTS["research"])
    result = llm_chat_to_note_apply(config, plan_id=plan["plan_id"])
    assert result["counts"]["applied"] == 1
    target = plan["target_path"]
    assert (vault / target).exists()
    receipt = llm_chat_plan_store.load_receipt(plan["plan_id"])
    assert receipt is not None
    mutations = recent_mutations(5)
    assert any(m.get("plan_id") == plan["plan_id"] for m in mutations)


def test_unknown_plan_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch, enable_writes=True)
    with pytest.raises(ObsidianMcpToolError, match="unknown_plan"):
        llm_chat_to_note_apply(config, plan_id="llm_chat_invalid")


def test_stale_sha_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, vault = _setup_vault(tmp_path, monkeypatch, enable_writes=True)
    topic = vault / "Topic" / "Parenting.md"
    plan = llm_chat_update_topic_memory_plan(
        config,
        target_path="Topic/Parenting.md",
        transcript=_TRANSCRIPTS["fatherhood"],
    )
    topic.write_text("# Parenting\n\nChanged externally.\n", encoding="utf-8")
    result = llm_chat_update_topic_memory_apply(config, plan_id=plan["plan_id"])
    assert result["counts"]["failed"] == 1
    assert result["failed"][0]["reason"] == "sha256_mismatch"


def test_topic_memory_update_with_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, vault = _setup_vault(tmp_path, monkeypatch, enable_writes=True)
    topic = vault / "Topic" / "Parenting.md"
    old_sha = sha256_file(topic)
    plan = llm_chat_update_topic_memory_plan(
        config,
        target_path="Topic/Parenting.md",
        transcript=_TRANSCRIPTS["fatherhood"],
    )
    result = llm_chat_update_topic_memory_apply(config, plan_id=plan["plan_id"])
    assert result["counts"]["applied"] == 1
    assert sha256_file(topic) != old_sha
    assert "LLM Memory Update" in topic.read_text(encoding="utf-8")


def test_hidden_path_blocked_in_plan_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    with pytest.raises(ObsidianMcpToolError, match="protected_path_blocked"):
        llm_chat_update_topic_memory_plan(
            config,
            target_path=".hidden.md",
            transcript=_TRANSCRIPTS["fatherhood"],
        )


def test_tool_registry_includes_llm_chat_tools() -> None:
    names = {tool["name"] for tool in tool_registry()}
    for tool_name in required_tool_names():
        assert tool_name in names
    assert not missing_required_tools()
    assert len(tool_registry()) >= len(required_tool_names())


def test_llm_chat_ingest_no_persist_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    result = llm_chat_ingest(config, transcript="Bearer secret-token-1234567890")
    assert result["redaction_count"] >= 1
    assert result["persist_raw_transcript"] is False


def test_software_template_selected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    result = llm_chat_select_template(config, transcript=_TRANSCRIPTS["software"])
    assert "Software Troubleshooting" in result["template_selection"]["template_name"]


def test_fatherhood_plan_no_dev_sections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    plan = llm_chat_to_note_plan(config, transcript=_TRANSCRIPTS["fatherhood"])
    stored = llm_chat_plan_store.load_plan(plan["plan_id"])
    body = stored["actions"][0]["payload"]
    assert "Root Cause Analysis" not in body
    assert "Patch Plan" not in body


def test_link_existing_notes_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, vault = _setup_vault(tmp_path, monkeypatch)
    before = list(vault.rglob("*.md"))
    llm_chat_link_existing_notes(config, transcript=_TRANSCRIPTS["fatherhood"])
    after = list(vault.rglob("*.md"))
    assert len(before) == len(after)


def test_classify_endpoint_wrapper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    result = llm_chat_classify(config, transcript=_TRANSCRIPTS["travel"])
    assert result["classification"]["primary_domain"] == "travel"


def test_transcript_text_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    a = llm_chat_classify(config, transcript=_TRANSCRIPTS["fatherhood"])
    b = llm_chat_classify(config, transcript_text=_TRANSCRIPTS["fatherhood"])
    assert a["classification"]["primary_domain"] == b["classification"]["primary_domain"]


def test_approved_actions_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, vault = _setup_vault(tmp_path, monkeypatch, enable_writes=True)
    plan = llm_chat_to_note_plan(config, transcript=_TRANSCRIPTS["research"])
    result = llm_chat_to_note_apply(config, plan_id=plan["plan_id"], approved_actions=["create_session_note"])
    assert result["counts"]["applied"] == 1
    assert (vault / plan["target_path"]).exists()


def test_plan_public_schema_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    plan = llm_chat_to_note_plan(
        config,
        transcript_text=_TRANSCRIPTS["fatherhood"],
        conversation_title="Custom Bedtime Title",
        conversation_date="2026-01-15",
        target_folder="LLM Sessions/Custom",
        topic_domain="fatherhood_parenting",
        source_platform="grok",
        source_model="grok-3",
        project_hint="evening routine",
    )
    assert plan["plan_id"].startswith("llm_chat_")
    assert plan["target_path"].startswith("LLM Sessions/Custom/")
    stored = llm_chat_plan_store.load_plan(plan["plan_id"])
    assert "Custom Bedtime Title" in stored["actions"][0]["payload"]
    assert stored["source"]["platform"] == "grok"


def test_template_lookup_llm_chat_subdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    tier1 = vault / "Templates" / "LLM Chat"
    tier1.mkdir(parents=True)
    (tier1 / "Template - LLM Session.md").write_text("TIER1_MARKER\n", encoding="utf-8")
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    config = load_config()
    body, rel, tier = _load_template_body(config, "Template - LLM Session.md")
    assert tier == "llm_chat_subdir"
    assert "TIER1_MARKER" in body
    assert rel.startswith("Templates/LLM Chat/")


def test_template_lookup_flat_templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    templates = vault / "Templates"
    templates.mkdir(parents=True)
    (templates / "Template - LLM Session.md").write_text("TIER2_MARKER\n", encoding="utf-8")
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    config = load_config()
    body, rel, tier = _load_template_body(config, "Template - LLM Session.md")
    assert tier == "templates_root"
    assert "TIER2_MARKER" in body
    assert rel.startswith("Templates/")


def test_template_lookup_internal_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    config = load_config()
    body, rel, tier = _load_template_body(config, "Template - LLM Session.md")
    assert tier == "internal"
    assert "Executive Summary" in body


def test_required_tool_readiness() -> None:
    assert not missing_required_tools()
    registered = {t["name"] for t in tool_registry()}
    assert required_tool_names().issubset(registered)


def test_research_no_dev_sections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    plan = llm_chat_to_note_plan(config, transcript=_TRANSCRIPTS["research"])
    body = llm_chat_plan_store.load_plan(plan["plan_id"])["actions"][0]["payload"]
    assert "Root Cause Analysis" not in body
    assert "Commands That Worked" not in body
    assert "Patch Plan" not in body


def test_apply_rejects_arbitrary_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch, enable_writes=True)
    plan = llm_chat_to_note_plan(config, transcript=_TRANSCRIPTS["research"])
    with pytest.raises(ObsidianMcpToolError) as exc_info:
        llm_chat_to_note_apply(config, plan_id=plan["plan_id"], content="# injected")
    assert exc_info.value.code == "unknown_argument"
    with pytest.raises(ObsidianMcpToolError) as exc_info2:
        llm_chat_to_note_apply(config, plan_id=plan["plan_id"], payload="bad")
    assert exc_info2.value.code == "unknown_argument"


def test_plan_skips_link_search_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    calls: list[dict[str, object]] = []

    def _track(*_args: object, **_kwargs: object) -> dict[str, object]:
        calls.append(_kwargs)
        return {"suggested_links": ["Topic/Parenting.md"], "query": "test"}

    monkeypatch.setattr(llm_chat_module, "llm_chat_link_existing_notes", _track)
    plan = llm_chat_to_note_plan(config, transcript=_TRANSCRIPTS["fatherhood"])
    assert calls == []
    assert plan["candidate_links"] == []


def test_plan_returns_quickly_for_short_transcript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    started = time.monotonic()
    llm_chat_to_note_plan(config, transcript=_TRANSCRIPTS["fatherhood"])
    assert time.monotonic() - started < 2.0


def test_plan_candidate_links_empty_when_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)
    plan = llm_chat_to_note_plan(config, transcript=_TRANSCRIPTS["research"])
    assert plan["candidate_links"] == []


def test_plan_opt_in_link_existing_notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)

    def _fake_link(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {"suggested_links": ["Topic/Parenting.md"], "query": "fatherhood parenting", "warnings": []}

    monkeypatch.setattr(llm_chat_module, "llm_chat_link_existing_notes", _fake_link)
    plan = llm_chat_to_note_plan(
        config,
        transcript=_TRANSCRIPTS["fatherhood"],
        link_existing_notes=True,
    )
    assert "Topic/Parenting.md" in plan["candidate_links"]
    assert "Topic/Parenting.md" in plan["related_notes"]


def test_plan_link_search_failure_non_fatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _vault = _setup_vault(tmp_path, monkeypatch)

    def _boom(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise OSError("disk read failed")

    monkeypatch.setattr(llm_chat_module, "llm_chat_link_existing_notes", _boom)
    plan = llm_chat_to_note_plan(
        config,
        transcript=_TRANSCRIPTS["fatherhood"],
        link_existing_notes=True,
    )
    assert plan["plan_id"].startswith("llm_chat_")
    assert "related_note_search_failed" in plan["warnings"]
    assert plan["candidate_links"] == []
