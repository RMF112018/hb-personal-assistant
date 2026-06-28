"""Local JSON configuration for the UI-managed Obsidian MCP service."""

from __future__ import annotations

import json
import os
import secrets
from contextlib import suppress
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from hb_assistant.config.path_policy import PathPolicy

DEFAULT_ALLOWED_FILE_TYPES = ["md", "txt", "pdf", "docx"]


class ObsidianMcpConfig(BaseModel):
    enabled: bool = False
    mode: Literal["filesystem"] = "filesystem"
    vault_root: str = Field(default_factory=lambda: str(PathPolicy().get_vault_root()))
    host: str = "127.0.0.1"
    port: int = 3010
    bearer_token: str | None = None
    max_file_mb: int = 100
    max_result_chars: int = 12000
    allowed_file_types: list[str] = Field(default_factory=lambda: list(DEFAULT_ALLOWED_FILE_TYPES))
    default_scope: str = ""
    schema_version: int = 1

    model_config = {"extra": "forbid"}

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        host = value.strip()
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError("host_must_be_localhost")
        return host

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if value < 1 or value > 65535:
            raise ValueError("port_out_of_range")
        return value

    @field_validator("max_file_mb", "max_result_chars")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value_must_be_positive")
        return value

    @field_validator("allowed_file_types")
    @classmethod
    def validate_file_types(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            ext = item.strip().lower().lstrip(".")
            if ext not in DEFAULT_ALLOWED_FILE_TYPES:
                raise ValueError(f"unsupported_file_type:{ext}")
            if ext not in normalized:
                normalized.append(ext)
        return normalized or list(DEFAULT_ALLOWED_FILE_TYPES)

    @property
    def endpoint_url(self) -> str:
        return f"http://{self.host}:{self.port}/mcp"

    @property
    def token_configured(self) -> bool:
        return bool((self.bearer_token or "").strip())

    def redacted(self) -> dict[str, object]:
        data = self.model_dump(exclude={"bearer_token"})
        data["token_configured"] = self.token_configured
        data["endpoint_url"] = self.endpoint_url
        return data


class ObsidianMcpConfigPatch(BaseModel):
    enabled: bool | None = None
    vault_root: str | None = None
    host: str | None = None
    port: int | None = None
    bearer_token: str | None = None
    rotate_token: bool | None = None
    clear_token: bool | None = None
    max_file_mb: int | None = None
    max_result_chars: int | None = None
    allowed_file_types: list[str] | None = None
    default_scope: str | None = None

    model_config = {"extra": "forbid"}


def config_path() -> Path:
    root = PathPolicy().get_app_support() / "analytics"
    root.mkdir(parents=True, exist_ok=True)
    return root / "obsidian_mcp_config.json"


def load_config() -> ObsidianMcpConfig:
    path = config_path()
    if not path.exists():
        return ObsidianMcpConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ObsidianMcpConfig()
    if not isinstance(raw, dict):
        return ObsidianMcpConfig()
    return ObsidianMcpConfig.model_validate(raw)


def save_config(config: ObsidianMcpConfig) -> ObsidianMcpConfig:
    path = config_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config.model_dump(), indent=2), encoding="utf-8")
    os.replace(tmp, path)
    with suppress(OSError):
        path.chmod(0o600)
    return config


def apply_patch(patch: ObsidianMcpConfigPatch) -> tuple[ObsidianMcpConfig, str | None]:
    current = load_config()
    updates = patch.model_dump(exclude_none=True)
    one_time_token: str | None = None

    if updates.pop("clear_token", False):
        updates["bearer_token"] = None
    elif updates.pop("rotate_token", False):
        one_time_token = secrets.token_urlsafe(32)
        updates["bearer_token"] = one_time_token
    elif "bearer_token" in updates:
        token = str(updates["bearer_token"] or "").strip()
        updates["bearer_token"] = token or None

    if "vault_root" in updates and updates["vault_root"] is not None:
        updates["vault_root"] = str(Path(str(updates["vault_root"])).expanduser())

    next_config = current.model_copy(update=updates)
    next_config = ObsidianMcpConfig.model_validate(next_config.model_dump())
    save_config(next_config)
    return next_config, one_time_token
