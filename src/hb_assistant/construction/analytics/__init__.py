"""Read-only analytics service boundary for future FastAPI/UI surfaces."""

from .api import ALLOWED_UI_ROLES, create_app, require_operator_role, role_dependency
from .auth_onboarding import AuthOnboardingService
from .connection_setup import ConnectionSetupService
from .project_keywords import ProjectKeywordsService
from .service import AnalyticsService

__all__ = [
    "ALLOWED_UI_ROLES",
    "AnalyticsService",
    "AuthOnboardingService",
    "ConnectionSetupService",
    "create_app",
    "ProjectKeywordsService",
    "require_operator_role",
    "role_dependency",
]
