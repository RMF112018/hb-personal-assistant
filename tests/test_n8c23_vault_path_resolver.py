"""N8C-23 — vault path resolver (routing into existing folders; no new top-level taxonomy)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.vault_path_resolver import (
    EXISTING_TOP_LEVEL_FOLDERS,
    resolve_relative_path,
    resolve_write_path,
)
from tests.n8c23_helpers import make_env


@pytest.mark.parametrize("atype,domain,top", [
    ("decision", "work", "Work"),
    ("decision", "home", "Home"),
    ("open_loop", "work", "Work"),
    ("preference", "home", "Home"),
    ("architecture_note", "work", "Work"),
    ("answer_draft", "work", "AI Outputs"),
    ("source_card_annotation", "shared", "Source Notes"),
    ("session_note", "work", "00 Inbox"),
])
def test_routes_into_existing_top_level_folders(atype, domain, top) -> None:
    r = resolve_relative_path(artifact_type=atype, domain=domain, canonical_id="DEC-20260708-ABC123", title="A Title")
    assert r.resolved_relative_path.split("/", 1)[0] == top
    assert top in EXISTING_TOP_LEVEL_FOLDERS
    assert r.filename.startswith("DEC-20260708-ABC123 - ") and r.filename.endswith(".md")


def test_override_rejects_new_top_level_and_traversal() -> None:
    with pytest.raises(ValueError, match="override_introduces_new_top_level_folder"):
        resolve_relative_path(artifact_type="decision", domain="work", canonical_id="X", title="t",
                              operator_override_path="Second Brain/Canonical/x.md")
    with pytest.raises(ValueError, match="unsafe_override_path"):
        resolve_relative_path(artifact_type="decision", domain="work", canonical_id="X", title="t",
                              operator_override_path="../escape.md")


def test_resolve_write_path_blocks_unsafe(tmp_path: Path) -> None:
    cfg = make_env(tmp_path)["config"]
    from hb_assistant.nas_mcp.obsidian_config import obsidian_config_from_nas
    ob = obsidian_config_from_nas(cfg)
    good = resolve_relative_path(artifact_type="decision", domain="work", canonical_id="DEC-1", title="ok")
    meta = resolve_write_path(ob, good)
    assert meta["resolved_relative_path"].startswith("Work/03 Decisions/")
    # a hidden/protected path is blocked
    from hb_assistant.obsidian_mcp.vault_path_resolver import ResolvedVaultPath
    bad = ResolvedVaultPath(".obsidian/x.md", ".obsidian", "x.md", ())
    with pytest.raises(ValueError):
        resolve_write_path(ob, bad)
