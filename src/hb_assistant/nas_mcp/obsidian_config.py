"""Build ObsidianMcpConfig for NAS MCP from NAS config."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig

from .config import NasMcpConfig

# roots keys that are indexable source trees (not the vault/outputs/analytics mounts). The index was
# built with the `syn-<key>` convention, so a live read of syn-work must resolve to the work mount.
_SOURCE_TREE_ROOT_KEYS = ("home", "work")


def resolve_external_sources(config: NasMcpConfig) -> list[ExternalSourceRoot]:
    """Map indexed source-root keys → mounted paths so ``prefer_live`` reads resolve instead of
    degrading to indexed excerpts. Explicit ``obsidian.external_sources`` config wins; otherwise derive
    a ``syn-<roots-key>`` entry for each mounted home/work source tree (sensitive=False → live enabled)."""
    ob = config.obsidian
    if ob is not None and ob.external_sources:
        out: list[ExternalSourceRoot] = []
        for e in ob.external_sources:
            try:
                out.append(ExternalSourceRoot(source_root_key=e["source_root_key"], path=e["path"],
                                              enabled=True, sensitive=bool(e.get("sensitive", False))))
            except Exception:  # noqa: BLE001 — a malformed entry must not break config load
                continue
        return out
    derived: list[ExternalSourceRoot] = []
    for key in _SOURCE_TREE_ROOT_KEYS:
        spec = config.roots.get(key)
        if spec is None:
            continue
        try:
            derived.append(ExternalSourceRoot(source_root_key=f"syn-{key}", path=str(spec.mount),
                                              enabled=True, sensitive=False))
        except Exception:  # noqa: BLE001
            continue
    return derived


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
        external_sources=resolve_external_sources(config),
    )


def apply_obsidian_support_env(config: NasMcpConfig) -> None:
    os.environ.setdefault("HB_OBSIDIAN_MCP_SUPPORT_DIR", str(config.obsidian.support_dir))
