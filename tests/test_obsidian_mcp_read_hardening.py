"""Read/traversal hardening for the UI-managed Obsidian MCP base tools."""

# ruff: noqa: I001,E402

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import (
    ObsidianMcpConfigPatch,
    apply_patch,
    load_config,
)
from hb_assistant.obsidian_mcp.mutations import (
    create_note,
    recent_mutations,
    recent_read_receipts,
    record_read_receipt,
)
from hb_assistant.obsidian_mcp.tools import (
    ObsidianMcpToolError,
    list_directory,
    read_file,
    search_vault,
)


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


def _setup(tmp_path, monkeypatch, *, enable_writes=False, operator_inspection=False):
    vault = tmp_path / "vault"
    # Protected/system dirs (always blocked, even for a local operator).
    for protected in (".git", ".obsidian", ".venv", ".smart-env"):
        (vault / protected).mkdir(parents=True)
        (vault / protected / "data.md").write_text("# sys\n\nconduit secret\n", encoding="utf-8")
    # Hidden (dot) paths that are NOT in the protected set.
    (vault / ".archive").mkdir(parents=True)
    (vault / ".archive" / "Hidden.md").write_text("# Hidden\n\nconduit archived\n", encoding="utf-8")
    (vault / ".secret.md").write_text("# Secret\n\nconduit hidden\n", encoding="utf-8")
    # A normal note.
    (vault / "Notes").mkdir()
    (vault / "Notes" / "Public.md").write_text("# Public\n\nconduit public\n", encoding="utf-8")

    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    patch: dict[str, bool] = {}
    if enable_writes:
        patch.update(writes_enabled=True, vault_markdown_write_enabled=True)
    if operator_inspection:
        patch.update(curation_operator_hidden_inspection=True)
    if patch:
        apply_patch(ObsidianMcpConfigPatch(**patch))
    return load_config(), vault


# ---------------------------------------------------------------------------
# list_directory
# ---------------------------------------------------------------------------
def test_oauth_list_directory_hides_hidden_and_protected(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = list_directory(config, path="", recursive=True, extensions=["md"], operator_mode=False)
    paths = {f["path"] for f in result["files"]}
    assert "Notes/Public.md" in paths
    for path in paths:
        assert not any(seg.startswith(".") for seg in path.split("/")), path


def test_operator_with_optin_can_see_hidden_but_not_protected(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch, operator_inspection=True)
    result = list_directory(config, path="", recursive=True, extensions=["md"], operator_mode=True)
    paths = {f["path"] for f in result["files"]}
    assert ".archive/Hidden.md" in paths  # hidden, not protected → visible to operator
    assert ".secret.md" in paths
    assert not any(p.startswith((".git", ".obsidian", ".venv", ".smart-env")) for p in paths)


def test_list_directory_rejects_protected_scope(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    with pytest.raises(ObsidianMcpToolError) as exc:
        list_directory(config, path=".obsidian", recursive=True, operator_mode=False)
    assert exc.value.code == "protected_path_blocked"


# ---------------------------------------------------------------------------
# search_vault
# ---------------------------------------------------------------------------
def test_oauth_search_excludes_hidden_and_protected(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = search_vault(config, query="conduit", operator_mode=False)
    paths = {r["path"] for r in result["results"]}
    assert paths == {"Notes/Public.md"}


def test_operator_search_includes_hidden_with_optin(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch, operator_inspection=True)
    result = search_vault(config, query="conduit", operator_mode=True)
    paths = {r["path"] for r in result["results"]}
    assert "Notes/Public.md" in paths
    assert ".secret.md" in paths
    assert not any(p.startswith((".git", ".obsidian", ".venv", ".smart-env")) for p in paths)


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------
def test_oauth_read_file_blocks_hidden_and_protected(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    for path in (".secret.md", ".git/data.md", ".archive/Hidden.md"):
        with pytest.raises(ObsidianMcpToolError) as exc:
            read_file(config, path=path, operator_mode=False)
        assert exc.value.code == "protected_path_blocked", path
    # A normal note still reads.
    assert "conduit" in read_file(config, path="Notes/Public.md", operator_mode=False)["content"]


def test_operator_read_file_allows_hidden_not_protected(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch, operator_inspection=True)
    assert "conduit" in read_file(config, path=".secret.md", operator_mode=True)["content"]
    with pytest.raises(ObsidianMcpToolError) as exc:
        read_file(config, path=".git/data.md", operator_mode=True)
    assert exc.value.code == "protected_path_blocked"


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------
def test_read_receipt_recorded(tmp_path, monkeypatch):
    _config, _vault = _setup(tmp_path, monkeypatch)
    record_read_receipt(
        tool_name="vault_email_inventory",
        scope="Work/Email",
        principal_kind="oauth",
        file_count=3,
        truncated=False,
    )
    receipts = recent_read_receipts(5)
    assert receipts and receipts[-1]["tool_name"] == "vault_email_inventory"
    assert receipts[-1]["principal_kind"] == "oauth"


def test_mutation_receipt_carries_tool_and_principal(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch, enable_writes=True)
    create_note(
        config,
        path="Notes/New.md",
        content="# New\n\nbody\n",
        caller_surface="mcp",
        tool_name="create_note",
        principal_kind="oauth",
    )
    last = recent_mutations(1)[-1]
    assert last["tool_name"] == "create_note"
    assert last["principal_kind"] == "oauth"
