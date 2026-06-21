"""Optional FastAPI shell for the future analytics UI.

FastAPI is an optional dependency. Imports stay inside ``create_app`` and the
dependency factory so the base package remains FastAPI-free.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from hb_assistant.config.path_policy import PathPolicy  # Prompt 20 prefs + daily_brief config path
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

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
    """Startup bootstrap: ensure configured forecast write-roots exist before serving.

    Informative and fail-closed — it creates ONLY configured+valid write-roots and never raises
    (a bootstrap failure must never block app startup, mirroring the optional-surface degrade
    posture). With nothing configured (the test/manual default) it is a no-op: no directories are
    created and no read-roots are ever touched.
    """
    try:
        from hb_assistant.construction.analytics.forecast_bootstrap import ensure_forecast_roots

        ensure_forecast_roots()
    except Exception:
        pass
    yield


def create_app(*, db_path: str | None = None) -> Any:
    """Create the optional FastAPI app shell.

    The shell intentionally exposes only health, OpenAPI, and disabled chat
    status. Future analytics route adapters should call ``AnalyticsService``
    directly and reuse ``role_dependency``.
    """
    from fastapi import Depends, FastAPI

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
    role_dep = Depends(require_role)

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
    def forecast_run_create(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)  # generation executes + writes (isolated work-root)
        return _forecast_run_call(_forecast_run_service().start_run)

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

    @app.post("/api/forecast/runs/db-config")
    def forecast_db_config_run_create(role: dict[str, str] = role_dep) -> dict[str, Any]:
        require_operator_role(role)  # executes + writes isolated work-root; reads live config DB ro
        return _forecast_db_config_run_call(_forecast_db_config_run_service().start_db_config_run)

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
        require_operator_role(role)  # mutates persisted runtime config
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

    return app
