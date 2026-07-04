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
    denied_name_patterns: tuple[str, ...] = DEFAULT_DENIED_NAME_PATTERNS
    denied_dir_segments: tuple[str, ...] = DEFAULT_DENIED_DIR_SEGMENTS
    actor: str = "bfetting-via-ssh-launcher"

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
        return cls(
            db_path=db_path,
            audit_dir=audit_dir,
            roots=roots,
            max_excerpt_bytes=int(limits.get("max_excerpt_bytes", 16_384)),
            max_list_entries=int(limits.get("max_list_entries", 100)),
            max_db_rows=int(limits.get("max_db_rows", 100)),
            default_db_rows=int(limits.get("default_db_rows", 25)),
            max_response_bytes=int(limits.get("max_response_bytes", 256_000)),
            actor=str(mcp.get("actor", "bfetting-via-ssh-launcher")),
        )

    def root_mount(self, root_key: str) -> Path:
        spec = self.roots.get(root_key)
        if spec is None:
            raise KeyError(f"unknown root_key: {root_key}")
        return spec.mount
