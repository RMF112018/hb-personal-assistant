"""Read-only analytics service boundary for future FastAPI/UI surfaces."""

from .api import ALLOWED_UI_ROLES, create_app, require_operator_role, role_dependency
from .auth_onboarding import AuthOnboardingService
from .connection_setup import ConnectionSetupService
from .daily_brief import DailyBriefService
from .environment_status import EnvironmentStatusService
from .forecast_catalog import ForecastCatalogError, ForecastCatalogService
from .forecast_config_catalog import ForecastConfigCatalogService, ForecastConfigError
from .forecast_external_eval_service import ForecastExternalEvalService
from .forecast_external_ingest import ForecastExternalError, ForecastExternalIngestService
from .forecast_external_mapping import ForecastExternalMappingService
from .forecast_run_service import ForecastRunError, ForecastRunService
from .project_keywords import ProjectKeywordsService
from .service import AnalyticsService
from .source_refresh_control import SourceRefreshControlService

__all__ = [
    "ALLOWED_UI_ROLES",
    "AnalyticsService",
    "AuthOnboardingService",
    "ConnectionSetupService",
    "create_app",
    "DailyBriefService",
    "EnvironmentStatusService",
    "ForecastCatalogError",
    "ForecastCatalogService",
    "ForecastConfigCatalogService",
    "ForecastConfigError",
    "ForecastExternalError",
    "ForecastExternalEvalService",
    "ForecastExternalIngestService",
    "ForecastExternalMappingService",
    "ForecastRunError",
    "ForecastRunService",
    "ProjectKeywordsService",
    "require_operator_role",
    "role_dependency",
    "SourceRefreshControlService",
]
