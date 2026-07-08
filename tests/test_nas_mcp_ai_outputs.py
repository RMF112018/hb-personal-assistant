"""N8C-1: AI Outputs cards use neutral frontmatter, and existing (legacy) cards keep working.

The single sanctioned remote write (``ai_outputs_card_upsert``) must stamp domain-neutral
provenance (``managed_by: personal_assistant`` / ``note_type: ai_output``) on new cards while
preserving every safety property, and must NOT break cards already on disk that carry the old
``hb_managed: ai_outputs_card`` frontmatter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.naming import sanitize_domain
from hb_assistant.nas_mcp.ai_outputs import AiOutputsError, _render_card, normalize_source_client
from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec


def _cfg(tmp_path: Path) -> NasMcpConfig:
    vault = tmp_path / "vault"
    outputs = tmp_path / "outputs"
    for p in (vault, outputs):
        p.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    return NasMcpConfig(
        db_path=tmp_path / "db.sqlite",
        audit_dir=audit,
        roots={
            "vault": RootSpec("vault", vault, "read_write"),
            "outputs": RootSpec("outputs", outputs, "read_write"),
        },
        obsidian=NasObsidianConfig(
            vault_root=vault,
            backup_dir=audit / "obsidian-backups",
            support_dir=audit / "obsidian-support",
        ),
    )


def _broker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[NasMcpBroker, NasMcpConfig]:
    monkeypatch.setenv("HB_MCP_PROFILE", "remote_cloudflare")
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("HB_OBSIDIAN_MCP_SUPPORT_DIR", str(cfg.obsidian.support_dir))
    return NasMcpBroker(cfg), cfg


def test_source_client_normalizes_model_variants() -> None:
    # A connected client may send a model/variant string; accept its family, reject an unknown family.
    assert normalize_source_client("chatgpt-gpt-5.5-thinking") == "chatgpt"
    assert normalize_source_client("claude/opus") == "claude"
    assert normalize_source_client("grok:2") == "grok"
    assert normalize_source_client("CHATGPT") == "chatgpt"
    assert normalize_source_client(None) == "unknown"
    assert normalize_source_client("") == "unknown"
    for bad in ("bogus-model", "gemini", "openai"):
        with pytest.raises(AiOutputsError):
            normalize_source_client(bad)


def test_render_card_frontmatter_is_neutral() -> None:
    card = _render_card("Weekly Notes", ["home", "admin", "home"], "chatgpt", "Body text.", "home")
    front = card.split("\n---\n", 1)[0]
    assert "managed_by: personal_assistant" in front
    assert "note_type: ai_output" in front
    assert "source_client: chatgpt" in front
    assert "domain: home" in front
    assert "created_via: mcp" in front
    assert "title: Weekly Notes" in front
    # tags are sorted + deduped
    assert "tags: [admin, home]" in front
    # No employer-branded marker is ever written on a new card.
    assert "hb_managed" not in card
    assert "ai_outputs_card" not in card


def test_domain_sanitizer() -> None:
    # Normal labels are lowercased and passed through.
    assert sanitize_domain("Work") == "work"
    assert sanitize_domain("personal_admin") == "personal_admin"
    assert sanitize_domain("home-ownership") == "home-ownership"
    # Empty / None / whitespace collapse to "unknown".
    assert sanitize_domain(None) == "unknown"
    assert sanitize_domain("") == "unknown"
    assert sanitize_domain("   ") == "unknown"
    # Path/traversal/YAML-hostile input is stripped; if nothing safe remains -> "unknown".
    assert sanitize_domain("../../etc") == "etc"      # separators + dots removed
    assert sanitize_domain("../..") == "unknown"      # nothing safe remains
    assert sanitize_domain("a: b\nc") == "abc"        # colon/space/newline removed
    assert "/" not in sanitize_domain("work/home")    # never contains a separator
    # Length-bounded.
    assert len(sanitize_domain("x" * 200)) <= 40


def test_created_card_has_neutral_frontmatter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broker, _ = _broker(tmp_path, monkeypatch)
    res = broker.dispatch(
        "ai_outputs_card_upsert",
        {"title": "Grocery Plan", "body_markdown": "eggs", "source_client": "grok", "mode": "create",
         "domain": "Home"},
    )
    assert res["ok"] is True
    text = (tmp_path / "vault" / "AI Outputs" / "Grocery Plan.md").read_text(encoding="utf-8")
    assert "managed_by: personal_assistant" in text
    assert "note_type: ai_output" in text
    assert "domain: home" in text          # lowercased by the sanitizer
    assert "created_via: mcp" in text
    assert "hb_managed" not in text


def test_domain_is_sanitized_and_path_inert(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A hostile domain value is metadata-only: it coerces to a safe token and never affects the path."""
    broker, _ = _broker(tmp_path, monkeypatch)
    res = broker.dispatch(
        "ai_outputs_card_upsert",
        {"title": "Trip Notes", "body_markdown": "x", "source_client": "claude", "mode": "create",
         "domain": "../../etc/passwd"},
    )
    assert res["ok"] is True
    # Card lands in the locked folder regardless of the domain value.
    assert res["result"]["relative_path"] == "AI Outputs/Trip Notes.md"
    assert not (tmp_path / "etc" / "passwd").exists()
    text = (tmp_path / "vault" / "AI Outputs" / "Trip Notes.md").read_text(encoding="utf-8")
    # Separators/dots stripped -> "etcpasswd"; the value is a single YAML-safe token, no path.
    assert "domain: etcpasswd" in text
    assert "/" not in text.split("domain:", 1)[1].splitlines()[0]

    # A value with nothing safe collapses to "unknown".
    res2 = broker.dispatch(
        "ai_outputs_card_upsert",
        {"title": "Trip Notes 2", "body_markdown": "x", "source_client": "claude", "mode": "create",
         "domain": "///"},
    )
    assert res2["ok"] is True
    text2 = (tmp_path / "vault" / "AI Outputs" / "Trip Notes 2.md").read_text(encoding="utf-8")
    assert "domain: unknown" in text2


def test_append_to_legacy_card_is_not_broken(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A card written by the OLD build (hb_managed frontmatter) can still be appended to."""
    broker, _ = _broker(tmp_path, monkeypatch)
    folder = tmp_path / "vault" / "AI Outputs"
    folder.mkdir(parents=True, exist_ok=True)
    legacy = folder / "Legacy Card.md"
    legacy.write_text(
        "---\ntitle: Legacy Card\ntags: [x]\nsource_client: claude\nhb_managed: ai_outputs_card\n---\n\nold body\n",
        encoding="utf-8",
    )
    res = broker.dispatch(
        "ai_outputs_card_upsert",
        {"title": "Legacy Card", "body_markdown": "new line", "source_client": "claude", "mode": "append"},
    )
    assert res["ok"] is True
    text = legacy.read_text(encoding="utf-8")
    # Existing card is preserved (including its legacy marker — not migrated in this slice) and appended.
    assert "old body" in text and "new line" in text
    assert "hb_managed: ai_outputs_card" in text


def test_update_of_legacy_card_rerenders_neutral(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A full update re-renders the card, so it migrates a legacy card to neutral frontmatter."""
    broker, _ = _broker(tmp_path, monkeypatch)
    from hb_assistant.obsidian_mcp.mutations import sha256_file

    folder = tmp_path / "vault" / "AI Outputs"
    folder.mkdir(parents=True, exist_ok=True)
    legacy = folder / "Migrate Me.md"
    legacy.write_text(
        "---\ntitle: Migrate Me\ntags: [x]\nsource_client: claude\nhb_managed: ai_outputs_card\n---\n\nold\n",
        encoding="utf-8",
    )
    res = broker.dispatch(
        "ai_outputs_card_upsert",
        {"title": "Migrate Me", "body_markdown": "fresh", "source_client": "claude", "mode": "update",
         "expected_sha": sha256_file(legacy)},
    )
    assert res["ok"] is True
    text = legacy.read_text(encoding="utf-8")
    assert "managed_by: personal_assistant" in text
    assert "hb_managed" not in text and "ai_outputs_card" not in text
