"""Local JSON configuration for the UI-managed Obsidian MCP service."""

from __future__ import annotations

import json
import os
import secrets
from contextlib import suppress
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from hb_assistant.config.path_policy import PathPolicy

DEFAULT_ALLOWED_FILE_TYPES = ["md", "txt", "pdf", "docx"]
DEFAULT_ALLOWED_WRITE_FILE_TYPES = ["md"]
DEFAULT_PROTECTED_PATHS = [".git", ".obsidian", ".trash", ".hb-assistant/backups"]


class ExternalSourceRoot(BaseModel):
    """A configured external directory to index (raw files stay where they are)."""

    source_root_key: str
    path: str
    enabled: bool = True
    source_kind: Literal["external_file"] = "external_file"
    sensitive: bool = False

    model_config = {"extra": "forbid"}

    @field_validator("path")
    @classmethod
    def _absolute_path(cls, value: str) -> str:
        candidate = Path(value.strip()).expanduser()
        if not str(value).strip() or not candidate.is_absolute():
            raise ValueError("external_source_path_must_be_absolute")
        return str(candidate)


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
    writes_enabled: bool = False
    vault_markdown_write_enabled: bool = False
    max_write_chars: int = 120000
    write_requires_expected_sha256: bool = True
    backup_before_replace: bool = True
    create_parent_dirs_enabled: bool = True
    allow_full_vault_markdown_writes: bool = True
    protected_paths: list[str] = Field(default_factory=lambda: list(DEFAULT_PROTECTED_PATHS))
    blocked_hidden_paths: bool = True
    allowed_write_file_types: list[str] = Field(default_factory=lambda: list(DEFAULT_ALLOWED_WRITE_FILE_TYPES))
    oauth_enabled: bool = False
    public_base_url: str | None = None
    chatgpt_enabled: bool = True
    chatgpt_readonly_mode: bool = True
    dynamic_client_registration_enabled: bool = True
    client_id_metadata_document_enabled: bool = False
    chatgpt_initial_scopes: list[str] = Field(default_factory=lambda: ["obsidian.read"])
    curation_dense_folder_threshold: int = 5
    curation_operator_hidden_inspection: bool = False
    llm_chat_enabled: bool = True
    llm_chat_template_dir: str = "Templates/LLM Chat"
    llm_chat_project_template_path: str = "Templates/Template - Project Note.md"
    llm_chat_max_transcript_chars: int = 120000
    llm_chat_max_plan_updates: int = 5
    llm_chat_persist_raw_transcript: bool = False
    llm_chat_default_target_folder: str = "Inbox/LLM Sessions"
    summarization_backend: Literal["auto", "deterministic", "llm"] = "auto"
    summarization_provider: Literal["ollama", "anthropic"] = "ollama"
    summarization_model: str = "llama3.1"
    daily_notes_folder: str = "Daily Notes"
    archive_folder: str = "Archive"
    tool_timeout_seconds: int = 30
    external_sources: list[ExternalSourceRoot] = Field(default_factory=list)
    external_source_index_enabled: bool = True
    external_source_watch_enabled: bool = False
    external_source_scan_max_files: int = 5000
    source_index_max_excerpt_chars: int = 8000
    source_index_max_chunks: int = 40
    source_index_max_chunk_chars: int = 1500
    watch_poll_interval_seconds: int = 30
    watch_debounce_seconds: float = 1.5
    source_notes_folder: str = "Source Notes"
    source_card_generation_enabled: bool = True
    source_card_excerpt_chars: int = 600
    source_summary_enabled: bool = True
    source_summary_max_input_chars: int = 6000
    source_summary_ollama_timeout_seconds: int = 45
    schema_version: int = 6

    model_config = {"extra": "forbid"}

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        host = value.strip()
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError("host_must_be_localhost")
        return host

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip().rstrip("/")
        if not candidate:
            return None
        parsed = urlsplit(candidate)
        if parsed.scheme == "https" and parsed.netloc:
            return candidate
        if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
            return candidate
        raise ValueError("public_base_url_must_be_https_or_localhost")

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if value < 1 or value > 65535:
            raise ValueError("port_out_of_range")
        return value

    @field_validator(
        "max_file_mb",
        "max_result_chars",
        "max_write_chars",
        "curation_dense_folder_threshold",
        "llm_chat_max_transcript_chars",
        "llm_chat_max_plan_updates",
        "tool_timeout_seconds",
        "external_source_scan_max_files",
        "source_index_max_excerpt_chars",
        "source_index_max_chunks",
        "source_index_max_chunk_chars",
        "watch_poll_interval_seconds",
        "source_card_excerpt_chars",
        "source_summary_max_input_chars",
        "source_summary_ollama_timeout_seconds",
    )
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

    @field_validator("allowed_write_file_types")
    @classmethod
    def validate_write_file_types(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            ext = item.strip().lower().lstrip(".")
            if ext not in DEFAULT_ALLOWED_WRITE_FILE_TYPES:
                raise ValueError(f"unsupported_write_file_type:{ext}")
            if ext not in normalized:
                normalized.append(ext)
        return normalized or list(DEFAULT_ALLOWED_WRITE_FILE_TYPES)

    @field_validator("chatgpt_initial_scopes")
    @classmethod
    def validate_chatgpt_initial_scopes(cls, value: list[str]) -> list[str]:
        supported = {"obsidian.read", "obsidian.write"}
        normalized: list[str] = []
        for item in value:
            scope = item.strip()
            if scope not in supported:
                raise ValueError(f"unsupported_chatgpt_scope:{scope}")
            if scope not in normalized:
                normalized.append(scope)
        return normalized or ["obsidian.read"]

    @field_validator("protected_paths")
    @classmethod
    def validate_protected_paths(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            path = item.strip().replace("\\", "/").strip("/")
            if path and path not in normalized:
                normalized.append(path)
        return normalized

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
    writes_enabled: bool | None = None
    vault_markdown_write_enabled: bool | None = None
    max_write_chars: int | None = None
    write_requires_expected_sha256: bool | None = None
    backup_before_replace: bool | None = None
    create_parent_dirs_enabled: bool | None = None
    allow_full_vault_markdown_writes: bool | None = None
    protected_paths: list[str] | None = None
    blocked_hidden_paths: bool | None = None
    allowed_write_file_types: list[str] | None = None
    oauth_enabled: bool | None = None
    public_base_url: str | None = None
    chatgpt_enabled: bool | None = None
    chatgpt_readonly_mode: bool | None = None
    dynamic_client_registration_enabled: bool | None = None
    client_id_metadata_document_enabled: bool | None = None
    chatgpt_initial_scopes: list[str] | None = None
    curation_dense_folder_threshold: int | None = None
    curation_operator_hidden_inspection: bool | None = None
    llm_chat_enabled: bool | None = None
    llm_chat_template_dir: str | None = None
    llm_chat_project_template_path: str | None = None
    llm_chat_max_transcript_chars: int | None = None
    llm_chat_max_plan_updates: int | None = None
    llm_chat_persist_raw_transcript: bool | None = None
    llm_chat_default_target_folder: str | None = None
    summarization_backend: Literal["auto", "deterministic", "llm"] | None = None
    summarization_provider: Literal["ollama", "anthropic"] | None = None
    summarization_model: str | None = None
    daily_notes_folder: str | None = None
    archive_folder: str | None = None
    tool_timeout_seconds: int | None = None
    external_sources: list[ExternalSourceRoot] | None = None
    external_source_index_enabled: bool | None = None
    external_source_watch_enabled: bool | None = None
    external_source_scan_max_files: int | None = None
    source_index_max_excerpt_chars: int | None = None
    source_index_max_chunks: int | None = None
    source_index_max_chunk_chars: int | None = None
    watch_poll_interval_seconds: int | None = None
    watch_debounce_seconds: float | None = None
    source_notes_folder: str | None = None
    source_card_generation_enabled: bool | None = None
    source_card_excerpt_chars: int | None = None
    source_summary_enabled: bool | None = None
    source_summary_max_input_chars: int | None = None
    source_summary_ollama_timeout_seconds: int | None = None

    model_config = {"extra": "forbid"}


def config_path() -> Path:
    root = PathPolicy().get_app_support() / "analytics"
    root.mkdir(parents=True, exist_ok=True)
    return root / "obsidian_mcp_config.json"


def load_config_with_warnings() -> tuple[ObsidianMcpConfig, list[str]]:
    """Load the persisted config, tolerating unknown keys written by newer code.

    The model keeps ``extra="forbid"`` so the typed patch path still rejects programmer
    error, but the *persisted-file* path may legitimately contain keys a newer branch
    added and this code does not know yet. We pre-filter the raw dict against the known
    model fields before validating, so an unknown key never 500s an older deployment;
    the dropped keys are reported as ``config_warnings`` for the operator surface.

    Invalid *values* on known keys still raise (real corruption, not forward-compat).
    """
    path = config_path()
    if not path.exists():
        return ObsidianMcpConfig(), []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ObsidianMcpConfig(), []
    if not isinstance(raw, dict):
        return ObsidianMcpConfig(), []
    known = set(ObsidianMcpConfig.model_fields)
    unknown = sorted(k for k in raw if k not in known)
    filtered = {k: v for k, v in raw.items() if k in known}
    config = ObsidianMcpConfig.model_validate(filtered)
    warnings = [f"unknown_keys_ignored:{','.join(unknown)}"] if unknown else []
    return config, warnings


def load_config() -> ObsidianMcpConfig:
    return load_config_with_warnings()[0]


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

    if "chatgpt_readonly_mode" in updates and "chatgpt_initial_scopes" not in updates:
        updates["chatgpt_initial_scopes"] = (
            ["obsidian.read"] if updates["chatgpt_readonly_mode"] else ["obsidian.read", "obsidian.write"]
        )
    elif "chatgpt_initial_scopes" in updates and "chatgpt_readonly_mode" not in updates:
        updates["chatgpt_readonly_mode"] = "obsidian.write" not in updates["chatgpt_initial_scopes"]

    # Merge as plain data then validate, so nested models (e.g. external_sources) are coerced
    # cleanly from dicts without an intermediate model_dump over half-built submodels.
    next_config = ObsidianMcpConfig.model_validate({**current.model_dump(), **updates})
    save_config(next_config)
    return next_config, one_time_token
