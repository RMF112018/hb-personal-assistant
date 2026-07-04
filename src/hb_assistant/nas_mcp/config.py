"""NAS MCP configuration (roots, limits, deny patterns)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_DENIED_NAME_PATTERNS = (
    ".enc",
    "msal-token-cache",
    "text-vault.key",
    "text-vault",
    "client_secret",
    "id_token",
    "refresh_token",
    "access_token",
    "private key",
    ".pem",
    ".p12",
)

DEFAULT_DENIED_DIR_SEGMENTS = (
    ".git",
    ".obsidian",
    "auth",
    "security",
    "secrets",
    "procore",
)


DEFAULT_READ_EXTENSIONS = frozenset(
    {"txt", "md", "csv", "json", "yaml", "yml", "pdf", "docx", "xlsx", "xls"}
)
DEFAULT_OUTPUT_WRITE_EXTENSIONS = frozenset({"txt", "md", "csv", "json", "yaml", "yml", "docx", "xlsx"})


@dataclass(frozen=True)
class NasObsidianConfig:
    vault_root: Path
    backup_dir: Path
    support_dir: Path
    writes_enabled: bool = True
    vault_markdown_write_enabled: bool = True
    summarization_backend: str = "deterministic"


@dataclass(frozen=True)
class RootSpec:
    key: str
    mount: Path
    mode: str = "read_only"


@dataclass
class NasMcpConfig:
    db_path: Path
    audit_dir: Path
    roots: dict[str, RootSpec]
    max_excerpt_bytes: int = 16_384
    max_list_entries: int = 100
    max_db_rows: int = 100
    default_db_rows: int = 25
    max_response_bytes: int = 256_000
    max_write_bytes: int = 262_144
    max_output_file_bytes: int = 1_048_576
    read_extensions: frozenset[str] = DEFAULT_READ_EXTENSIONS
    output_write_extensions: frozenset[str] = DEFAULT_OUTPUT_WRITE_EXTENSIONS
    denied_name_patterns: tuple[str, ...] = DEFAULT_DENIED_NAME_PATTERNS
    denied_dir_segments: tuple[str, ...] = DEFAULT_DENIED_DIR_SEGMENTS
    actor: str = "bfetting-via-ssh-launcher"
    obsidian: NasObsidianConfig | None = None

    @classmethod
    def from_env(cls) -> NasMcpConfig:
        config_file = os.environ.get("HB_PA_CONFIG", "/config/hb-pa-config.yml")
        data: dict[str, Any] = {}
        path = Path(config_file)
        if path.is_file():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                data = loaded
        mcp = data.get("mcp") if isinstance(data.get("mcp"), dict) else {}
        return cls.from_mapping(mcp, fallback_db=data)

    @classmethod
    def from_mapping(cls, mcp: dict[str, Any], *, fallback_db: dict[str, Any] | None = None) -> NasMcpConfig:
        fb = fallback_db or {}
        paths = fb.get("paths") if isinstance(fb.get("paths"), dict) else {}
        app_support = Path(
            str(
                mcp.get("app_support_dir")
                or paths.get("application_support_root")
                or os.environ.get("HB_APP_SUPPORT_DIR", "/volume1/personal-assistant/app-support")
            )
        )
        db_path = Path(
            str(
                mcp.get("db_path")
                or paths.get("db_path")
                or app_support / "db" / "hb-personal-assistant.sqlite"
            )
        )
        audit_dir = Path(str(mcp.get("audit_dir") or app_support / "audit" / "mcp"))
        roots_raw = mcp.get("roots") if isinstance(mcp.get("roots"), dict) else {}
        roots: dict[str, RootSpec] = {}
        for key, spec in roots_raw.items():
            if not isinstance(spec, dict):
                continue
            mount = Path(str(spec.get("mount", "")))
            if not str(mount):
                continue
            roots[str(key)] = RootSpec(key=str(key), mount=mount, mode=str(spec.get("mode", "read_only")))
        limits = mcp.get("limits") if isinstance(mcp.get("limits"), dict) else {}
        obs_raw = mcp.get("obsidian") if isinstance(mcp.get("obsidian"), dict) else {}
        vault_mount = roots.get("vault").mount if roots.get("vault") else Path("/mnt/vault")
        obsidian = NasObsidianConfig(
            vault_root=Path(str(obs_raw.get("vault_root") or vault_mount)),
            backup_dir=Path(str(obs_raw.get("backup_dir") or audit_dir / "obsidian-backups")),
            support_dir=Path(str(obs_raw.get("support_dir") or audit_dir / "obsidian-support")),
            writes_enabled=bool(obs_raw.get("writes_enabled", True)),
            vault_markdown_write_enabled=bool(obs_raw.get("vault_markdown_write_enabled", True)),
            summarization_backend=str(obs_raw.get("summarization_backend", "deterministic")),
        )
        return cls(
            db_path=db_path,
            audit_dir=audit_dir,
            roots=roots,
            max_excerpt_bytes=int(limits.get("max_excerpt_bytes", 16_384)),
            max_list_entries=int(limits.get("max_list_entries", 100)),
            max_db_rows=int(limits.get("max_db_rows", 100)),
            default_db_rows=int(limits.get("default_db_rows", 25)),
            max_response_bytes=int(limits.get("max_response_bytes", 256_000)),
            max_write_bytes=int(limits.get("max_write_bytes", 262_144)),
            max_output_file_bytes=int(limits.get("max_output_file_bytes", 1_048_576)),
            actor=str(mcp.get("actor", "bfetting-via-ssh-launcher")),
            obsidian=obsidian,
        )

    def root_mount(self, root_key: str) -> Path:
        spec = self.roots.get(root_key)
        if spec is None:
            raise KeyError(f"unknown root_key: {root_key}")
        return spec.mount
