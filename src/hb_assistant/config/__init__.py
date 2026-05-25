"""Configuration models, loader, and path policy for HB Personal Assistant."""

from .loader import load_config, AppConfig
from .models import (
    AppConfig as _AppConfig,  # re-export for convenience
    ProjectConfig,
    IdentityConfig,
    PathsConfig,
    MailConfig,
    CalendarConfig,
    FilesConfig,
    AutomationConfig,
    SecurityConfig,
)
from .path_policy import PathPolicy

__all__ = [
    "load_config",
    "AppConfig",
    "ProjectConfig",
    "IdentityConfig",
    "PathsConfig",
    "MailConfig",
    "CalendarConfig",
    "FilesConfig",
    "AutomationConfig",
    "SecurityConfig",
    "PathPolicy",
]
