"""Optional FastAPI shell for the future analytics UI.

FastAPI is an optional dependency. Imports stay inside ``create_app`` and the
dependency factory so the base package remains FastAPI-free.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from hb_assistant.config.path_policy import PathPolicy  # Prompt 20 prefs + daily_brief config path
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

try:
    from fastapi import File as FastAPIFile
    from fastapi import Form as FastAPIForm
    from fastapi import UploadFile as FastAPIUploadFile
    from starlette.datastructures import UploadFile as StarletteUploadFile
    from starlette.requests import Request as StarletteRequest
except ImportError:  # pragma: no cover - analytics-ui optional
    FastAPIFile = Any  # type: ignore[misc,assignment]
    FastAPIForm = Any  # type: ignore[misc,assignment]
    FastAPIUploadFile = Any  # type: ignore[misc,assignment]
    StarletteRequest = Any  # type: ignore[misc,assignment]
    StarletteUploadFile = Any  # type: ignore[misc,assignment]

_logger = logging.getLogger(__name__)

ALLOWED_UI_ROLES = frozenset({"viewer", "operator", "admin"})


class GraphDeviceLoginCompleteRequest(BaseModel):
    flow_id: str


class ForecastExternalPreviewRequest(BaseModel):
    filename: str
    content_b64: str
    source_system: str = "excel"
    period: str | None = None


class ForecastExternalMappingRequest(BaseModel):
    import_id: str
    project_key: str = "tropical"


class ForecastExternalEvaluateRequest(BaseModel):
    import_id: str
    column_roles: dict[str, str]
    project_key: str = "tropical"


class ForecastConfigEditRequest(BaseModel):
    base_snapshot_id: str
    edits: list[dict[str, Any]]
    project_key: str = "tropical"


class ForecastConfigPromoteRequest(BaseModel):
    confirm: bool = False


class ForecastRuntimeConfigRequest(BaseModel):
    package_roots: list[str] | None = None
    data_root: str | None = None
    runs_root: str | None = None
    eval_root: str | None = None
    db_path: str | None = None
    cfr_src: str | None = None
    config_edit_root: str | None = None


class ForecastRuntimeResetRequest(BaseModel):
    confirm: bool = False


class ScheduleImportCommitRequest(BaseModel):
    import_id: str
    project_key: str
    confirm: bool = False
    confirm_supersede: bool = False
    column_roles: dict[str, str] | None = None


class ScheduleIdentityReassignRequest(BaseModel):
    target_identity_key: str
    reason: str | None = None


class ScheduleIdentitySplitRequest(BaseModel):
    canonical_schedule_name: str | None = None
    reason: str | None = None


class ScheduleIdentityMergeRequest(BaseModel):
    target_identity_key: str
    reason: str | None = None


class ScheduleCostMappingRunRequest(BaseModel):
    project_key: str
    schedule_version_key: str
    operator_objective: str = "association_only"


class ScheduleCostMappingReviewRequest(BaseModel):
    operator_status: str
    operator_notes: str | None = None
    candidate_cost_code: str | None = None


class ProcoreOAuthExchangeRequest(BaseModel):
    code: str


class RefreshLiveRequest(BaseModel):
    confirm: bool = False


class ConnectionSetupRequest(BaseModel):
    url: str | None = None
    connection_type: str | None = None
    project_key: str | None = None
    source_name: str | None = None
    scope_mode: str | None = None
    selected_folder_item_ids: list[str] | None = None
    include_outlook: bool = False
    include_calendar: bool = False
    connection_id: str | None = None


class SyncScheduleRequest(BaseModel):
    cadence_minutes: int | None = None
    priority: str | None = None
    rate_limit: str | None = None
    scope: str | None = None


class KeywordCreateRequest(BaseModel):
    term: str
    strength: str | None = "normal"
    notes_redacted: str | None = None


class KeywordUpdateRequest(BaseModel):
    strength: str | None = None
    registry_status: str | None = None
    notes_redacted: str | None = None


class KeywordExplainRequest(BaseModel):
    candidate: str | dict[str, Any] | None = None


class OperatorAssumptionCreateRequest(BaseModel):
    assumption_type: str
    value: str | None = None
    unit: str | None = None
    budget_code_key: str | None = None
    source: str | None = None
    operator: str | None = None
    confidence_impact: str | None = None
    is_required: bool = False
    notes: str | None = None


class OperatorAssumptionEditRequest(BaseModel):
    value: str | None = None
    unit: str | None = None
    source: str | None = None
    operator: str | None = None
    confidence_impact: str | None = None
    is_required: bool | None = None
    overridden: bool | None = None
    notes: str | None = None


class RequiredAssumptionCreateRequest(BaseModel):
    assumption_type: str
    reason: str | None = None


class RequiredAssumptionSatisfyRequest(BaseModel):
    satisfied: bool = True


class StaffingConfigCreateRequest(BaseModel):
    role_title: str | None = None
    person_name: str | None = None
    employment_type: str | None = None
    cost_code: str | None = None
    cost_code_description: str | None = None
    rate_unit: str | None = None
    lab_rate: str | None = None
    lbn_rate: str | None = None
    mat_rate: str | None = None
    start_date: str | None = None
    finish_date: str | None = None
    template_id: str | None = None
    override_fields: list[str] | None = None
    created_by_role: str | None = None


class StaffingConfigPatchRequest(BaseModel):
    role_title: str | None = None
    person_name: str | None = None
    employment_type: str | None = None
    cost_code: str | None = None
    cost_code_description: str | None = None
    rate_unit: str | None = None
    lab_rate: str | None = None
    lbn_rate: str | None = None
    mat_rate: str | None = None
    start_date: str | None = None
    finish_date: str | None = None
    template_id: str | None = None
    override_fields: list[str] | None = None


class StaffingAssumptionsPatchRequest(BaseModel):
    hours_per_business_day: str | None = None
    business_days_per_week: str | None = None
    full_time_hours_per_week: str | None = None
    holiday_calendar_id: str | None = None


class StaffingAbsenceCreateRequest(BaseModel):
    staffing_config_id: str | None = None
    person_name: str | None = None
    start_date: str | None = None
    finish_date: str | None = None
    absence_hours: str | None = None
    notes: str | None = None


class StaffingAbsencePatchRequest(BaseModel):
    staffing_config_id: str | None = None
    person_name: str | None = None
    start_date: str | None = None
    finish_date: str | None = None
    absence_hours: str | None = None
    notes: str | None = None


class StaffingRuleCreateRequest(BaseModel):
    cost_code: str
    category: str
    staffing_config_id: str
    created_by_role: str | None = None


class StaffingReviewResolveRequest(BaseModel):
    staffing_config_id: str
    resolved_by_role: str | None = None


class StaffingTemplateCreateRequest(BaseModel):
    template_key: str
    template_name: str
    created_by_role: str | None = None


class StaffingTemplateVersionCreateRequest(BaseModel):
    cost_code: str | None = None
    cost_code_description: str | None = None
    default_role_title: str | None = None
    default_employment_type: str | None = None
    default_rate_unit: str | None = None
    default_lab_rate: str | None = None
    default_lbn_rate: str | None = None
    default_mat_rate: str | None = None
    created_by_role: str | None = None


class RefreshRequest(BaseModel):
    note_redacted: str | None = None


class DailyBriefConfigureRequest(BaseModel):
    enabled: bool | None = None
    platform: str | None = None
    output_folder: str | None = None
    file_pattern: str | None = None
    stale_threshold_minutes: int | None = None
    show_on_today: bool | None = None


class DailyBriefInstructionsRequest(BaseModel):
    platform: str | None = None
    output_folder: str | None = None
    file_pattern: str | None = None


class DailyBriefValidateFolderRequest(BaseModel):
    folder: str | None = None


class ObsidianMcpConfigPatchRequest(BaseModel):
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
    tool_timeout_seconds: int | None = None
    external_sources: list[dict[str, Any]] | None = None
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
    summarization_backend: str | None = None
    summarization_provider: str | None = None
    summarization_model: str | None = None
    source_summary_enabled: bool | None = None
    source_summary_max_input_chars: int | None = None
    source_summary_ollama_timeout_seconds: int | None = None
    source_card_auto_generate_enabled: bool | None = None
    source_summary_auto_generate_enabled: bool | None = None
    source_note_auto_refresh_enabled: bool | None = None
    source_card_auto_generate_kinds: list[str] | None = None
    source_summary_auto_generate_kinds: list[str] | None = None
    source_summary_auto_max_per_drain: int | None = None
    source_card_auto_max_per_drain: int | None = None
    source_index_excluded_path_parts: list[str] | None = None
    source_index_deferred_path_parts: list[str] | None = None
    source_index_unsupported_file_types: list[str] | None = None
    source_index_metadata_only_file_types: list[str] | None = None
    source_value_high_priority_path_signals: list[str] | None = None
    source_value_normal_priority_path_signals: list[str] | None = None
    source_card_auto_metadata_only_enabled: bool | None = None


class ObsidianMcpGenerateSourceCardRequest(BaseModel):
    source_id: str
    overwrite: bool = False


class ObsidianMcpRefreshStaleRequest(BaseModel):
    max_updates: int = 25


class ObsidianMcpRetireSourceCardsRequest(BaseModel):
    apply: bool = False  # default dry-run (no mutation)
    delete_files: bool = False  # only with apply; removes the card .md file (never the source)


class ObsidianMcpSummarizeSourceRequest(BaseModel):
    source_id: str


class ObsidianMcpListDirectoryRequest(BaseModel):
    path: str = ""
    recursive: bool = False
    extensions: list[str] | None = None
    max_depth: int | None = None


class ObsidianMcpSearchRequest(BaseModel):
    query: str
    path_scope: str | None = None
    file_types: list[str] | None = None
    limit: int | None = None
    include_content_snippet: bool = True


class ObsidianMcpReadFileRequest(BaseModel):
    path: str
    start_page: int | None = None
    end_page: int | None = None
    section: str | None = None
    max_chars: int | None = None


# Prompt 14B — Settings / Connection Management UX (role-aware, plain-language, no secrets/tokens)
class SettingsPreferencesPatch(BaseModel):
    theme: str | None = None  # "dark" | "light" | "system"
    default_landing_page: str | None = None  # "Today" | "Projects" | "My Items"
    show_daily_brief_on_today: bool | None = None
    followed_projects: list[str] | None = None


class SettingsAdminPatch(BaseModel):
    global_rate_limit: int | None = None
    backoff_seconds: int | None = None


# Prompt A — normalized safe response models for auth/onboarding, connections, and data-quality.
# These are the frontend contract shapes. All fields are safe (no tokens, secrets, raw payloads,
# cache paths, signed/download URLs, or raw external content).
class AuthSource(str, Enum):
    graph = "graph"
    procore = "procore"


class AuthStatus(str, Enum):
    never_connected = "never_connected"
    connected_valid = "connected_valid"
    connected_refreshing = "connected_refreshing"
    connected_stale_refreshable = "connected_stale_refreshable"
    connected_stale_reauth_required = "connected_stale_reauth_required"
    connected_error = "connected_error"
    disconnected_by_user = "disconnected_by_user"


class OnboardingState(str, Enum):
    first_time = "first_time"
    ready = "ready"
    degraded = "degraded"
    reauth_required = "reauth_required"
    blocked = "blocked"


class DataQualityStatus(str, Enum):
    good = "good"
    degraded = "degraded"
    poor = "poor"
    unknown = "unknown"


class ApprovalStatus(str, Enum):
    not_requested = "not_requested"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    not_required = "not_required"


class RequiredAction(BaseModel):
    source: AuthSource
    status: AuthStatus
    message: str | None = None


class DataQualitySummary(BaseModel):
    status: DataQualityStatus | str
    label: str = "Data Quality"
    last_updated_at: str | None = None
    message: str | None = None
    admin_detail_available: bool = False


class OnboardingReadinessResponse(BaseModel):
    onboarding_state: OnboardingState
    has_prior_setup: bool
    main_app_allowed: bool
    get_started_required: bool
    reauth_required: list[AuthSource] = []
    required_actions: list[RequiredAction] = []
    data_quality: DataQualitySummary


class AccountStatus(BaseModel):
    source: AuthSource
    status: AuthStatus
    display_name: str | None = None
    account_hint: str | None = None
    tenant_hint: str | None = None
    company_hint: str | None = None
    scopes: list[str] = []
    needs_reauth: bool = False
    last_verified_at: str | None = None
    message: str | None = None


class ConnectionsAccountsResponse(BaseModel):
    graph: AccountStatus
    procore: AccountStatus


class AuthRefreshResultItem(BaseModel):
    source: AuthSource
    before: AuthStatus
    after: AuthStatus
    reauth_required: bool
    message: str | None = None


class AuthRefreshResponse(BaseModel):
    results: list[AuthRefreshResultItem] = []


class ProjectConnectionPreviewResponse(BaseModel):
    # Mirrors the existing preview shape for the normalized path; values are safe metadata only.
    status: str
    connection_id: str | None = None
    detected_source_type: str | None = None
    proposed_source: dict[str, Any] | None = None
    warnings: list[str] = []
    admin_approval_required: bool = True
    first_sync_status: str | None = None
    guardrails: dict[str, Any] | None = None
    options: dict[str, Any] | None = None


class ProjectConnectionSaveResponse(BaseModel):
    ok: bool
    kind: str | None = None
    connection_id: str | None = None
    detected_source_type: str | None = None
    first_sync_status: str | None = None
    admin_approval_required: bool = True
    guardrails: dict[str, Any] | None = None
    preview: dict[str, Any] | None = None
    reason_code: str | None = None


class AdminApprovalResponse(BaseModel):
    ok: bool
    kind: str | None = None
    connection_id: str | None = None
    source_type: str | None = None
    first_sync_status: str | None = None
    first_sync_triggered: bool = False
    guardrails: dict[str, Any] | None = None


class DataQualityDetail(BaseModel):
    # Admin-only richer view; still advisory metadata only. No raw content.
    surface: str
    generated_utc: str | None = None
    summary: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = []
    attention_items: list[dict[str, Any]] = []
    advisory_notes: list[str] = []
    guardrails: dict[str, Any] | None = None


def _schema_version(db_path: str | None) -> int:
    try:
        return int(SQLiteMigrator(db_path=db_path).current_version())
    except Exception:
        return 0


def _guardrails() -> dict[str, Any]:
    return {
        "read_only": True,
        "local_first": True,
        "no_cli_shellout": True,
        "no_live_endpoint_calls": True,
        "no_external_writeback": True,
        "active_chat_routes": False,
        "chat_enabled": False,
    }


def role_dependency() -> Any:
    """Build a FastAPI dependency that resolves the UI role from a header."""
    from fastapi import Header, HTTPException

    def _resolve_role(x_hb_ui_role: str = Header(default="viewer")) -> dict[str, str]:
        role = x_hb_ui_role.strip().lower()
        if role not in ALLOWED_UI_ROLES:
            raise HTTPException(status_code=403, detail="invalid_ui_role")
        return {"role": role, "permission_scope": "read_only"}

    return _resolve_role


def require_operator_role(role: dict[str, str]) -> dict[str, str]:
    """Require a write-local-auth capable UI role."""
    from fastapi import HTTPException

    if role.get("role") not in {"operator", "admin"}:
        raise HTTPException(status_code=403, detail="operator_role_required")
    return role


def require_admin_role(role: dict[str, str]) -> dict[str, str]:
    """Require an admin UI role."""
    from fastapi import HTTPException

    if role.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin_role_required")
    return role


def _oauth_error_html(error: str, description: str | None = None) -> str:
    """Minimal, dependency-free HTML error page for the OAuth authorize surface."""
    import html as _html

    detail = _html.escape(description or error)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>HB Obsidian MCP — authorization error</title></head>"
        "<body style='font-family:system-ui;max-width:32rem;margin:3rem auto;padding:0 1rem'>"
        f"<h1 style='font-size:1.1rem'>Authorization error: {_html.escape(error)}</h1>"
        f"<p>{detail}</p></body></html>"
    )


def _oauth_consent_html(*, scopes: list[str], vault_root: str, write_enabled: bool, params: dict[str, str]) -> str:
    """Simple local approval page for trusted MCP OAuth clients (no login system)."""
    import html as _html
    from urllib.parse import urlsplit

    hidden = "".join(
        f"<input type='hidden' name='{_html.escape(key)}' value='{_html.escape(value)}'>"
        for key, value in params.items()
    )
    scope_items = "".join(f"<li><code>{_html.escape(scope)}</code></li>" for scope in scopes)
    write_warning = (
        "<p style='border:1px solid #f59e0b;padding:.75rem'>"
        "This connection is requesting write access to your Obsidian vault. Write operations remain subject to "
        "the configured vault write policy and protected-path rules.</p>"
        if "obsidian.write" in scopes
        else ""
    )
    write_label = "enabled" if write_enabled else "disabled"
    client_name = params.get("client_name") or "MCP client"
    redirect_host = urlsplit(params.get("redirect_uri") or "").hostname or "unknown"
    resource = params.get("resource") or "not provided"
    public_base_url = params.get("public_base_url") or "not configured"
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>HB Obsidian MCP — authorize client</title></head>"
        "<body style='font-family:system-ui;max-width:34rem;margin:3rem auto;padding:0 1rem'>"
        f"<h1 style='font-size:1.15rem'>{_html.escape(client_name)} is requesting access to HB Obsidian MCP</h1>"
        "<p>Approve this request to let this remote MCP connector use your local Obsidian vault.</p>"
        "<p><strong>Requested scopes</strong></p>"
        f"<ul>{scope_items}</ul>"
        f"{write_warning}"
        f"<p><strong>Redirect host:</strong> <code>{_html.escape(redirect_host)}</code></p>"
        f"<p><strong>MCP resource:</strong> <code>{_html.escape(resource)}</code></p>"
        f"<p><strong>Public base URL:</strong> <code>{_html.escape(public_base_url)}</code></p>"
        f"<p><strong>Vault root:</strong> <code>{_html.escape(vault_root)}</code></p>"
        f"<p><strong>Write mode:</strong> {write_label}</p>"
        "<form method='post' action='/oauth/authorize'>"
        f"{hidden}"
        "<button type='submit' name='decision' value='approve' "
        "style='padding:.5rem 1rem;font-size:1rem;margin-right:.5rem'>Approve</button>"
        "<button type='submit' name='decision' value='deny' "
        "style='padding:.5rem 1rem;font-size:1rem'>Deny</button>"
        "</form></body></html>"
    )


@asynccontextmanager
async def _forecast_lifespan(app: Any) -> Any:
    """Startup bootstrap: ensure app-managed forecast storage before serving.

    NAS runtime (``HB_NAS_RUNTIME=1``) fails closed on storage-guard or startup schema policy
    violations. Non-NAS dev mode keeps the prior degrade posture for optional bootstrap faults.
    """
    import asyncio
    import logging
    import os

    from hb_assistant.config.db_storage_guard import (
        DbStorageGuardError,
        assert_db_storage_allowed,
        is_nas_runtime,
    )
    from hb_assistant.config.path_policy import PathPolicy
    from hb_assistant.construction.schedule_clean_db.diagnostics import evidence_disable_background_workers
    from hb_assistant.store.db_posture import log_db_posture_at_startup
    from hb_assistant.store.startup_schema_policy import StartupSchemaPolicyError

    _logger = logging.getLogger(__name__)
    nas_runtime = is_nas_runtime()
    app.state.nas_runtime = nas_runtime
    app.state.startup_migration_performed = False
    app.state.db_storage_class = "blocked"

    from hb_assistant.construction.schedule_clean_db.diagnostics import (
        resolve_background_worker_disable,
    )

    env_disabled = evidence_disable_background_workers()
    if os.environ.get("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "").strip() not in {"", "1"}:
        _logger.warning(
            "HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS has unexpected value; treating as unset"
        )
        env_disabled = False

    # NAS runtime is single-purpose (viewer/API): HB_NAS_RUNTIME=1 forces the poll loop, source
    # watcher, and root registration off at boot even if the env kill-switch was forgotten
    # (authoritative default-off posture for single-writer safety).
    disable_workers, nas_forced_workers_off = resolve_background_worker_disable(
        nas_runtime=nas_runtime, env_disabled=env_disabled
    )
    if nas_forced_workers_off:
        _logger.info("HB_NAS_RUNTIME=1 forces background workers off (NAS default-off posture)")

    app.state.background_worker_mode = "disabled" if disable_workers else "enabled"
    app.state.background_workers_disabled_by_env = disable_workers
    app.state.background_workers_forced_off_by_nas_runtime = nas_forced_workers_off
    app.state.background_workers = {
        "quality_poll_started": False,
        "source_watcher_initialized": False,
        "source_watcher_started": False,
    }

    poll_task: asyncio.Task[None] | None = None
    configured = getattr(app.state, "db_path", None)
    resolved_db = str(configured) if configured else str(PathPolicy().get_db_path())

    try:
        app.state.db_storage_class = assert_db_storage_allowed(resolved_db, context="startup")

        from hb_assistant.construction.analytics.forecast_bootstrap import (
            ensure_forecast_managed_storage,
        )

        bootstrap = ensure_forecast_managed_storage()
        db_report = bootstrap.get("bootstrap", {}).get("db", {})
        app.state.startup_migration_performed = bool(db_report.get("migration_performed"))
        log_db_posture_at_startup(
            _logger,
            resolved_db,
            background_worker_mode=app.state.background_worker_mode,
            startup_migration_performed=app.state.startup_migration_performed,
        )
    except (DbStorageGuardError, StartupSchemaPolicyError):
        if nas_runtime:
            raise
        _logger.exception("startup guard/policy failure (non-NAS runtime degrade)")
    except Exception:
        if nas_runtime:
            raise
        pass

    async def _quality_poll_loop() -> None:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.construction.analytics.schedule_quality_worker import poll_and_process

        configured = getattr(app.state, "db_path", None)
        db = str(configured) if configured else str(PathPolicy().get_db_path())
        while True:
            try:
                await asyncio.to_thread(poll_and_process, db_path=db, limit=3)
            except Exception:
                pass
            await asyncio.sleep(60)

    if not disable_workers:
        try:
            poll_task = asyncio.create_task(_quality_poll_loop())
            app.state.background_workers["quality_poll_started"] = poll_task is not None
        except Exception:
            poll_task = None

    # Source-intelligence: register configured roots (indexing ON by default) and start the
    # external-source watcher only when enabled. Fail-closed — never blocks app startup.
    source_watcher: Any = None
    if not disable_workers:
        try:
            from hb_assistant.config.path_policy import PathPolicy
            from hb_assistant.obsidian_mcp.config import load_config as _load_obsidian_config
            from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
            from hb_assistant.obsidian_mcp.source_watch import SourceWatcher

            _configured = getattr(app.state, "db_path", None)
            _watch_db = str(_configured) if _configured else str(PathPolicy().get_db_path())
            _watch_config = _load_obsidian_config()
            if getattr(_watch_config, "external_source_index_enabled", True):
                SourceIndexRepository(_watch_db).register_source_roots(
                    [{"source_root_key": r.source_root_key, "enabled": r.enabled}
                     for r in _watch_config.external_sources]
                )
            source_watcher = SourceWatcher(_watch_db, _watch_config)
            app.state.background_workers["source_watcher_initialized"] = source_watcher is not None
            if getattr(_watch_config, "external_source_watch_enabled", False):
                await asyncio.to_thread(source_watcher.start)
                app.state.background_workers["source_watcher_started"] = True
            app.state.source_watcher = source_watcher
        except Exception:
            app.state.source_watcher = None
            source_watcher = None
    else:
        app.state.source_watcher = None
        source_watcher = None

    mcp_wrapper = getattr(app.state, "mcp_streamable_http_app", None)
    mcp_app = getattr(mcp_wrapper, "app", mcp_wrapper)
    mcp_lifespan = getattr(getattr(mcp_app, "router", None), "lifespan_context", None)

    async with AsyncExitStack() as stack:
        if callable(mcp_lifespan):
            await stack.enter_async_context(mcp_lifespan(mcp_app))
        try:
            yield
        finally:
            if source_watcher is not None:
                with suppress(Exception):
                    source_watcher.stop()
            if poll_task is not None:
                poll_task.cancel()
                try:
                    await poll_task
                except asyncio.CancelledError:
                    pass


def create_app(*, db_path: str | None = None) -> Any:
    """Create the optional FastAPI app shell.

    The shell intentionally exposes only health, OpenAPI, and disabled chat
    status. Future analytics route adapters should call ``AnalyticsService``
    directly and reuse ``role_dependency``.
    """
    from fastapi import Body, Depends, FastAPI, Query, Request

    # ``from __future__ import annotations`` makes route annotations strings that
    # FastAPI resolves against this module's globals. ``Request`` is imported
    # lazily here (the base install stays FastAPI-free), so publish it to the
    # module namespace at runtime for annotation resolution.
    globals()["Request"] = Request

    require_role = role_dependency()
    app = FastAPI(
        lifespan=_forecast_lifespan,
        title="HB Personal Assistant Analytics UI Shell",
        version="0.1.0-prompt-14b",
        description=(
            "Optional read-only FastAPI shell for future analytics UI routes. "
            "Active chat is disabled. Project keyword training (Prompt 05), sync governance (Prompt 06), "
            "dashboard read models (Prompt 07), UI kit and screens (Prompts 08-09), external Daily Brief "
            "workflow (Prompt 10), connection setup hardening (Prompt 14A), and Settings / Connection Management UX "
            "(Prompt 14B: account/project connections, source scope, keywords, daily brief config, preferences, admin sync controls) supported."
        ),
    )
    app.state.db_path = db_path
    role_dep = Depends(require_role)
    optional_json_body = Body(default=None)  # bound to a var so call isn't in an arg default (B008)
    app.state.mcp_streamable_http_app = None

    mcp_streamable_http_app: Any | None = None
    try:
        from hb_assistant.obsidian_mcp.mcp_app import build_streamable_http_app

        mcp_streamable_http_app = build_streamable_http_app(db_path=db_path)
        app.state.mcp_streamable_http_app = mcp_streamable_http_app
    except Exception:
        # Optional SDK or adapter unavailable: the UI health check reports the precise blocker.
        pass

    @app.get("/health")
    def health(role: dict[str, str] = role_dep) -> dict[str, Any]:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.construction.schedule_clean_db.diagnostics import build_db_diagnostics
        from hb_assistant.store.db_posture import public_health_posture

        resolved = db_path or str(PathPolicy().get_db_path())
        schema_version = _schema_version(resolved)
        worker_mode = getattr(app.state, "background_worker_mode", "enabled")
        startup_migration_performed = bool(getattr(app.state, "startup_migration_performed", False))
        payload: dict[str, Any] = {
            "status": "ok",
            "surface": "analytics.fastapi_shell",
            "role": role,
            "schema_version": schema_version,
            "schema_expected": LATEST_SCHEMA_VERSION,
            "schema_ready": schema_version >= LATEST_SCHEMA_VERSION,
            "chat_enabled": False,
            "guardrails": _guardrails(),
            "background_worker_mode": worker_mode,
            "background_workers_disabled_by_env": getattr(
                app.state, "background_workers_disabled_by_env", False
            ),
            "background_workers_forced_off_by_nas_runtime": getattr(
                app.state, "background_workers_forced_off_by_nas_runtime", False
            ),
            "nas_runtime": bool(getattr(app.state, "nas_runtime", False)),
        }
        workers = getattr(app.state, "background_workers", None)
        if workers is not None:
            payload["background_workers"] = workers
        payload.update(
            public_health_posture(
                resolved,
                background_worker_mode=worker_mode,
                startup_migration_performed=startup_migration_performed,
            )
        )
        payload.update(
            build_db_diagnostics(
                db_path,
                role=role,
                background_worker_mode=payload["background_worker_mode"],
                background_workers_disabled_by_env=payload["background_workers_disabled_by_env"],
                background_workers=workers,
            )
        )
        return payload

    @app.get("/chat/status")
    def chat_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        return {
            "status": "disabled",
            "surface": "analytics.chat_status",
            "role": role,
            "chat_enabled": False,
            "active_chat_routes": False,
            "reason_code": "active_chat_not_implemented",
            "guardrails": _guardrails(),
        }

    @app.get("/onboarding/auth/status")
    def onboarding_auth_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().build_combined_status()

    @app.get("/auth/graph/status")
    def graph_auth_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().graph_status()

    @app.post("/auth/graph/device-login/start")
    def graph_device_login_start(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().start_graph_device_login()

    @app.post("/auth/graph/device-login/complete")
    def graph_device_login_complete(
        request: GraphDeviceLoginCompleteRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().complete_graph_device_login(request.flow_id)

    # Prompt B — normalized Microsoft Graph local auth contract routes.
    # These are additive to the legacy /auth/graph/* surfaces. Role: operator+ for
    # start/poll/disconnect (consistent with prior device-login). All responses safe;
    # no tokens, secrets, cache paths, or raw claims. Does not start sync.
    @app.post("/api/settings/connections/graph/auth/start")
    def settings_graph_auth_start(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().start_graph_device_auth()

    @app.get("/api/settings/connections/graph/auth/status")
    def settings_graph_auth_status(
        flow_id: str,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().poll_graph_device_auth_status(flow_id)

    @app.post("/api/settings/connections/graph/disconnect-local")
    def settings_graph_disconnect_local(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().disconnect_graph_local()

    @app.get("/auth/procore/status")
    def procore_auth_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().procore_status()

    @app.post("/auth/procore/oauth/start")
    def procore_oauth_start(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().start_procore_oauth()

    @app.post("/auth/procore/oauth/exchange")
    def procore_oauth_exchange(
        request: ProcoreOAuthExchangeRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().exchange_procore_oauth_code(request.code)

    # Prompt C — normalized Procore local OAuth contract family under /api/settings/connections/procore/auth/*.
    # Additive to legacy /auth/procore/* (OOB start/exchange/status). 
    # - start: operator, returns safe authorize URL + flow_id + state-driven callback support.
    # - callback: browser redirect target (state-validated), performs exchange server-side, returns minimal safe HTML.
    # - status (poll): operator, pending/complete/expired/failed.
    # - exchange-code: operator, manual OOB fallback.
    # - disconnect-local: operator, clears local token cache only.
    # All responses safe: no tokens, secrets, codes, state values, cache paths, or raw Procore payloads.
    # Callback security is the one-time code + state CSRF; UI role header not required for the redirect target.

    @app.post("/api/settings/connections/procore/auth/start")
    def settings_procore_auth_start(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().start_procore_auth_flow()

    @app.get("/api/settings/connections/procore/auth/callback")
    def settings_procore_auth_callback(code: str, state: str) -> Any:
        # Browser callback (no UI role enforcement; protected by state + one-time code).
        from fastapi import Response

        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        html = AuthOnboardingService().handle_procore_oauth_callback(code=code, state=state)
        return Response(content=html, media_type="text/html")

    @app.get("/api/settings/connections/procore/auth/status")
    def settings_procore_auth_status(flow_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().poll_procore_auth_status(flow_id)

    @app.post("/api/settings/connections/procore/auth/exchange-code")
    def settings_procore_auth_exchange_code(
        request: ProcoreOAuthExchangeRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        # Manual fallback; reuses the exchange logic but under normalized path (no cache_path in response).
        return AuthOnboardingService().exchange_procore_oauth_code(request.code, normalized_path=True)

    @app.post("/api/settings/connections/procore/disconnect-local")
    def settings_procore_disconnect_local(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().disconnect_procore_local()

    @app.post("/connections/preview")
    def connection_preview(
        request: ConnectionSetupRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        return ConnectionSetupService(db_path=db_path).preview_connection(
            request.model_dump(exclude_none=True)
        )

    @app.post("/connections/save")
    def connection_save(
        request: ConnectionSetupRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        return ConnectionSetupService(db_path=db_path).save_connection(
            request.model_dump(exclude_none=True)
        )

    @app.post("/admin/connections/{connection_id}/approve-first-sync")
    def admin_approve_first_sync(
        connection_id: str,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_admin_role(role)
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        return ConnectionSetupService(db_path=db_path).approve_first_sync(connection_id)

    @app.post("/admin/projects/{project_key}/sync-schedule")
    def admin_project_sync_schedule(
        project_key: str,
        request: SyncScheduleRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_admin_role(role)
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        return ConnectionSetupService(db_path=db_path).save_project_sync_schedule(
            project_key, request.model_dump(exclude_none=True)
        )

    # Prompt 05 / UI-05 — project keyword training (registry CRUD + explain)
    @app.get("/projects/{project_key}/keywords")
    def list_project_keywords(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.project_keywords import ProjectKeywordsService

        return ProjectKeywordsService(db_path=db_path).list_keywords(project_key)

    @app.post("/projects/{project_key}/keywords")
    def add_project_keyword(
        project_key: str,
        request: KeywordCreateRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.project_keywords import ProjectKeywordsService

        return ProjectKeywordsService(db_path=db_path).add_keyword(
            project_key,
            request.term,
            strength=request.strength or "normal",
            notes_redacted=request.notes_redacted,
        )

    @app.patch("/projects/{project_key}/keywords/{keyword_id}")
    def update_project_keyword(
        project_key: str,
        keyword_id: str,
        request: KeywordUpdateRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.project_keywords import ProjectKeywordsService

        return ProjectKeywordsService(db_path=db_path).update_keyword(
            keyword_id,
            strength=request.strength,
            registry_status=request.registry_status,
            notes_redacted=request.notes_redacted,
        )

    @app.delete("/projects/{project_key}/keywords/{keyword_id}")
    def delete_project_keyword(
        project_key: str,
        keyword_id: str,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.project_keywords import ProjectKeywordsService

        return ProjectKeywordsService(db_path=db_path).delete_keyword(keyword_id)

    @app.post("/projects/{project_key}/keywords/explain")
    def explain_project_keyword_match(
        project_key: str,
        request: KeywordExplainRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.project_keywords import ProjectKeywordsService

        return ProjectKeywordsService(db_path=db_path).explain_match(
            project_key, candidate=request.candidate
        )

    # Prompt 06 / UI-06 — sync governance (admin-only first live sync approval/schedule with cadence/priority,
    # automatic freshness status from local state, low-friction user refresh request)
    @app.post("/projects/{project_key}/refresh-request")
    def user_request_project_refresh(
        project_key: str,
        request: RefreshRequest | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        return ConnectionSetupService(db_path=db_path).request_user_refresh(project_key)

    @app.get("/projects/{project_key}/sync-freshness")
    def project_sync_freshness(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        return ConnectionSetupService(db_path=db_path).get_project_sync_freshness(project_key)

    @app.get("/admin/sync/pending-approvals")
    def admin_list_pending_sync_approvals(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        return ConnectionSetupService(db_path=db_path).list_pending_approvals()

    # Prompt 07 / UI-07 — first set of CM-first dashboard read models (composed, advisory-only).
    # Viewer access for all (read-only metadata + badges). No top-level domain dashboards.
    @app.get("/api/today")
    def today(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_today()

    @app.get("/api/today/changes")
    def today_changes(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_today_section("changes")

    @app.get("/api/today/meetings")
    def today_meetings(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_today_section("meetings")

    @app.get("/api/today/action-items")
    def today_action_items(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_today_section("action-items")

    @app.get("/api/today/portfolio-signals")
    def today_portfolio_signals(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_today_section("portfolio-signals")

    @app.get("/api/projects")
    def projects(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_summary_readmodel import (
            ProjectSummaryReadModelError,
            ProjectSummaryReadModelService,
        )

        try:
            return ProjectSummaryReadModelService(db_path=db_path).build()
        except ProjectSummaryReadModelError as exc:
            raise HTTPException(status_code=503, detail="project_summaries_not_available") from exc

    @app.get("/api/projects/portfolio")
    def projects_portfolio(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_projects_portfolio()

    @app.get("/api/projects/all/overview")
    def all_projects_overview(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_all_projects_overview()

    @app.get("/api/projects/schedule-review-dashboard")
    def schedule_review_dashboard(
        status: str | None = None,
        project_key: str | None = None,
        include_technical: int = 0,
        as_of: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        from datetime import date as date_type

        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_portfolio_review_service import (
            ProjectSchedulePortfolioReviewService,
            _STATUS_FILTERS,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        if status and status not in _STATUS_FILTERS:
            raise HTTPException(status_code=400, detail="invalid_status_filter")
        technical = bool(include_technical)
        if technical:
            require_operator_role(role)
        else:
            del role
        return ProjectSchedulePortfolioReviewService(db_path=_schedule_db_path()).build_dashboard(
            status=status,
            project_key=project_key,
            include_technical=technical,
            as_of=as_of_date,
        )

    @app.get("/api/projects/schedule-review-dashboard/export")
    def schedule_review_dashboard_export(
        format: str = "markdown",
        status: str | None = None,
        project_key: str | None = None,
        role: dict[str, str] = role_dep,
    ):
        del role
        from fastapi import HTTPException, Response

        from hb_assistant.construction.analytics.project_schedule_portfolio_review_service import (
            ProjectSchedulePortfolioReviewService,
            _STATUS_FILTERS,
        )

        if status and status not in _STATUS_FILTERS:
            raise HTTPException(status_code=400, detail="invalid_status_filter")
        svc = ProjectSchedulePortfolioReviewService(db_path=_schedule_db_path())
        export_format = str(format or "markdown").lower()
        if export_format == "markdown":
            body = svc.build_export_markdown(status=status, project_key=project_key)
            content_type = "text/markdown; charset=utf-8"
            filename = "portfolio-schedule-review.md"
        elif export_format == "csv":
            body = svc.build_export_csv(status=status, project_key=project_key)
            content_type = "text/csv; charset=utf-8"
            filename = "portfolio-schedule-review.csv"
        elif export_format == "json":
            body = svc.build_export_json(status=status, project_key=project_key)
            content_type = "application/json; charset=utf-8"
            filename = "portfolio-schedule-review.json"
        else:
            raise HTTPException(status_code=400, detail="unsupported_export_format")
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(content=body, media_type=content_type, headers=headers)

    @app.get("/api/projects/{project_key}/overview")
    def project_overview(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_project_overview(project_key)

    @app.get("/api/projects/{project_key}/meetings")
    def project_meetings(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_project_meetings(project_key)

    @app.get("/api/projects/{project_key}/field-operations")
    def project_field_operations(
        project_key: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_project_field_operations(project_key)

    @app.get("/api/projects/{project_key}/cost-time")
    def project_cost_time(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_project_cost_time(project_key)

    @app.get("/api/projects/{project_key}/schedule")
    def project_schedule(
        project_key: str,
        as_of: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from datetime import date as date_type

        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_summary_service import (
            ProjectScheduleSummaryService,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc

        return ProjectScheduleSummaryService(db_path=_schedule_db_path()).build_summary(
            project_key, as_of=as_of_date
        )

    @app.get("/api/projects/{project_key}/schedule/controls")
    def project_schedule_controls(
        project_key: str,
        as_of: str | None = None,
        comparison_basis: str = "prior_update",
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        from datetime import date as date_type

        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_baseline_vocabulary import (
            validate_controls_comparison_basis,
        )
        from hb_assistant.construction.analytics.project_schedule_controls_service import (
            ProjectScheduleControlsService,
        )

        include_technical = role.get("role") in {"operator", "admin"}

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        try:
            basis = validate_controls_comparison_basis(comparison_basis)
        except ValueError as exc:
            if str(exc) == "invalid_comparison_basis":
                raise HTTPException(status_code=400, detail="invalid_comparison_basis") from exc
            raise
        return ProjectScheduleControlsService(db_path=_schedule_db_path()).build_controls(
            project_key,
            as_of=as_of_date,
            comparison_basis=basis,
            include_technical=include_technical,
        )

    @app.get("/api/projects/{project_key}/schedule/drilldowns")
    def project_schedule_drilldowns(
        project_key: str,
        type: str,
        limit: int = 100,
        offset: int = 0,
        as_of: str | None = None,
        comparison_basis: str = "prior_update",
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from datetime import date as date_type
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_summary_service import (
            ProjectScheduleSummaryService,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc

        try:
            return ProjectScheduleSummaryService(db_path=_schedule_db_path()).build_drilldown(
                project_key,
                drilldown_type=type,
                limit=limit,
                offset=offset,
                as_of=as_of_date,
                comparison_basis=comparison_basis,
            )
        except ValueError as exc:
            if str(exc) == "unsupported_drilldown_type":
                raise HTTPException(status_code=400, detail="unsupported_drilldown_type") from exc
            if str(exc) == "invalid_comparison_basis":
                raise HTTPException(status_code=400, detail="invalid_comparison_basis") from exc
            raise

    @app.get("/api/projects/{project_key}/schedule/drivers")
    def project_schedule_drivers(
        project_key: str,
        type: str,
        limit: int = 100,
        offset: int = 0,
        driver_activity_id: str | None = None,
        as_of: str | None = None,
        comparison_basis: str = "prior_update",
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from datetime import date as date_type
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_summary_service import (
            ProjectScheduleSummaryService,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        try:
            return ProjectScheduleSummaryService(db_path=_schedule_db_path()).build_driver_drilldown(
                project_key,
                drilldown_type=type,
                limit=limit,
                offset=offset,
                driver_activity_id=driver_activity_id,
                as_of=as_of_date,
                comparison_basis=comparison_basis,
            )
        except ValueError as exc:
            if str(exc) == "driver_activity_id_required":
                raise HTTPException(status_code=400, detail="driver_activity_id_required") from exc
            if str(exc) == "unsupported_driver_drilldown_type":
                raise HTTPException(status_code=400, detail="unsupported_driver_drilldown_type") from exc
            if str(exc) == "invalid_comparison_basis":
                raise HTTPException(status_code=400, detail="invalid_comparison_basis") from exc
            raise

    def _project_schedule_driver_detail_response(
        project_key: str,
        activity_id: str,
        *,
        comparison_basis: str | None,
        basis: str | None,
        as_of: str | None,
    ) -> dict[str, Any]:
        from datetime import date as date_type

        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_comparison_basis_resolver import (
            reconcile_driver_detail_comparison_params,
        )
        from hb_assistant.construction.analytics.project_schedule_summary_service import (
            ProjectScheduleSummaryService,
        )

        if not str(activity_id or "").strip():
            raise HTTPException(status_code=400, detail="driver_activity_id_required")

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        try:
            resolved_basis = reconcile_driver_detail_comparison_params(
                comparison_basis=comparison_basis,
                basis=basis,
            )
        except ValueError as exc:
            detail = str(exc)
            if detail in {"invalid_comparison_basis", "conflicting_comparison_params"}:
                raise HTTPException(status_code=400, detail=detail) from exc
            raise
        return ProjectScheduleSummaryService(db_path=_schedule_db_path()).build_driver_detail(
            project_key,
            activity_id,
            comparison_basis=resolved_basis,
            as_of=as_of_date,
        )

    @app.get("/api/projects/{project_key}/schedule/drivers/detail")
    def project_schedule_driver_detail_query(
        project_key: str,
        activity_id: str = Query(...),
        comparison_basis: str | None = None,
        basis: str | None = None,
        as_of: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        return _project_schedule_driver_detail_response(
            project_key,
            activity_id,
            comparison_basis=comparison_basis,
            basis=basis,
            as_of=as_of,
        )

    @app.get("/api/projects/{project_key}/schedule/drivers/{activity_id}/detail")
    def project_schedule_driver_detail(
        project_key: str,
        activity_id: str,
        comparison_basis: str | None = None,
        basis: str | None = None,
        as_of: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        return _project_schedule_driver_detail_response(
            project_key,
            activity_id,
            comparison_basis=comparison_basis,
            basis=basis,
            as_of=as_of,
        )

    @app.get("/api/projects/{project_key}/schedule/review-items")
    def project_schedule_review_items_get(
        project_key: str,
        review_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
        as_of: str | None = None,
        comparison_basis: str = "prior_update",
        source_metric: str | None = None,
        severity: str | None = None,
        item_type: str | None = None,
        confidence: str | None = None,
        phase: str | None = None,
        floor: str | None = None,
        sector_area: str | None = None,
        subcontractor: str | None = None,
        cost_code: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from datetime import date as date_type

        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_comparison_basis_resolver import (
            resolve_workbench_comparison_basis,
        )
        from hb_assistant.construction.analytics.project_schedule_summary_service import (
            ProjectScheduleSummaryService,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        try:
            resolve_workbench_comparison_basis(comparison_basis)
        except ValueError as exc:
            if str(exc) == "invalid_comparison_basis":
                raise HTTPException(status_code=400, detail="invalid_comparison_basis") from exc
            raise
        return ProjectScheduleSummaryService(db_path=_schedule_db_path()).build_review_items(
            project_key,
            review_status=review_status,
            limit=limit,
            offset=offset,
            as_of=as_of_date,
            comparison_basis=comparison_basis,
            source_metric=source_metric,
            severity=severity,
            item_type=item_type,
            confidence=confidence,
            phase=phase,
            floor=floor,
            sector_area=sector_area,
            subcontractor=subcontractor,
            cost_code=cost_code,
        )

    @app.get("/api/projects/{project_key}/schedule/review-items/{review_item_id}")
    def project_schedule_review_item_detail_get(
        project_key: str,
        review_item_id: str,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del project_key, role
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_review_service import (
            ProjectScheduleReviewService,
        )

        try:
            return ProjectScheduleReviewService(db_path=_schedule_db_path()).get_item_detail(
                review_item_id=review_item_id,
            )
        except ValueError as exc:
            if str(exc) == "review_item_not_found":
                raise HTTPException(status_code=404, detail="review_item_not_found") from exc
            raise

    @app.get("/api/projects/{project_key}/schedule/review-items/{review_item_id}/events")
    def project_schedule_review_item_events_get(
        project_key: str,
        review_item_id: str,
        limit: int = 100,
        offset: int = 0,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del project_key, role
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_review_service import (
            ProjectScheduleReviewService,
        )

        try:
            return ProjectScheduleReviewService(db_path=_schedule_db_path()).list_item_events(
                review_item_id=review_item_id,
                limit=limit,
                offset=offset,
            )
        except ValueError as exc:
            if str(exc) == "review_item_not_found":
                raise HTTPException(status_code=404, detail="review_item_not_found") from exc
            raise

    @app.post("/api/projects/{project_key}/schedule/review-items")
    def project_schedule_review_items_sync(
        project_key: str,
        as_of: str | None = None,
        comparison_basis: str = "prior_update",
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from datetime import date as date_type

        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_comparison_basis_resolver import (
            resolve_workbench_comparison_basis,
        )
        from hb_assistant.construction.analytics.project_schedule_summary_service import (
            ProjectScheduleSummaryService,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        try:
            resolve_workbench_comparison_basis(comparison_basis)
        except ValueError as exc:
            if str(exc) == "invalid_comparison_basis":
                raise HTTPException(status_code=400, detail="invalid_comparison_basis") from exc
            raise
        try:
            workbench = ProjectScheduleSummaryService(db_path=_schedule_db_path()).sync_review_workbench(
                project_key,
                as_of=as_of_date,
                comparison_basis=comparison_basis,
            )
        except ValueError as exc:
            if str(exc) in {"baseline_not_selected", "baseline_invalid"}:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            raise
        return {"available": workbench.get("available", True), "workbench": workbench}

    @app.patch("/api/projects/{project_key}/schedule/review-items/{review_item_id}")
    def project_schedule_review_item_patch(
        project_key: str,
        review_item_id: str,
        request: dict[str, Any],
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_review_service import (
            ProjectScheduleReviewService,
        )
        from hb_assistant.construction.analytics.project_schedule_summary_service import (
            ProjectScheduleSummaryService,
        )

        trust = ProjectScheduleSummaryService(db_path=_schedule_db_path()).review_trust_context(project_key)
        try:
            return ProjectScheduleReviewService(db_path=_schedule_db_path()).update_item(
                review_item_id=review_item_id,
                project_key=project_key,
                review_status=request.get("review_status"),
                disposition=request.get("disposition"),
                pm_notes=request.get("pm_notes"),
                disposition_reason=request.get("disposition_reason"),
                reviewed_by_operator=role.get("role"),
                identity_gate=trust.get("identity_gate"),
                analytics_trust_status=trust.get("analytics_trust_status"),
            )
        except ValueError as exc:
            code = str(exc)
            if code == "review_item_not_found":
                raise HTTPException(status_code=404, detail="review_item_not_found") from exc
            if code == "review_item_project_mismatch":
                raise HTTPException(status_code=403, detail="review_item_project_mismatch") from exc
            if code in {
                "invalid_review_status",
                "disposition_reason_required",
                "operator_disposition_not_allowed",
                "blocked_disposition_cannot_be_cleared",
                "trust_blocked_disposition_change",
            }:
                raise HTTPException(status_code=400, detail=code) from exc
            raise

    @app.post("/api/projects/{project_key}/schedule/review-items/promote")
    def project_schedule_review_items_promote(
        project_key: str,
        request: dict[str, Any],
        as_of: str | None = None,
        comparison_basis: str = "prior_update",
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from datetime import date as date_type

        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_comparison_basis_resolver import (
            resolve_workbench_comparison_basis,
        )
        from hb_assistant.construction.analytics.project_schedule_summary_service import (
            ProjectScheduleSummaryService,
        )

        stable_item_keys = request.get("stable_item_keys") or []
        if not isinstance(stable_item_keys, list) or not stable_item_keys:
            raise HTTPException(status_code=400, detail="stable_item_keys_required")
        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        try:
            resolve_workbench_comparison_basis(comparison_basis)
        except ValueError as exc:
            if str(exc) == "invalid_comparison_basis":
                raise HTTPException(status_code=400, detail="invalid_comparison_basis") from exc
            raise
        try:
            return ProjectScheduleSummaryService(db_path=_schedule_db_path()).promote_review_cues(
                project_key,
                stable_item_keys=[str(key) for key in stable_item_keys],
                as_of=as_of_date,
                comparison_basis=comparison_basis,
                reviewed_by_operator=role.get("role"),
            )
        except ValueError as exc:
            if str(exc) in {"baseline_not_selected", "baseline_invalid"}:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            raise

    @app.get("/api/projects/{project_key}/schedule/metrics/{metric_key}/trend")
    def project_schedule_metric_trend(
        project_key: str,
        metric_key: str,
        as_of: str | None = None,
        weighting_basis: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from datetime import date as date_type

        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_trend_aggregation_service import (
            ProjectScheduleTrendAggregationService,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        try:
            return ProjectScheduleTrendAggregationService(db_path=_schedule_db_path()).build_trend(
                project_key,
                metric_key,
                as_of=as_of_date,
                weighting_basis=weighting_basis,
            )
        except ValueError as exc:
            code = str(exc)
            if code in {"unsupported_metric_key", "unsupported_weighting_basis"}:
                raise HTTPException(status_code=400, detail=code) from exc
            if code in {"metric_not_trend_ready", "cost_weighted_unavailable"}:
                raise HTTPException(status_code=422, detail=code) from exc
            raise

    @app.get("/api/projects/{project_key}/schedule/metrics/trends")
    def project_schedule_metric_trends(
        project_key: str,
        as_of: str | None = None,
        metrics: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from datetime import date as date_type

        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_trend_aggregation_service import (
            ProjectScheduleTrendAggregationService,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        metric_keys = [m.strip() for m in metrics.split(",") if m.strip()] if metrics else None
        return ProjectScheduleTrendAggregationService(db_path=_schedule_db_path()).build_trends(
            project_key,
            metric_keys=metric_keys,
            as_of=as_of_date,
        )

    @app.get("/api/projects/{project_key}/schedule/metric-proof")
    def project_schedule_metric_proof(
        project_key: str,
        schedule_version_key: str,
        as_of: str | None = None,
        comparison_basis: str = "prior_update",
        weighting_basis: str = "duration_weighted",
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from datetime import date as date_type

        from fastapi import HTTPException

        from hb_assistant.construction.analytics.schedule_metric_formula_service import (
            ScheduleMetricFormulaService,
            build_activation_proof,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        if comparison_basis not in {"prior_update", "selected_baseline"}:
            raise HTTPException(status_code=400, detail="invalid_comparison_basis")
        svc = ScheduleMetricFormulaService(db_path=_schedule_db_path())
        body = svc.compute_all(
            project_key,
            schedule_version_key,
            comparison_basis=comparison_basis,
            weighting_basis=weighting_basis,
            as_of=as_of_date,
        )
        body["activation_proof"] = build_activation_proof(project_key=project_key)
        body["activation_cross_check"] = body["activation_proof"]["cross_check_findings"]
        return body

    @app.get("/api/projects/{project_key}/schedule/export")
    def project_schedule_export(
        project_key: str,
        format: str = "markdown",
        as_of: str | None = None,
        variant: str = "standard",
        scope: str = "full",
        include_persisted_review: bool = False,
        comparison_basis: str = "prior_update",
        role: dict[str, str] = role_dep,
    ):
        del role
        from datetime import date as date_type

        from fastapi import HTTPException, Response

        from hb_assistant.construction.analytics.project_schedule_summary_service import (
            ProjectScheduleSummaryService,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        try:
            export_variant = variant if variant in {"standard", "executive"} else "standard"
            export_scope = scope if scope in {"full", "review_items"} else "full"
            payload = ProjectScheduleSummaryService(db_path=_schedule_db_path()).build_export(
                project_key,
                export_format=format,
                as_of=as_of_date,
                variant=export_variant,
                scope=export_scope,
                include_persisted_review=include_persisted_review,
                comparison_basis=comparison_basis,
            )
        except ValueError as exc:
            if str(exc) == "unsupported_export_format":
                raise HTTPException(status_code=400, detail="unsupported_export_format") from exc
            if str(exc) == "invalid_comparison_basis":
                raise HTTPException(status_code=400, detail="invalid_comparison_basis") from exc
            raise
        if not payload.get("available"):
            raise HTTPException(status_code=422, detail=payload.get("reason") or "export_unavailable")
        headers = {"Content-Disposition": f'attachment; filename="{payload["filename"]}"'}
        return Response(content=payload["body"], media_type=payload["content_type"], headers=headers)

    @app.get("/api/projects/{project_key}/schedule/baseline")
    def project_schedule_baseline_get(
        project_key: str,
        as_of: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from datetime import date as date_type
        from fastapi import HTTPException
        from hb_assistant.construction.analytics.project_schedule_summary_service import (
            ProjectScheduleSummaryService,
        )
        from hb_assistant.construction.analytics.project_schedule_selected_baseline_service import (
            ProjectScheduleSelectedBaselineService,
            public_selected_baseline_state,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc

        service = ProjectScheduleSummaryService(db_path=_schedule_db_path())
        summary = service.build_summary(project_key, as_of=as_of_date)
        current = summary.get("current_schedule") or {}
        if not current.get("available"):
            return {"available": False, "reason": "no_schedule"}
        current_key = summary.get("technical_evidence", {}).get("schedule_version_key")
        if not current_key:
            return {"available": False, "reason": "no_current_schedule"}
        state = ProjectScheduleSelectedBaselineService(db_path=_schedule_db_path()).get_state(
            project_key=project_key, current_schedule_version_key=str(current_key)
        )
        return {
            "available": True,
            **public_selected_baseline_state(state),
            "baseline_summary": summary.get("baseline_summary"),
        }

    @app.put("/api/projects/{project_key}/schedule/baseline")
    def project_schedule_baseline_put(
        project_key: str,
        request: dict[str, Any],
        as_of: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from datetime import date as date_type
        from hb_assistant.construction.analytics.project_schedule_summary_service import (
            ProjectScheduleSummaryService,
        )
        from hb_assistant.construction.analytics.project_schedule_selected_baseline_service import (
            ProjectScheduleSelectedBaselineService,
            public_selected_baseline_state,
        )
        from fastapi import HTTPException

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc

        current_key = str(request.get("current_schedule_version_key") or "")
        baseline_key = str(request.get("selected_baseline_schedule_version_key") or "")
        try:
            state = ProjectScheduleSelectedBaselineService(db_path=_schedule_db_path()).select_baseline(
                project_key=project_key,
                current_schedule_version_key=current_key,
                selected_baseline_schedule_version_key=baseline_key,
                selected_by_operator=role.get("role"),
                selection_note=str(request.get("selection_note") or "") or None,
            )
        except ValueError as exc:
            code = str(exc)
            if code in {
                "baseline_selection_required",
                "baseline_must_differ_from_current",
                "invalid_current_schedule_version",
                "invalid_selected_baseline_version",
                "baseline_project_mismatch",
                "baseline_identity_mismatch",
                "baseline_must_not_be_future_of_current",
            }:
                raise HTTPException(status_code=400, detail=code) from exc
            raise
        summary = ProjectScheduleSummaryService(db_path=_schedule_db_path()).build_summary(
            project_key, as_of=as_of_date
        )
        return {**public_selected_baseline_state(state), "baseline_summary": summary.get("baseline_summary")}

    @app.get("/api/projects/{project_key}/schedule/baselines")
    def project_schedule_baselines_get(
        project_key: str,
        as_of: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from datetime import date as date_type

        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_named_baseline_service import (
            ProjectScheduleNamedBaselineService,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        return ProjectScheduleNamedBaselineService(db_path=_schedule_db_path()).get_baselines_state(
            project_key, as_of=as_of_date
        )

    @app.put("/api/projects/{project_key}/schedule/baselines")
    def project_schedule_baselines_put(
        project_key: str,
        request: dict[str, Any],
        as_of: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from datetime import date as date_type

        from fastapi import HTTPException

        from hb_assistant.construction.analytics.project_schedule_named_baseline_service import (
            ProjectScheduleNamedBaselineService,
        )

        as_of_date: date_type | None = None
        if as_of:
            try:
                as_of_date = date_type.fromisoformat(as_of)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_as_of_date") from exc
        selections = request.get("selections")
        if not isinstance(selections, dict):
            raise HTTPException(status_code=400, detail="invalid_selections_payload")
        try:
            return ProjectScheduleNamedBaselineService(db_path=_schedule_db_path()).update_baselines(
                project_key,
                selections=selections,
                as_of=as_of_date,
                selected_by=role.get("role"),
            )
        except ValueError as exc:
            code = str(exc)
            if code in {
                "unknown_slot_key",
                "invalid_selections_payload",
                "invalid_slot_selection",
                "schedule_version_key_required",
                "no_schedule",
                "baseline_cannot_equal_current_schedule_version",
                "invalid_schedule_version_key",
                "baseline_project_mismatch",
                "baseline_must_not_be_future_of_current",
                "baseline_identity_mismatch",
                "duplicate_schedule_version_across_slots",
            }:
                raise HTTPException(status_code=400, detail=code) from exc
            raise


    @app.get("/api/my-items")
    def my_items(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_my_items()

    # Prompt 10 / UI-10 — Daily Brief external-agent Markdown workflow.
    # Setup wizard surfaces (configure, validate, instructions, detect), 7-state file detector,
    # scheduled prompt generation helper, and polished presentation (present/polish only).
    # Viewer read access for status/latest/today sub-resource; operator/admin for configuration actions.
    # Guardrails: external generation owner, app detects and presents only, never generates/rewrites,
    # no raw sensitive, advisory only.
    @app.get("/api/daily-brief/status")
    def daily_brief_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.daily_brief import DailyBriefService

        return DailyBriefService().get_status()

    @app.get("/api/daily-brief/latest")
    def daily_brief_latest(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.daily_brief import DailyBriefService

        return DailyBriefService().get_latest()

    @app.post("/api/daily-brief/configure")
    def daily_brief_configure(
        request: DailyBriefConfigureRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.daily_brief import DailyBriefService

        return DailyBriefService().configure(request.model_dump(exclude_none=True))

    @app.post("/api/daily-brief/generate-setup-instructions")
    def daily_brief_generate_instructions(
        request: DailyBriefInstructionsRequest | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.daily_brief import DailyBriefService

        data = request.model_dump(exclude_none=True) if request else {}
        return DailyBriefService().generate_setup_instructions(
            platform=data.get("platform"), overrides=data
        )

    @app.post("/api/daily-brief/validate-output-folder")
    def daily_brief_validate_folder(
        request: DailyBriefValidateFolderRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.daily_brief import DailyBriefService

        return DailyBriefService().validate_output_folder(request.folder)

    @app.post("/api/daily-brief/detect-latest")
    def daily_brief_detect_latest(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.daily_brief import DailyBriefService

        return DailyBriefService().detect_latest()

    @app.get("/api/today/daily-brief")
    def today_daily_brief(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_today_daily_brief()

    # Prompt 14B — Settings / Connection Management UX Completion
    # Role-aware, plain-language surfaces for account/project connections, source scope,
    # keywords (delegated), daily brief (delegated), user preferences, admin sync controls.
    # Guardrails: no raw secrets/tokens, preview/save/approve boundary preserved, chat disabled.
    # Viewer: read; operator: save local config/keywords/daily-brief config; admin: approve + admin controls.
    @app.get("/api/settings")
    def settings_overview(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService
        from hb_assistant.construction.analytics.daily_brief import DailyBriefService

        auth = AuthOnboardingService().build_combined_status()
        db_status = DailyBriefService().get_status()
        pending = (
            ConnectionSetupService(db_path=db_path).list_pending_approvals()
            if db_path
            else {"items": []}
        )
        return {
            "surface": "analytics.settings.overview",
            "accounts": {
                "graph": auth.get("graph", {}),
                "procore": auth.get("procore", {}),
            },
            "daily_brief": db_status,
            "pending_first_sync": pending,
            "guardrails": _guardrails(),
        }

    @app.get("/api/settings/accounts")
    def settings_accounts(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().build_combined_status()

    @app.get("/api/settings/projects")
    def settings_projects(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        conn = ConnectionSetupService(db_path=db_path)
        return {
            "pending_approvals": conn.list_pending_approvals(),
            "note": "Project connections managed via /connections/preview and /save (Prompt 14A boundary).",
            "guardrails": _guardrails(),
        }

    @app.get("/api/settings/sources")
    def settings_sources(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return {
            "source_scope_note": "See project connections for current scopes (procore, sharepoint, onedrive, outlook, calendar).",
            "outlook_calendar": "project_matching_only is optional and false by default (index selected scope safely, then classify/project-match after ingestion).",
            "onedrive": "all_folders requires explicit scope_mode=all_folders_explicit and emits large-scope admin-approval warning.",
            "guardrails": _guardrails(),
        }

    @app.get("/api/environment")
    def environment(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role  # all-roles; user-safe metadata only
        from hb_assistant.construction.analytics.environment_status import (
            EnvironmentStatusService,
        )

        return EnvironmentStatusService().build_environment()

    @app.get("/api/sources/status")
    def sources_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role  # all-roles; user-safe metadata only
        from hb_assistant.construction.analytics.environment_status import (
            EnvironmentStatusService,
        )

        return EnvironmentStatusService().build_sources_status()

    @app.get("/api/sources/graph/status")
    def sources_graph_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role  # all-roles; user-safe metadata only (no mail/calendar/files read)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().graph_source_status()

    @app.post("/api/sources/graph/auth/start")
    def sources_graph_auth_start(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().start_graph_device_auth()

    @app.get("/api/sources/graph/auth/status")
    def sources_graph_auth_status(
        flow_id: str,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().poll_graph_device_auth_status(flow_id)

    @app.post("/api/sources/graph/auth/refresh")
    def sources_graph_auth_refresh(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)  # safe silent refresh only; never reads content or starts sync
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().attempt_auth_refresh(["graph"])

    @app.get("/api/sources/procore/status")
    def sources_procore_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role  # all-roles; user-safe metadata only (no projects/sync/live content)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().procore_source_status()

    @app.post("/api/sources/procore/auth/start")
    def sources_procore_auth_start(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().start_procore_auth_flow()

    @app.get("/api/sources/procore/auth/callback")
    def sources_procore_auth_callback(code: str, state: str) -> Any:
        # Browser callback (no UI role enforcement; protected by CSRF state + one-time code).
        from fastapi import Response

        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        html = AuthOnboardingService().handle_procore_oauth_callback(code=code, state=state)
        return Response(content=html, media_type="text/html")

    @app.get("/api/sources/procore/auth/status")
    def sources_procore_auth_status(
        flow_id: str,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().poll_procore_auth_status(flow_id)

    @app.post("/api/sources/procore/auth/refresh")
    def sources_procore_auth_refresh(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)  # safe silent refresh only; never starts sync or reads content
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().attempt_auth_refresh(["procore"])

    @app.post("/api/sources/refresh/dry-run")
    def sources_refresh_dry_run(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)  # plan only; never writes the DB
        from hb_assistant.construction.analytics.source_refresh_control import (
            SourceRefreshControlService,
        )

        return SourceRefreshControlService(db_path=db_path).dry_run()

    @app.post("/api/sources/refresh/local")
    def sources_refresh_local(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)  # local/mock only; never constructs a live client
        from hb_assistant.construction.analytics.source_refresh_control import (
            SourceRefreshControlService,
        )

        return SourceRefreshControlService(db_path=db_path).local()

    @app.post("/api/sources/refresh/live")
    def sources_refresh_live(
        request: RefreshLiveRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)  # fails closed unless env+config+confirm all permit live reads
        from hb_assistant.construction.analytics.source_refresh_control import (
            SourceRefreshControlService,
        )

        return SourceRefreshControlService(db_path=db_path).live(confirm=request.confirm)

    @app.get("/api/scheduler/daily-source-refresh/status")
    def scheduler_daily_source_refresh_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role  # all-roles; user-safe status metadata only
        from hb_assistant.construction.analytics.environment_status import EnvironmentStatusService

        return EnvironmentStatusService().build_scheduler_status()

    @app.get("/api/settings/keywords")
    def settings_keywords(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return {
            "note": "Manage via /projects/{project_key}/keywords (add/edit/disable/delete/explain). Standard/template folder names (drawings, specifications, submittals, rfis, etc.) are excluded by policy.",
            "guardrails": _guardrails(),
        }

    @app.get("/api/settings/daily-brief")
    def settings_daily_brief(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.daily_brief import DailyBriefService

        return DailyBriefService().get_status()

    @app.get("/api/settings/obsidian-mcp/config")
    def settings_obsidian_mcp_config(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        service = ObsidianMcpService()
        return {
            "surface": "settings.obsidian_mcp.config",
            "config": service.get_config().redacted(),
            "config_warnings": service.config_warnings(),
            "guardrails": service.guardrails(),
        }

    @app.patch("/api/settings/obsidian-mcp/config")
    def settings_obsidian_mcp_update_config(
        request: ObsidianMcpConfigPatchRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp import ObsidianMcpConfigPatch, ObsidianMcpService
        from hb_assistant.obsidian_mcp.llm import validate_summary_model

        from fastapi import HTTPException
        from pydantic import ValidationError

        service = ObsidianMcpService()
        try:
            patch = ObsidianMcpConfigPatch.model_validate(request.model_dump(exclude_none=True))
        except ValidationError as exc:
            # Surface invalid config (e.g. a non-absolute external source path) as a clean 422
            # instead of letting the raw validation error escape as a 500. The detail is a stable,
            # non-sensitive code; field-level guidance is enforced in the settings UI.
            raise HTTPException(status_code=422, detail="invalid_obsidian_mcp_config") from exc
        result = service.update_config(patch)
        # Advisory (never blocking): if the operator set a summary model, validate it against the
        # installed Ollama tags so the UI can flag a missing/tag-resolved model. Ollama may be down
        # at save time, so this never rejects the save.
        if request.summarization_model is not None:
            with suppress(Exception):
                result["model_validation"] = validate_summary_model(service.get_config())
        return result

    @app.get("/api/settings/obsidian-mcp/status")
    def settings_obsidian_mcp_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().status()

    @app.post("/api/settings/obsidian-mcp/health-check")
    def settings_obsidian_mcp_health_check(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().health_check()

    @app.get("/api/settings/obsidian-mcp/source-index/status")
    def settings_obsidian_mcp_source_index_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        service = ObsidianMcpService(db_path=db_path)
        result = service.source_index_status({})
        result["config_warnings"] = service.config_warnings()
        watcher = getattr(app.state, "source_watcher", None)
        if watcher is not None:
            with suppress(Exception):
                # Derive the nested watcher's watch_enabled/roots from the CURRENT on-disk config so
                # it matches the top-level (service-derived) watch_enabled — no stale nested state.
                result["watcher"] = watcher.status(config=_fresh_obsidian_config())
        return result

    # ----- N8C-3 read-only source/card/note navigation (local UI surface) -----------------
    # All GET, all-roles, read-only. Delegates to the shared obsidian_mcp.source_navigation service
    # over a live-DB SourceIndexRepository. No writes, no raw SQL/fs; relative paths only.
    def _assistant_nav() -> tuple[Any, Any]:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp import source_navigation as nav
        from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

        return nav, SourceIndexRepository(db_path or str(PathPolicy().get_db_path()))

    def _assistant_env(payload: dict[str, Any]) -> dict[str, Any]:
        return {**payload, "guardrails": _guardrails()}

    # --- NAS source-structure layered index (V115) — read-only, bounded, root-relative only ----
    def _source_structure() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.source_structure_service import SourceStructureService

        return SourceStructureService(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/source-structure/status")
    def assistant_source_structure_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _assistant_env(_source_structure().status())

    @app.get("/api/assistant/source-structure/roots")
    def assistant_source_structure_roots(
        role: dict[str, str] = role_dep,
        query_family: str | None = Query(default=None),
        limit: int = Query(default=50),
    ) -> dict[str, Any]:
        del role
        return _assistant_env(_source_structure().root_map(query_family=query_family, limit=limit))

    @app.get("/api/assistant/source-structure/folders")
    def assistant_source_structure_folders(
        role: dict[str, str] = role_dep,
        root_key: str | None = Query(default=None),
        parent_folder_id: str | None = Query(default=None),
        depth: int | None = Query(default=None),
        folder_class: str | None = Query(default=None),
        doc_family: str | None = Query(default=None),
        project_number: str | None = Query(default=None),
        include_noise: bool = Query(default=False),
        limit: int = Query(default=50),
        cursor: str | None = Query(default=None),
    ) -> dict[str, Any]:
        del role
        return _assistant_env(_source_structure().folder_map(
            root_key=root_key, parent_folder_id=parent_folder_id, depth=depth,
            folder_class=folder_class, doc_family=doc_family, project_number=project_number,
            include_noise=include_noise, limit=limit, cursor=cursor,
        ))

    @app.get("/api/assistant/source-structure/folder-summary")
    def assistant_source_structure_folder_summary(
        role: dict[str, str] = role_dep, folder_id: str = Query(...),
    ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        result = _source_structure().folder_summary(folder_id)
        if result is None:
            raise HTTPException(status_code=404, detail="folder_not_found")
        return _assistant_env(result)

    @app.get("/api/assistant/source-structure/search-route")
    def assistant_source_structure_search_route(
        role: dict[str, str] = role_dep,
        query: str | None = Query(default=None),
        query_family: str | None = Query(default=None),
        project_number: str | None = Query(default=None),
        doc_family: str | None = Query(default=None),
        limit: int = Query(default=10),
    ) -> dict[str, Any]:
        del role
        return _assistant_env(_source_structure().search_route(
            query=query, query_family=query_family, project_number=project_number,
            doc_family=doc_family, limit=limit,
        ))

    @app.get("/api/assistant/source-structure/project-map")
    def assistant_source_structure_project_map(
        role: dict[str, str] = role_dep,
        project_number: str = Query(...),
        limit: int = Query(default=50),
    ) -> dict[str, Any]:
        del role
        return _assistant_env(_source_structure().project_map(project_number, limit=limit))

    @app.get("/api/assistant/source-structure/quality")
    def assistant_source_structure_quality(
        role: dict[str, str] = role_dep,
        severity: str | None = Query(default=None),
        finding_type: str | None = Query(default=None),
        status: str | None = Query(default="open"),
        limit: int = Query(default=50),
        cursor: str | None = Query(default=None),
    ) -> dict[str, Any]:
        del role
        return _assistant_env(_source_structure().quality(
            severity=severity, finding_type=finding_type, status=status, limit=limit, cursor=cursor,
        ))

    @app.get("/api/assistant/source-structure/readiness")
    def assistant_source_structure_readiness(
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        return _assistant_env(_source_structure().readiness())

    @app.get("/api/assistant/sources")
    def assistant_sources(
        role: dict[str, str] = role_dep,
        q: str = Query(default=""),
        limit: int = Query(default=25),
        project_key: str | None = Query(default=None),
    ) -> dict[str, Any]:
        del role
        nav, repo = _assistant_nav()
        return _assistant_env(nav.search_sources(repo, q, limit=limit, project_key=project_key))

    @app.get("/api/assistant/sources/{source_id}")
    def assistant_source(source_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        nav, repo = _assistant_nav()
        result = nav.get_source(repo, source_id)
        if result is None:
            raise HTTPException(status_code=404, detail="source_not_found")
        return _assistant_env(result)

    @app.get("/api/assistant/sources/{source_id}/card")
    def assistant_source_card(source_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        nav, repo = _assistant_nav()
        return _assistant_env(nav.get_card_for_source(repo, source_id))

    @app.get("/api/assistant/sources/{source_id}/state")
    def assistant_source_state(source_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        nav, repo = _assistant_nav()
        return _assistant_env(nav.get_card_state(repo, _fresh_obsidian_config(), source_id))

    @app.get("/api/assistant/sources/{source_id}/related")
    def assistant_source_related(source_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        nav, repo = _assistant_nav()
        return _assistant_env(nav.get_related_sources(repo, source_id))

    @app.get("/api/assistant/cards/search")
    def assistant_cards_search(
        role: dict[str, str] = role_dep,
        q: str = Query(default=""),
        limit: int = Query(default=25),
        path_prefix: str | None = Query(default=None),
    ) -> dict[str, Any]:
        del role
        nav, repo = _assistant_nav()
        return _assistant_env(nav.search_cards(repo, q, limit=limit, path_prefix=path_prefix))

    @app.get("/api/assistant/cards/stale")
    def assistant_cards_stale(role: dict[str, str] = role_dep, limit: int = Query(default=25)) -> dict[str, Any]:
        del role
        nav, repo = _assistant_nav()
        return _assistant_env(nav.list_stale_cards(repo, limit=limit))

    @app.get("/api/assistant/cards/duplicates")
    def assistant_cards_duplicates(role: dict[str, str] = role_dep, limit: int = Query(default=25)) -> dict[str, Any]:
        del role
        nav, repo = _assistant_nav()
        return _assistant_env(nav.list_duplicate_cards(repo, limit=limit))

    @app.get("/api/assistant/cards/ambiguous")
    def assistant_cards_ambiguous(role: dict[str, str] = role_dep, limit: int = Query(default=25)) -> dict[str, Any]:
        del role
        nav, repo = _assistant_nav()
        return _assistant_env(nav.list_ambiguous_card_links(repo, limit=limit))

    @app.get("/api/assistant/card-source")
    def assistant_card_source(role: dict[str, str] = role_dep, note_rel_path: str = Query(default="")) -> dict[str, Any]:
        del role
        nav, repo = _assistant_nav()
        return _assistant_env(nav.get_source_for_card(repo, note_rel_path))

    @app.get("/api/assistant/recent-changes")
    def assistant_recent_changes(
        role: dict[str, str] = role_dep,
        limit: int = Query(default=25),
        event_types: str | None = Query(default=None),
    ) -> dict[str, Any]:
        del role
        nav, repo = _assistant_nav()
        types = tuple(t.strip() for t in event_types.split(",") if t.strip()) if event_types else None
        return _assistant_env(nav.recent_changes(repo, limit=limit, event_types=types))

    @app.get("/api/assistant/vault-note")
    def assistant_vault_note(
        role: dict[str, str] = role_dep,
        note_rel_path: str = Query(default=""),
        max_chars: int | None = Query(default=None),
    ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        from hb_assistant.obsidian_mcp import source_navigation as nav
        from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

        try:
            result = nav.get_vault_note(_fresh_obsidian_config(), note_rel_path, max_chars=max_chars)
        except ObsidianMcpToolError as exc:
            raise HTTPException(status_code=400, detail=str(getattr(exc, "code", exc))) from exc
        return _assistant_env(result)

    # ----- N8C-4 read-only claim navigation (local UI surface; claims stay OFF the remote MCP) -----
    def _claim_repo() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository

        return ClaimRepository(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/claims")
    def assistant_claims(
        role: dict[str, str] = role_dep,
        limit: int = Query(default=50),
        claim_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
        source_id: str | None = Query(default=None),
        note_rel_path: str | None = Query(default=None),
    ) -> dict[str, Any]:
        del role
        claims = _claim_repo().list_claims(limit=limit, claim_type=claim_type, status=status,
                                           source_id=source_id, note_rel_path=note_rel_path)
        return _assistant_env({"claims": claims, "count": len(claims)})

    @app.get("/api/assistant/sources/{source_id}/claims")
    def assistant_source_claims(source_id: str, role: dict[str, str] = role_dep,
                                limit: int = Query(default=50)) -> dict[str, Any]:
        del role
        claims = _claim_repo().get_claims_for_source(source_id, limit=limit)
        return _assistant_env({"source_id": source_id, "claims": claims, "count": len(claims)})

    @app.get("/api/assistant/cards/claims")
    def assistant_card_claims(role: dict[str, str] = role_dep,
                              note_rel_path: str = Query(default=""),
                              limit: int = Query(default=50)) -> dict[str, Any]:
        del role
        claims = _claim_repo().get_claims_for_note(note_rel_path, limit=limit)
        return _assistant_env({"note_rel_path": note_rel_path, "claims": claims, "count": len(claims)})

    # ----- N8C-5 read-only enrichment queue navigation (local UI surface; NO remote MCP, NO write) -----
    # Write operations (queue/claim/complete/fail) are driven only by the internal service +
    # `hb-assistant qwen-worker` CLI. A local write API is deferred (default-OFF flag
    # HB_ASSISTANT_ENRICHMENT_WORKER_API reserved for a later operator-only slice).
    def _enrichment_repo() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository

        return EnrichmentRepository(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/enrichment/jobs")
    def assistant_enrichment_jobs(
        role: dict[str, str] = role_dep,
        limit: int = Query(default=50),
        status: str | None = Query(default=None),
        job_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        del role
        jobs = _enrichment_repo().list_jobs(status=status, job_type=job_type, limit=limit)
        return _assistant_env({"jobs": jobs, "count": len(jobs)})

    @app.get("/api/assistant/enrichment/jobs/{job_id}")
    def assistant_enrichment_job(job_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        job = _enrichment_repo().get_job(job_id)
        if job is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="job_not_found")
        return _assistant_env({"job": job})

    @app.get("/api/assistant/enrichment/receipts")
    def assistant_enrichment_receipts(
        role: dict[str, str] = role_dep,
        job_id: str | None = Query(default=None),
        limit: int = Query(default=50),
    ) -> dict[str, Any]:
        del role
        receipts = _enrichment_repo().list_receipts(job_id=job_id, limit=limit)
        return _assistant_env({"receipts": receipts, "count": len(receipts)})

    # ----- N8C-6 read-only enrichment-review + context-pack navigation (local UI surface) -----
    # All GET, all-roles, read-only. The enrichment-review read model is DERIVED (no table). Context
    # packs are persisted; the BUILD/apply path is CLI-only (`hb-assistant context-pack build
    # --apply`) — there is intentionally no write route here.
    def _review_deps() -> tuple[Any, Any, Any]:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
        from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
        from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

        path = db_path or str(PathPolicy().get_db_path())
        return EnrichmentRepository(path), ClaimRepository(path), SourceIndexRepository(path)

    def _context_pack_repo() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository

        return ContextPackRepository(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/enrichment/review")
    def assistant_enrichment_review(
        role: dict[str, str] = role_dep,
        limit: int = Query(default=50),
        job_type: str | None = Query(default=None),
        review_tier: str | None = Query(default=None),
    ) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import enrichment_review as rv

        er, cr, sr = _review_deps()
        return _assistant_env(rv.list_enrichment_review_items(
            er, cr, sr, limit=limit, job_type=job_type, review_tier=review_tier))

    @app.get("/api/assistant/enrichment/review/{item_id}")
    def assistant_enrichment_review_item(item_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        from hb_assistant.obsidian_mcp import enrichment_review as rv

        er, cr, sr = _review_deps()
        item = rv.get_enrichment_review_item(er, cr, sr, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="review_item_not_found")
        return _assistant_env({"review_item": item})

    @app.get("/api/assistant/context-packs")
    def assistant_context_packs(
        role: dict[str, str] = role_dep,
        limit: int = Query(default=50),
        pack_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
    ) -> dict[str, Any]:
        del role
        packs = _context_pack_repo().list_packs(pack_type=pack_type, status=status, limit=limit)
        return _assistant_env({"context_packs": packs, "count": len(packs)})

    @app.get("/api/assistant/context-packs/{pack_id}")
    def assistant_context_pack(pack_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        pack = _context_pack_repo().get_pack(pack_id)
        if pack is None:
            raise HTTPException(status_code=404, detail="context_pack_not_found")
        return _assistant_env({"context_pack": pack})

    @app.get("/api/assistant/context-packs/{pack_id}/items")
    def assistant_context_pack_items(pack_id: str, role: dict[str, str] = role_dep,
                                     limit: int = Query(default=200)) -> dict[str, Any]:
        del role
        items = _context_pack_repo().list_items(pack_id, limit=limit)
        return _assistant_env({"pack_id": pack_id, "items": items, "count": len(items)})

    @app.get("/api/assistant/context-packs/{pack_id}/export")
    def assistant_context_pack_export(pack_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        from hb_assistant.obsidian_mcp import context_pack_builder as builder

        repo = _context_pack_repo()
        pack = repo.get_pack(pack_id)
        if pack is None:
            raise HTTPException(status_code=404, detail="context_pack_not_found")
        export = builder.export_context_pack(pack, repo.list_items(pack_id))
        return _assistant_env(export)

    # ----- N8C-7 read-only memory-node navigation (local UI surface) -----------------------
    # All GET, all-roles, read-only. Memory objects are DERIVED/COMPILED and ADVISORY (never claim
    # acceptance). The compile/apply path is CLI-only (`hb-assistant memory compile --apply`) — there
    # is intentionally no write route here.
    def _memory_repo() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository

        return MemoryRepository(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/memory/nodes")
    def assistant_memory_nodes(
        role: dict[str, str] = role_dep,
        limit: int = Query(default=50),
        node_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
        domain: str | None = Query(default=None),
    ) -> dict[str, Any]:
        del role
        nodes = _memory_repo().list_nodes(node_type=node_type, status=status, domain=domain,
                                          limit=limit)
        return _assistant_env({"memory_nodes": nodes, "count": len(nodes)})

    @app.get("/api/assistant/memory/search")
    def assistant_memory_search(role: dict[str, str] = role_dep, q: str = Query(default=""),
                                limit: int = Query(default=50)) -> dict[str, Any]:
        del role
        nodes = _memory_repo().search_nodes(q, limit=limit)
        return _assistant_env({"memory_nodes": nodes, "count": len(nodes)})

    @app.get("/api/assistant/memory/nodes/{node_id}")
    def assistant_memory_node(node_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        node = _memory_repo().get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="memory_node_not_found")
        return _assistant_env({"memory_node": node})

    @app.get("/api/assistant/memory/nodes/{node_id}/mentions")
    def assistant_memory_node_mentions(node_id: str, role: dict[str, str] = role_dep,
                                       limit: int = Query(default=200)) -> dict[str, Any]:
        del role
        mentions = _memory_repo().list_mentions(node_id, limit=limit)
        return _assistant_env({"node_id": node_id, "mentions": mentions, "count": len(mentions)})

    @app.get("/api/assistant/memory/nodes/{node_id}/compilations")
    def assistant_memory_node_compilations(node_id: str, role: dict[str, str] = role_dep,
                                           limit: int = Query(default=50)) -> dict[str, Any]:
        del role
        comps = _memory_repo().list_compilations(node_id, limit=limit)
        return _assistant_env({"node_id": node_id, "compilations": comps, "count": len(comps)})

    # ----- N8C-8 read-only decision / preference / open-loop navigation (local UI surface) ------
    # All GET, all-roles, read-only. Records are DERIVED/EXTRACTED and ADVISORY (candidate/unreviewed;
    # never claim acceptance, never an action). The extract/apply path is CLI-only
    # (`hb-assistant decision-memory extract --apply`) — there is intentionally no write route here.
    def _decision_memory_repo() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository

        return DecisionMemoryRepository(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/decisions")
    def assistant_decisions(role: dict[str, str] = role_dep, limit: int = Query(default=50),
                            decision_type: str | None = Query(default=None),
                            status: str | None = Query(default=None)) -> dict[str, Any]:
        del role
        records = _decision_memory_repo().list_decisions(decision_type=decision_type, status=status,
                                                         limit=limit)
        return _assistant_env({"decisions": records, "count": len(records)})

    @app.get("/api/assistant/decisions/{decision_id}")
    def assistant_decision(decision_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        record = _decision_memory_repo().get_decision(decision_id)
        if record is None:
            raise HTTPException(status_code=404, detail="decision_not_found")
        return _assistant_env({"decision": record})

    @app.get("/api/assistant/preferences")
    def assistant_preferences(role: dict[str, str] = role_dep, limit: int = Query(default=50),
                              preference_type: str | None = Query(default=None),
                              status: str | None = Query(default=None)) -> dict[str, Any]:
        del role
        records = _decision_memory_repo().list_preferences(preference_type=preference_type,
                                                          status=status, limit=limit)
        return _assistant_env({"preferences": records, "count": len(records)})

    @app.get("/api/assistant/preferences/{preference_id}")
    def assistant_preference(preference_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        record = _decision_memory_repo().get_preference(preference_id)
        if record is None:
            raise HTTPException(status_code=404, detail="preference_not_found")
        return _assistant_env({"preference": record})

    @app.get("/api/assistant/open-loops")
    def assistant_open_loops(role: dict[str, str] = role_dep, limit: int = Query(default=50),
                             open_loop_type: str | None = Query(default=None),
                             status: str | None = Query(default=None)) -> dict[str, Any]:
        del role
        records = _decision_memory_repo().list_open_loops(open_loop_type=open_loop_type,
                                                        status=status, limit=limit)
        return _assistant_env({"open_loops": records, "count": len(records)})

    @app.get("/api/assistant/open-loops/{open_loop_id}")
    def assistant_open_loop(open_loop_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        record = _decision_memory_repo().get_open_loop(open_loop_id)
        if record is None:
            raise HTTPException(status_code=404, detail="open_loop_not_found")
        return _assistant_env({"open_loop": record})

    # ----- N8C-9 read-only review queue / disposition ledger / effective state (local UI surface) ---
    # All GET, all-roles, read-only. Review items are review-OVERLAY snapshots over the advisory records;
    # dispositions are an append-only local ledger. There is intentionally NO write route here — the
    # build/apply and disposition/apply writers are CLI-only (`hb-assistant review build|disposition
    # --apply`). Reading a review item never mutates a source record or executes an action.
    def _review_repo() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.review_repository import ReviewRepository

        return ReviewRepository(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/review/items")
    def assistant_review_items(role: dict[str, str] = role_dep, limit: int = Query(default=50),
                               target_kind: str | None = Query(default=None),
                               review_type: str | None = Query(default=None),
                               review_state: str | None = Query(default=None),
                               effective_state: str | None = Query(default=None),
                               include_superseded: bool = Query(default=False)) -> dict[str, Any]:
        del role
        records = _review_repo().list_review_items(
            target_kind=target_kind, review_type=review_type, review_state=review_state,
            effective_state=effective_state, include_superseded=include_superseded, limit=limit)
        return _assistant_env({"review_items": records, "count": len(records)})

    @app.get("/api/assistant/review/items/{review_item_id}")
    def assistant_review_item(review_item_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        record = _review_repo().get_review_item(review_item_id)
        if record is None:
            raise HTTPException(status_code=404, detail="review_item_not_found")
        return _assistant_env({"review_item": record})

    @app.get("/api/assistant/review/items/{review_item_id}/dispositions")
    def assistant_review_item_dispositions(review_item_id: str, role: dict[str, str] = role_dep,
                                           limit: int = Query(default=50)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        repo = _review_repo()
        if repo.get_review_item(review_item_id) is None:
            raise HTTPException(status_code=404, detail="review_item_not_found")
        records = repo.list_dispositions(review_item_id, limit=limit)
        return _assistant_env({"review_item_id": review_item_id, "dispositions": records,
                               "count": len(records)})

    @app.get("/api/assistant/review/effective-state/{target_kind}/{target_id}")
    def assistant_review_effective_state(target_kind: str, target_id: str,
                                         role: dict[str, str] = role_dep,
                                         limit: int = Query(default=50)) -> dict[str, Any]:
        del role
        states = _review_repo().effective_state_for_target(target_kind, target_id, limit=limit)
        return _assistant_env({"target_kind": target_kind, "target_id": target_id,
                               "effective_states": states, "count": len(states)})

    @app.get("/api/assistant/review/summary")
    def assistant_review_summary(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _assistant_env({"summary": _review_repo().summary()})

    # ----- N8C-10 read-only review-aware intelligence projections (local UI surface) -----------
    # All GET, all-roles, read-only. Projections are materialized review-aware READ PRODUCTS; there is
    # intentionally NO write route here — the build/apply writer is CLI-only (`hb-assistant intelligence
    # build --apply`). Reading a projection never mutates a source/review record or executes an action.
    def _intelligence_repo() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.intelligence_projection_repository import (
            IntelligenceProjectionRepository,
        )

        return IntelligenceProjectionRepository(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/intelligence/projections")
    def assistant_intelligence_projections(role: dict[str, str] = role_dep, limit: int = Query(default=50),
                                           projection_type: str | None = Query(default=None),
                                           status: str | None = Query(default=None)) -> dict[str, Any]:
        del role
        records = _intelligence_repo().list_projections(projection_type=projection_type, status=status,
                                                        limit=limit)
        return _assistant_env({"projections": records, "count": len(records)})

    @app.get("/api/assistant/intelligence/projections/{projection_id}")
    def assistant_intelligence_projection(projection_id: str,
                                          role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        record = _intelligence_repo().get_projection(projection_id)
        if record is None:
            raise HTTPException(status_code=404, detail="projection_not_found")
        return _assistant_env({"projection": record})

    @app.get("/api/assistant/intelligence/projections/{projection_id}/items")
    def assistant_intelligence_projection_items(projection_id: str, role: dict[str, str] = role_dep,
                                                limit: int = Query(default=100),
                                                inclusion_state: str | None = Query(default=None),
                                                included_only: bool = Query(default=False)
                                                ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        repo = _intelligence_repo()
        if repo.get_projection(projection_id) is None:
            raise HTTPException(status_code=404, detail="projection_not_found")
        items = repo.list_projection_items(projection_id, inclusion_state=inclusion_state,
                                           included_only=included_only, limit=limit)
        return _assistant_env({"projection_id": projection_id, "items": items, "count": len(items)})

    @app.get("/api/assistant/intelligence/projections/{projection_id}/export")
    def assistant_intelligence_projection_export(projection_id: str, role: dict[str, str] = role_dep,
                                                 limit: int = Query(default=200),
                                                 included_only: bool = Query(default=True)
                                                 ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        from hb_assistant.obsidian_mcp import intelligence_projection_builder as ib
        from hb_assistant.obsidian_mcp.intelligence_projection_models import (
            ProjectionValidationError,
        )

        try:
            payload = ib.export_intelligence_projection(_intelligence_repo(),
                                                        projection_id=projection_id,
                                                        included_only=included_only, limit=limit)
        except ProjectionValidationError:
            raise HTTPException(status_code=404, detail="projection_not_found") from None
        return _assistant_env(payload)

    @app.get("/api/assistant/intelligence/summary")
    def assistant_intelligence_summary(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _assistant_env({"summary": _intelligence_repo().summary()})

    # ----- N8C-11 read-only review-aware research packets + citations (local UI surface) --------
    # All GET, all-roles, read-only. Packets are bounded, citation-backed answer-CONTEXT read products;
    # there is intentionally NO write route and NO answer-generation route here — the build/apply writer is
    # CLI-only (`hb-assistant research-packet build --apply`). Reading a packet never mutates a source /
    # review / projection record, generates no answer, and executes nothing.
    def _research_packet_repo() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository

        return ResearchPacketRepository(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/research-packets")
    def assistant_research_packets(role: dict[str, str] = role_dep, limit: int = Query(default=50),
                                   packet_type: str | None = Query(default=None),
                                   status: str | None = Query(default=None)) -> dict[str, Any]:
        del role
        records = _research_packet_repo().list_research_packets(packet_type=packet_type, status=status,
                                                               limit=limit)
        return _assistant_env({"packets": records, "count": len(records)})

    # NOTE: /summary is declared BEFORE /{packet_id} so the literal path is not shadowed by the
    # path-param route (FastAPI matches in declaration order).
    @app.get("/api/assistant/research-packets/summary")
    def assistant_research_packets_summary(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _assistant_env({"summary": _research_packet_repo().summary()})

    @app.get("/api/assistant/research-packets/{packet_id}")
    def assistant_research_packet(packet_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        record = _research_packet_repo().get_research_packet(packet_id)
        if record is None:
            raise HTTPException(status_code=404, detail="packet_not_found")
        return _assistant_env({"packet": record})

    @app.get("/api/assistant/research-packets/{packet_id}/items")
    def assistant_research_packet_items(packet_id: str, role: dict[str, str] = role_dep,
                                        limit: int = Query(default=100),
                                        answer_role: str | None = Query(default=None),
                                        included_only: bool = Query(default=False)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        repo = _research_packet_repo()
        if repo.get_research_packet(packet_id) is None:
            raise HTTPException(status_code=404, detail="packet_not_found")
        items = repo.list_research_packet_items(packet_id, answer_role=answer_role,
                                                included_only=included_only, limit=limit)
        return _assistant_env({"packet_id": packet_id, "items": items, "count": len(items)})

    @app.get("/api/assistant/research-packets/{packet_id}/citations")
    def assistant_research_packet_citations(packet_id: str, role: dict[str, str] = role_dep,
                                            limit: int = Query(default=200),
                                            packet_item_id: str | None = Query(default=None)
                                            ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        repo = _research_packet_repo()
        if repo.get_research_packet(packet_id) is None:
            raise HTTPException(status_code=404, detail="packet_not_found")
        citations = repo.list_research_packet_citations(packet_id, packet_item_id=packet_item_id,
                                                        limit=limit)
        return _assistant_env({"packet_id": packet_id, "citations": citations, "count": len(citations)})

    @app.get("/api/assistant/research-packets/{packet_id}/export")
    def assistant_research_packet_export(packet_id: str, role: dict[str, str] = role_dep,
                                         limit: int = Query(default=200),
                                         included_only: bool = Query(default=True)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        from hb_assistant.obsidian_mcp import research_packet_builder as pb
        from hb_assistant.obsidian_mcp.research_packet_models import ResearchPacketValidationError

        try:
            payload = pb.export_research_packet(_research_packet_repo(), packet_id=packet_id,
                                                included_only=included_only, limit=limit)
        except ResearchPacketValidationError:
            raise HTTPException(status_code=404, detail="packet_not_found") from None
        return _assistant_env(payload)

    # ----- N8C-12 read-only NAS source-root file connector (local UI surface) -----------------
    # All GET, all-roles, read-only. These expose INDEXED original source FILES (root-aware, cursor-paged,
    # bounded reads) — distinct from vault notes and generated source cards. There is intentionally NO
    # scan/reindex, card-generation, or write route here; reading never mutates a source/index record and
    # never triggers a live recursive filesystem scan (a bounded read opens exactly one configured file).
    def _source_connector_ctx() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.config import load_config
        from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

        repo = SourceIndexRepository(db_path or str(PathPolicy().get_db_path()))
        return repo, load_config()

    def _source_connector_error(exc: Exception) -> Any:
        from fastapi import HTTPException

        code = 404 if str(exc) == "source_not_found" else 400
        return HTTPException(status_code=code, detail=str(exc))

    # NOTE: ``/source-index/status`` (not ``/sources/status``) — the ``/sources/{source_id}`` nav route
    # (N8C-3) is declared earlier and would shadow a literal ``/sources/status``.
    @app.get("/api/assistant/source-index/status")
    def assistant_sources_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import source_connector_service as svc

        repo, config = _source_connector_ctx()
        return _assistant_env(svc.source_status(repo, config))

    @app.get("/api/assistant/source-roots")
    def assistant_source_roots(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import source_connector_service as svc

        repo, config = _source_connector_ctx()
        return _assistant_env(svc.list_source_roots(repo, config))

    @app.get("/api/assistant/source-files/search")
    def assistant_source_files_search(role: dict[str, str] = role_dep, query: str = Query(default=""),
                                      source_root_key: str | None = Query(default=None),
                                      file_ext: str | None = Query(default=None),
                                      limit: int = Query(default=25),
                                      cursor: str | None = Query(default=None)) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import source_connector_service as svc
        from hb_assistant.obsidian_mcp.source_connector_models import SourceConnectorValidationError

        repo, config = _source_connector_ctx()
        try:
            payload = svc.search_source_files(repo, config, query=query, source_root_key=source_root_key,
                                              file_ext=file_ext, limit=limit, cursor=cursor)
        except SourceConnectorValidationError as e:
            raise _source_connector_error(e) from None
        return _assistant_env(payload)

    @app.get("/api/assistant/source-files")
    def assistant_source_files_list(role: dict[str, str] = role_dep,
                                    source_root_key: str = Query(...),
                                    prefix: str | None = Query(default=None),
                                    limit: int = Query(default=25),
                                    cursor: str | None = Query(default=None)) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import source_connector_service as svc
        from hb_assistant.obsidian_mcp.source_connector_models import SourceConnectorValidationError

        repo, config = _source_connector_ctx()
        try:
            payload = svc.list_source_files(repo, config, source_root_key=source_root_key,
                                            prefix=prefix, limit=limit, cursor=cursor)
        except SourceConnectorValidationError as e:
            raise _source_connector_error(e) from None
        return _assistant_env(payload)

    @app.get("/api/assistant/source-files/{source_id}")
    def assistant_source_file_metadata(source_id: str,
                                       role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import source_connector_service as svc
        from hb_assistant.obsidian_mcp.source_connector_models import SourceConnectorValidationError

        repo, config = _source_connector_ctx()
        try:
            payload = svc.source_file_metadata(repo, config, source_id=source_id)
        except SourceConnectorValidationError as e:
            raise _source_connector_error(e) from None
        return _assistant_env(payload)

    @app.get("/api/assistant/source-files/{source_id}/read")
    def assistant_source_file_read(source_id: str, role: dict[str, str] = role_dep,
                                   max_chars: int = Query(default=4000),
                                   prefer_live: bool = Query(default=True)) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import source_connector_service as svc
        from hb_assistant.obsidian_mcp.source_connector_models import SourceConnectorValidationError

        repo, config = _source_connector_ctx()
        try:
            payload = svc.read_source_file(repo, config, source_id=source_id, max_chars=max_chars,
                                           prefer_live=prefer_live)
        except SourceConnectorValidationError as e:
            raise _source_connector_error(e) from None
        return _assistant_env(payload)

    # ----- N8C-14 read-only citation-safe answer drafts (local UI surface) ---------------------
    # All GET, all-roles, read-only. Drafts are bounded, citation-safe DRAFT artifacts built from N8C-11
    # research packets; there is intentionally NO write route, NO build/apply route, and NO answer-generation
    # route here — the build/apply writer is CLI-only (`hb-assistant answer-draft build --apply`). Reading a
    # draft never mutates a packet / projection / review / source record, generates no final/authoritative
    # answer, performs no live source file read, and executes nothing.
    def _answer_draft_repo() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.answer_draft_repository import AnswerDraftRepository

        return AnswerDraftRepository(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/answer-drafts")
    def assistant_answer_drafts(role: dict[str, str] = role_dep, limit: int = Query(default=50),
                                draft_type: str | None = Query(default=None),
                                status: str | None = Query(default=None),
                                packet_id: str | None = Query(default=None)) -> dict[str, Any]:
        del role
        records = _answer_draft_repo().list_answer_drafts(draft_type=draft_type, status=status,
                                                          packet_id=packet_id, limit=limit)
        return _assistant_env({"drafts": records, "count": len(records)})

    # NOTE: /summary is declared BEFORE /{draft_id} so the literal path is not shadowed by the
    # path-param route (FastAPI matches in declaration order).
    @app.get("/api/assistant/answer-drafts/summary")
    def assistant_answer_drafts_summary(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _assistant_env({"summary": _answer_draft_repo().summary()})

    @app.get("/api/assistant/answer-drafts/{draft_id}")
    def assistant_answer_draft(draft_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        record = _answer_draft_repo().get_answer_draft(draft_id)
        if record is None:
            raise HTTPException(status_code=404, detail="draft_not_found")
        return _assistant_env({"draft": record})

    @app.get("/api/assistant/answer-drafts/{draft_id}/sections")
    def assistant_answer_draft_sections(draft_id: str, role: dict[str, str] = role_dep,
                                        limit: int = Query(default=100),
                                        section_type: str | None = Query(default=None)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        repo = _answer_draft_repo()
        if repo.get_answer_draft(draft_id) is None:
            raise HTTPException(status_code=404, detail="draft_not_found")
        sections = repo.list_answer_draft_sections(draft_id, section_type=section_type, limit=limit)
        return _assistant_env({"draft_id": draft_id, "sections": sections, "count": len(sections)})

    @app.get("/api/assistant/answer-drafts/{draft_id}/citations")
    def assistant_answer_draft_citations(draft_id: str, role: dict[str, str] = role_dep,
                                         limit: int = Query(default=200),
                                         draft_section_id: str | None = Query(default=None)
                                         ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        repo = _answer_draft_repo()
        if repo.get_answer_draft(draft_id) is None:
            raise HTTPException(status_code=404, detail="draft_not_found")
        citations = repo.list_answer_draft_citations(draft_id, draft_section_id=draft_section_id,
                                                     limit=limit)
        return _assistant_env({"draft_id": draft_id, "citations": citations, "count": len(citations)})

    @app.get("/api/assistant/answer-drafts/{draft_id}/export")
    def assistant_answer_draft_export(draft_id: str, role: dict[str, str] = role_dep,
                                      limit: int = Query(default=200)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        from hb_assistant.obsidian_mcp import answer_draft_builder as ab
        from hb_assistant.obsidian_mcp.answer_draft_models import AnswerDraftValidationError

        try:
            payload = ab.export_answer_draft(_answer_draft_repo(), draft_id=draft_id, limit=limit)
        except AnswerDraftValidationError:
            raise HTTPException(status_code=404, detail="draft_not_found") from None
        return _assistant_env(payload)

    # ----- N8C-18 read-only feedback / review-loop recommendations (local UI surface) ------------
    # All GET, all-roles, read-only. Feedback records are bounded operator feedback on existing N8C artifacts;
    # recommendations are ADVISORY, operator-review-required review-loop suggestions. There is intentionally NO
    # write route and NO review-disposition route here — the `feedback add --apply` writer is CLI-only. Reading
    # feedback never mutates a review disposition, source/workflow/packet/draft/projection/context-pack/
    # decision/preference/open-loop record, stages nothing, and executes nothing.
    def _feedback_repo() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository

        return FeedbackRepository(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/feedback")
    def assistant_feedback(role: dict[str, str] = role_dep, limit: int = Query(default=50),
                           feedback_type: str | None = Query(default=None),
                           status: str | None = Query(default=None),
                           workflow_id: str | None = Query(default=None)) -> dict[str, Any]:
        del role
        records = _feedback_repo().list_feedback(feedback_type=feedback_type, status=status,
                                                 workflow_id=workflow_id, limit=limit)
        return _assistant_env({"feedback": records, "count": len(records)})

    # NOTE: /summary and /recommendations are declared BEFORE /{feedback_id} so the literal paths are not
    # shadowed by the path-param route (FastAPI matches in declaration order).
    @app.get("/api/assistant/feedback/summary")
    def assistant_feedback_summary(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _assistant_env({"summary": _feedback_repo().summary()})

    @app.get("/api/assistant/feedback/recommendations")
    def assistant_feedback_recommendations(role: dict[str, str] = role_dep, limit: int = Query(default=50),
                                           feedback_id: str | None = Query(default=None),
                                           recommendation_type: str | None = Query(default=None)
                                           ) -> dict[str, Any]:
        del role
        recs = _feedback_repo().list_recommendations(feedback_id, recommendation_type=recommendation_type,
                                                     limit=limit)
        return _assistant_env({"recommendations": recs, "count": len(recs)})

    @app.get("/api/assistant/feedback/{feedback_id}")
    def assistant_feedback_record(feedback_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        record = _feedback_repo().get_feedback(feedback_id)
        if record is None:
            raise HTTPException(status_code=404, detail="feedback_not_found")
        return _assistant_env({"feedback": record})

    @app.get("/api/assistant/feedback/{feedback_id}/targets")
    def assistant_feedback_targets(feedback_id: str, role: dict[str, str] = role_dep,
                                   limit: int = Query(default=100)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        repo = _feedback_repo()
        if repo.get_feedback(feedback_id) is None:
            raise HTTPException(status_code=404, detail="feedback_not_found")
        targets = repo.list_targets(feedback_id, limit=limit)
        return _assistant_env({"feedback_id": feedback_id, "targets": targets, "count": len(targets)})

    @app.get("/api/assistant/feedback/{feedback_id}/export")
    def assistant_feedback_export(feedback_id: str, role: dict[str, str] = role_dep,
                                  limit: int = Query(default=200)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        from hb_assistant.obsidian_mcp import feedback_service as fs
        from hb_assistant.obsidian_mcp.feedback_models import FeedbackValidationError

        try:
            payload = fs.export_feedback(_feedback_repo(), feedback_id=feedback_id, limit=limit)
        except FeedbackValidationError:
            raise HTTPException(status_code=404, detail="feedback_not_found") from None
        return _assistant_env(payload)

    # ----- N8C-19 read-only action-stage surface (local UI surface) -----------------------------
    # All GET, all-roles, read-only. An action stage is a bounded set of proposed follow-up CANDIDATES
    # derived from the N8C-17 workflow context + N8C-18 advisory feedback; every staged item is pinned to
    # not_executed / external_system=none / requires_operator_review=1. There is intentionally NO write route
    # and NO build/apply/execute route here — the `action-stage build --apply` writer is CLI-only. Reading a
    # stage never executes anything, never contacts an external system, and never mutates an upstream record.
    def _action_stage_repo() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.action_stage_repository import ActionStageRepository

        return ActionStageRepository(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/action-stages")
    def assistant_action_stages(role: dict[str, str] = role_dep, limit: int = Query(default=50),
                                stage_type: str | None = Query(default=None),
                                status: str | None = Query(default=None),
                                workflow_type: str | None = Query(default=None)) -> dict[str, Any]:
        del role
        stages = _action_stage_repo().list_stages(stage_type=stage_type, status=status,
                                                  workflow_type=workflow_type, limit=limit)
        return _assistant_env({"stages": stages, "count": len(stages)})

    # NOTE: /summary is declared BEFORE /{stage_id} so the literal path is not shadowed by the path-param
    # route (FastAPI matches in declaration order).
    @app.get("/api/assistant/action-stages/summary")
    def assistant_action_stages_summary(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _assistant_env({"summary": _action_stage_repo().summary()})

    @app.get("/api/assistant/action-stages/{stage_id}")
    def assistant_action_stage_record(stage_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        stage = _action_stage_repo().get_stage(stage_id)
        if stage is None:
            raise HTTPException(status_code=404, detail="stage_not_found")
        return _assistant_env({"stage": stage})

    @app.get("/api/assistant/action-stages/{stage_id}/items")
    def assistant_action_stage_items(stage_id: str, role: dict[str, str] = role_dep,
                                     staged_state: str | None = Query(default=None),
                                     limit: int = Query(default=100)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        repo = _action_stage_repo()
        if repo.get_stage(stage_id) is None:
            raise HTTPException(status_code=404, detail="stage_not_found")
        items = repo.list_items(stage_id, staged_state=staged_state, limit=limit)
        return _assistant_env({"stage_id": stage_id, "items": items, "count": len(items)})

    @app.get("/api/assistant/action-stages/{stage_id}/citations")
    def assistant_action_stage_citations(stage_id: str, role: dict[str, str] = role_dep,
                                         limit: int = Query(default=100)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        repo = _action_stage_repo()
        if repo.get_stage(stage_id) is None:
            raise HTTPException(status_code=404, detail="stage_not_found")
        citations = repo.list_citations(stage_id, limit=limit)
        return _assistant_env({"stage_id": stage_id, "citations": citations, "count": len(citations)})

    @app.get("/api/assistant/action-stages/{stage_id}/export")
    def assistant_action_stage_export(stage_id: str, role: dict[str, str] = role_dep,
                                      limit: int = Query(default=200)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        from hb_assistant.obsidian_mcp import action_stage_builder as asb
        from hb_assistant.obsidian_mcp.action_stage_models import ActionStageValidationError

        try:
            payload = asb.export_action_stage(_action_stage_repo(), stage_id=stage_id, limit=limit)
        except ActionStageValidationError:
            raise HTTPException(status_code=404, detail="stage_not_found") from None
        return _assistant_env(payload)

    # ----- N8C-20 read-only quality/evaluation surface (advisory findings) -----------------------
    # GET-only. Findings are ADVISORY: reading a quality run never accepts/rejects/defers/disposes/repairs
    # anything, never executes, never contacts an external system, and never mutates an upstream record.
    # There is NO build/apply/evaluate/repair route here — the `quality build --apply` writer is CLI-only,
    # and it writes only the five `assistant_quality_*` tables.
    def _quality_repo() -> Any:
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.quality_repository import QualityRepository

        return QualityRepository(db_path or str(PathPolicy().get_db_path()))

    @app.get("/api/assistant/quality")
    def assistant_quality(role: dict[str, str] = role_dep, limit: int = Query(default=50),
                          target_kind: str | None = Query(default=None),
                          target_id: str | None = Query(default=None),
                          status: str | None = Query(default=None)) -> dict[str, Any]:
        del role
        runs = _quality_repo().list_quality_runs(target_kind=target_kind, target_id=target_id,
                                                 status=status, limit=limit)
        return _assistant_env({"quality_runs": runs, "count": len(runs)})

    # NOTE: /summary is declared BEFORE /{quality_run_id} so the literal path is not shadowed.
    @app.get("/api/assistant/quality/summary")
    def assistant_quality_summary(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _assistant_env({"summary": _quality_repo().summary()})

    @app.get("/api/assistant/quality/{quality_run_id}")
    def assistant_quality_record(quality_run_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        run = _quality_repo().get_quality_run(quality_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="quality_run_not_found")
        return _assistant_env({"run": run})

    @app.get("/api/assistant/quality/{quality_run_id}/findings")
    def assistant_quality_findings(quality_run_id: str, role: dict[str, str] = role_dep,
                                   finding_type: str | None = Query(default=None),
                                   severity: str | None = Query(default=None),
                                   limit: int = Query(default=200)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        repo = _quality_repo()
        if repo.get_quality_run(quality_run_id) is None:
            raise HTTPException(status_code=404, detail="quality_run_not_found")
        findings = repo.list_findings(quality_run_id, finding_type=finding_type, severity=severity,
                                      limit=limit)
        return _assistant_env({"quality_run_id": quality_run_id, "findings": findings,
                               "count": len(findings)})

    @app.get("/api/assistant/quality/{quality_run_id}/targets")
    def assistant_quality_targets(quality_run_id: str, role: dict[str, str] = role_dep,
                                  limit: int = Query(default=200)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        repo = _quality_repo()
        if repo.get_quality_run(quality_run_id) is None:
            raise HTTPException(status_code=404, detail="quality_run_not_found")
        targets = repo.list_targets(quality_run_id, limit=limit)
        return _assistant_env({"quality_run_id": quality_run_id, "targets": targets, "count": len(targets)})

    @app.get("/api/assistant/quality/{quality_run_id}/export")
    def assistant_quality_export(quality_run_id: str, role: dict[str, str] = role_dep,
                                 limit: int = Query(default=200)) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        from hb_assistant.obsidian_mcp import quality_evaluator as qe
        from hb_assistant.obsidian_mcp.quality_models import QualityValidationError

        try:
            payload = qe.export_quality(_quality_repo(), quality_run_id=quality_run_id, limit=limit)
        except QualityValidationError:
            raise HTTPException(status_code=404, detail="quality_run_not_found") from None
        return _assistant_env(payload)

    # ----- N8C-15 read-only workflow contract + routing (local service surface) ------------------
    # Both GET, all-roles, read-only. `catalog` dumps the workflow registry (no DB). `route` resolves a
    # bounded workflow request to EXISTING N8C read surfaces and returns a normalized envelope. There is
    # intentionally NO POST/PUT/PATCH/DELETE, NO build/apply/execute route, and NO workflow-run persistence:
    # routing reads existing artifacts only, executes nothing, and writes nothing (N8C-15 adds no schema).
    @app.get("/api/assistant/workflows/catalog")
    def assistant_workflows_catalog(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp.workflow_registry import catalog as _wf_catalog

        return _assistant_env({"catalog": _wf_catalog()})

    @app.get("/api/assistant/workflows/route")
    def assistant_workflows_route(
        role: dict[str, str] = role_dep,
        workflow_type: str | None = Query(default=None),
        query: str | None = Query(default=None),
        objective: str | None = Query(default=None),
        domain: str | None = Query(default=None),
        project_key: str | None = Query(default=None),
        source_root_key: str | None = Query(default=None),
        draft_id: str | None = Query(default=None),
        packet_id: str | None = Query(default=None),
        projection_id: str | None = Query(default=None),
        context_pack_id: str | None = Query(default=None),
        review_item_id: str | None = Query(default=None),
        memory_node_id: str | None = Query(default=None),
        decision_id: str | None = Query(default=None),
        preference_id: str | None = Query(default=None),
        open_loop_id: str | None = Query(default=None),
    ) -> dict[str, Any]:
        del role
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.workflow_models import WorkflowRequest
        from hb_assistant.obsidian_mcp.workflow_router import WorkflowRouter

        request = WorkflowRequest.from_inputs(
            workflow_type=workflow_type, query=query, objective=objective, domain=domain,
            project_key=project_key, source_root_key=source_root_key, draft_id=draft_id,
            packet_id=packet_id, projection_id=projection_id, context_pack_id=context_pack_id,
            review_item_id=review_item_id, memory_node_id=memory_node_id, decision_id=decision_id,
            preference_id=preference_id, open_loop_id=open_loop_id, requested_by="api")
        router = WorkflowRouter(db_path or str(PathPolicy().get_db_path()))
        return _assistant_env({"workflow": router.route(request)})

    @app.post("/api/settings/obsidian-mcp/source-index/rebuild")
    def settings_obsidian_mcp_source_index_rebuild(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService(db_path=db_path).rebuild_source_index({})

    @app.post("/api/settings/obsidian-mcp/source-cards/retire")
    def settings_obsidian_mcp_source_cards_retire(
        request: ObsidianMcpRetireSourceCardsRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        # Non-destructive by default: apply=False is a dry-run; delete_files only acts with apply.
        return ObsidianMcpService(db_path=db_path).retire_source_cards(
            {"apply": request.apply, "delete_files": request.delete_files}
        )

    def _fresh_obsidian_config() -> Any:
        """Current on-disk Obsidian MCP config (no cache) — used to keep watcher start/status in
        sync with a just-PATCHed config without a backend restart."""
        from hb_assistant.obsidian_mcp.config import load_config as _load_obsidian_config

        return _load_obsidian_config()

    def _nas_watch_guard() -> dict[str, Any] | None:
        """Under NAS runtime the watcher is default-off; these routes lazily construct + start a
        watcher, bypassing the boot gate. Refuse on-demand START/RESTART/TEST unless the operator
        opts in deliberately with HB_NAS_ALLOW_WATCH=1 — single-writer ownership then rests on the
        watcher lease. Returns a blocked payload to short-circuit, or None to proceed."""
        from hb_assistant.config.db_storage_guard import nas_on_demand_watch_allowed

        if not nas_on_demand_watch_allowed():
            return {
                "running": False,
                "mode": "blocked",
                "reason_code": "NAS_ON_DEMAND_WATCH_BLOCKED",
                "detail": "NAS runtime is default-off; set HB_NAS_ALLOW_WATCH=1 to start the "
                          "watcher deliberately (single-writer ownership via the watcher lease).",
            }
        return None

    def _resolve_source_watcher() -> Any:
        """Return the lifespan watcher, lazily constructing one if watch was disabled at boot."""
        watcher = getattr(app.state, "source_watcher", None)
        if watcher is not None:
            return watcher
        from hb_assistant.config.path_policy import PathPolicy
        from hb_assistant.obsidian_mcp.source_watch import SourceWatcher

        _watch_db = str(db_path) if db_path else str(PathPolicy().get_db_path())
        watcher = SourceWatcher(_watch_db, _fresh_obsidian_config())
        app.state.source_watcher = watcher
        return watcher

    @app.get("/api/settings/obsidian-mcp/source-watch/status")
    def settings_obsidian_mcp_source_watch_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        watcher = getattr(app.state, "source_watcher", None)
        if watcher is None:
            return {"running": False, "mode": "stopped", "watch_enabled": False}
        return watcher.status(config=_fresh_obsidian_config())

    @app.post("/api/settings/obsidian-mcp/source-watch/start")
    async def settings_obsidian_mcp_source_watch_start(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        if (blocked := _nas_watch_guard()) is not None:
            return blocked
        watcher = _resolve_source_watcher()
        cfg = _fresh_obsidian_config()  # honor a just-PATCHed external_source_watch_enabled
        await asyncio.to_thread(watcher.start, config=cfg)
        return watcher.status(config=cfg)

    @app.post("/api/settings/obsidian-mcp/source-watch/stop")
    async def settings_obsidian_mcp_source_watch_stop(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        watcher = getattr(app.state, "source_watcher", None)
        if watcher is None:
            return {"running": False, "mode": "stopped"}
        await asyncio.to_thread(watcher.stop)
        return watcher.status(config=_fresh_obsidian_config())

    @app.post("/api/settings/obsidian-mcp/source-watch/restart")
    async def settings_obsidian_mcp_source_watch_restart(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        if (blocked := _nas_watch_guard()) is not None:
            return blocked
        watcher = _resolve_source_watcher()
        return await asyncio.to_thread(watcher.restart)

    @app.post("/api/settings/obsidian-mcp/source-watch/test-event")
    async def settings_obsidian_mcp_source_watch_test_event(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        if (blocked := _nas_watch_guard()) is not None:
            return blocked
        watcher = _resolve_source_watcher()
        return await asyncio.to_thread(watcher.test_event)

    @app.post("/api/settings/obsidian-mcp/source-watch/recover-stuck")
    async def settings_obsidian_mcp_source_watch_recover_stuck(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        if (blocked := _nas_watch_guard()) is not None:
            return blocked
        watcher = _resolve_source_watcher()
        return await asyncio.to_thread(watcher.recover_stuck)

    @app.post("/api/settings/obsidian-mcp/source-card/generate")
    def settings_obsidian_mcp_source_card_generate(
        request: ObsidianMcpGenerateSourceCardRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        from fastapi import HTTPException

        from hb_assistant.obsidian_mcp import ObsidianMcpService
        from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

        try:
            return ObsidianMcpService(db_path=db_path).generate_source_card(
                {"source_id": request.source_id, "overwrite": request.overwrite, "principal_kind": "local"}
            )
        except ObsidianMcpToolError as exc:
            # Surface tool guards (e.g. source_excluded_path / source_deleted) as a clean 422 with a
            # stable code, instead of an opaque 500. No vault note is written on these guards.
            raise HTTPException(status_code=422, detail=exc.code) from exc

    @app.post("/api/settings/obsidian-mcp/source-notes/refresh-stale")
    def settings_obsidian_mcp_source_notes_refresh(
        request: ObsidianMcpRefreshStaleRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService(db_path=db_path).refresh_stale_source_notes(
            {"max_updates": request.max_updates, "principal_kind": "local"}
        )

    @app.post("/api/settings/obsidian-mcp/source-card/summarize")
    def settings_obsidian_mcp_source_card_summarize(
        request: ObsidianMcpSummarizeSourceRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        from fastapi import HTTPException

        from hb_assistant.obsidian_mcp import ObsidianMcpService
        from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

        try:
            return ObsidianMcpService(db_path=db_path).summarize_source(
                {"source_id": request.source_id, "principal_kind": "local"}
            )
        except ObsidianMcpToolError as exc:
            raise HTTPException(status_code=422, detail=exc.code) from exc

    @app.post("/api/settings/obsidian-mcp/model/test")
    def settings_obsidian_mcp_model_test(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp import ObsidianMcpService
        from hb_assistant.obsidian_mcp.llm import validate_summary_model

        return validate_summary_model(ObsidianMcpService().get_config())

    @app.get("/api/settings/obsidian-mcp/tools")
    def settings_obsidian_mcp_tools(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().tools()

    @app.get("/api/settings/obsidian-mcp/mutations")
    def settings_obsidian_mcp_mutations(
        limit: int = Query(default=20, ge=1, le=100),
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().mutations(limit)

    @app.get("/api/settings/obsidian-mcp/read-receipts")
    def settings_obsidian_mcp_read_receipts(
        limit: int = Query(default=20, ge=1, le=100),
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().read_receipts(limit)

    @app.post("/api/settings/obsidian-mcp/write-readiness")
    def settings_obsidian_mcp_write_readiness(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().write_readiness()

    @app.post("/api/settings/obsidian-mcp/enable")
    def settings_obsidian_mcp_enable(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().lifecycle("enable")

    @app.post("/api/settings/obsidian-mcp/disable")
    def settings_obsidian_mcp_disable(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().lifecycle("disable")

    @app.post("/api/settings/obsidian-mcp/restart")
    def settings_obsidian_mcp_restart(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().lifecycle("restart")

    @app.post("/api/settings/obsidian-mcp/test/list-directory")
    def settings_obsidian_mcp_test_list_directory(
        request: ObsidianMcpListDirectoryRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp.service import ObsidianMcpService, safe_tool_response

        svc = ObsidianMcpService()
        return safe_tool_response(
            svc.list_directory, {**request.model_dump(exclude_none=True), "operator_mode": True}
        )

    @app.post("/api/settings/obsidian-mcp/test/search")
    def settings_obsidian_mcp_test_search(
        request: ObsidianMcpSearchRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp.service import ObsidianMcpService, safe_tool_response

        svc = ObsidianMcpService()
        return safe_tool_response(
            svc.search_vault, {**request.model_dump(exclude_none=True), "operator_mode": True}
        )

    @app.post("/api/settings/obsidian-mcp/test/read-file")
    def settings_obsidian_mcp_test_read_file(
        request: ObsidianMcpReadFileRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp.service import ObsidianMcpService, safe_tool_response

        svc = ObsidianMcpService()
        return safe_tool_response(
            svc.read_file, {**request.model_dump(exclude_none=True), "operator_mode": True}
        )

    @app.post("/api/settings/obsidian-mcp/test/write-smoke")
    def settings_obsidian_mcp_test_write_smoke(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp.service import ObsidianMcpService, safe_tool_response

        svc = ObsidianMcpService()
        return safe_tool_response(lambda _args: svc.write_smoke_test(), {})

    @app.get("/api/settings/obsidian-mcp/grok-config")
    def settings_obsidian_mcp_grok_config(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().grok_config()

    # --- Phase 3A: OAuth 2.1 / PKCE for Grok Remote MCP ---------------------
    # UI status route (role-gated). The public OAuth protocol + discovery routes
    # below are intentionally unauthenticated so Grok/the browser can reach them
    # via the Cloudflare tunnel; they are declared before the MCP mount so they
    # win over the catch-all mounted MCP app.
    @app.get("/api/settings/obsidian-mcp/oauth")
    def settings_obsidian_mcp_oauth(request: Request, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().oauth_status(request_base=str(request.base_url).rstrip("/"))

    @app.get("/api/settings/obsidian-mcp/llm-chat/status")
    def settings_obsidian_mcp_llm_chat_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().llm_chat_status()

    @app.get("/api/settings/obsidian-mcp/chatgpt")
    def settings_obsidian_mcp_chatgpt(request: Request, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().chatgpt_status(base=str(request.base_url).rstrip("/"))

    @app.post("/api/settings/obsidian-mcp/chatgpt/readiness-check")
    def settings_obsidian_mcp_chatgpt_readiness(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return ObsidianMcpService().chatgpt_readiness()

    def _oauth_base_url(request: Request) -> str:
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        config = ObsidianMcpService().get_config()
        if config.public_base_url:
            return config.public_base_url.rstrip("/")
        return str(request.base_url).rstrip("/")

    def _oauth_enabled() -> bool:
        from hb_assistant.obsidian_mcp import ObsidianMcpService

        return bool(ObsidianMcpService().get_config().oauth_enabled)

    async def _oauth_form_params(request: Request) -> dict[str, str]:
        from urllib.parse import parse_qsl

        body = await request.body()
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                data = json.loads(body or b"{}")
            except (json.JSONDecodeError, ValueError):
                return {}
            if not isinstance(data, dict):
                return {}
            return {str(k): str(v) for k, v in data.items()}
        return dict(parse_qsl(body.decode("utf-8"), keep_blank_values=True))

    @app.get("/.well-known/oauth-authorization-server")
    def oauth_authorization_server_metadata(request: Request) -> dict[str, Any]:
        from hb_assistant.obsidian_mcp.oauth_store import authorization_server_metadata

        return authorization_server_metadata(_oauth_base_url(request))

    @app.get("/.well-known/openid-configuration")
    def oauth_openid_configuration(request: Request) -> dict[str, Any]:
        from hb_assistant.obsidian_mcp.oauth_store import authorization_server_metadata

        return authorization_server_metadata(_oauth_base_url(request))

    @app.get("/.well-known/oauth-protected-resource")
    def oauth_protected_resource_metadata(request: Request) -> dict[str, Any]:
        from hb_assistant.obsidian_mcp.oauth_store import protected_resource_metadata

        return protected_resource_metadata(_oauth_base_url(request))

    @app.get("/.well-known/oauth-protected-resource/mcp")
    def oauth_protected_resource_metadata_mcp(request: Request) -> dict[str, Any]:
        from hb_assistant.obsidian_mcp.oauth_store import protected_resource_metadata

        return protected_resource_metadata(_oauth_base_url(request))

    @app.post("/oauth/register")
    async def oauth_register(request: Request) -> Any:
        from fastapi.responses import JSONResponse

        from hb_assistant.obsidian_mcp import ObsidianMcpService
        from hb_assistant.obsidian_mcp.oauth_store import OAuthError, register_client

        config = ObsidianMcpService().get_config()
        if not config.oauth_enabled:
            return JSONResponse({"error": "invalid_request", "error_description": "oauth disabled"}, status_code=403)
        if not config.dynamic_client_registration_enabled:
            return JSONResponse({"error": "invalid_request", "error_description": "dynamic client registration disabled"}, status_code=403)
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            return JSONResponse({"error": "invalid_client_metadata", "error_description": "JSON object required"}, status_code=400)
        try:
            return JSONResponse(register_client(payload), status_code=201)
        except OAuthError as exc:
            return JSONResponse({"error": exc.error, "error_description": exc.description}, status_code=400)

    @app.get("/oauth/authorize")
    def oauth_authorize_form(
        request: Request,
        response_type: str = Query(default=""),
        client_id: str = Query(default=""),
        redirect_uri: str = Query(default=""),
        scope: str = Query(default=""),
        state: str = Query(default=""),
        code_challenge: str = Query(default=""),
        code_challenge_method: str = Query(default=""),
        resource: str = Query(default=""),
    ) -> Any:
        from fastapi.responses import HTMLResponse

        from hb_assistant.obsidian_mcp import ObsidianMcpService
        from hb_assistant.obsidian_mcp.oauth_store import (
            OAuthError,
            get_client,
            mcp_resource,
            validate_authorize_request,
        )

        if not _oauth_enabled():
            return HTMLResponse(_oauth_error_html("oauth_disabled", "OAuth is not enabled on this server."), status_code=403)
        base_url = _oauth_base_url(request)
        resolved_resource = resource or mcp_resource(base_url)
        try:
            scopes = validate_authorize_request(
                response_type=response_type,
                client_id=client_id,
                redirect_uri=redirect_uri,
                scope=scope,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                resource=resolved_resource,
                base_url=base_url,
            )
        except OAuthError as exc:
            return HTMLResponse(_oauth_error_html(exc.error, exc.description), status_code=400)
        config = ObsidianMcpService().get_config()
        oauth_client = get_client(client_id)
        html = _oauth_consent_html(
            scopes=scopes,
            vault_root=config.vault_root,
            write_enabled=bool(config.writes_enabled and config.vault_markdown_write_enabled),
            params={
                "response_type": response_type,
                "client_id": client_id,
                "client_name": oauth_client.client_name if oauth_client else client_id,
                "redirect_uri": redirect_uri,
                "scope": scope,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method,
                "resource": resolved_resource,
                "public_base_url": base_url,
            },
        )
        return HTMLResponse(html)

    @app.post("/oauth/authorize")
    async def oauth_authorize_submit(request: Request) -> Any:
        from fastapi.responses import HTMLResponse, RedirectResponse

        from hb_assistant.obsidian_mcp.oauth_store import (
            OAuthError,
            create_authorization_code,
            redirect_with,
            validate_authorize_request,
        )

        if not _oauth_enabled():
            return HTMLResponse(_oauth_error_html("oauth_disabled", "OAuth is not enabled on this server."), status_code=403)
        params = await _oauth_form_params(request)
        redirect_uri = params.get("redirect_uri", "")
        state = params.get("state", "")
        base_url = _oauth_base_url(request)
        from hb_assistant.obsidian_mcp.oauth_store import mcp_resource

        resource = params.get("resource", "") or mcp_resource(base_url)
        try:
            validate_authorize_request(
                response_type=params.get("response_type", ""),
                client_id=params.get("client_id", ""),
                redirect_uri=redirect_uri,
                scope=params.get("scope", ""),
                code_challenge=params.get("code_challenge", ""),
                code_challenge_method=params.get("code_challenge_method", ""),
                resource=resource,
                base_url=base_url,
            )
        except OAuthError as exc:
            return HTMLResponse(_oauth_error_html(exc.error, exc.description), status_code=400)
        if params.get("decision", "approve") != "approve":
            return RedirectResponse(redirect_with(redirect_uri, {"error": "access_denied", "state": state}), status_code=302)
        code = create_authorization_code(
            client_id=params.get("client_id", ""),
            redirect_uri=redirect_uri,
            scope=params.get("scope", ""),
            code_challenge=params.get("code_challenge", ""),
            code_challenge_method=params.get("code_challenge_method", ""),
            resource=resource,
            base_url=base_url,
        )
        return RedirectResponse(redirect_with(redirect_uri, {"code": code, "state": state}), status_code=302)

    @app.post("/oauth/token")
    async def oauth_token(request: Request) -> Any:
        from fastapi.responses import JSONResponse

        from hb_assistant.obsidian_mcp.oauth_store import (
            OAuthError,
            consume_authorization_code,
            issue_access_token,
        )

        if not _oauth_enabled():
            return JSONResponse({"error": "invalid_request", "error_description": "oauth disabled"}, status_code=403)
        params = await _oauth_form_params(request)
        if params.get("grant_type", "") != "authorization_code":
            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
        try:
            scopes, client_id, resource = consume_authorization_code(
                raw_code=params.get("code", ""),
                client_id=params.get("client_id", ""),
                redirect_uri=params.get("redirect_uri", ""),
                code_verifier=params.get("code_verifier", ""),
                resource=params.get("resource", "") or None,
                base_url=_oauth_base_url(request),
            )
            token = issue_access_token(scopes=scopes, client_id=client_id, resource=resource)
        except OAuthError as exc:
            return JSONResponse({"error": exc.error, "error_description": exc.description}, status_code=400)
        return JSONResponse(token)

    # Prompt 20: real local JSON preferences persistence (FPR-016), mirroring daily_brief pattern.
    def _prefs_config_path() -> Path:
        pp = PathPolicy()
        base = pp.get_app_support() / "analytics"
        base.mkdir(parents=True, exist_ok=True)
        return base / "ui_preferences.json"

    DEFAULT_PREFS: dict[str, Any] = {
        "theme": "dark",
        "default_landing_page": "Today",
        "show_daily_brief_on_today": True,
        "followed_projects": [],
    }

    def _load_prefs() -> dict[str, Any]:
        p = _prefs_config_path()
        prefs = dict(DEFAULT_PREFS)
        if p.exists():
            try:
                loaded = json.loads(p.read_text())
                if isinstance(loaded, dict):
                    prefs.update({k: v for k, v in loaded.items() if k in DEFAULT_PREFS})
            except Exception:
                pass
        return prefs

    def _save_prefs(updates: dict[str, Any]) -> dict[str, Any]:
        current = _load_prefs()
        for k, v in updates.items():
            if k in DEFAULT_PREFS:
                current[k] = v
        current["schema_version"] = 1
        _prefs_config_path().write_text(json.dumps(current, indent=2))
        return current

    @app.get("/api/settings/preferences")
    def settings_preferences(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        prefs = _load_prefs()
        return {
            **prefs,
            "note": "Preferences are local-first; persisted under Application Support (Prompt 20).",
            "guardrails": _guardrails(),
        }

    @app.patch("/api/settings/preferences")
    def patch_settings_preferences(
        patch: SettingsPreferencesPatch,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        applied = _save_prefs(patch.model_dump(exclude_none=True))
        return {
            "ok": True,
            "applied": applied,
            "guardrails": _guardrails(),
        }

    @app.get("/api/settings/admin-sync")
    def settings_admin_sync(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        return ConnectionSetupService(db_path=db_path).list_pending_approvals()

    @app.patch("/api/settings/admin")
    def patch_settings_admin(
        patch: SettingsAdminPatch,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_admin_role(role)
        return {
            "ok": True,
            "applied": patch.model_dump(exclude_none=True),
            "note": "Admin sync controls (rate-limit/backoff) applied locally for scheduling.",
            "guardrails": _guardrails(),
        }

    # Prompt 11 / UI-11 — Admin / Data Confidence (source/sync, workflow/jobs, evidence/guardrails,
    # retrieval/AI quality, permissions/governance, data completeness).
    # These are support surfaces. Detailed diagnostics here; primary screens (Today/Projects/My Items)
    # show only compact badges and links to /admin. Admin role required for the detailed views.
    # All responses follow the read-model contract: metric cards with IDs/names/values/freshness/confidence/
    # sources/drilldowns + guardrails + advisory (no raw sensitive fields, no determinations).
    @app.get("/api/admin")
    def admin_root(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_admin_confidence_summary()

    @app.get("/api/admin/source-sync-health")
    def admin_source_sync_health(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_admin_source_sync_health()

    @app.get("/api/admin/workflow-job-health")
    def admin_workflow_job_health(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_admin_workflow_job_health()

    @app.get("/api/admin/evidence-guardrails")
    def admin_evidence_guardrails(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_admin_evidence_guardrails()

    @app.get("/api/admin/retrieval-ai-quality")
    def admin_retrieval_ai_quality(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_admin_retrieval_ai_quality()

    @app.get("/api/admin/permissions-governance")
    def admin_permissions_governance(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_admin_permissions_governance()

    @app.get("/api/admin/data-completeness")
    def admin_data_completeness(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        from hb_assistant.construction.analytics.service import AnalyticsService

        return AnalyticsService(db_path=db_path).build_admin_data_completeness()

    def _admin_schema_db_path() -> str:
        return db_path or str(PathPolicy().get_db_path())

    def _admin_schema_object_counts(schema_db: str) -> dict[str, int]:
        from hb_assistant.store.db_posture import schema_object_counts

        return schema_object_counts(schema_db)

    def _schedule_v65_physical_status(schema_db: str) -> dict[str, object]:
        from hb_assistant.store.connection import get_connection
        from hb_assistant.store.schedule_schema_verify import schedule_v65_physical_report

        conn = get_connection(schema_db)
        try:
            return schedule_v65_physical_report(conn)
        finally:
            conn.close()

    @app.get("/api/admin/schema/status")
    def admin_schema_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        schema_db = _admin_schema_db_path()
        current = _schema_version(schema_db)
        physical = _schedule_v65_physical_status(schema_db)
        counts = _admin_schema_object_counts(schema_db)
        return {
            "schema_version": current,
            "schema_expected": LATEST_SCHEMA_VERSION,
            "schema_ready": current >= LATEST_SCHEMA_VERSION,
            **counts,
            **physical,
        }

    @app.get("/api/admin/db/status")
    def admin_db_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        from hb_assistant.store.db_posture import collect_db_posture

        schema_db = _admin_schema_db_path()
        return collect_db_posture(
            schema_db,
            background_worker_mode=getattr(app.state, "background_worker_mode", "enabled"),
            startup_migration_performed=bool(getattr(app.state, "startup_migration_performed", False)),
        )

    @app.post("/api/admin/schema/migrate")
    def admin_schema_migrate(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        schema_db = _admin_schema_db_path()
        before = _schema_version(schema_db)
        physical_before = _schedule_v65_physical_status(schema_db)
        # NF-F-001 (N-A2) / NF-AUD-004: the admin migrate route mints an authorization from an
        # ENFORCED ADMIN capability. ``acquire_admin_capability`` re-verifies the admin role itself
        # (raising if not admin), so the authority is not merely caller-asserted; ``authorize_migration``
        # binds it to the resolved target + device/inode, returning ``None`` for a non-managed target.
        from hb_assistant.store.migration_authorization import (
            acquire_admin_capability,
            authorize_migration,
        )

        _migrate_auth = authorize_migration(
            acquire_admin_capability(role),
            resolved_path=str(schema_db),
            expected_origin_version=before,
            target_version=LATEST_SCHEMA_VERSION,
        )
        after = int(SQLiteMigrator(db_path=schema_db).apply(authorization=_migrate_auth))
        physical_after = _schedule_v65_physical_status(schema_db)
        counts = _admin_schema_object_counts(schema_db)
        return {
            "schema_before": before,
            "schema_after": after,
            "schema_expected": LATEST_SCHEMA_VERSION,
            "schema_ready": after >= LATEST_SCHEMA_VERSION,
            **counts,
            "migration_name": f"v{after}_schema",
            "schedule_v65_physical_before": physical_before,
            "schedule_v65_physical_after": physical_after,
        }

    # Prompt A — normalized frontend contract routes under /api/onboarding/readiness and
    # /api/settings/connections/* (plus data-quality). These coexist with (do not replace)
    # all prior root-level routes so existing tests and any legacy callers continue to work.
    # All responses are safe; no tokens/secrets/raw payloads/paths are emitted.
    # Readiness and connection setup actions never start live sync.

    @app.get("/api/onboarding/readiness")
    def onboarding_readiness(role: dict[str, str] = role_dep) -> dict[str, Any]:
        # Delegate to the service for the canonical mapping (7 auth states + 5 onboarding states).
        # Response shape matches the contract in the planning package.
        del role
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().build_readiness(db_path=db_path)

    @app.get("/api/settings/connections/accounts")
    def settings_connections_accounts(role: dict[str, str] = role_dep) -> dict[str, Any]:
        # Delegate for the normalized account connection summaries (safe, no secrets).
        del role
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().build_account_summaries()

    @app.post("/api/settings/connections/auth/refresh")
    def settings_connections_auth_refresh(
        request: dict[str, Any] | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        # Delegates to service (safe stub behavior: status check + optimistic transition for
        # stale-refreshable; never starts sync or login flows).
        del role
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        sources = (request or {}).get("sources") or ["graph", "procore"]
        return AuthOnboardingService().attempt_auth_refresh(list(sources))

    # Normalized project connection routes under the settings/connections/projects family.
    # These delegate to the same ConnectionSetupService as the legacy paths to guarantee
    # identical behavior and guardrails (preview/save never start sync; admin approval is explicit).
    @app.post("/api/settings/connections/projects/preview")
    def settings_connections_projects_preview(
        request: ConnectionSetupRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        # Return the established safe preview payload (identical to legacy /connections/preview).
        # The ProjectConnectionPreviewResponse model documents the normalized contract shape.
        del role
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        return ConnectionSetupService(db_path=db_path).preview_connection(
            request.model_dump(exclude_none=True)
        )

    @app.post("/api/settings/connections/projects/save")
    def settings_connections_projects_save(
        request: ConnectionSetupRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        return ConnectionSetupService(db_path=db_path).save_connection(
            request.model_dump(exclude_none=True)
        )

    @app.get("/api/settings/connections/projects")
    def settings_connections_projects(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        conn = ConnectionSetupService(db_path=db_path)
        return {
            "pending_approvals": conn.list_pending_approvals(),
            "note": "Project connections managed via /api/settings/connections/projects/preview and /save (Prompt A normalized contract). Legacy paths preserved for compatibility.",
            "guardrails": _guardrails(),
        }

    # Admin approval surfaces under the normalized admin family.
    @app.post("/api/settings/connections/admin/{connection_id}/approve-first-sync")
    def settings_connections_admin_approve(
        connection_id: str,
        role: dict[str, str] = role_dep,
    ) -> AdminApprovalResponse:
        require_admin_role(role)
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        raw = ConnectionSetupService(db_path=db_path).approve_first_sync(connection_id)
        return AdminApprovalResponse(**{k: raw.get(k) for k in AdminApprovalResponse.model_fields if k in raw} | {"guardrails": raw.get("guardrails")})  # type: ignore[arg-type]

    # Prompt F: normalized reject sibling (additive; admin only; first_sync_triggered remains false)
    @app.post("/api/settings/connections/admin/{connection_id}/reject-first-sync")
    def settings_connections_admin_reject(
        connection_id: str,
        role: dict[str, str] = role_dep,
    ) -> AdminApprovalResponse:
        require_admin_role(role)
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        raw = ConnectionSetupService(db_path=db_path).reject_first_sync(connection_id)
        # Reuse the approval response shape for simplicity (kind distinguishes approved vs rejected)
        return AdminApprovalResponse(**{k: raw.get(k) for k in AdminApprovalResponse.model_fields if k in raw} | {"guardrails": raw.get("guardrails")})  # type: ignore[arg-type]

    # Prompt G: Data-quality summary (all roles) and detail (admin). Safe projections; no raw content.
    # Implementation delegates to ConnectionSetupService (post-F approval + freshness aware) so the
    # indicator and detail reflect saved project connections, pending/approved/rejected state, and
    # last sync timestamps. Conservative degrade if freshness cannot be proven. The broad admin
    # confidence summary (phase gates etc.) remains available under /api/admin/* surfaces.
    @app.get("/api/settings/data-quality/summary")
    def settings_data_quality_summary(role: dict[str, str] = role_dep) -> DataQualitySummary:
        del role
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        dq = ConnectionSetupService(db_path=db_path).build_data_quality_summary()
        return DataQualitySummary(
            status=dq.get("status", "unknown"),
            label=dq.get("label", "Data Quality"),
            last_updated_at=dq.get("last_updated_at"),
            message=dq.get("message"),
            admin_detail_available=bool(dq.get("admin_detail_available", True)),
        )

    @app.get("/api/settings/data-quality/detail")
    def settings_data_quality_detail(role: dict[str, str] = role_dep) -> DataQualityDetail:
        require_admin_role(role)
        from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService

        dq = ConnectionSetupService(db_path=db_path).build_data_quality_detail()
        return DataQualityDetail(
            surface=dq.get("surface", "analytics.settings.data_quality.detail"),
            generated_utc=dq.get("generated_utc"),
            summary=dq.get("summary"),
            sources=dq.get("sources", []),
            attention_items=dq.get("attention_items", []),
            advisory_notes=dq.get("advisory_notes", []),
            guardrails=dq.get("guardrails"),
        )

    # Forecasting — read-only package browser (Implementation Phase 1).
    # All routes are viewer-readable and delegate to ForecastCatalogService, which performs
    # pure file reads over explicitly configured package roots (env HB_FORECAST_PACKAGE_ROOTS).
    # Zero DB access, zero writes. Errors are mapped to safe codes with NO path/internal leakage.
    def _forecast_service() -> Any:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_catalog import (
            ForecastCatalogError,
            ForecastCatalogService,
        )
        from hb_assistant.construction.analytics.forecast_runtime_config import (
            resolve_db_path,
            resolve_package_roots,
        )

        # Runtime wiring (Phase 6): explicit create_app arg > env > settings-file > None.
        roots = resolve_package_roots(None)
        try:
            return ForecastCatalogService(
                package_roots=roots, db_path=resolve_db_path(db_path)
            )
        except ForecastCatalogError:
            # Misconfigured / unset roots — fail closed with a generic, path-free message.
            raise HTTPException(status_code=503, detail="forecast_packages_not_configured")

    def _forecast_call(fn: Any, *args: Any) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_catalog import ForecastCatalogError

        try:
            return fn(*args)
        except ForecastCatalogError as exc:
            if str(exc).startswith("unknown package_id"):
                raise HTTPException(status_code=404, detail="forecast_package_not_found")
            raise HTTPException(status_code=500, detail="forecast_catalog_error")

    @app.get("/api/forecast/projects")
    def forecast_projects(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        svc = _forecast_service()
        return _forecast_call(svc.list_projects)

    @app.get("/api/forecast/projects/{project_key}/periods")
    def forecast_periods(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        svc = _forecast_service()
        return _forecast_call(svc.list_periods, project_key)

    @app.get("/api/forecast/projects/{project_key}/periods/{period}/packages")
    def forecast_packages(
        project_key: str, period: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        svc = _forecast_service()
        return _forecast_call(svc.list_packages, project_key, period)

    @app.get("/api/forecast/packages/{package_id}/summary")
    def forecast_package_summary(package_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        svc = _forecast_service()
        return _forecast_call(svc.read_package_summary, package_id)

    @app.get("/api/forecast/packages/{package_id}/validation")
    def forecast_package_validation(package_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        svc = _forecast_service()
        return _forecast_call(svc.read_validation_status, package_id)

    @app.get("/api/forecast/packages/{package_id}/manifest")
    def forecast_package_manifest(package_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        svc = _forecast_service()
        return _forecast_call(svc.read_manifest, package_id)

    @app.get("/api/forecast/packages/{package_id}/review-items")
    def forecast_package_review_items(package_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        svc = _forecast_service()
        return _forecast_call(svc.read_review_items, package_id)

    @app.get("/api/forecast/packages/{package_id}/forecast-rows")
    def forecast_package_rows(package_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        svc = _forecast_service()
        return _forecast_call(svc.read_forecast_rows, package_id)

    # Forecast Review surfaces (Implementation Phase 5). Read-only over package files.
    @app.get("/api/forecast/packages/{package_id}/monthly")
    def forecast_package_monthly(package_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        svc = _forecast_service()
        return _forecast_call(svc.read_monthly_forecast, package_id)

    @app.get("/api/forecast/packages/{package_id}/probability")
    def forecast_package_probability(package_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        svc = _forecast_service()
        return _forecast_call(svc.read_probability, package_id)

    @app.get("/api/forecast/packages/{package_id}/risk-register")
    def forecast_package_risk_register(package_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        svc = _forecast_service()
        return _forecast_call(svc.read_risk_register, package_id)

    @app.get("/api/forecast/packages/{package_id}/top-risks")
    def forecast_package_top_risks(package_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        svc = _forecast_service()
        return _forecast_call(svc.read_top_risks, package_id)

    # Forecast configuration — read-only viewer over the v60 config-registry snapshot
    # (Implementation Phase 2). Read-only DB access (mode=ro); viewer-readable; fail-closed.
    def _forecast_config_service() -> Any:
        from hb_assistant.construction.analytics.forecast_config_catalog import (
            ForecastConfigCatalogService,
        )
        from hb_assistant.construction.analytics.forecast_runtime_config import resolve_db_path

        return ForecastConfigCatalogService(db_path=resolve_db_path(db_path))

    def _forecast_config_call(fn: Any, *args: Any) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_config_catalog import ForecastConfigError

        try:
            return fn(*args)
        except ForecastConfigError as exc:
            msg = str(exc)
            if msg.startswith("unknown snapshot_id"):
                raise HTTPException(status_code=404, detail="forecast_config_snapshot_not_found")
            if msg.startswith("unknown item_id"):
                raise HTTPException(status_code=404, detail="forecast_config_item_not_found")
            # DB missing / schema too low / tables absent — fail closed, path-free.
            raise HTTPException(status_code=503, detail="forecast_config_not_available")

    @app.get("/api/forecast/config/snapshots")
    def forecast_config_snapshots(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_config_call(_forecast_config_service().list_snapshots)

    @app.get("/api/forecast/config/snapshots/{snapshot_id}")
    def forecast_config_snapshot(snapshot_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_config_call(_forecast_config_service().read_snapshot, snapshot_id)

    @app.get("/api/forecast/config/snapshots/{snapshot_id}/domains/{config_domain}")
    def forecast_config_domain(
        snapshot_id: str, config_domain: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        return _forecast_config_call(
            _forecast_config_service().read_domain, snapshot_id, config_domain
        )

    @app.get("/api/forecast/config/snapshots/{snapshot_id}/items/{item_id}")
    def forecast_config_item(
        snapshot_id: str, item_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        return _forecast_config_call(_forecast_config_service().read_item, snapshot_id, item_id)

    # --- Phase 4: DB-backed read-model for v63 run-output + v66 decision-support -----------
    # Read-only; navigates by the hash-based output_id (never the stamp-format run_id);
    # graceful-empty until the Phase-3 gated live write has populated the tables.
    def _forecast_readmodel_service() -> Any:
        from hb_assistant.construction.analytics.forecast_run_readmodel import (
            ForecastRunReadModelService,
        )
        from hb_assistant.construction.analytics.forecast_runtime_config import resolve_db_path

        return ForecastRunReadModelService(db_path=resolve_db_path(db_path))

    def _forecast_readmodel_call(fn: Any, *args: Any) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_run_readmodel import (
            ForecastRunReadModelError,
        )

        try:
            return fn(*args)
        except ForecastRunReadModelError as exc:
            if str(exc).startswith("unknown output_id"):
                raise HTTPException(status_code=404, detail="forecast_output_not_found")
            raise HTTPException(status_code=503, detail="forecast_run_output_not_available")

    @app.get("/api/forecast/db/projects")
    def forecast_db_projects(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_readmodel_call(_forecast_readmodel_service().list_projects)

    @app.get("/api/forecast/db/projects/{project_key}/outputs")
    def forecast_db_outputs(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_readmodel_call(_forecast_readmodel_service().list_outputs, project_key)

    # Generation-ready project read model (Phase P-B). Discovers projects across procore_ep_projects,
    # committed schedule imports, and forecast outputs; reports per-project availability + readiness
    # (ready/degraded/blocked, coded reasons). Viewer-readable, redaction-safe. Additive: the existing
    # /api/forecast/db/projects (output-derived) is unchanged.
    def _forecast_generation_projects_service() -> Any:
        from hb_assistant.construction.analytics.forecast_generation_project_readmodel import (
            ForecastGenerationProjectReadModelService,
        )
        from hb_assistant.construction.analytics.forecast_runtime_config import resolve_db_path

        return ForecastGenerationProjectReadModelService(db_path=resolve_db_path(db_path))

    def _forecast_generation_projects_call(fn: Any, *args: Any) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_generation_project_readmodel import (
            ForecastGenerationProjectReadModelError,
        )

        try:
            return fn(*args)
        except ForecastGenerationProjectReadModelError:
            raise HTTPException(status_code=503, detail="forecast_generation_projects_not_available")

    @app.get("/api/forecast/generation/projects")
    def forecast_generation_projects(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_generation_projects_call(
            _forecast_generation_projects_service().list_generation_projects
        )

    @app.get("/api/forecast/db/outputs/{output_id}")
    def forecast_db_output(output_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_readmodel_call(_forecast_readmodel_service().read_output, output_id)

    @app.get("/api/forecast/db/outputs/{output_id}/decision-support")
    def forecast_db_decision_support(
        output_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        return _forecast_readmodel_call(
            _forecast_readmodel_service().read_decision_support, output_id
        )

    @app.get("/api/forecast/db/outputs/{output_id}/narratives")
    def forecast_db_narratives(
        output_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        return _forecast_readmodel_call(_forecast_readmodel_service().read_narratives, output_id)

    @app.get("/api/forecast/db/outputs/{output_id}/monthly-table")
    def forecast_db_monthly_table(
        output_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role  # viewer-readable; redaction-safe coded/money/label fields only
        return _forecast_readmodel_call(_forecast_readmodel_service().read_monthly_table, output_id)

    # --- Operator assumptions capture — first interactive forecast WRITE surface ----------
    # Operator-entered assumptions persist DIRECTLY into the v66 managed-DB tables (not the
    # gated temp-swap-certify projection, which only fits re-derivable data). Mirrors the
    # add_project_keyword write pattern. GET=viewer, POST/PATCH=operator. Read paths are
    # redaction-safe (never raw_json/run_id); the tables sit outside the gated projection set.
    def _forecast_assumptions_service() -> Any:
        from hb_assistant.construction.analytics.forecast_operator_assumptions import (
            ForecastOperatorAssumptionsService,
        )
        from hb_assistant.construction.analytics.forecast_runtime_config import resolve_db_path

        return ForecastOperatorAssumptionsService(db_path=resolve_db_path(db_path))

    def _forecast_assumptions_call(fn: Any, *args: Any) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_operator_assumptions import (
            ForecastOperatorAssumptionsError,
        )

        # Invalid input / not-found return ok:False dicts (200), matching the keyword convention;
        # only fail-closed unavailability (missing/unreadable DB or schema < 66) maps to 503.
        try:
            return fn(*args)
        except ForecastOperatorAssumptionsError as exc:
            raise HTTPException(
                status_code=503, detail="forecast_assumptions_not_available"
            ) from exc

    @app.get("/api/forecast/db/projects/{project_key}/operator-assumptions")
    def forecast_operator_assumptions_list(
        project_key: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        return _forecast_assumptions_call(
            _forecast_assumptions_service().list_operator_assumptions, project_key
        )

    @app.post("/api/forecast/db/projects/{project_key}/operator-assumptions")
    def forecast_operator_assumption_create(
        project_key: str,
        request: OperatorAssumptionCreateRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_assumptions_service()
        return _forecast_assumptions_call(
            lambda: svc.create_operator_assumption(
                project_key,
                request.assumption_type,
                value=request.value,
                unit=request.unit,
                budget_code_key=request.budget_code_key,
                source=request.source,
                operator=request.operator,
                confidence_impact=request.confidence_impact,
                is_required=request.is_required,
                notes=request.notes,
            )
        )

    @app.patch("/api/forecast/db/operator-assumptions/{assumption_id}")
    def forecast_operator_assumption_edit(
        assumption_id: str,
        request: OperatorAssumptionEditRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_assumptions_service()
        return _forecast_assumptions_call(
            lambda: svc.edit_operator_assumption(
                assumption_id,
                value=request.value,
                unit=request.unit,
                source=request.source,
                operator=request.operator,
                confidence_impact=request.confidence_impact,
                is_required=request.is_required,
                overridden=request.overridden,
                notes=request.notes,
            )
        )

    @app.get("/api/forecast/db/projects/{project_key}/required-assumptions")
    def forecast_required_assumptions_list(
        project_key: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        return _forecast_assumptions_call(
            _forecast_assumptions_service().list_required_assumptions, project_key
        )

    @app.post("/api/forecast/db/projects/{project_key}/required-assumptions")
    def forecast_required_assumption_create(
        project_key: str,
        request: RequiredAssumptionCreateRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_assumptions_service()
        return _forecast_assumptions_call(
            lambda: svc.create_required_assumption(
                project_key, request.assumption_type, reason=request.reason
            )
        )

    @app.patch("/api/forecast/db/required-assumptions/{required_id}")
    def forecast_required_assumption_satisfy(
        required_id: str,
        request: RequiredAssumptionSatisfyRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_assumptions_service()
        return _forecast_assumptions_call(
            lambda: svc.set_required_assumption_satisfied(required_id, satisfied=request.satisfied)
        )

    # Project Staffing (Phase 3): project-scoped config / assumptions / absences / readiness +
    # attribution (rules / review / unmatched / resolve) + actuals rebuild. Reads are viewer-safe;
    # writes are operator-gated. Validate-on-write never rejects a row (it persists with its
    # validation_status). Responses are redaction-safe (the repos never select raw_json).
    def _forecast_staffing_service() -> Any:
        from hb_assistant.construction.analytics.forecast_runtime_config import resolve_db_path
        from hb_assistant.construction.analytics.forecast_staffing_service import (
            ForecastStaffingService,
        )

        return ForecastStaffingService(db_path=resolve_db_path(db_path))

    def _forecast_staffing_call(fn: Any, *args: Any) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_staffing_service import (
            ForecastStaffingError,
        )

        try:
            return fn(*args)
        except ForecastStaffingError as exc:
            raise HTTPException(status_code=503, detail="forecast_staffing_not_available") from exc

    @app.get("/api/projects/{project_key}/staffing/config")
    def staffing_config_list(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_staffing_call(_forecast_staffing_service().list_config, project_key)

    @app.post("/api/projects/{project_key}/staffing/config")
    def staffing_config_create(
        project_key: str, request: StaffingConfigCreateRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(
            lambda: svc.create_config(project_key, request.model_dump(exclude_none=True))
        )

    @app.patch("/api/projects/{project_key}/staffing/config/{config_id}")
    def staffing_config_patch(
        project_key: str,
        config_id: str,
        request: StaffingConfigPatchRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(
            lambda: svc.patch_config(project_key, config_id, request.model_dump(exclude_none=True))
        )

    @app.delete("/api/projects/{project_key}/staffing/config/{config_id}")
    def staffing_config_delete(
        project_key: str, config_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(lambda: svc.deactivate_config(project_key, config_id))

    @app.get("/api/projects/{project_key}/staffing/assumptions")
    def staffing_assumptions_get(
        project_key: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        return _forecast_staffing_call(_forecast_staffing_service().get_assumptions, project_key)

    @app.patch("/api/projects/{project_key}/staffing/assumptions")
    def staffing_assumptions_patch(
        project_key: str,
        request: StaffingAssumptionsPatchRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(
            lambda: svc.patch_assumptions(project_key, request.model_dump(exclude_none=True))
        )

    @app.get("/api/projects/{project_key}/staffing/absence-overrides")
    def staffing_absences_list(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_staffing_call(_forecast_staffing_service().list_absences, project_key)

    @app.post("/api/projects/{project_key}/staffing/absence-overrides")
    def staffing_absence_create(
        project_key: str, request: StaffingAbsenceCreateRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(
            lambda: svc.create_absence(project_key, request.model_dump(exclude_none=True))
        )

    @app.patch("/api/projects/{project_key}/staffing/absence-overrides/{absence_id}")
    def staffing_absence_patch(
        project_key: str,
        absence_id: str,
        request: StaffingAbsencePatchRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(
            lambda: svc.patch_absence(project_key, absence_id, request.model_dump(exclude_none=True))
        )

    @app.delete("/api/projects/{project_key}/staffing/absence-overrides/{absence_id}")
    def staffing_absence_delete(
        project_key: str, absence_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(lambda: svc.deactivate_absence(project_key, absence_id))

    @app.get("/api/projects/{project_key}/staffing/readiness")
    def staffing_readiness(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_staffing_call(_forecast_staffing_service().readiness, project_key)

    @app.get("/api/projects/{project_key}/staffing/attribution-rules")
    def staffing_rules_list(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_staffing_call(_forecast_staffing_service().list_rules, project_key)

    @app.post("/api/projects/{project_key}/staffing/attribution-rules")
    def staffing_rule_create(
        project_key: str, request: StaffingRuleCreateRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(
            lambda: svc.create_rule(project_key, request.model_dump(exclude_none=True))
        )

    @app.delete("/api/projects/{project_key}/staffing/attribution-rules/{rule_id}")
    def staffing_rule_delete(
        project_key: str, rule_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(lambda: svc.deactivate_rule(project_key, rule_id))

    @app.get("/api/projects/{project_key}/staffing/unmatched-actuals")
    def staffing_unmatched_list(
        project_key: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        return _forecast_staffing_call(_forecast_staffing_service().list_unmatched, project_key)

    @app.post("/api/projects/{project_key}/staffing/attribution-review/{review_item_id}/resolve")
    def staffing_review_resolve(
        project_key: str,
        review_item_id: str,
        request: StaffingReviewResolveRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(
            lambda: svc.resolve_review_item(
                project_key, review_item_id, request.model_dump(exclude_none=True)
            )
        )

    @app.get("/api/projects/{project_key}/staffing/mat-summary")
    def staffing_mat_summary(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_staffing_call(_forecast_staffing_service().mat_summary, project_key)

    @app.post("/api/projects/{project_key}/staffing/actuals/rebuild-projection")
    def staffing_actuals_rebuild(
        project_key: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(lambda: svc.rebuild_actuals(project_key))

    # Project Staffing global config (Phase 3c): the reusable staffing-template library (operator
    # writes) + the seeded company holiday calendars (read-only), under Forecasting Config.
    @app.get("/api/forecast/config/staffing-templates")
    def staffing_templates_list(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_staffing_call(_forecast_staffing_service().list_templates)

    @app.post("/api/forecast/config/staffing-templates")
    def staffing_template_create(
        request: StaffingTemplateCreateRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(
            lambda: svc.create_template(
                template_key=request.template_key,
                template_name=request.template_name,
                created_by_role=request.created_by_role,
            )
        )

    @app.get("/api/forecast/config/staffing-templates/{template_id}")
    def staffing_template_get(template_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_staffing_call(_forecast_staffing_service().get_template, template_id)

    @app.delete("/api/forecast/config/staffing-templates/{template_id}")
    def staffing_template_delete(
        template_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(lambda: svc.deactivate_template(template_id))

    @app.get("/api/forecast/config/staffing-templates/{template_id}/versions")
    def staffing_template_versions(
        template_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(lambda: svc.get_template(template_id))

    @app.post("/api/forecast/config/staffing-templates/{template_id}/versions")
    def staffing_template_version_create(
        template_id: str,
        request: StaffingTemplateVersionCreateRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        svc = _forecast_staffing_service()
        return _forecast_staffing_call(
            lambda: svc.add_template_version(template_id, request.model_dump(exclude_none=True))
        )

    @app.get("/api/forecast/config/holiday-calendars")
    def staffing_holiday_calendars_list(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_staffing_call(_forecast_staffing_service().list_holiday_calendars)

    @app.get("/api/forecast/config/holiday-calendars/{holiday_calendar_id}")
    def staffing_holiday_calendar_get(
        holiday_calendar_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        return _forecast_staffing_call(
            _forecast_staffing_service().get_holiday_calendar, holiday_calendar_id
        )

    # Forecast config editing — isolated proposals (Implementation Phase E). An operator proposes
    # edits; the service seeds from a chosen live snapshot (mode=ro), applies edits in an isolated
    # config-edit root, runs the CFR import→snapshot→materialize→parity pipeline in an isolated temp
    # DB, and returns a redacted report. ZERO live-DB / live-data-root writes. POST=operator, GET=viewer.
    def _forecast_config_edit_service() -> Any:
        from hb_assistant.construction.analytics.forecast_config_edit_service import (
            ForecastConfigEditService,
        )
        from hb_assistant.construction.analytics.forecast_runtime_config import (
            resolve_cfr_src,
            resolve_config_edit_root_value,
            resolve_db_path,
        )

        return ForecastConfigEditService(
            config_edit_root=resolve_config_edit_root_value(None),
            db_path=resolve_db_path(db_path),
            cfr_src=resolve_cfr_src(None),
        )

    def _forecast_config_edit_call(fn: Any, *args: Any) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_config_edit_service import (
            ForecastConfigEditError,
        )

        try:
            return fn(*args)
        except ForecastConfigEditError as exc:
            msg = str(exc)
            if msg.startswith("unknown snapshot_id"):
                raise HTTPException(status_code=404, detail="forecast_config_snapshot_not_found")
            if msg.startswith("unknown edit_id"):
                raise HTTPException(status_code=404, detail="forecast_config_edit_not_found")
            if (
                msg.startswith("invalid input")
                or "deprecated" in msg
                or msg.startswith("unsupported project_key")
                or "not editable" in msg
                or "not a decimal" in msg
                or "must be" in msg
                or "value rejected" in msg
                or msg.startswith("unknown item_key")
                or "has no config items" in msg
            ):
                raise HTTPException(status_code=400, detail="forecast_config_edit_invalid_input")
            # not configured / under data root / CFR unavailable / DB not ro-openable — fail closed.
            raise HTTPException(status_code=503, detail="forecast_config_edit_not_configured")

    @app.post("/api/forecast/config/edits")
    def forecast_config_edit_create(
        request: ForecastConfigEditRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)  # proposes a write into the isolated config-edit root
        return _forecast_config_edit_call(
            _forecast_config_edit_service().propose_config_edit,
            request.base_snapshot_id,
            request.edits,
            request.project_key,
        )

    @app.get("/api/forecast/config/edits")
    def forecast_config_edits_list(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_config_edit_call(_forecast_config_edit_service().list_edits)

    @app.get("/api/forecast/config/edits/{edit_id}")
    def forecast_config_edit_detail(edit_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_config_edit_call(_forecast_config_edit_service().read_edit, edit_id)

    @app.get("/api/forecast/config/edits/{edit_id}/manifest")
    def forecast_config_edit_manifest(
        edit_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        return _forecast_config_edit_call(
            _forecast_config_edit_service().read_edit_manifest, edit_id
        )

    # Forecast config promotion — certified live write (Implementation Phase E2). Promotes an approved
    # (parity-passed) proposal into the live config DB as a new snapshot, gated by a default-OFF opt-in
    # + an explicit per-request confirm + the byte-backed CFR workflow. POST=operator.
    def _forecast_config_promotion_service() -> Any:
        from hb_assistant.construction.analytics.forecast_config_promotion_service import (
            ForecastConfigPromotionService,
        )
        from hb_assistant.construction.analytics.forecast_runtime_config import (
            resolve_cfr_src,
            resolve_config_edit_root_value,
            resolve_db_path,
            resolve_promotion_enabled,
        )

        return ForecastConfigPromotionService(
            config_edit_root=resolve_config_edit_root_value(None),
            db_path=resolve_db_path(db_path),
            cfr_src=resolve_cfr_src(None),
            promotion_enabled=resolve_promotion_enabled(None),
        )

    def _forecast_config_promotion_call(fn: Any, *args: Any) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_config_promotion_service import (
            ForecastConfigPromotionError,
        )

        try:
            return fn(*args)
        except ForecastConfigPromotionError as exc:
            msg = str(exc)
            if msg.startswith("unknown edit_id"):
                raise HTTPException(status_code=404, detail="forecast_config_promotion_edit_not_found")
            if msg == "promotion disabled":
                raise HTTPException(status_code=503, detail="forecast_config_promotion_disabled")
            if msg == "not confirmed":
                raise HTTPException(status_code=400, detail="forecast_config_promotion_not_confirmed")
            if msg.startswith("proposal not eligible"):
                raise HTTPException(status_code=400, detail="forecast_config_promotion_not_eligible")
            # CFR workflow refusal / live-write failure — fail closed, path-free.
            raise HTTPException(status_code=500, detail="forecast_config_promotion_failed")

    @app.post("/api/forecast/config/edits/{edit_id}/promote")
    def forecast_config_edit_promote(
        edit_id: str, request: ForecastConfigPromoteRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)  # the first analytics live-DB write (gated + confirmed + backed up)
        return _forecast_config_promotion_call(
            _forecast_config_promotion_service().promote_config_edit, edit_id, request.confirm
        )

    # Forecast Run Center — isolated context->analysis generation (Implementation Phase 3).
    # POST executes + writes (isolated work-root only) → operator role. GET reads runs → viewer.
    def _forecast_run_service() -> Any:
        from hb_assistant.construction.analytics.forecast_run_service import ForecastRunService
        from hb_assistant.construction.analytics.forecast_runtime_config import (
            resolve_data_root,
            resolve_runs_root,
        )

        return ForecastRunService(
            data_root=resolve_data_root(None), runs_root=resolve_runs_root(None)
        )

    def _forecast_run_call(fn: Any, *args: Any) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_run_service import ForecastRunError

        try:
            return fn(*args)
        except ForecastRunError as exc:
            if str(exc).startswith("unknown run_id"):
                raise HTTPException(status_code=404, detail="forecast_run_not_found")
            # not configured / invalid roots / CFR source unavailable — fail closed, path-free.
            raise HTTPException(status_code=503, detail="forecast_runs_not_configured")

    @app.post("/api/forecast/runs")
    def forecast_run_create(
        payload: dict[str, Any] | None = optional_json_body,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)  # generation executes + writes (isolated work-root)
        return _persist_and_run(mode="file_config", body=payload, role=role)

    @app.get("/api/forecast/runs")
    def forecast_runs_list(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_run_call(_forecast_run_service().list_runs)

    # DB-config-backed generation: generate the comprehensive package CONSUMING the live config
    # snapshot (so a promoted config drives generation). Default-OFF opt-in; live config DB read-only;
    # writes only the isolated work-root. Registered BEFORE the {run_id} catch-all so "db-config" wins.
    def _forecast_db_config_run_service() -> Any:
        from hb_assistant.construction.analytics.forecast_db_config_run_service import (
            ForecastDbConfigRunService,
        )
        from hb_assistant.construction.analytics.forecast_runtime_config import (
            resolve_cfr_src,
            resolve_data_root,
            resolve_db_config_run_enabled,
            resolve_runs_root,
        )

        return ForecastDbConfigRunService(
            data_root=resolve_data_root(None),
            runs_root=resolve_runs_root(None),
            cfr_src=resolve_cfr_src(None),
            db_config_run_enabled=resolve_db_config_run_enabled(None),
        )

    def _forecast_db_config_run_call(fn: Any, *args: Any) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_db_config_run_service import (
            ForecastDbConfigRunError,
        )

        try:
            return fn(*args)
        except ForecastDbConfigRunError as exc:
            if str(exc).startswith("unknown run_id"):
                raise HTTPException(status_code=404, detail="forecast_db_config_run_not_found")
            if str(exc).startswith("db_config_run disabled"):
                raise HTTPException(status_code=503, detail="forecast_db_config_run_disabled")
            # not configured / config DB not ready — fail closed, path-free.
            raise HTTPException(status_code=503, detail="forecast_db_config_run_not_configured")

    # -- Phase P-C: durable generation-request contract + persistence ---------
    # Both generation routes parse + validate a typed request body, persist a forecast_generation_requests
    # row BEFORE invoking generation, then update it with the outcome (run linkage + terminal status).
    # project_key is REQUIRED (no silent tropical default). Existing fail-closed 503/404 codes are
    # preserved by re-raising the service's HTTPException after recording the rejection.
    def _forecast_request_repository() -> Any:
        from hb_assistant.construction.analytics.forecast_runtime_config import resolve_db_path
        from hb_assistant.store.forecast_generation_request_repository import (
            ForecastGenerationRequestRepository,
        )

        return ForecastGenerationRequestRepository(db_path=resolve_db_path(db_path))

    def _resolve_generation_project(project_key: str) -> tuple[bool, dict[str, Any] | None]:
        # (resolvable, project). resolvable=False ⇒ read model unavailable: skip the unknown-project
        # check so the downstream service's fail-closed codes (disabled/not_configured) are preserved.
        from hb_assistant.construction.analytics.forecast_generation_project_readmodel import (
            ForecastGenerationProjectReadModelError,
            ForecastGenerationProjectReadModelService,
        )
        from hb_assistant.construction.analytics.forecast_runtime_config import resolve_db_path

        svc = ForecastGenerationProjectReadModelService(db_path=resolve_db_path(db_path))
        try:
            listing = svc.list_generation_projects()
        except ForecastGenerationProjectReadModelError:
            return (False, None)
        for proj in listing.get("projects", []):
            if proj.get("project_key") == project_key:
                return (True, proj)
        return (True, None)

    def _validation_status_code(errors: list[str]) -> int:
        date_errors = {
            "invalid_forecast_start_date",
            "invalid_forecast_cutoff_date",
            "forecast_start_after_cutoff",
        }
        return 422 if errors and errors[0] in date_errors else 400

    def _failure_code_for(detail: Any) -> str:
        text = str(detail)
        if "disabled" in text:
            return "generation_disabled"
        if "not_configured" in text:
            return "generation_not_configured"
        return "generation_rejected"

    def _date_defaults_service() -> Any:
        from hb_assistant.construction.analytics.forecast_generation_date_defaults import (
            ForecastGenerationDateDefaultsService,
        )
        from hb_assistant.construction.analytics.forecast_runtime_config import resolve_db_path

        return ForecastGenerationDateDefaultsService(db_path=resolve_db_path(db_path))

    def _verify_cutoff_basis(parsed: dict[str, Any]) -> str | None:
        # Returns schedule_version_key when a schedule-derived basis is confirmed; otherwise downgrades
        # parsed["forecast_cutoff_date_basis"] to operator_supplied and returns None.
        basis = parsed.get("forecast_cutoff_date_basis")
        cutoff = parsed.get("forecast_cutoff_date")
        if not cutoff or basis in (None, "operator_supplied"):
            return None
        from hb_assistant.construction.analytics.forecast_generation_date_defaults import (
            ForecastGenerationDateDefaultsError,
        )

        try:
            defaults = _date_defaults_service().resolve(parsed["project_key"])
        except ForecastGenerationDateDefaultsError:
            parsed["forecast_cutoff_date_basis"] = "operator_supplied"
            return None
        if defaults.forecast_cutoff_date == cutoff and defaults.forecast_cutoff_date_basis == basis:
            return defaults.schedule_version_key
        parsed["forecast_cutoff_date_basis"] = "operator_supplied"
        return None

    def _persist_and_run(
        *, mode: str, body: dict[str, Any] | None, role: dict[str, str]
    ) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_generation_request_dto import (
            request_row_to_public,
            validate_request,
        )

        parsed, errors = validate_request(body, mode=mode)
        repo = _forecast_request_repository()
        requested_by_role = role.get("role")

        readiness_status: str | None = None
        readiness_reasons: list[str] = []
        if parsed["project_key"]:
            resolvable, project = _resolve_generation_project(parsed["project_key"])
            if resolvable and project is None:
                errors.append("unknown_project_key")
            if project is not None:
                readiness_status = project.get("readiness_status")
                readiness_reasons = list(project.get("readiness_reasons") or [])

        if errors:
            # missing_project_key cannot persist (project_key is NOT NULL) — raise without a row.
            if parsed["project_key"]:
                repo.record_validation_rejection(
                    project_key=parsed["project_key"],
                    generation_mode=mode,
                    validation_errors=errors,
                    generator_kind=parsed["generator_kind"],
                    forecast_start_date=parsed["forecast_start_date"],
                    forecast_cutoff_date=parsed["forecast_cutoff_date"],
                    forecast_cutoff_date_basis=parsed["forecast_cutoff_date_basis"],
                    actuals_start_month=parsed["actuals_start_month"],
                    actuals_through_month=parsed["actuals_through_month"],
                    forecast_start_month=parsed["forecast_start_month"],
                    forecast_end_month=parsed["forecast_end_month"],
                    requested_by_role=requested_by_role,
                    readiness_status_at_request=readiness_status,
                    readiness_reasons=readiness_reasons,
                )
            raise HTTPException(status_code=_validation_status_code(errors), detail=errors[0])

        # P-D: a schedule-derived cut-off basis is re-verified server-side against the resolver. If
        # the (date, basis) matches we keep it and capture the schedule_version_key; otherwise we
        # downgrade to operator_supplied (deterministic, non-blocking). Never trust the client basis.
        schedule_version_key = _verify_cutoff_basis(parsed)

        request_id = repo.create(
            project_key=parsed["project_key"],
            generation_mode=mode,
            request_status="running",
            validation_status="valid",
            generator_kind=parsed["generator_kind"],
            forecast_start_date=parsed["forecast_start_date"],
            forecast_cutoff_date=parsed["forecast_cutoff_date"],
            forecast_cutoff_date_basis=parsed["forecast_cutoff_date_basis"],
            actuals_start_month=parsed["actuals_start_month"],
            actuals_through_month=parsed["actuals_through_month"],
            forecast_start_month=parsed["forecast_start_month"],
            forecast_end_month=parsed["forecast_end_month"],
            schedule_version_key=schedule_version_key,
            requested_by_role=requested_by_role,
            readiness_status_at_request=readiness_status,
            readiness_reasons=readiness_reasons,
        )

        # Phase B: the explicit true-DB-native mode. This seam is fail-closed and package-free — it
        # never calls _run_generation / generate_and_persist / the db-config service / any CFR
        # package workflow. It returns a curated, path-free db_native_generation_not_implemented
        # result. The DB-native generation engine is supplied by later phases. See ADR 314 / 313.
        if mode == "db_native":
            from hb_assistant.construction.analytics.forecast_db_native_generation_service import (
                DbNativeGenerationRequest,
                generate_db_native,
            )
            from hb_assistant.construction.analytics.forecast_generation_modes import GenerationMode

            from hb_assistant.construction.analytics.forecast_runtime_config import (
                resolve_db_path,
                resolve_run_output_db_write_enabled,
            )

            result = generate_db_native(
                DbNativeGenerationRequest(
                    project_key=parsed["project_key"],
                    generator_kind=parsed["generator_kind"],
                    forecast_start_date=parsed["forecast_start_date"],
                    forecast_cutoff_date=parsed["forecast_cutoff_date"],
                    forecast_end_date=parsed["forecast_end_date"],
                    forecast_cutoff_date_basis=parsed["forecast_cutoff_date_basis"],
                    actuals_start_month=parsed["actuals_start_month"],
                    actuals_through_month=parsed["actuals_through_month"],
                    forecast_start_month=parsed["forecast_start_month"],
                    forecast_end_month=parsed["forecast_end_month"],
                    source_snapshot_id=(body or {}).get("source_snapshot_id"),
                    request_id=request_id,
                    db_path=resolve_db_path(db_path),
                    write_enabled=resolve_run_output_db_write_enabled(),
                )
            )
            if result.db_persisted:
                repo.update_status(request_id, "completed", run_id=result.run_id)
            else:
                repo.record_failure(request_id, result.failure_code or "db_native_generation_failed", result.failure_message)
            return {
                "request_id": request_id,
                "project_key": parsed["project_key"],
                "generation_mode": GenerationMode.DB_NATIVE.value,
                "generator_kind": parsed["generator_kind"],
                "request_status": result.request_status,
                "validation_status": "valid",
                "forecast_start_date": parsed["forecast_start_date"],
                "forecast_cutoff_date": parsed["forecast_cutoff_date"],
                "forecast_end_date": parsed["forecast_end_date"],
                "forecast_cutoff_date_basis": parsed["forecast_cutoff_date_basis"],
                "actuals_start_month": parsed["actuals_start_month"],
                "actuals_through_month": parsed["actuals_through_month"],
                "forecast_start_month": parsed["forecast_start_month"],
                "forecast_end_month": parsed["forecast_end_month"],
                "source_snapshot_id": result.source_snapshot_id,
                "db_persisted": result.db_persisted,
                "package_generated": False,
                "persisted_output_ids": list(result.persisted_output_ids),
                "failure_code": result.failure_code,
                "failure_message": result.failure_message,
                "readiness_status_at_request": readiness_status,
                "readiness_reasons": readiness_reasons,
            }

        # P-E: gated authorized live-DB run-output write (default OFF). When enabled, Generate
        # Forecast persists forecast_outputs + child rows to the app DB (backup+certify) instead of
        # producing a package; success requires DB persistence + certification.
        from hb_assistant.construction.analytics.forecast_runtime_config import (
            resolve_db_path,
            resolve_run_output_db_write_enabled,
            resolve_runs_root,
        )

        if mode == "db_config" and resolve_run_output_db_write_enabled():
            from hb_assistant.construction.analytics.forecast_run_output_persistence_service import (
                generate_and_persist,
            )

            work_root = Path(resolve_runs_root(None) or "") / f"runoutput-{request_id}"
            # The Generate-Forecast DB-output-write route is DB-native-intended; the engine is not yet
            # DB-native, so this fails closed up front (db_native_generation_not_implemented) and never
            # falls back to file-backed CFR generation. See ADR 313.
            receipt = generate_and_persist(
                project_key=parsed["project_key"],
                db_path=Path(resolve_db_path(db_path)),
                work_root=work_root,
                db_native_intended=True,
            )
            if receipt.db_persisted:
                repo.update_status(request_id, "completed")
                final_status = "completed"
            else:
                repo.record_failure(
                    request_id,
                    receipt.failure_code or "db_persistence_failed",
                    receipt.failure_message,
                )
                final_status = "failed"
            return {
                "request_id": request_id,
                "forecast_output_id": receipt.forecast_output_id,
                "project_key": parsed["project_key"],
                "generation_mode": mode,
                "generator_kind": parsed["generator_kind"],
                "request_status": final_status,
                "validation_status": "valid",
                "forecast_start_date": parsed["forecast_start_date"],
                "forecast_cutoff_date": parsed["forecast_cutoff_date"],
                "forecast_cutoff_date_basis": parsed["forecast_cutoff_date_basis"],
                "db_persisted": receipt.db_persisted,
                "package_generated": False,
                "failure_code": receipt.failure_code,
                "failure_message": receipt.failure_message,
                "readiness_status_at_request": readiness_status,
                "readiness_reasons": readiness_reasons,
            }

        if mode == "file_config":
            error_mapper = _forecast_run_call

            def _call() -> dict[str, Any]:
                return _forecast_run_service().start_run(project_key=parsed["project_key"])

        else:
            error_mapper = _forecast_db_config_run_call

            def _call() -> dict[str, Any]:
                return _forecast_db_config_run_service().start_db_config_run(
                    generator_kind=parsed["generator_kind"], project_key=parsed["project_key"]
                )

        try:
            summary = error_mapper(_call)
        except HTTPException as exc:
            # Service fail-closed (disabled / not_configured / ...). Record the rejection, then
            # re-raise UNCHANGED so the existing 503/404 contract is preserved.
            repo.record_failure(
                request_id, _failure_code_for(exc.detail), request_status="rejected"
            )
            raise

        run_id = summary.get("run_id")
        if summary.get("status") == "failed":
            repo.update_status(
                request_id, "failed", run_id=run_id, failure_code="generation_failed"
            )
        else:
            repo.update_status(request_id, "completed", run_id=run_id)

        public = request_row_to_public(repo.get(request_id) or {})
        return {
            **summary,
            "request_id": request_id,
            "generation_mode": mode,
            "generator_kind": parsed["generator_kind"],
            "request_status": public["request_status"],
            "validation_status": public["validation_status"],
            "forecast_start_date": parsed["forecast_start_date"],
            "forecast_cutoff_date": parsed["forecast_cutoff_date"],
            "forecast_cutoff_date_basis": parsed["forecast_cutoff_date_basis"],
            "schedule_version_key": schedule_version_key,
            "db_persisted": False,
            "package_generated": False,
            "readiness_status_at_request": readiness_status,
            "readiness_reasons": readiness_reasons,
        }

    @app.post("/api/forecast/runs/db-config")
    def forecast_db_config_run_create(
        payload: dict[str, Any] | None = optional_json_body,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)  # executes + writes isolated work-root; reads live config DB ro
        return _persist_and_run(mode="db_config", body=payload, role=role)

    @app.post("/api/forecast/runs/db-native")
    def forecast_db_native_run_create(
        payload: dict[str, Any] | None = optional_json_body,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        # Phase B: explicit true-DB-native route. Fail-closed + package-free seam (no source/context/
        # analysis package, no CFR generation); records a db_native request and returns a curated,
        # path-free db_native_generation_not_implemented result. Engine deferred to later phases.
        require_operator_role(role)
        return _persist_and_run(mode="db_native", body=payload, role=role)

    @app.get("/api/forecast/generation/requests")
    def forecast_generation_requests(
        project_key: str | None = None,
        limit: int = 20,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role  # viewer-readable; redaction-safe coded fields only
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_generation_request_dto import (
            request_row_to_public,
        )

        key = (project_key or "").strip() or None
        try:
            rows = _forecast_request_repository().list_recent(project_key=key, limit=limit)
        except Exception:
            # Repo DB unavailable — fail closed, path-free (mirrors the read-model list pattern).
            raise HTTPException(
                status_code=503, detail="forecast_generation_requests_not_available"
            )
        return {
            "surface": "analytics.forecast_generation_requests",
            "requests": [request_row_to_public(r) for r in rows],
            "guardrails": {"read_only": True, "redaction_safe": True},
        }

    @app.get("/api/forecast/generation/date-defaults")
    def forecast_generation_date_defaults(
        project_key: str,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role  # viewer-readable; redaction-safe coded fields only (missing param → 422)
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_generation_date_defaults import (
            ForecastGenerationDateDefaultsError,
        )

        key = (project_key or "").strip()
        if not key:
            raise HTTPException(status_code=422, detail="missing_project_key")
        # Unknown project (resolvable but absent) → 404; if the read model can't resolve, fall through
        # to the defaults service which fails closed (503) on an unavailable DB.
        resolvable, project = _resolve_generation_project(key)
        if resolvable and project is None:
            raise HTTPException(status_code=404, detail="unknown_project_key")
        try:
            return _date_defaults_service().public(key)
        except ForecastGenerationDateDefaultsError:
            raise HTTPException(
                status_code=503, detail="forecast_generation_date_defaults_not_available"
            )

    @app.get("/api/forecast/runs/db-config")
    def forecast_db_config_runs_list(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_db_config_run_call(_forecast_db_config_run_service().list_db_config_runs)

    @app.get("/api/forecast/runs/db-config/{run_id}")
    def forecast_db_config_run_detail(run_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_db_config_run_call(
            _forecast_db_config_run_service().read_db_config_run, run_id
        )

    @app.get("/api/forecast/runs/{run_id}")
    def forecast_run_detail(run_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_run_call(_forecast_run_service().read_run, run_id)

    # External-Forecast Evaluation — upload an operator forecast, map it, and compare it against
    # actuals/budget/ERP-JTD/backend-model/prior baselines (Implementation Phase 4). POST routes
    # upload/map/evaluate and write only to the isolated eval-root → operator role; GET reads
    # results → viewer. Nothing is written to the live DB or live data root.
    # Runtime wiring (Phase 6): resolve eval_root / db_path / package_roots via env > settings-file.
    def _external_resolved() -> dict[str, Any]:
        from hb_assistant.construction.analytics.forecast_runtime_config import (
            resolve_db_path,
            resolve_eval_root_value,
            resolve_package_roots,
        )

        return {
            "eval_root": resolve_eval_root_value(None),
            "db_path": resolve_db_path(None),
            "package_roots": resolve_package_roots(None),
        }

    def _external_ingest_service() -> Any:
        from hb_assistant.construction.analytics.forecast_external_ingest import (
            ForecastExternalIngestService,
        )

        return ForecastExternalIngestService(eval_root=_external_resolved()["eval_root"])

    def _external_mapping_service() -> Any:
        from hb_assistant.construction.analytics.forecast_external_mapping import (
            ForecastExternalMappingService,
        )

        r = _external_resolved()
        return ForecastExternalMappingService(eval_root=r["eval_root"], db_path=r["db_path"])

    def _external_eval_service() -> Any:
        from hb_assistant.construction.analytics.forecast_external_eval_service import (
            ForecastExternalEvalService,
        )

        r = _external_resolved()
        return ForecastExternalEvalService(
            eval_root=r["eval_root"], db_path=r["db_path"], package_roots=r["package_roots"]
        )

    def _forecast_external_call(fn: Any, *args: Any) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_external_ingest import (
            ForecastExternalError,
        )

        try:
            return fn(*args)
        except ForecastExternalError as exc:
            msg = str(exc)
            if msg.startswith("unknown import_id") or msg.startswith("unknown eval_id"):
                raise HTTPException(status_code=404, detail="forecast_external_not_found")
            if (
                "not configured" in msg
                or "absolute path" in msg
                or "could not be created" in msg
                or "opened read-only" in msg
            ):
                # misconfigured environment — fail closed, path-free.
                raise HTTPException(status_code=503, detail="forecast_external_not_configured")
            # invalid/untrusted input (bad base64, unsupported type, unmapped columns, …).
            raise HTTPException(status_code=400, detail="forecast_external_invalid_input")

    @app.post("/api/forecast/external/preview")
    def forecast_external_preview(
        request: ForecastExternalPreviewRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)  # ingests an untrusted file into the isolated eval-root
        return _forecast_external_call(
            _external_ingest_service().preview,
            request.filename,
            request.content_b64,
            request.source_system,
            request.period,
        )

    @app.post("/api/forecast/external/mapping")
    def forecast_external_mapping(
        request: ForecastExternalMappingRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        return _forecast_external_call(
            _external_mapping_service().propose_mapping,
            request.import_id,
            request.project_key,
        )

    @app.post("/api/forecast/external/evaluate")
    def forecast_external_evaluate(
        request: ForecastExternalEvaluateRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)  # runs the evaluation + writes the isolated eval package/DB
        return _forecast_external_call(
            _external_eval_service().evaluate,
            request.import_id,
            request.column_roles,
            request.project_key,
        )

    @app.get("/api/forecast/external/evaluations")
    def forecast_external_evaluations_list(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _forecast_external_call(_external_eval_service().list_evaluations)

    @app.get("/api/forecast/external/evaluations/{eval_id}")
    def forecast_external_evaluation_detail(
        eval_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        return _forecast_external_call(_external_eval_service().read_evaluation, eval_id)

    # Forecast runtime configuration (Implementation Phase 6). Wires the HB_FORECAST_* roots into
    # the live app via a persistent app-support settings file. GET status is viewer-readable and
    # redaction-safe (booleans + coded blockers, no paths). GET config echoes the raw configured
    # paths and is ADMIN-only (the single deliberate carve-out from the no-path-echo convention).
    # POST config validates + persists (operator), returning the redaction-safe status.
    @app.get("/api/forecast/runtime/status")
    def forecast_runtime_status(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.forecast_runtime_config import (
            build_runtime_status,
        )

        return build_runtime_status()

    # DB-config-backed generation readiness (viewer-readable, redaction-safe). Lets the UI disable
    # the Generate control BEFORE click and explain why, instead of surfacing a raw 503 after the
    # POST. Returns booleans + coded reasons only — never a path. The POST route stays fail-closed.
    @app.get("/api/forecast/generation/readiness")
    def forecast_generation_readiness(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.forecast_runtime_config import (
            build_generation_readiness,
        )

        return build_generation_readiness()

    @app.get("/api/forecast/runtime/config")
    def forecast_runtime_config_read(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)  # echoes raw filesystem paths — admin-only carve-out
        from hb_assistant.construction.analytics.forecast_runtime_config import (
            read_runtime_config_admin,
        )

        return read_runtime_config_admin()

    @app.post("/api/forecast/runtime/config")
    def forecast_runtime_config_write(
        request: ForecastRuntimeConfigRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_admin_role(role)  # advanced manual path override — admin-only carve-out
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_runtime_config import (
            ForecastRuntimeConfigError,
            save_runtime_config,
        )

        try:
            return save_runtime_config(request.model_dump(exclude_none=True))
        except ForecastRuntimeConfigError as exc:
            # Path-free blocker code ("<root>:<blocker>"); never persisted on failure.
            raise HTTPException(status_code=400, detail=f"forecast_runtime_invalid:{exc}")

    @app.post("/api/forecast/runtime/repair")
    def forecast_runtime_storage_repair(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.forecast_bootstrap import (
            ensure_forecast_managed_storage,
        )

        return ensure_forecast_managed_storage(repair=True)

    @app.post("/api/forecast/runtime/reset")
    def forecast_runtime_storage_reset(
        request: ForecastRuntimeResetRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_admin_role(role)
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.forecast_bootstrap import (
            ensure_forecast_managed_storage,
        )
        from hb_assistant.construction.analytics.forecast_runtime_config import (
            reset_runtime_config_to_managed_defaults,
        )

        if not request.confirm:
            raise HTTPException(status_code=400, detail="forecast_runtime_reset_confirm_required")
        reset_runtime_config_to_managed_defaults()
        return ensure_forecast_managed_storage(repair=True)

    # Schedule Intelligence (V62) — canonical schedule activity storage + cost mapping.
    def _schedule_db_path() -> str:
        return db_path or str(PathPolicy().get_db_path())

    def _schedule_import_service() -> Any:
        from hb_assistant.construction.analytics.schedule_import_service import (
            ScheduleImportService,
        )

        return ScheduleImportService(db_path=_schedule_db_path())

    def _project_schedule_import_pipeline_service() -> Any:
        from hb_assistant.construction.analytics.project_schedule_import_pipeline_service import (
            ProjectScheduleImportPipelineService,
        )

        return ProjectScheduleImportPipelineService(db_path=_schedule_db_path())

    def _schedule_read_service() -> Any:
        from hb_assistant.construction.analytics.schedule_import_service import (
            ScheduleReadService,
        )

        return ScheduleReadService(db_path=_schedule_db_path())

    def _schedule_identity_repo() -> Any:
        from hb_assistant.store.schedule_identity_repository import ScheduleIdentityRepository

        return ScheduleIdentityRepository(db_path=_schedule_db_path())

    def _schedule_cost_mapping_service() -> Any:
        from hb_assistant.construction.analytics.schedule_cost_mapping import (
            ScheduleCostMappingService,
        )

        return ScheduleCostMappingService(db_path=_schedule_db_path())

    def _raise_schedule_import_error(exc: Any) -> None:
        from fastapi import HTTPException

        code = getattr(exc, "code", None) or str(exc)
        payload = getattr(exc, "payload", None) or {}
        if code == "schedule_not_found":
            raise HTTPException(status_code=404, detail="schedule_not_found")
        if code == "schedule_schema_not_ready":
            raise HTTPException(status_code=503, detail="schedule_schema_not_ready")
        if code == "schedule_file_too_large":
            raise HTTPException(status_code=413, detail="schedule_file_too_large")
        if code == "duplicate_schedule_version":
            raise HTTPException(status_code=409, detail={"code": code, **payload})
        if code in {"schedule_project_required", "schedule_project_unknown"}:
            raise HTTPException(status_code=422, detail={"code": code, **payload})
        if code in {
            "schedule_project_mismatch",
            "schedule_import_persistence_failed",
            "schedule_supersede_confirmation_required",
            "schedule_supersede_state_mismatch",
            "schedule_identity_merge_same_identity",
        }:
            raise HTTPException(status_code=409, detail={"code": code, **payload})
        if code in {
            "schedule_identity_not_found",
            "schedule_identity_match_not_found",
        }:
            raise HTTPException(status_code=404, detail={"code": code, **payload})
        if code == "schedule_identity_not_active":
            raise HTTPException(status_code=409, detail={"code": code, **payload})
        if code == "schedule_package_multiple_current_candidates":
            raise HTTPException(status_code=409, detail={"code": code, **payload})
        if code == "schedule_multipart_unavailable":
            raise HTTPException(status_code=503, detail="schedule_multipart_unavailable")
        if code == "schedule_quality_not_ready":
            raise HTTPException(status_code=409, detail="schedule_quality_not_ready")
        if code in {"unsupported_schedule_format", "schedule_parse_failed"}:
            raise HTTPException(status_code=400, detail=code)
        raise HTTPException(status_code=400, detail=code or "schedule_import_invalid")

    def require_schedule_schema_ready() -> None:
        from hb_assistant.construction.analytics.schedule_import_service import ensure_schedule_schema

        try:
            ensure_schedule_schema(_schedule_db_path())
        except Exception as exc:
            _raise_schedule_import_error(exc)

    def _schedule_call(fn: Any, *args: Any, **kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
        from hb_assistant.construction.analytics.schedule_file_parser import ScheduleImportError

        try:
            result = fn(*args, **kwargs)
            if isinstance(result, list):
                return result
            return result if isinstance(result, dict) else {"result": result}
        except ScheduleImportError as exc:
            _raise_schedule_import_error(exc)
            raise AssertionError("unreachable") from exc

    def _json_object(value: Any) -> dict[str, Any]:
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _public_identity_row(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        if "requires_review" in out:
            out["requires_review"] = bool(int(out.get("requires_review") or 0))
        if "review_required_count" in out:
            out["review_required_count"] = int(out.get("review_required_count") or 0)
        if "version_count" in out:
            out["version_count"] = int(out.get("version_count") or 0)
        if "evidence_json" in out:
            out["evidence_summary"] = _json_object(out.pop("evidence_json"))
        return out

    def _public_identity_detail(payload: dict[str, Any]) -> dict[str, Any]:
        identity = _public_identity_row(dict(payload.get("identity") or {}))
        versions = [_public_identity_row(dict(v)) for v in payload.get("versions") or []]
        actions = []
        for action in payload.get("manual_actions") or []:
            item = dict(action)
            if "evidence_json" in item:
                item["evidence_summary"] = _json_object(item.pop("evidence_json"))
            actions.append(item)
        return {"identity": identity, "versions": versions, "manual_actions": actions}

    @app.get("/api/schedules/projects")
    def schedule_list_projects(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        return _schedule_call(_schedule_read_service().list_projects)

    @app.get("/api/schedules/versions")
    def schedule_list_versions_query(
        project_key: str | None = None,
        sort: str = Query(default="imported_at"),
        order: str = Query(default="desc"),
        role: dict[str, str] = role_dep,
    ) -> list[dict[str, Any]]:
        del role
        return _schedule_call(
            _schedule_read_service().list_versions,
            project_key,
            sort=sort,
            order=order,
        )

    @app.get("/api/schedules/projects/{project_key}/versions")
    def schedule_list_versions(
        project_key: str,
        sort: str = Query(default="imported_at"),
        order: str = Query(default="desc"),
        role: dict[str, str] = role_dep,
    ) -> list[dict[str, Any]]:
        del role
        return _schedule_call(
            _schedule_read_service().list_versions,
            project_key,
            sort=sort,
            order=order,
        )

    @app.get("/api/schedules/projects/{project_key}/identities")
    def schedule_list_identities(
        project_key: str,
        show_merged: bool = Query(default=False),
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        require_schedule_schema_ready()
        rows = _schedule_call(
            _schedule_identity_repo().list_identities,
            project_key=project_key,
            show_merged=show_merged,
        )
        return {
            "project_key": project_key,
            "identities": [_public_identity_row(dict(r)) for r in rows],
            "show_merged": show_merged,
        }

    @app.get("/api/schedules/projects/{project_key}/identities/{schedule_identity_key}")
    def schedule_identity_detail(
        project_key: str,
        schedule_identity_key: str,
        show_merged: bool = Query(default=True),
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        require_schedule_schema_ready()
        payload = _schedule_identity_repo().get_identity_detail(
            project_key=project_key,
            schedule_identity_key=schedule_identity_key,
            show_merged=show_merged,
        )
        if not payload:
            raise HTTPException(status_code=404, detail="schedule_identity_not_found")
        return _public_identity_detail(dict(payload))

    @app.get("/api/schedules/projects/{project_key}/identity-review")
    def schedule_identity_review_queue(
        project_key: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        require_schedule_schema_ready()
        rows = _schedule_call(_schedule_identity_repo().list_review_queue, project_key=project_key)
        identities = _schedule_call(
            _schedule_identity_repo().list_identities,
            project_key=project_key,
            show_merged=False,
        )
        from hb_assistant.construction.analytics.schedule_trust_service import ScheduleTrustService

        trust = ScheduleTrustService(db_path=_schedule_db_path())
        return {
            "project_key": project_key,
            "review_items": [
                trust.enrich_review_item(project_key=project_key, item=_public_identity_row(dict(r)))
                for r in rows
            ],
            "active_identities": [_public_identity_row(dict(r)) for r in identities],
            "series_memberships": trust.list_series_memberships(project_key=project_key),
        }

    @app.post("/api/schedules/projects/{project_key}/versions/{schedule_version_key}/series-membership")
    def schedule_series_membership(
        project_key: str,
        schedule_version_key: str,
        request: dict[str, Any],
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        _enforce_version_project_scope(schedule_version_key, project_key)
        require_schedule_schema_ready()
        from hb_assistant.construction.analytics.schedule_trust_service import ScheduleTrustService

        membership = ScheduleTrustService(db_path=_schedule_db_path()).set_series_membership(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            membership_status=str(request.get("membership_status") or ""),
            reason=str(request.get("reason") or "") or None,
            operator=role.get("role"),
        )
        return {"membership": membership}

    @app.post("/api/schedules/projects/{project_key}/versions/{schedule_version_key}/identity")
    def schedule_identity_reassign(
        project_key: str,
        schedule_version_key: str,
        request: ScheduleIdentityReassignRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        _enforce_version_project_scope(schedule_version_key, project_key)
        require_schedule_schema_ready()
        payload = _schedule_call(
            _schedule_identity_repo().reassign_version_identity,
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            target_identity_key=request.target_identity_key,
            reason=request.reason,
            actor=role.get("role"),
        )
        return _public_identity_detail(dict(payload))

    @app.post("/api/schedules/projects/{project_key}/versions/{schedule_version_key}/identity/split")
    def schedule_identity_split(
        project_key: str,
        schedule_version_key: str,
        request: ScheduleIdentitySplitRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        _enforce_version_project_scope(schedule_version_key, project_key)
        require_schedule_schema_ready()
        payload = _schedule_call(
            _schedule_identity_repo().split_version_identity,
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            canonical_schedule_name=request.canonical_schedule_name,
            reason=request.reason,
            actor=role.get("role"),
        )
        return _public_identity_detail(dict(payload))

    @app.post("/api/schedules/projects/{project_key}/identities/{source_identity_key}/merge")
    def schedule_identity_merge(
        project_key: str,
        source_identity_key: str,
        request: ScheduleIdentityMergeRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        require_schedule_schema_ready()
        payload = _schedule_call(
            _schedule_identity_repo().merge_identities,
            project_key=project_key,
            source_identity_key=source_identity_key,
            target_identity_key=request.target_identity_key,
            reason=request.reason,
            actor=role.get("role"),
        )
        return _public_identity_detail(dict(payload))

    def _enforce_version_project_scope(
        schedule_version_key: str, project_key: str | None
    ) -> None:
        from hb_assistant.construction.analytics.schedule_import_service import (
            assert_version_matches_project,
        )
        from hb_assistant.construction.analytics.schedule_file_parser import (
            ScheduleImportError,
        )

        try:
            assert_version_matches_project(schedule_version_key, project_key)
        except ScheduleImportError as exc:
            _raise_schedule_import_error(exc)

    @app.get("/api/schedules/versions/{schedule_version_key}/summary")
    def schedule_version_summary(
        schedule_version_key: str,
        project_key: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        _enforce_version_project_scope(schedule_version_key, project_key)
        out = _schedule_call(_schedule_read_service().get_summary, schedule_version_key)
        if out is None:
            raise HTTPException(status_code=404, detail="schedule_not_found")
        return out

    @app.get("/api/schedules/versions/{schedule_version_key}/health-data")
    def schedule_version_health_data(
        schedule_version_key: str,
        project_key: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        _enforce_version_project_scope(schedule_version_key, project_key)
        out = _schedule_call(_schedule_read_service().get_health_data, schedule_version_key)
        if out is None:
            raise HTTPException(status_code=404, detail="schedule_not_found")
        # Phase 9A.1: additive, read-only Application-computed CPM health envelope. Fail-soft so a
        # CPM-side issue can never break the source-export Schedule Health response.
        try:
            out["computed_cpm_health"] = _schedule_health_cpm_service().build_computed_cpm_health(
                schedule_version_key
            )
        except Exception:  # pragma: no cover - defensive: keep /health-data resilient
            out["computed_cpm_health"] = {
                "available": False,
                "reason": "computed_cpm_error",
                "evidence_class": "application_computed_cpm",
                "source_export_evidence": "separate",
            }
        return out

    @app.get("/api/schedules/versions/{schedule_version_key}/activities")
    def schedule_version_activities(
        schedule_version_key: str,
        limit: int | None = Query(default=None, ge=1, le=10000),
        offset: int = Query(default=0, ge=0),
        project_key: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        _enforce_version_project_scope(schedule_version_key, project_key)
        read = _schedule_read_service()
        items = _schedule_call(
            read.list_activities,
            schedule_version_key,
            limit=limit,
            offset=offset,
        )
        total = read.count_activities(schedule_version_key)
        return {
            "schedule_version_key": schedule_version_key,
            "activities": items,
            "total_count": total,
            "limit": limit if limit is not None else 500,
            "offset": offset,
            "truncated": len(items) + offset < total,
        }

    @app.get("/api/schedules/versions/{schedule_version_key}/relationships")
    def schedule_version_relationships(
        schedule_version_key: str,
        project_key: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        _enforce_version_project_scope(schedule_version_key, project_key)
        items = _schedule_call(_schedule_read_service().list_relationships, schedule_version_key)
        return {"schedule_version_key": schedule_version_key, "relationships": items}

    def _schedule_quality_service() -> Any:
        from hb_assistant.construction.analytics.schedule_quality_service import (
            ScheduleQualityService,
        )

        return ScheduleQualityService(db_path=_schedule_db_path())

    @app.get("/api/schedules/quality")
    def schedule_list_quality(
        project_key: str | None = None,
        sort: str = Query(default="evaluated_at"),
        order: str = Query(default="desc"),
        include_history: bool = Query(default=False),
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        evaluations = _schedule_call(
            _schedule_quality_service().list_evaluations,
            project_key=project_key,
            sort=sort,
            order=order,
            include_history=include_history,
        )
        return {"project_key": project_key, "evaluations": evaluations}

    @app.get("/api/schedules/versions/{schedule_version_key}/quality")
    def schedule_version_quality(
        schedule_version_key: str,
        project_key: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        _enforce_version_project_scope(schedule_version_key, project_key)
        return _schedule_call(
            _schedule_quality_service().get_quality_summary,
            schedule_version_key,
        )

    @app.get("/api/schedules/versions/{schedule_version_key}/quality/findings")
    def schedule_version_quality_findings(
        schedule_version_key: str,
        evaluation_run_id: str | None = None,
        limit: int = Query(default=500, ge=1, le=5000),
        offset: int = Query(default=0, ge=0),
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        return _schedule_call(
            _schedule_quality_service().get_findings,
            schedule_version_key,
            evaluation_run_id=evaluation_run_id,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/schedules/versions/{schedule_version_key}/quality/metrics")
    def schedule_version_quality_metrics(
        schedule_version_key: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        summary = _schedule_call(
            _schedule_quality_service().get_quality_summary,
            schedule_version_key,
        )
        return {
            "schedule_version_key": schedule_version_key,
            "evaluation_run_id": summary.get("evaluation_run_id"),
            "metrics": summary.get("metrics", []),
        }

    # ------------------------------------------------------------ Phase 8 computed CPM (read-only)

    def _schedule_cpm_read_service() -> Any:
        from hb_assistant.construction.analytics.schedule_cpm_read_service import (
            ScheduleCpmReadService,
        )

        return ScheduleCpmReadService(db_path=_schedule_db_path())

    def _schedule_health_cpm_service() -> Any:
        from hb_assistant.construction.analytics.schedule_health_cpm_service import (
            ScheduleHealthCpmService,
        )

        return ScheduleHealthCpmService(db_path=_schedule_db_path())

    @app.get("/api/schedules/versions/{schedule_version_key}/cpm/summary")
    def schedule_version_cpm_summary(
        schedule_version_key: str,
        project_key: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        _enforce_version_project_scope(schedule_version_key, project_key)
        return _schedule_call(
            _schedule_cpm_read_service().cpm_summary, schedule_version_key
        )

    @app.get("/api/schedules/versions/{schedule_version_key}/cpm/activities")
    def schedule_version_cpm_activities(
        schedule_version_key: str,
        limit: int | None = Query(default=None, ge=1, le=10000),
        offset: int = Query(default=0, ge=0),
        project_key: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        _enforce_version_project_scope(schedule_version_key, project_key)
        return _schedule_call(
            _schedule_cpm_read_service().cpm_activities,
            schedule_version_key,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/schedules/versions/{schedule_version_key}/cpm/longest-path")
    def schedule_version_cpm_longest_path(
        schedule_version_key: str,
        project_key: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        _enforce_version_project_scope(schedule_version_key, project_key)
        return _schedule_call(
            _schedule_cpm_read_service().cpm_longest_path, schedule_version_key
        )

    @app.get("/api/schedules/versions/{schedule_version_key}/cpm/diagnostics")
    def schedule_version_cpm_diagnostics(
        schedule_version_key: str,
        project_key: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        _enforce_version_project_scope(schedule_version_key, project_key)
        return _schedule_call(
            _schedule_cpm_read_service().cpm_diagnostics, schedule_version_key
        )

    @app.post("/api/schedules/versions/{schedule_version_key}/quality/rerun")
    def schedule_version_quality_rerun(
        schedule_version_key: str,
        profile: str | None = None,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.construction.analytics.schedule_quality_worker import poll_and_process

        out = _schedule_call(
            _schedule_quality_service().request_rerun,
            schedule_version_key=schedule_version_key,
            profile_id=profile,
        )
        poll_and_process(db_path=_schedule_db_path(), limit=1)
        return out

    @app.get("/api/schedules/quality/runs/{evaluation_run_id}")
    def schedule_quality_run_detail(
        evaluation_run_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        out = _schedule_call(
            _schedule_quality_service().get_run_detail,
            evaluation_run_id,
        )
        if out is None:
            raise HTTPException(status_code=404, detail="schedule_not_found")
        return out

    @app.get("/api/schedules/projects/{project_key}/quality/summary")
    def schedule_project_quality_summary(
        project_key: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        return _schedule_call(
            _schedule_quality_service().get_project_summary,
            project_key,
        )

    @app.get("/api/schedules/projects/{project_key}/diff")
    def schedule_version_diff(
        project_key: str,
        from_version: str = Query(alias="from"),
        to_version: str = Query(alias="to"),
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from hb_assistant.construction.analytics.schedule_version_diff import compute_version_diff
        from hb_assistant.construction.analytics.schedule_diff_intelligence import (
            build_detail_facts,
            summarize_detail_facts,
        )
        from hb_assistant.store.schedule_mapping_repository import ScheduleMappingRepository

        read = _schedule_read_service()
        from_acts = read.list_activities(from_version, for_diff=True)
        to_acts = read.list_activities(to_version, for_diff=True)
        from_rels = read.list_relationships(from_version)
        to_rels = read.list_relationships(to_version)
        from_wbs = read.list_wbs_nodes(from_version)
        to_wbs = read.list_wbs_nodes(to_version)
        from_calendars = read.list_calendars(from_version)
        to_calendars = read.list_calendars(to_version)
        from_codes = read.list_activity_codes(from_version)
        to_codes = read.list_activity_codes(to_version)
        from_udfs = read.list_udf_values(from_version)
        to_udfs = read.list_udf_values(to_version)
        diff = compute_version_diff(
            project_key=project_key,
            from_version=from_version,
            to_version=to_version,
            from_activities=from_acts,
            to_activities=to_acts,
            from_relationships=from_rels,
            to_relationships=to_rels,
        )
        from_match = _schedule_identity_repo().get_match_for_version(from_version)
        to_match = _schedule_identity_repo().get_match_for_version(to_version)
        from_identity = from_match.get("schedule_identity_key") if from_match else None
        to_identity = to_match.get("schedule_identity_key") if to_match else None
        from_review = bool(from_match and int(from_match.get("requires_review") or 0))
        to_review = bool(to_match and int(to_match.get("requires_review") or 0))
        if from_identity and to_identity and from_identity == to_identity and not from_review and not to_review:
            comparison_status = "identity_safe"
        elif from_review or to_review:
            comparison_status = "identity_requires_review"
        elif from_identity and to_identity and from_identity != to_identity:
            comparison_status = "cross_identity"
        else:
            comparison_status = "identity_unavailable"
        identity_safe = comparison_status == "identity_safe"
        comparison_type = "identity_safe_manual" if identity_safe else (
            "cross_identity_manual" if comparison_status == "cross_identity" else "manual"
        )
        schedule_identity_key = from_identity if identity_safe else None
        diff["identity_comparison"] = {
            "status": comparison_status,
            "from_schedule_identity_key": from_identity,
            "to_schedule_identity_key": to_identity,
            "from_requires_review": from_review,
            "to_requires_review": to_review,
        }
        details_cache: list[dict[str, Any]] = []

        def _detail_builder(diff_id: int) -> list[dict[str, Any]]:
            details_cache[:] = build_detail_facts(
                diff_id=diff_id,
                project_key=project_key,
                from_version=from_version,
                to_version=to_version,
                schedule_identity_key=schedule_identity_key,
                identity_safe=identity_safe,
                comparison_type=comparison_type,
                from_activities=from_acts,
                to_activities=to_acts,
                from_relationships=from_rels,
                to_relationships=to_rels,
                from_wbs=from_wbs,
                to_wbs=to_wbs,
                from_calendars=from_calendars,
                to_calendars=to_calendars,
                from_codes=from_codes,
                to_codes=to_codes,
                from_udfs=from_udfs,
                to_udfs=to_udfs,
            )
            return details_cache

        mapping_repo = ScheduleMappingRepository(db_path=_schedule_db_path())
        diff_id, details = mapping_repo.insert_version_diff_with_detail_builders(
            diff,
            detail_builder=_detail_builder,
        )
        summary_counts = summarize_detail_facts(details)
        diff["diff_id"] = diff_id
        diff["identity_safe"] = identity_safe
        diff["comparison_type"] = comparison_type
        diff["detail_summary_counts"] = summary_counts
        diff["detail_preview"] = details[:25]
        impact_summary = mapping_repo.summarize_diff_impact_rollups(diff_id, project_key=project_key)
        diff["impact_summary"] = impact_summary.get("summary")
        diff["impact_top_wbs"] = impact_summary.get("top_wbs")
        return diff

    @app.get("/api/schedules/projects/{project_key}/diffs/{diff_id}/summary")
    def schedule_version_diff_summary(
        project_key: str,
        diff_id: int,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        out = _schedule_read_service().get_diff_summary(project_key, diff_id)
        if not out:
            raise HTTPException(status_code=404, detail="schedule_diff_not_found")
        return out

    @app.get("/api/schedules/projects/{project_key}/diffs/{diff_id}/details")
    def schedule_version_diff_details(
        project_key: str,
        diff_id: int,
        change_domain: str | None = None,
        change_type: str | None = None,
        severity: str | None = None,
        requires_attention: bool | None = None,
        wbs_code: str | None = None,
        activity_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        out = _schedule_read_service().list_diff_details(
            project_key,
            diff_id,
            change_domain=change_domain,
            change_type=change_type,
            severity=severity,
            requires_attention=requires_attention,
            wbs_code=wbs_code,
            activity_id=activity_id,
            limit=limit,
            offset=offset,
        )
        if not out:
            raise HTTPException(status_code=404, detail="schedule_diff_not_found")
        return out

    @app.get("/api/schedules/projects/{project_key}/diffs/{diff_id}/impact")
    def schedule_version_diff_impact(
        project_key: str,
        diff_id: int,
        rollup_type: str | None = None,
        impact_level: str | None = None,
        requires_attention: bool | None = None,
        wbs_code: str | None = None,
        activity_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        out = _schedule_read_service().list_diff_impact(
            project_key,
            diff_id,
            rollup_type=rollup_type,
            impact_level=impact_level,
            requires_attention=requires_attention,
            wbs_code=wbs_code,
            activity_id=activity_id,
            limit=limit,
            offset=offset,
        )
        if not out:
            raise HTTPException(status_code=404, detail="schedule_diff_not_found")
        return out

    async def _read_schedule_upload(file: Any, *, max_bytes: int) -> tuple[str, bytes]:
        from hb_assistant.construction.analytics.schedule_file_parser import ScheduleImportError
        from hb_assistant.construction.analytics.schedule_import_service import MAX_UPLOAD_BYTES

        limit = max_bytes or MAX_UPLOAD_BYTES
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise ScheduleImportError(
                    "schedule_file_too_large",
                    message="uploaded file exceeds the size limit",
                )
            chunks.append(chunk)
        data = b"".join(chunks)
        filename = str(getattr(file, "filename", None) or "upload")
        return filename, data

    @app.post("/api/schedules/import-preview")
    async def schedule_import_preview(
        role: dict[str, str] = role_dep,
        _schema: None = Depends(require_schedule_schema_ready),
        file: FastAPIUploadFile = FastAPIFile(...),
        project_key: str = FastAPIForm(...),
        column_roles: str | None = FastAPIForm(None),
        confirm_supersede: bool = FastAPIForm(False),
    ) -> dict[str, Any]:
        from fastapi import HTTPException

        from hb_assistant.construction.analytics.schedule_file_parser import ScheduleImportError
        from hb_assistant.construction.analytics.schedule_import_service import MAX_UPLOAD_BYTES

        require_operator_role(role)
        try:
            filename, data = await _read_schedule_upload(file, max_bytes=MAX_UPLOAD_BYTES)
            parsed_roles: dict[str, str] | None = None
            if column_roles:
                try:
                    parsed_roles = json.loads(column_roles)
                except json.JSONDecodeError as exc:
                    raise ScheduleImportError(
                        "schedule_import_invalid",
                        message="column_roles must be valid JSON",
                    ) from exc
            return _schedule_call(
                _schedule_import_service().preview_bytes,
                filename=filename,
                data=data,
                project_key=project_key,
                column_roles=parsed_roles,
                confirm_supersede=confirm_supersede,
            )
        except HTTPException:
            raise
        except ScheduleImportError as exc:
            _raise_schedule_import_error(exc)
            raise AssertionError("unreachable") from exc
        except AssertionError as exc:
            if "python-multipart" in str(exc):
                _logger.exception("schedule import-preview missing python-multipart")
                raise HTTPException(
                    status_code=503,
                    detail="schedule_multipart_unavailable",
                ) from exc
            raise
        except Exception as exc:
            _logger.exception("schedule import-preview failed")
            raise HTTPException(status_code=500, detail="schedule_import_invalid") from exc

    @app.post("/api/schedules/import-commit")
    def schedule_import_commit(
        request: ScheduleImportCommitRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        return _schedule_call(
            _schedule_import_service().commit,
            import_id=request.import_id,
            project_key=request.project_key,
            confirm=request.confirm,
            confirm_supersede=request.confirm_supersede,
            column_roles=request.column_roles,
        )

    @app.post("/api/projects/{project_key}/schedule/import-preview")
    async def project_schedule_import_preview(
        project_key: str,
        role: dict[str, str] = role_dep,
        _schema: None = Depends(require_schedule_schema_ready),
        file: FastAPIUploadFile = FastAPIFile(...),
        column_roles: str | None = FastAPIForm(None),
        confirm_supersede: bool = FastAPIForm(False),
    ) -> dict[str, Any]:
        from hb_assistant.construction.analytics.schedule_file_parser import ScheduleImportError
        from hb_assistant.construction.analytics.schedule_import_service import MAX_UPLOAD_BYTES

        require_operator_role(role)
        try:
            filename, data = await _read_schedule_upload(file, max_bytes=MAX_UPLOAD_BYTES)
            parsed_roles: dict[str, str] | None = None
            if column_roles:
                try:
                    parsed_roles = json.loads(column_roles)
                except json.JSONDecodeError as exc:
                    raise ScheduleImportError(
                        "schedule_import_invalid",
                        message="column_roles must be valid JSON",
                    ) from exc
            return _schedule_call(
                _project_schedule_import_pipeline_service().preview_bytes,
                project_key=project_key,
                filename=filename,
                data=data,
                column_roles=parsed_roles,
                confirm_supersede=confirm_supersede,
            )
        except HTTPException:
            raise
        except ScheduleImportError as exc:
            _raise_schedule_import_error(exc)
            raise AssertionError("unreachable") from exc
        except Exception as exc:
            _logger.exception("project schedule import-preview failed project_key=%s", project_key)
            raise HTTPException(status_code=500, detail="schedule_import_invalid") from exc

    @app.post("/api/projects/{project_key}/schedule/import-commit")
    def project_schedule_import_commit(
        project_key: str,
        request: ScheduleImportCommitRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        from fastapi import HTTPException

        require_operator_role(role)
        if request.project_key != project_key:
            raise HTTPException(status_code=400, detail="schedule_project_mismatch")
        return _schedule_call(
            _project_schedule_import_pipeline_service().commit,
            project_key=project_key,
            import_id=request.import_id,
            confirm=request.confirm,
            confirm_supersede=request.confirm_supersede,
            column_roles=request.column_roles,
        )

    @app.get("/api/projects/{project_key}/schedule/imports/{import_id}/status")
    def project_schedule_import_status(
        project_key: str,
        import_id: str,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        return _schedule_call(
            _project_schedule_import_pipeline_service().build_status,
            project_key=project_key,
            import_id=import_id,
        )

    @app.post("/api/projects/{project_key}/schedule/imports/{import_id}/recompute-cpm")
    def project_schedule_import_recompute_cpm(
        project_key: str,
        import_id: str,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        return _schedule_call(
            _project_schedule_import_pipeline_service().retry_cpm,
            project_key=project_key,
            import_id=import_id,
        )

    @app.post("/api/schedules/cost-mapping/runs")
    def schedule_cost_mapping_create(
        request: ScheduleCostMappingRunRequest, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        require_operator_role(role)
        return _schedule_call(
            _schedule_cost_mapping_service().create_run,
            project_key=request.project_key,
            schedule_version_key=request.schedule_version_key,
            operator_objective=request.operator_objective,
        )

    @app.get("/api/schedules/cost-mapping/runs/{mapping_run_id}")
    def schedule_cost_mapping_get(mapping_run_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        from fastapi import HTTPException

        out = _schedule_call(_schedule_cost_mapping_service().get_run, mapping_run_id)
        if out is None:
            raise HTTPException(status_code=404, detail="schedule_not_found")
        return out

    @app.get("/api/schedules/cost-mapping/runs/{mapping_run_id}/candidates")
    def schedule_cost_mapping_candidates(
        mapping_run_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        items = _schedule_call(_schedule_cost_mapping_service().list_candidates, mapping_run_id)
        return {"mapping_run_id": mapping_run_id, "candidates": items}

    @app.post("/api/schedules/cost-mapping/candidates/{candidate_id}/review")
    def schedule_cost_mapping_review(
        candidate_id: int,
        request: ScheduleCostMappingReviewRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        _schedule_call(
            _schedule_cost_mapping_service().review_candidate,
            candidate_id,
            operator_status=request.operator_status,
            operator_notes=request.operator_notes,
            candidate_cost_code=request.candidate_cost_code,
        )
        return {"candidate_id": candidate_id, "status": request.operator_status}

    @app.post("/api/schedules/cost-mapping/runs/{mapping_run_id}/approve")
    def schedule_cost_mapping_approve(mapping_run_id: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)
        return _schedule_call(_schedule_cost_mapping_service().approve_run, mapping_run_id)

    @app.get("/api/schedules/cost-mapping/runs/{mapping_run_id}/distribution")
    def schedule_cost_mapping_distribution(
        mapping_run_id: str, role: dict[str, str] = role_dep
    ) -> dict[str, Any]:
        del role
        items = _schedule_call(_schedule_cost_mapping_service().list_distributions, mapping_run_id)
        return {"mapping_run_id": mapping_run_id, "distributions": items}

    @app.get("/api/schedules/cost-weighting/{project_key}")
    def schedule_cost_weighting(project_key: str, role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        items = _schedule_call(_schedule_cost_mapping_service().list_weighting, project_key)
        return {"project_key": project_key, "weighting_results": items}

    if mcp_streamable_http_app is not None:
        app.mount("/", mcp_streamable_http_app)

    return app
