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
# Legacy local-scratch writer extensions (hb_output_write_file) — unchanged.
DEFAULT_OUTPUT_WRITE_EXTENSIONS = frozenset({"txt", "md", "csv", "json", "yaml", "yml", "docx", "xlsx"})
# N8C-24 connected-client generated-output workspace (pa_output_*). Broader, receipt-backed.
DEFAULT_CLIENT_OUTPUT_WRITE_EXTENSIONS = frozenset(
    {"txt", "md", "csv", "json", "docx", "xlsx", "pptx", "pdf", "html", "zip"}
)
# Executable/script/credential extensions that must never be written as generated output.
DENIED_OUTPUT_EXTENSIONS = frozenset(
    {"sh", "command", "app", "exe", "dmg", "pkg", "py", "js", "ts", "jar", "bat", "ps1", "ps",
     "sqlite", "db", "pem", "p12", "key", "enc"}
)


@dataclass(frozen=True)
class NasObsidianConfig:
    vault_root: Path
    backup_dir: Path
    support_dir: Path
    writes_enabled: bool = True
    vault_markdown_write_enabled: bool = True
    summarization_backend: str = "deterministic"
    ai_outputs_folder: str = "AI Outputs"
    # Maps indexed source-root keys → their mounted paths so live source reads resolve instead of
    # falling back to indexed excerpts. Each entry: {"source_root_key", "path", "sensitive"?}. Left
    # empty → obsidian_config_from_nas derives a `syn-<roots-key>` default for the home/work trees.
    external_sources: tuple[dict[str, Any], ...] = ()


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
    # N8C-24 client generated-output workspace limits (separate from the 1 MiB scratch cap).
    max_client_output_file_bytes: int = 26_214_400  # 25 MiB
    max_client_output_zip_members: int = 200
    max_client_output_zip_uncompressed_bytes: int = 104_857_600  # 100 MiB
    max_client_output_writes_per_window: int = 20
    client_output_write_window_seconds: int = 3600
    # N8B safe-mode/limits seams (all env-overridable via HB_MCP_MAX_* — see limits.py).
    max_search_results: int = 50
    max_card_bytes: int = 262_144
    max_ai_outputs_writes_per_window: int = 20
    write_window_seconds: int = 3600
    max_concurrent_calls: int = 8
    tool_timeout_seconds: int = 30
    read_extensions: frozenset[str] = DEFAULT_READ_EXTENSIONS
    output_write_extensions: frozenset[str] = DEFAULT_OUTPUT_WRITE_EXTENSIONS
    client_output_extensions: frozenset[str] = DEFAULT_CLIENT_OUTPUT_WRITE_EXTENSIONS
    denied_output_extensions: frozenset[str] = DENIED_OUTPUT_EXTENSIONS
    denied_name_patterns: tuple[str, ...] = DEFAULT_DENIED_NAME_PATTERNS
    denied_dir_segments: tuple[str, ...] = DEFAULT_DENIED_DIR_SEGMENTS
    actor: str = "bfetting-via-ssh-launcher"
    origin_auth_store_path: Path | None = None
    override_store_path: Path | None = None
    obsidian: NasObsidianConfig | None = None
    # External HTTPS base URL for OAuth discovery/issuer (e.g. https://nas-mcp.example.me).
    # Required when OAuth is enabled; used to build AS/PRM metadata and resource binding.
    public_base_url: str | None = None

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
                or os.environ.get("HB_APP_SUPPORT_DIR", "/volume2/personal-assistant/app-support")
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
        origin_auth_store_path = Path(
            str(
                os.environ.get("HB_MCP_ORIGIN_AUTH_TOKEN_STORE")
                or mcp.get("origin_auth_store_path")
                or app_support / "origin-auth" / "tokens.json"
            )
        )
        override_store_path = Path(
            str(
                os.environ.get("HB_MCP_OVERRIDE_STORE")
                or mcp.get("override_store_path")
                or app_support / "origin-auth" / "overrides.json"
            )
        )
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
        ext_raw = obs_raw.get("external_sources")
        external_sources = tuple(
            {"source_root_key": str(e.get("source_root_key")), "path": str(e.get("path")),
             "sensitive": bool(e.get("sensitive", False))}
            for e in ext_raw if isinstance(e, dict) and e.get("source_root_key") and e.get("path")
        ) if isinstance(ext_raw, list) else ()
        obsidian = NasObsidianConfig(
            vault_root=Path(str(obs_raw.get("vault_root") or vault_mount)),
            backup_dir=Path(str(obs_raw.get("backup_dir") or audit_dir / "obsidian-backups")),
            support_dir=Path(str(obs_raw.get("support_dir") or audit_dir / "obsidian-support")),
            writes_enabled=bool(obs_raw.get("writes_enabled", True)),
            vault_markdown_write_enabled=bool(obs_raw.get("vault_markdown_write_enabled", True)),
            summarization_backend=str(obs_raw.get("summarization_backend", "deterministic")),
            ai_outputs_folder=str(obs_raw.get("ai_outputs_folder", "AI Outputs")),
            external_sources=external_sources,
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
            max_client_output_file_bytes=int(limits.get("max_client_output_file_bytes", 26_214_400)),
            max_client_output_zip_members=int(limits.get("max_client_output_zip_members", 200)),
            max_client_output_zip_uncompressed_bytes=int(
                limits.get("max_client_output_zip_uncompressed_bytes", 104_857_600)),
            max_client_output_writes_per_window=int(limits.get("max_client_output_writes_per_window", 20)),
            client_output_write_window_seconds=int(limits.get("client_output_write_window_seconds", 3600)),
            max_search_results=int(limits.get("max_search_results", 50)),
            max_card_bytes=int(limits.get("max_card_bytes", 262_144)),
            max_ai_outputs_writes_per_window=int(limits.get("max_ai_outputs_writes_per_window", 20)),
            write_window_seconds=int(limits.get("write_window_seconds", 3600)),
            max_concurrent_calls=int(limits.get("max_concurrent_calls", 8)),
            tool_timeout_seconds=int(limits.get("tool_timeout_seconds", 30)),
            actor=str(mcp.get("actor", "bfetting-via-ssh-launcher")),
            origin_auth_store_path=origin_auth_store_path,
            override_store_path=override_store_path,
            obsidian=obsidian,
            public_base_url=(
                os.environ.get("HB_MCP_PUBLIC_BASE_URL")
                or (str(mcp.get("public_base_url")) if mcp.get("public_base_url") else None)
            ),
        )

    def root_mount(self, root_key: str) -> Path:
        spec = self.roots.get(root_key)
        if spec is None:
            raise KeyError(f"unknown root_key: {root_key}")
        return spec.mount
