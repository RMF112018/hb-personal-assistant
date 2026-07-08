"""N8C-23 shared vault-write helpers (reuse the atomic mutations engine).

All writes go through ``obsidian_mcp.mutations`` (temp-file + fsync + atomic rename + backup + sha
optimistic-concurrency + mutation receipt) via the same NAS→Obsidian config bridge ``ai_outputs`` uses. Card
writes are markdown-only. The manifest writer narrowly permits ``.json`` ONLY for files under
``99 System/Manifests`` — a control-plane artifact — never a general json write surface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hb_assistant.nas_mcp.obsidian_config import (
    apply_obsidian_support_env,
    obsidian_config_from_nas,
)

from . import mutations
from .vault_path_resolver import EXISTING_TOP_LEVEL_FOLDERS, MANIFESTS_FOLDER

_PRINCIPAL = "operator_approved"


def md_config(nas_config: Any) -> Any:
    apply_obsidian_support_env(nas_config)
    return obsidian_config_from_nas(nas_config)


def _json_manifest_config(nas_config: Any) -> Any:
    """A config that permits ``.json`` writes — used ONLY for the manifests folder, guarded at call sites."""
    return md_config(nas_config).model_copy(update={"allowed_write_file_types": ["md", "json"]})


def _guard_existing_top_level(rel: str) -> None:
    top = rel.split("/", 1)[0]
    if top not in EXISTING_TOP_LEVEL_FOLDERS:
        raise ValueError(f"path_introduces_new_top_level_folder:{top}")


def upsert_note(config: Any, rel: str, content: str, *, tool_name: str) -> dict[str, Any]:
    """Create the note if absent, else overwrite it with the required expected-sha (backup + receipt)."""
    _guard_existing_top_level(rel)
    target = Path(config.vault_root) / rel
    if target.exists():
        expected = mutations.sha256_file(target)
        return mutations.patch_note(config, path=rel, content=content, expected_sha256=expected,
                                    caller_surface="nas_mcp", tool_name=tool_name, principal_kind=_PRINCIPAL)
    return mutations.create_note(config, path=rel, content=content, overwrite=False,
                                 caller_surface="nas_mcp", tool_name=tool_name, principal_kind=_PRINCIPAL)


def create_card(nas_config: Any, rel: str, content: str, *, tool_name: str) -> dict[str, Any]:
    """Create a NEW markdown card (fails closed if it already exists — idempotency is enforced upstream)."""
    _guard_existing_top_level(rel)
    return mutations.create_note(md_config(nas_config), path=rel, content=content, overwrite=False,
                                 caller_surface="nas_mcp", tool_name=tool_name, principal_kind=_PRINCIPAL)


def write_manifest_pair(nas_config: Any, basename: str, md_content: str, json_content: str, *,
                        tool_name: str) -> dict[str, Any]:
    """Upsert ``{basename}.md`` + ``{basename}.json`` under 99 System/Manifests (json permitted only here)."""
    md_rel = f"{MANIFESTS_FOLDER}/{basename}.md"
    json_rel = f"{MANIFESTS_FOLDER}/{basename}.json"
    if not md_rel.startswith(MANIFESTS_FOLDER + "/") or not json_rel.startswith(MANIFESTS_FOLDER + "/"):
        raise ValueError("manifest_write_out_of_folder")
    md_res = upsert_note(md_config(nas_config), md_rel, md_content, tool_name=tool_name)
    json_res = upsert_note(_json_manifest_config(nas_config), json_rel, json_content, tool_name=tool_name)
    return {"md_path": md_res["path"], "json_path": json_res["path"]}
