"""Pydantic models for HB Personal Assistant configuration.

These mirror the structure and defaults in resources/config.example.yml (and config/config.example.yml).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel, Field, field_validator


class ProjectConfig(BaseModel):
    name: str = "HB Personal Assistant + Work Product Intelligence System"
    slug: str = "hb-personal-assistant"


class IdentityConfig(BaseModel):
    tenant_id: str = "0e834bd7-628b-42c8-b9ec-ecebc9719be4"
    client_id: str = "08c399eb-a394-4087-b859-659d493f8dc7"
    delegated_scopes: List[str] = Field(
        default_factory=lambda: [
            "User.Read",
            "Mail.Read",
            "Calendars.Read",
            "Files.Read.All",
            "offline_access",
        ]
    )


class PathsConfig(BaseModel):
    application_support_root: str = "~/Library/Application Support/HB Personal Assistant"
    obsidian_vault: str = "/Users/bobbyfetting/Documents/Obsidian Vault"
    daily_notes_folder: str = "Daily Notes"
    ai_outputs_folder: str = "AI Outputs"
    reference_root: str = "Work/References"


class MailConfig(BaseModel):
    inbound_lookback_days: int = 5
    sent_lookback_days: int = 7
    max_body_retrieval_per_run: int = 75
    max_items_per_run: int = 25
    persist_full_body: bool = False


class CalendarConfig(BaseModel):
    window: dict = Field(default_factory=lambda: {"start": "yesterday", "end": "next_2_business_days"})
    max_items_per_run: int = 25


class FilesConfig(BaseModel):
    max_file_size_mb_default: int = 100
    max_file_size_mb_pdf: int = 250
    max_file_size_mb_office: int = 100
    max_file_size_mb_cad_export_pdf: int = 300
    warn_above_mb: int = 100
    require_manual_approval_above_mb: int = 300
    parse_timeout_seconds: int = 180
    ocr_enabled: bool = False
    max_drive_items_per_run: int = 25


class GraphConfig(BaseModel):
    max_pages_per_call: int = 5


class MorningRunConfig(BaseModel):
    time: str = "05:00"
    timezone: str = "America/New_York"
    catch_up_if_machine_wakes_after: bool = True
    weekend_behavior: Literal["manual_only", "run"] = "manual_only"


class LaunchdConfig(BaseModel):
    executable_path: str | None = None
    working_directory: str | None = None
    label: str | None = None
    python_path: str | None = None


class AutomationConfig(BaseModel):
    morning_run: MorningRunConfig = Field(default_factory=MorningRunConfig)
    launchd: LaunchdConfig = Field(default_factory=LaunchdConfig)


class SecurityConfig(BaseModel):
    microsoft_365_writeback_enabled: bool = False
    external_llm_enabled: bool = False


class AppConfig(BaseModel):
    """Root configuration object."""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    identity: IdentityConfig = Field(default_factory=IdentityConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    mail: MailConfig = Field(default_factory=MailConfig)
    calendar: CalendarConfig = Field(default_factory=CalendarConfig)
    files: FilesConfig = Field(default_factory=FilesConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    automation: AutomationConfig = Field(default_factory=AutomationConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    @field_validator("paths")
    @classmethod
    def expand_paths(cls, v: PathsConfig) -> PathsConfig:
        # Expand ~ in application_support_root at model level for convenience
        if v.application_support_root.startswith("~"):
            v.application_support_root = str(Path(v.application_support_root).expanduser())
        return v

    model_config = {"extra": "forbid"}
