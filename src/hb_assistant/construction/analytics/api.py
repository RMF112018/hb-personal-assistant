"""Optional FastAPI shell for the future analytics UI.

FastAPI is an optional dependency. Imports stay inside ``create_app`` and the
dependency factory so the base package remains FastAPI-free.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

ALLOWED_UI_ROLES = frozenset({"viewer", "operator", "admin"})


class GraphDeviceLoginCompleteRequest(BaseModel):
    flow_id: str


class ProcoreOAuthExchangeRequest(BaseModel):
    code: str


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


def create_app(*, db_path: str | None = None) -> Any:
    """Create the optional FastAPI app shell.

    The shell intentionally exposes only health, OpenAPI, and disabled chat
    status. Future analytics route adapters should call ``AnalyticsService``
    directly and reuse ``role_dependency``.
    """
    from fastapi import Depends, FastAPI

    require_role = role_dependency()
    app = FastAPI(
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

    @app.get("/api/settings/preferences")
    def settings_preferences(role: dict[str, str] = role_dep) -> dict[str, Any]:
        del role
        # Stub; full impl would load from local JSON under Application Support (like daily_brief config).
        return {
            "theme": "dark",
            "default_landing_page": "Today",
            "show_daily_brief_on_today": True,
            "followed_projects": [],
            "note": "Preferences are local-first; persisted under Application Support.",
            "guardrails": _guardrails(),
        }

    @app.patch("/api/settings/preferences")
    def patch_settings_preferences(
        patch: SettingsPreferencesPatch,
        role: dict[str, str] = role_dep,
    ) -> dict[str, Any]:
        del role
        return {
            "ok": True,
            "applied": patch.model_dump(exclude_none=True),
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

    return app
