"""Build ObsidianMcpConfig for NAS MCP from NAS config."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig

from .config import NasMcpConfig


@dataclass(frozen=True)
class NasObsidianConfig:
    vault_root: Path
    backup_dir: Path
    support_dir: Path
    writes_enabled: bool = True
    vault_markdown_write_enabled: bool = True
    summarization_backend: str = "deterministic"


def obsidian_config_from_nas(config: NasMcpConfig) -> ObsidianMcpConfig:
    ob = config.obsidian
    if os.environ.get("HB_OBSIDIAN_MCP_SUPPORT_DIR", "").strip():
        support = Path(os.environ["HB_OBSIDIAN_MCP_SUPPORT_DIR"])
    else:
        support = ob.support_dir
    support.mkdir(parents=True, exist_ok=True)
    ob.backup_dir.mkdir(parents=True, exist_ok=True)
    return ObsidianMcpConfig(
        enabled=True,
        vault_root=str(ob.vault_root),
        writes_enabled=ob.writes_enabled,
        vault_markdown_write_enabled=ob.vault_markdown_write_enabled,
        allowed_write_file_types=["md"],
        summarization_backend=ob.summarization_backend,
        backup_before_replace=True,
        write_requires_expected_sha256=True,
        create_parent_dirs_enabled=True,
    )


def apply_obsidian_support_env(config: NasMcpConfig) -> None:
    os.environ.setdefault("HB_OBSIDIAN_MCP_SUPPORT_DIR", str(config.obsidian.support_dir))
