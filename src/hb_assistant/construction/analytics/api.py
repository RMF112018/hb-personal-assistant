"""Optional FastAPI shell for the future analytics UI.

FastAPI is an optional dependency. Imports stay inside ``create_app`` and the
dependency factory so the base package remains FastAPI-free.
"""

from __future__ import annotations

import json
import logging
from contextlib import AsyncExitStack, asynccontextmanager
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


@asynccontextmanager
async def _forecast_lifespan(app: Any) -> Any:
    """Startup bootstrap: ensure app-managed forecast storage before serving.

    Informative and fail-closed — never raises (a bootstrap failure must never block app startup,
    mirroring the optional-surface degrade posture).
    """
    import asyncio

    poll_task: asyncio.Task[None] | None = None
    try:
        from hb_assistant.construction.analytics.forecast_bootstrap import (
            ensure_forecast_managed_storage,
        )

        ensure_forecast_managed_storage()
    except Exception:
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

    try:
        poll_task = asyncio.create_task(_quality_poll_loop())
    except Exception:
        poll_task = None

    mcp_wrapper = getattr(app.state, "mcp_streamable_http_app", None)
    mcp_app = getattr(mcp_wrapper, "app", mcp_wrapper)
    mcp_lifespan = getattr(getattr(mcp_app, "router", None), "lifespan_context", None)

    async with AsyncExitStack() as stack:
        if callable(mcp_lifespan):
            await stack.enter_async_context(mcp_lifespan(mcp_app))
        try:
            yield
        finally:
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
    from fastapi import Body, Depends, FastAPI, Query

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

        mcp_streamable_http_app = build_streamable_http_app()
        app.state.mcp_streamable_http_app = mcp_streamable_http_app
    except Exception:
        # Optional SDK or adapter unavailable: the UI health check reports the precise blocker.
        pass

    @app.get("/health")
    def health(role: dict[str, str] = role_dep) -> dict[str, Any]:
        schema_version = _schema_version(db_path)
        return {
            "status": "ok",
            "surface": "analytics.fastapi_shell",
            "role": role,
            "schema_version": schema_version,
            "schema_expected": LATEST_SCHEMA_VERSION,
            "schema_ready": schema_version >= LATEST_SCHEMA_VERSION,
            "chat_enabled": False,
            "guardrails": _guardrails(),
        }

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

        return {
            "surface": "settings.obsidian_mcp.config",
            "config": ObsidianMcpService().get_config().redacted(),
            "guardrails": ObsidianMcpService().guardrails(),
        }

    @app.patch("/api/settings/obsidian-mcp/config")
    def settings_obsidian_mcp_update_config(
        request: ObsidianMcpConfigPatchRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp import ObsidianMcpConfigPatch, ObsidianMcpService

        return ObsidianMcpService().update_config(
            ObsidianMcpConfigPatch.model_validate(request.model_dump(exclude_none=True))
        )

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
        return safe_tool_response(svc.list_directory, request.model_dump(exclude_none=True))

    @app.post("/api/settings/obsidian-mcp/test/search")
    def settings_obsidian_mcp_test_search(
        request: ObsidianMcpSearchRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp.service import ObsidianMcpService, safe_tool_response

        svc = ObsidianMcpService()
        return safe_tool_response(svc.search_vault, request.model_dump(exclude_none=True))

    @app.post("/api/settings/obsidian-mcp/test/read-file")
    def settings_obsidian_mcp_test_read_file(
        request: ObsidianMcpReadFileRequest,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        require_operator_role(role)
        from hb_assistant.obsidian_mcp.service import ObsidianMcpService, safe_tool_response

        svc = ObsidianMcpService()
        return safe_tool_response(svc.read_file, request.model_dump(exclude_none=True))

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

    def _admin_table_count(schema_db: str) -> int:
        import sqlite3

        conn = sqlite3.connect(f"file:{schema_db}?mode=ro", uri=True)
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) FROM sqlite_master
                WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
                """
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()

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
        return {
            "schema_version": current,
            "schema_expected": LATEST_SCHEMA_VERSION,
            "schema_ready": current >= LATEST_SCHEMA_VERSION,
            "table_count": _admin_table_count(schema_db),
            **physical,
        }

    @app.post("/api/admin/schema/migrate")
    def admin_schema_migrate(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_admin_role(role)
        schema_db = _admin_schema_db_path()
        before = _schema_version(schema_db)
        physical_before = _schedule_v65_physical_status(schema_db)
        after = int(SQLiteMigrator(db_path=schema_db).apply())
        physical_after = _schedule_v65_physical_status(schema_db)
        return {
            "schema_before": before,
            "schema_after": after,
            "schema_expected": LATEST_SCHEMA_VERSION,
            "schema_ready": after >= LATEST_SCHEMA_VERSION,
            "table_count": _admin_table_count(schema_db),
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
        return {
            "project_key": project_key,
            "review_items": [_public_identity_row(dict(r)) for r in rows],
            "active_identities": [_public_identity_row(dict(r)) for r in identities],
        }

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
